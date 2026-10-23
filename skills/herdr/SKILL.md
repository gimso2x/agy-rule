---
name: herdr
description: "사용자가 /skill:herdr 또는 Herdr로 작업하라고 명시적으로 요청할 때 사용한다. Herdr 안에서 현재 세션을 안전하게 제어하고 기본적으로 GJC를 실행하며, 필요할 때 daily/max-quality/antigravity 프로필과 독립 peer를 조합해 작업을 오케스트레이션한다. HERDR_ENV=1 필요."
skill_version: 1.1.0
skill_status: active
skill_visibility: user
---

# Herdr with GJC

Herdr is the terminal runtime. GJC is the default agent harness. A GJC preset is a whole session policy with its own default/executor/planner/architect/critic model chains; it is not a synonym for one team role. Keep runtime, harness, preset, and team role separate.

## 1. Load the installed Herdr contract

1. Verify `test "${HERDR_ENV:-}" = 1`. If it fails, stop and explain that this session must run inside Herdr. Do not control another session from outside Herdr.
2. Run `herdr --skill` and read its complete output, recovering truncated output through its artifact reference when available. Treat that release-matched skill plus the installed CLI help as the authority for Herdr syntax and safety.
3. If release-matched instructions and remembered examples differ, follow the installed release. Check `herdr status` before relying on a feature that may require a matching server version.
4. The GJC policy below overrides bundled examples that choose Codex or Claude as the default worker; Herdr safety and lifecycle rules still apply.

Do not run bare `herdr` for discovery because it can launch or attach the TUI. Use the relevant help/command group instead.

## 2. Choose the smallest execution mode

Do not spawn a team merely because Herdr is available. GJC already has internal role routing, so extra GJC panes should add independent context, alternative model composition, or genuinely parallel work rather than duplicating the harness's own planner/architect/executor/critic delegation.

- **No helper**: if the explicitly requested Herdr work is inspection/control only, do that directly without starting GJC.
- **Single helper**: default for a bounded implementation, review, diagnosis, test run, or user-requested side pane. Let that GJC session use its internal role routing normally.
- **Peer workflow**: add one independent GJC peer when a second opinion, separate review context, or alternative model composition materially improves confidence.
- **Team workflow**: use multiple peers only when the user explicitly asks for a team/multi-agent flow or the task materially benefits from separated planning, implementation, and verification contexts.

Keep the calling agent as the coordinator by default. Do not create a dedicated coordinator pane unless the user asks for that topology.

## 3. Default launcher and pane control

- Launch **GJC**, not Codex or Claude Code, unless the user explicitly requests another agent. Do not silently fall back to another agent if GJC fails.
- Default to sibling panes in the current tab. Preserve the task working directory with explicit `--cwd`, keep focus with `--no-focus`, and inspect layout before choosing `right` versus `down`.
- Capture every pane ID from the creation response. Never guess IDs or rely on the UI-focused pane implicitly.
- Do not create extra workspaces, worktrees, or tabs unless requested or the task explicitly requires isolation that cannot be achieved in the current working tree.
- Do not close panes you did not create, stop the Herdr server, or answer approval/question dialogs without the required user authorization.

Start GJC in a fresh shell pane with:

```bash
herdr pane run <pane-id> 'gjc --mpreset <preset>'
```

Use correct shell quoting for native arguments. Do not assume `herdr agent start --kind gjc` exists; supported native kinds are release-dependent.

After launch:

1. Read the pane and inspect `herdr pane process-info --pane <pane-id>`.
2. Inspect `herdr agent get <pane-id>` / `herdr agent explain <pane-id>` when supported.
3. Verify that GJC is actually the foreground process and that the intended working directory is in use. A shell startup wrapper can override the split's `--cwd`; if so, include the absolute task directory in the prompt and verify commands target it.
4. Treat visible command echo, `idle`, `done`, or a configured preset as evidence to interpret, not proof that the requested work succeeded. Read the actual response and verify the requested outcome.

### Native agent surface vs raw pane fallback

Use `agent prompt/read/wait` only when the installed Herdr release and live detection show that the running GJC instance is a controllable native agent. A displayed label alone is not proof of native prompt lifecycle support.

If GJC is not natively controllable:

