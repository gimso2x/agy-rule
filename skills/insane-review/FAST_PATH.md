# insane-review fast path

Use this as the default personal-coding entrypoint.

## Public surface

```text
insane-review [run] <request-or-scope...>
insane-review check
insane-review status
insane-review cleanup
```

If the first token is not `run`, `check`, `status`, or `cleanup`, treat the full input as `run`.

Example:

```text
insane-review "인세인 리뷰해줘"
# equivalent to: insane-review run "인세인 리뷰해줘"
```

## run (Default workflow)

Orchestrate the review flow as a single end-to-end agent task. The agent
starts the dedicated browser itself; the user never launches anything by hand:

1. **Bootstrap & readiness (browser-owning command)** — `mygjc-cdp start insane-review`
   is idempotent when already ready and (as a chatgpt role) opens
   `https://chatgpt.com/` on fresh launch. Keep the browser-owned process alive
   with `wait` while `check-env` observes login/model concurrently:
   ```bash
   (~/my-wiki/gjc-config/bin/mygjc-cdp start insane-review && \
    ~/my-wiki/gjc-config/bin/mygjc-cdp wait insane-review --timeout 900) & \
   python3 ~/my-wiki/gjc-config/skills/insane-review/bin/pack_and_ask.py check-env \
     --cdp-endpoint http://127.0.0.1:9222 \
     --profile-dir "$HOME/.local/state/mygjc/insane-review-profile"
   ```
   Branch on the observation: `ready:true` → continue;
   `authentication_required` → while the `wait` job is alive, `ask` "로그인 완료"
   and re-run `check-env` (nothing was sent); `model:"mismatch"/"unobservable"` →
   while the same job is alive, `ask` the user to select `GPT-5.6 Sol`, then
   re-run `check-env`; `no_chatgpt_page` → re-run the chain.
2. **Resolve scope**: Determine review scope from the user's request and current git/coding context. Build the intended manifest with canonical paths and SHA-256 digests.
3. **Prepare pack**: Run `bin/pack_and_ask.py prepare` (`--repo`, `--intended`, `--secretlint-config`) to execute mandatory secretlint scanning, token measurement with fixed `js-tiktoken`, and verify the 100k-token / 4MB limit.
4. **Single approval boundary**: Present one `ask` immediately before external transfer containing:
   - File count & scope
   - Measured token count & byte size
   - Secretlint scan verdict
   - Manifest SHA-256 & Pack SHA-256
   - Target model (`GPT-5.6 Sol` on ChatGPT Web via dedicated CDP 9222)
5. **Send & Retrieve**: After explicit approval of the exact pack digests, run `~/my-wiki/gjc-config/bin/mygjc-cdp start insane-review &&` `bin/pack_and_ask.py send ...` as one background command (the browser only lives while its starting command lives; start is a no-op when already ready) once with all required flags and `--timeout 1200` (`--prompt` takes the literal prompt text). The trusted launcher executes the validated immutable generation, verifies CDP/profile process binding, attaches the pack once, and waits for a substantive assistant reply. On timeout/failure a `*.failure.json` receipt is written — never re-run `send` for the same pack; report and wait for user direction.
6. **Return review**: Report the review result as a summary with the agent's own agreement/disagreement, reference the saved 0600 response artifact, then `ask` whether to apply suggested fixes; on approval the agent applies them to the code itself.

Do not make the user manually execute `prepare` and `send` as separate commands. Those remain internal steps orchestrated by the agent.

## check

Perform read-only readiness checks:
- Verify trusted launcher dependencies, Node, Playwright, tokenizer, and secretlint:
  `python3 ~/my-wiki/gjc-config/skills/insane-review/bin/pack_and_ask.py check-env`
- Verify dedicated browser process and CDP 9222 state:
  `~/my-wiki/gjc-config/bin/mygjc-cdp status insane-review`
Do not send content or mutate state.

## status

Report the dedicated browser/CDP 9222 state and the latest relevant review artifacts in `.insane-review/` without mutation.

## cleanup

Remove only disposable temporary packs and stale locks that are provably unreferenced by active reviews. Never edit or delete signed generations in `vendor/`, `vendor/current`, or durable response artifacts. Fail closed on ambiguous ownership.

## Advanced/debug interface

`bin/pack_and_ask.py prepare`, `send`, and `check-env` remain available as low-level diagnostic and recovery surfaces. Do not present them as the primary personal-coding path.
