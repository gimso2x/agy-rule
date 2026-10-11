---
name: aidlc-workflow
description: >-
  Use this skill when the user explicitly requests the AWS AI-DLC (AI-Driven Development Lifecycle) workflow,
  or asks for full structured software planning including inception, application design, reverse engineering,
  and per-unit construction loops.
---

# AWS AI-DLC (AI-Driven Development Life Cycle) Workflow

AI-DLC is a structured, adaptive development process that guides development across three major phases with clear approval gates.

## Phase 1: Inception (What & Why)

1. **Workspace Detection**:
   - Detect greenfield (new) vs brownfield (existing) codebase.
   - For brownfield, analyze packages, transaction flows, and architecture before modifications.
2. **Requirements Analysis (Adaptive Depth)**:
   - Minimal (simple/clear) vs Standard vs Comprehensive (high risk).
   - Proactively ask clarifying questions for any ambiguities.
3. **User Stories & Acceptance Criteria**:
   - Identify user personas, interactions, and acceptance criteria.
4. **Application Design & Units of Work**:
   - Decompose complex systems into independent units of work with defined dependencies and contracts.

## Phase 2: Construction (How)

For each Unit of Work:
1. **Functional & NFR Design**:
   - Design data structures, interfaces, and evaluate non-functional requirements (security, resiliency, performance).
2. **Code Generation (Two-Part Process)**:
   - **Part 1 - Planning**: Create a numbered step-by-step plan with `[ ]` checkboxes. Get explicit user approval before modifying code.
   - **Part 2 - Generation**: Execute the plan step-by-step. Modify existing files in-place without creating duplicate temporary files.
3. **Build & Verification**:
   - Run type checks, linters, unit tests, and property-based tests.

## Phase 3: Operations & Review

- Verify test coverage and lint pass.
- Produce audit summary of changes, modified files, and verification steps.
