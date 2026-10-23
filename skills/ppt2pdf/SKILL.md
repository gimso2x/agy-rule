---
name: ppt2pdf
description: Convert SharePoint/OneDrive protected PowerPoint or Word documents through browser rendering into PDF, captured page/slide PNGs, and a Markdown transcription made directly by the agent (without external gimso2xproxy). Use for requests like "pptx/docx를 PDF로", "링크만 주면 PDF", or when the user explicitly invokes ppt2pdf. Natural input defaults to the run fast path, which always ends with Markdown unless the user opts out.
skill_version: 2.8.0
skill_status: active
skill_visibility: user
---

# ppt2pdf

Use the fast path for normal requests. Read [FAST_PATH.md](FAST_PATH.md) first and follow its public `run/check/status/cleanup` contract.

## Default behavior

Treat `ppt2pdf "<url>"` as `ppt2pdf run "<url>"`.

Use the bundled public wrapper:

```bash
python3 "<skill_dir>/skill_cli.py" "<sharepoint-or-onedrive-url>"
```

Default run = one shot: PDF + page/slide PNGs **and** Markdown, in the same turn without asking.
- Run `python3 "<skill_dir>/skill_cli.py" "<url>"` first to capture PDF + `slide-*.png`.
- Then **the agent directly transcribes the slide PNGs into Markdown** (see Direct Markdown Conversion below). Do **NOT** invoke `ppt2md.py`, `gimso2xproxy`, or external model scripts. The wrapper captures only PDF/PNGs and leaves transcription to the invoking agent.
- Skip Markdown only when the user explicitly opts out (e.g. "PDF만", "마크다운 없이").

Operational commands:

```bash
python3 "<skill_dir>/skill_cli.py" check
python3 "<skill_dir>/skill_cli.py" status
python3 "<skill_dir>/skill_cli.py" cleanup
```

