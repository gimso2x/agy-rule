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

Default `run` means: open/reuse the dedicated M365 browser, wait for manual login only when necessary, capture the document, produce PDF + page/slide PNG artifacts, and then — in the same turn, without asking — have the agent transcribe `~/decks/<document>/slide-*.png` into `~/decks/<document>/<document>.md` (parallel subagents for decks over 15 slides: `invoke_subagent` with `Model: 'flash'`, max 3 per wave, sliding-window context for slide continuity, abort on 429; see SKILL.md "Direct Markdown Conversion").

Markdown is processed directly by the agent in Antigravity (never `gimso2xproxy`, external proxies, or legacy scripts). Skip it only when the user explicitly opts out (e.g. "PDF만", "마크다운 없이").

A Markdown failure must not discard the already-produced PDF/PNGs; report it separately.

## check

Perform read-only readiness checks: `ego-browser` CLI, img2pdf, and observable M365/ego profile prerequisites. Do not navigate to a new document or send images externally.

## status

Report the `ego-browser` CLI availability, user profiles, and active task space state. Do not mutate browser/session state.

## cleanup

Remove only ppt2pdf-owned disposable temporary capture files and stale locks that are provably not held by a running job. Preserve generated PDFs, PNGs, Markdown, dedicated browser profile, and login session. Fail closed when ownership is ambiguous.

## Advanced/debug options

Existing `--out`, `--keep-tab`, `--reuse`, and `--fresh` options remain supported behind the run path. They are not separate top-level commands.