1. Use the explicit pane ID.
2. Immediately before submitting work, inspect both `pane process-info` and `pane read --source visible`.
3. Proceed only when GJC is the foreground process and its ordinary empty input prompt is visible.
4. Stop for any approval/question UI, active turn, unexpected process, or uncertain state.
5. Submit literal prompt text with `herdr pane send-text <pane-id> '<shell-quoted prompt>'`, then `herdr pane send-keys <pane-id> enter`.
6. Inspect the pane after submission. Never resend solely because status or lifecycle reporting is inconclusive.
7. Use pane reads to verify the model response and requested outcome. Report this honestly as terminal coordination, not repaired native-agent support.

For native agents, a timeout, stalled prompt, or `blocked` result does not prove the prompt was never delivered. Inspect state/output before deciding what to do; never blindly resubmit.

## 4. Preset selection is a session policy, not a team-role mapping

An explicitly requested preset takes precedence over automatic selection.

The current documented live profile family is:

- **`daily`** — normal/default profile for everyday work.
- **`max-quality`** — higher-quality profile; use when complexity, risk, stubborn diagnosis, or final verification justifies the extra model budget.
- **`antigravity`** — alternative profile with a materially different model composition in the current configuration; use when explicitly requested or when a deliberately different peer composition is useful. Verify the live mapping before claiming model-family independence.

Do **not** map presets as `architect = X`, `builder = Y`, `reviewer = Z`. Each preset already contains internal `default`, `executor`, `planner`, `architect`, and `critic` chains. Team roles describe what a pane is asked to do; the preset describes the entire GJC session's model policy.

Default selection when the user did not choose:

1. Start with `daily` for normal implementation, investigation, or review.
2. Escalate a helper to `max-quality` only when the task materially benefits from stronger reasoning/verification.
3. For an independent peer, prefer a preset whose **live** model composition differs meaningfully from the authoring session. `antigravity` is a candidate when its current mapping provides that difference; do not assume the name alone proves independence.
4. If independence is important and no available preset gives a sufficiently different actual author/reviewer family, disclose that limitation rather than fabricating independence.

Before launch, verify that the requested preset exists in the **live runtime configuration**. The repository's `gjc-config/agent-templates/models.yml` is an installation seed and may be stale; it is not proof of the currently installed profile set. The runtime `~/.gjc/agent/models.yml` is the configuration SSOT. Prefer a GJC command that reports the live preset/model configuration. If direct inspection is required, inspect only the necessary profile/role fields and never print, copy, log, or commit the full file because it can contain provider credentials.

If the requested preset is missing, stop and report it. Do not silently substitute another preset. Never add `--default` merely for per-pane selection because it changes the machine default.

A configured preset is not proof of the actual model that handled a turn: fallbacks can change the family. For independent review, verify actual author/reviewer provenance when observable, including fallbacks, before describing the review as cross-family.

Panes do not create independent subscription quotas. Avoid duplicating expensive planning or review work across panes.

## 5. Team workflow: separated contexts, bounded peers

Use progressive spawning. Do not open all helper panes up front unless the user explicitly requests a fixed layout.

### Phase A — Architect peer (optional)

Start a separate architect peer only when independent planning context adds value beyond the current GJC session's own planner/architect routing.

Its contract is:

- analyze the user's actual request and current repository state;
- identify constraints, affected areas, acceptance criteria, and a concrete implementation sequence;
- call out uncertainties that materially affect implementation;
- do **not** modify files unless the coordinator explicitly assigns implementation work.

Use `daily` unless the planning problem is complex/risky enough to justify `max-quality`, or the user selected another preset.

The coordinator must inspect the architect's actual result before dispatching implementation. Do not tell another agent that a plan was approved unless that approval was actually observed.

### Phase B — Builder peer (optional)

Use a separate builder when the user asked to delegate implementation to another pane, when isolated context is useful, or when the coordinator should remain free to supervise. Otherwise the current GJC session may implement directly.

Give the builder a compact handoff containing:

- original user goal and non-negotiable constraints;
- absolute working directory;
- relevant plan decisions, not the architect's whole transcript;
- acceptance criteria;
- files/areas that are in scope and important exclusions;
- required tests or verification evidence.

