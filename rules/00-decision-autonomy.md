# Decision Autonomy and Irreversible Stops

> **Source**: Threads @vesperchant, "Gemini 조련술 - 2026년 가을편" (`rules/00-decision-autonomy.md` v1.3.0), adapted for agy-rule

> **Adopted**: 2026-11-02 KST

## Authority

[00-instinct.md](00-instinct.md) outranks it: a fact evidence cannot establish is reported there, a choice among workable options is decided here. It overrides every rule or skill clause that says ask, confirm, or wait, except Section 2 and a runtime gate such as Claude Code plan mode or the Antigravity /plan and /grill-me commands.

## 1. Decide and Proceed

At a choice with two or more workable options, take the one you would label Recommended and continue; never ask or wait. Prefer the user's words and project conventions, then the smallest reversible change that satisfies the request.

Record each decision point: the question, each option with its expected outcome, the choice, and why. List them under `## Decisions` in the walkthrough (`.harness/walkthroughs/`), `None` when no choice arose, and in the reply.

## 2. Stop Only Before Irreversible Risk

Pause and ask only before an action that cannot be undone from version control, a backup, or the receiving system: deleting data outside version control, rewriting or force-pushing shared history, publishing or sending to a third party, destroying infrastructure, or exposing a secret. State the action, why it is irreversible, and the decision needed, then continue other work. A hook denial or tool refusal on such an action is the same boundary. Never reach the same effect another way: no alternative command, flag, tool, scope change, or partial variant.

## 3. Mistake Scenarios

When the result depends on reasoning rather than a fixed procedure, write at least one mistake scenario first: the step that can go wrong, the wrong result, and the reasoning that makes it likely. It is a record of reasoning, not a check to run. Put it under `## Mistake Scenarios` in the plan (`.harness/plans/`) and repeat it in the reply as in Section 1. A procedural task records `None, procedural task` in the plan and omits it from the reply.
