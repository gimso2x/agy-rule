---
name: ppt2pdf
description: Convert SharePoint/OneDrive protected PowerPoint or Word documents through browser rendering into PDF and captured page/slide PNGs, with direct Markdown transcription by AGY (without external gimso2xproxy). Use for requests like "pptx/docx를 PDF로", "링크만 주면 PDF", or when the user explicitly invokes ppt2pdf. Natural input defaults to the run fast path; Markdown extraction is opt-in and handled directly by AGY.
skill_version: 2.4.0
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

This default run produces PDF + page/slide PNGs only.

Explicit Markdown opt-in (or when user asks for Markdown):
- Run `python3 "<skill_dir>/skill_cli.py" "<url>"` first to capture PDF + `slide-*.png`.
- Then **AGY directly transcribes the slide PNGs into Markdown** (see Direct AGY Markdown Conversion below). Do **NOT** use `gimso2xproxy` or external proxies.

Operational commands:

```bash
python3 "<skill_dir>/skill_cli.py" check
python3 "<skill_dir>/skill_cli.py" status
python3 "<skill_dir>/skill_cli.py" cleanup
```

Existing run options such as `--out`, `--keep-tab`, and `--reuse` pass through to the legacy capture engine.

## Capture engine

`ppt2pdf.py` remains the low-level capture engine. It:

1. Uses the dedicated WSL Playwright Chromium profile `~/.local/state/mygjc/ppt2pdf-profile` on CDP port **9223**.
2. Reuses an existing browser only after verifying exact port/profile process binding; foreign ownership fails closed.
3. Opens or reuses SharePoint/OneDrive, waits for manual M365 login when necessary, and detects PowerPoint or Word Online.
4. Captures the rendered document page/slide surfaces without unsafe whole-screen fallback.
5. Assembles an image-only PDF with `img2pdf` and stores captured PNGs beside it.

Default output is `~/decks/<document>/<document>.pdf` plus `slide-*.png`.

## Direct AGY Markdown Conversion (No gimso2xproxy)

Do **NOT** send slide images to `gimso2xproxy` or external model scripts. When the user requests Markdown (e.g. "마크다운까지", `--markdown`, or text conversion):

1. **Direct Inspection**: AGY inspects the generated `~/decks/<document>/slide-*.png` directly via `view_file`.
2. **Parallel Subagents for Multi-Slide Decks**:
   - If the deck has more than 15 slides, divide slides into parallel chunks (e.g. 10~15 slides per chunk) and invoke `self` subagents via `invoke_subagent`.
   - Each subagent inspects its assigned `slide-*.png` images via `view_file` and writes its chunk to `.chunk_NN.md`.
   - Once all subagents finish, merge the chunks into `~/decks/<document>/<document>.md` and remove temporary chunks.
   - If 15 slides or fewer, AGY processes them directly.
3. **Fidelity Rules**:
   - Preserve all visible text in full (titles, body items, table cells, labels, annotations, footnotes, UI text). No summary or omission.
   - For diagrams, flowcharts, and complex UI, include Mermaid diagrams or clear 1-2 line descriptive explanations.
   - Use exactly one heading `## 슬라이드 N` per slide.
   - End each slide with `<!-- PPT2MD_SLIDE_END:N -->`.
4. **No External Send Approval Needed**: Because AGY processes the local images directly within the user's workspace session, external proxy transmission is avoided completely.

## check/status/cleanup

- `check`: read-only dependency/readiness probe for Playwright, img2pdf, Chromium, and dedicated CDP/profile ownership. It does not launch a browser or navigate a document.
- `status`: report current dedicated browser/profile/CDP state without mutation.
- `cleanup`: acquire the existing non-blocking run lock and remove only skill-owned `/tmp/ppt2pdf/slide-*.png` temporary captures. Preserve PDFs, PNGs under `~/decks`, Markdown, the dedicated profile, and login session.

## Safety boundary

Keep port 9223 dedicated to ppt2pdf; 9222-9224 remain reserved for insane-review/ppt2pdf/gptplan. Do not use a foreign browser on the dedicated port. Preserve the existing manual-login model and never export cookies/credentials. The browser/profile may stay alive so the M365 session survives; `cleanup` must not stop it.

## Tests

Run the existing offline tests after changes:

```bash
python3 "<skill_dir>/test_ppt2pdf.py"
python3 "<skill_dir>/test_ppt2md.py"
```
