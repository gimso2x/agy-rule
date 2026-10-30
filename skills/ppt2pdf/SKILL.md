---
name: ppt2pdf
description: Convert SharePoint/OneDrive protected PowerPoint or Word documents through browser rendering into PDF, captured page/slide PNGs, and a Markdown transcription made directly by the agent (without external gimso2xproxy). Use for requests like "pptx/docx를 PDF로", "링크만 주면 PDF", or when the user explicitly invokes ppt2pdf. Natural input defaults to the run fast path, which always ends with Markdown unless the user opts out.
skill_version: 2.9.0
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

1. **Ego browser (`ego-browser` CLI) native operation**:
   - Uses the user's primary **ego-browser** (`ego lite`) profile, preserving logged-in M365/SharePoint sessions without running background Chrome CDP processes or separate debug ports.
   - Automatically discovers the `ego-browser` CLI via PATH (`~/.local/bin/ego-browser`) or Windows installation directories (`/mnt/c/Users/*`).
2. Opens or reuses SharePoint/OneDrive tabs in the dedicated `taskSpace("ppt2pdf")`, waits for manual M365 login when necessary, and detects PowerPoint or Word Online.
3. **DOM Virtualization Defense (100+ slides)**: PowerPoint Online virtualizes left thumbnail items; calls `scrollIntoView()` before clicking each slide with rendering synchronization to eliminate missing slides.
4. **Resume & Revision Handling**:
   - `--reuse` enables resume mode: existing valid `slide-*.png` files in the work directory are skipped, finishing remaining slides instantly upon interruption.
   - For document revisions ("바뀐 거 체크해서 업데이트"), use `--fresh` (or back up previous slide SHA256 hashes to diff and detect added/modified slides).
5. Captures the rendered document page/slide surfaces (via `SlideRootViewElement` bounding box clip) without unsafe whole-screen fallback.
6. Assembles an image-only PDF with `img2pdf` and stores captured PNGs beside it.

Default output is `~/decks/<document>/<document>.pdf` plus `slide-*.png`, then `<document>.md` from the Markdown step.

## Direct Markdown Conversion (Sliding-Window Subagent Architecture)

Do **NOT** send slide images to legacy external proxy scripts (`gimso2xproxy`, etc.). This step runs on every `run` unless the user opted out:

1. **Direct Inspection**: the agent inspects the generated `~/decks/<document>/slide-*.png` directly with its image-capable file reader (`read_file` in Antigravity).
   - Read images individually within each chunk. If a read shows metadata but no image payload, retry with an alternate local path spelling (e.g. `..././slide-001.png`) or a local lossless re-encoding. Crop/enlarge small text as needed; never infer content from a blank payload.
2. **Parallel Subagents for Multi-Slide Decks (Sliding-Window Pipeline)**:
   - If 15 slides or fewer, the invoking agent processes them directly in session.
   - If the deck has more than 15 slides, divide slides into parallel chunks (10~15 slides per chunk) and spawn subagents (`invoke_subagent`).
   - **Model budget — Antigravity Standard**: spawn transcription subagents specifying `Model: 'flash'` (inherits the current Gemini 3.8 Flash session model). Do NOT spawn unbounded `pro` models or legacy models.
   - **Sliding-Window Context (Unlimited-OCR Inspired)**:
     - To prevent slide numbering gaps and preserve topic continuity across chunks, pass a 1-slide sliding window to each subsequent subagent: the preceding chunk's final slide number and heading (e.g. `[Context from prior chunk: Slide 15 ended with '## 슬라이드 15: 아키텍처 개요'. Your chunk starts at Slide 16.]`).
     - This guarantees contiguous numbering (`## 슬라이드 N`) and term consistency across parallel waves with minimal token overhead.
   - **Concurrency cap**: at most 3 subagents per wave. Start the next wave only after the previous wave fully completes.
   - **Rate-limit abort**: if any subagent reports `rate_limit_error` / `usage_limit_reached` (429), stop spawning further waves. Do NOT retry the failed chunk on other models via fallback chains. Finish the remaining chunks serially in the parent session, or report the blocker to the user.
   - Each subagent inspects its assigned `slide-*.png` images and writes its chunk to `~/decks/<document>/.chunk_NN.md`.
   - Once all subagents finish, merge the chunks in order into `~/decks/<document>/<document>.md` (title line `# <document>` first), verify every slide 1..N has exactly one `## 슬라이드 N` and one `<!-- PPT2MD_SLIDE_END:N -->`, then remove the temporary chunks.
   - If the deck has more than 40 slides, state the expected chunk count and get user confirmation before the first wave.
3. **Fidelity Rules**:
   - Preserve all visible text in full (titles, body items, table cells, labels, annotations, footnotes, UI text). No summary or omission.
   - **Structured Data**: Reconstruct complex tables in standard Markdown table syntax, and preserve formulas using LaTeX (`$...$` or `$$...$$`).
   - **Visual Diagrams**: For flowcharts, architecture diagrams, and complex UI, include Mermaid diagrams or clear 1-2 line descriptive explanations.
   - Use exactly one heading `## 슬라이드 N` per slide.
   - End each slide with `<!-- PPT2MD_SLIDE_END:N -->`.
4. **No Separate Proxy Transmission**: Images are read directly by the agent and its same-model subagents in Antigravity. Do not call external proxy scripts.

## check/status/cleanup

- `check`: read-only dependency/readiness probe for `ego-browser` CLI, img2pdf, and ego profiles. It does not launch a browser or navigate a document.
- `status`: report current `ego-browser` availability, active user profiles, and task space state without mutation.
- `cleanup`: acquire the existing non-blocking run lock and remove only skill-owned temporary captures under `/mnt/c/tmp/ppt2pdf` or `/tmp/ppt2pdf`. Preserve PDFs, PNGs under `~/decks`, Markdown, and ego browser sessions.

## Safety boundary

Default: uses the ego browser (`ego-browser` CLI) and preserves the existing manual-login session in the user's primary profile without exporting cookies/credentials or opening unauthenticated debug ports. The browser and session stay alive so the M365 session survives; `cleanup` must not stop it.

## Tests

Run the existing offline tests after changes:

```bash
python3 "<skill_dir>/test_ppt2pdf.py"
python3 "<skill_dir>/test_ppt2md.py"
```
