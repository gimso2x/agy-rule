# ppt2pdf fast path

Use this as the default personal-coding entrypoint.

## Public surface

```text
ppt2pdf [run] <sharepoint-or-onedrive-url>
ppt2pdf check
ppt2pdf status
ppt2pdf cleanup
```

If the first token is not `run`, `check`, `status`, or `cleanup`, treat the full input as `run`.

Example:

```text
ppt2pdf "https://tenant.sharepoint.com/..."
# equivalent to: ppt2pdf run "https://tenant.sharepoint.com/..."
```

## run

Default `run` means: open/reuse the dedicated M365 browser, wait for manual login only when necessary, capture the document, and produce PDF + page/slide PNG artifacts. Finish there when the user asked for PDF conversion.

Markdown extraction is opt-in and processed directly by AGY (without `gimso2xproxy` or external proxies). When the user explicitly asks for Markdown/text extraction (or passes `--markdown`), AGY directly inspects `~/decks/<document>/slide-*.png` (using parallel subagents for multi-slide decks) to produce `~/decks/<document>/<document>.md`.

Do not make a PDF-only request fail merely because Markdown generation was not requested.

## check

Perform read-only readiness checks: Playwright/Chromium, img2pdf, Ego browser (chrome-agent)/CDP 9222 ownership, and observable M365/browser prerequisites. Do not navigate to a new document or send images externally.

## status

Report the dedicated ppt2pdf browser/CDP/profile state and whether a reusable SharePoint/OneDrive tab is observable. Do not mutate browser/session state.

## cleanup

Remove only ppt2pdf-owned disposable temporary capture files and stale locks that are provably not held by a running job. Preserve generated PDFs, PNGs, Markdown, dedicated browser profile, and login session. Fail closed when ownership is ambiguous.

## Advanced/debug options

Existing `--out`, `--keep-tab`, and `--reuse` options remain supported behind the run path. They are not separate top-level commands.