Existing run options pass through to the capture engine:
- `--reuse`: Reuse an already-open SharePoint tab and resume from the last captured slide (disaster recovery).
- `--fresh`: Force full re-capture without reusing cached slides (mandatory for document revision updates).
- `--keep-tab`: Keep the browser tab open after capture completes (preserves user's manual debugging session).
- `--out <path>`: Custom PDF output path.

## Capture engine

`ppt2pdf.py` remains the low-level capture engine. It:

1. Supports two coexisting browser modes, selected by `PPT2PDF_PORT`:
   - **Ego mode (default, CDP 9222)**: the user's Windows Chrome `C:\chrome-agent`, preserving logged-in M365/SharePoint sessions. Reuses an existing browser on 9222 if alive; if down, launches Windows Chrome with `--remote-debugging-port=9222 --user-data-dir=C:\chrome-agent` (or local Chromium fallback).
   - **Dedicated mode (`PPT2PDF_PORT=9223`)**: the dedicated WSL Playwright Chromium profile `~/.local/state/mygjc/ppt2pdf-profile` on CDP port **9223** (`PPT2PDF_PROFILE` overrides the profile path). Reuses an existing browser only after verifying exact port/profile process binding; foreign ownership fails closed.
2. In both modes the CDP browser is reused when alive and never closed by the skill.
3. Opens or reuses SharePoint/OneDrive tabs, waits for manual M365 login when necessary, and detects PowerPoint or Word Online.
4. **DOM Virtualization Defense (100+ slides)**: PowerPoint Online virtualizes left thumbnail items; calls `scroll_into_view_if_needed(timeout=3000)` before clicking each slide, with an automated 2-stage retry loop to eliminate `TimeoutError`.
5. **Resume & Revision Handling**:
   - `--reuse` enables resume mode: existing valid `slide-*.png` files in the work directory are skipped, finishing remaining slides instantly upon interruption.
   - For document revisions ("바뀐 거 체크해서 업데이트"), use `--fresh` (or back up previous slide SHA256 hashes to diff and detect added/modified slides).
6. Captures the rendered document page/slide surfaces without unsafe whole-screen fallback.
7. Assembles an image-only PDF with `img2pdf` and stores captured PNGs beside it.

Default output is `~/decks/<document>/<document>.pdf` plus `slide-*.png`, then `<document>.md` from the Markdown step.

The launcher fills in WSLg `DISPLAY=:0` / `WAYLAND_DISPLAY=/mnt/wslg/runtime-dir/wayland-0` when the calling shell has none, so non-interactive agent shells can start Chromium.

## Direct Markdown Conversion (No gimso2xproxy)

Do **NOT** send slide images to `gimso2xproxy` or external model scripts. This step runs on every `run` unless the user opted out:

1. **Direct Inspection**: the agent inspects the generated `~/decks/<document>/slide-*.png` directly with its image-capable file reader (`read` in omp, `view_file` in AGY).
   - Read images individually within each chunk. If a read shows metadata but no image payload, retry with an alternate local path spelling (e.g. `..././slide-001.png`) or a local lossless re-encoding. Crop/enlarge small text as needed; never infer content from a blank payload.
2. **Parallel Subagents for Multi-Slide Decks**:
   - If the deck has more than 15 slides, divide slides into parallel chunks (10~15 slides per chunk) and spawn subagents (`task` in omp, `invoke_subagent` in AGY).
   - **Model budget — mandatory**: spawn every transcription subagent with an explicit `model: "gimso2xproxy/glm-5.3-flash"`. Do NOT omit the model: omp's `task` role defaults to claude-sonnet, and 8 parallel Claude agents burned ~70M tokens and exhausted the shared OAuth account on 2026-10-06. glm-5.3-flash reads slide PNGs fine at a fraction of the cost.
   - **Concurrency cap**: at most 3 subagents per wave. Start the next wave only after the previous wave fully completes.
   - **Rate-limit abort**: if any subagent reports `rate_limit_error` / `usage_limit_reached` (429), stop spawning further waves. Do NOT retry the failed chunk on other models via fallback chains — each retry re-sends the full chunk context and multiplies usage across accounts. Finish the remaining chunks serially in the parent session, or report the blocker to the user.
   - Each subagent inspects its assigned `slide-*.png` images and writes its chunk to `~/decks/<document>/.chunk_NN.md`.
   - Once all subagents finish, merge the chunks in order into `~/decks/<document>/<document>.md` (title line `# <document>` first), verify every slide 1..N has exactly one `## 슬라이드 N` and one `<!-- PPT2MD_SLIDE_END:N -->`, then remove the temporary chunks.
   - If 15 slides or fewer, the agent processes them directly.
   - If the deck has more than 40 slides, state the expected chunk count and get user confirmation before the first wave.
3. **Fidelity Rules**:
   - Preserve all visible text in full (titles, body items, table cells, labels, annotations, footnotes, UI text). No summary or omission.
   - For diagrams, flowcharts, and complex UI, include Mermaid diagrams or clear 1-2 line descriptive explanations.
   - Use exactly one heading `## 슬라이드 N` per slide.
   - End each slide with `<!-- PPT2MD_SLIDE_END:N -->`.
4. **No Separate Proxy Transmission**: Images are read directly by the agent and its same-model subagents. Do not call external model scripts or the legacy proxy converter.

## check/status/cleanup

- `check`: read-only dependency/readiness probe for Playwright, img2pdf, Chromium, and dedicated CDP/profile ownership. It does not launch a browser or navigate a document.
- `status`: report current dedicated browser/profile/CDP state without mutation.
- `cleanup`: acquire the existing non-blocking run lock and remove only skill-owned `/tmp/ppt2pdf/slide-*.png` temporary captures. Preserve PDFs, PNGs under `~/decks`, Markdown, the dedicated profile, and login session.

## Safety boundary

Default: connects to Ego browser via CDP port 9222 and preserves the existing manual-login session in `C:\chrome-agent` without exporting cookies/credentials. Dedicated mode (`PPT2PDF_PORT=9223`) uses only the ppt2pdf-owned profile `~/.local/state/mygjc/ppt2pdf-profile` and fails closed on foreign port ownership. In either mode the browser/profile stays alive so the M365 session survives; `cleanup` must not stop it.

## Tests

Run the existing offline tests after changes:

```bash
python3 "<skill_dir>/test_ppt2pdf.py"
python3 "<skill_dir>/test_ppt2md.py"
```