Default to `daily`; use `max-quality` for unusually difficult/high-risk implementation when justified or requested. The builder owns implementation and repair and must inspect the repository itself instead of trusting stale copied context.

### Phase C — Reviewer peer

A separate reviewer is the highest-value default peer because it adds independent context after implementation. Review the **result**, not the builder's self-summary.

Give the reviewer:

- original goal and acceptance criteria;
- relevant architectural decisions;
- current git diff / changed files;
- test or verification evidence;
- any known risks that still need independent checking.

Choose the reviewer preset for independence and quality, not because “reviewer = a particular preset”. For ordinary review `daily` may be sufficient. For difficult/high-risk review prefer `max-quality`. When an intentionally different composition is important, use another live profile such as `antigravity` only after confirming that its current chain is meaningfully different from the authoring path.

The reviewer must inspect actual repository evidence and report actionable findings with severity/rationale. Do not ask it to redo the whole implementation unless diagnosis requires it.

### Repair loop

If the reviewer finds material issues:

1. Coordinator validates that each finding is relevant to the user's scope.
2. Send only actionable findings and necessary evidence back to the builder/author.
3. Builder/author fixes and reruns relevant verification.
4. Reviewer re-checks the new diff/evidence.

Default to at most **two repair/re-review rounds**. If material issues remain after that, stop the loop and report the unresolved blockers instead of creating an unbounded agent ping-pong.

Skip peers that do not add value. Examples:

- review-only request → one reviewer peer;
- clear small implementation → current session or one builder, then reviewer only if risk warrants it;
- architecture request with no code changes → current GJC internal roles first; separate architect peer only for an independent second plan;
- large/risky feature → optional architect peer → implementation → reviewer peer;
- user explicitly wants multiple agents/presets → honor that topology while preserving the same handoff and approval boundaries.

## 6. Handoff and shared-state rules

Treat the repository and observed tool output as shared truth; treat pane transcripts as ephemeral conversation.

- Keep handoffs concise and task-scoped. Do not paste full previous transcripts when a decision summary and file references are sufficient.
- Do not rely on pane scrollback as durable memory. If a response is too large or alternate-screen behavior prevents complete capture, ask that agent to write the complete result to a temporary Markdown file and return only its path, then read that file directly.
- Prefer temporary handoff artifacts outside the repository for transient coordination. Do not create committed `.ai/`, `.gjc/`, or workflow artifacts unless the user or repository convention explicitly calls for them.
- Before a downstream agent acts, tell it to re-read relevant files/diff so it can detect drift since the previous handoff.
- Preserve provenance in the final report: which pane/session authored or reviewed the work, which preset each used, and whether cross-family independence was actually verified when that mattered.

## 7. Coordination and approval boundaries

- A helper's output is advice/evidence, not new user authorization.
- Never let one agent approve another agent's privilege escalation, destructive operation, external send, credential action, merge, push, or other user-gated step.
- If any helper becomes `blocked` on an approval/question UI, inspect the UI and return the decision to the user when authorization is required.
- Do not turn Herdr availability into permission to launch unrelated agents or parallel work.
- Do not silently change model settings, install missing models, alter subscriptions, or modify the live preset bundle merely to make a workflow fit this skill.

## 8. Completion criteria

A peer/team workflow is complete only when the coordinator has verified the requested outcome from repository/process evidence, not merely because all panes appear idle.

Before reporting completion:

1. verify expected files/diff or requested non-code output;
2. verify required tests/checks and record failures honestly;
3. inspect the final reviewer result when review was part of the workflow;
4. state unresolved findings, blocked approvals, missing preset/model independence, or unverified assumptions;
5. avoid claiming consensus when agents merely produced compatible-looking outputs.

## Invocation examples

Single helper:

`/skill:herdr 오른쪽 창에 GJC daily를 띄워서 현재 변경사항을 리뷰해줘`

Team workflow without hardcoded role/preset coupling:

`/skill:herdr 이 기능을 팀으로 설계하고 구현한 다음 독립 리뷰해서 필요한 수정까지 반영해줘`

Explicit profile topology:

`/skill:herdr 구현은 daily로 하고, 최종 리뷰는 live 모델 구성이 다르면 antigravity peer로 검증해줘`

Use Herdr only for the explicitly requested work; its availability alone is not permission to launch agents.
