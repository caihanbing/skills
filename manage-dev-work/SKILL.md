---
name: manage-dev-work
description: Use for substantive requirements analysis, feature development, or bug fixes that need a project-local Work Item, risk-based quality gates, requirement-to-verification traceability, release readiness, or cross-session progress recovery. Do not use for pure questions, reading, formatting-only edits, or explicit low-risk trivial changes.
---

# Manage Development Work

Manage the short-lived delivery lifecycle of one development work item. Keep durable system knowledge in Feature Docs; do not turn a Work Item into a second Feature Doc.

## Start or restore work

1. Resolve the repository root and inspect `docs/work-items/index.md`.
2. Restore a matching open Work Item when one exists; otherwise create one with `dev_work.py init`.
3. Associate existing stable Feature IDs when known. Do not create a Feature Doc merely because a Work Item exists.
4. Read [workflow.md](references/workflow.md) before transitioning state or applying a gate.
5. Read only the relevant reference for the active mode:
   - requirements, acceptance, impacts, decisions, and risks: [work-item-contract.md](references/work-item-contract.md);
   - verification and review: [verification-policy.md](references/verification-policy.md);
   - release or user regression: [release-handoff.md](references/release-handoff.md).

## Gate rules

- Investigate repository facts first. A material unresolved decision is a `BLOCKER`; ask the user and do not encode an assumption.
- An `OPEN` decision or risk may remain only when it does not affect the current transition; record its owner or confirmation path.
- Use `low`, `medium`, or `high` risk. Elevate rather than downgrade when data, deletion, permissions, transactions, concurrency, messaging, cross-service behavior, or compatibility may be affected.
- Medium and high risk require a recorded passing code review before `handoff-ready`; high risk also requires a release and rollback strategy.
- `handoff-ready` is not `closed`. If user regression is required, retain `handoff-ready` until its result is recorded as passed.
- Entering `verifying` records an implementation `verification-basis`; `handoff-ready` and `closed` require the implementation worktree to match it.
- When `feature-ids` is non-empty, closure requires each ID to resolve to `docs/features/<feature-id>.md` with matching metadata.
- Closeout invokes the canonical Feature Docs contract for every associated ID; in a Git repository it uses fresh validation against the current implementation snapshot, while a non-Git repository uses structural validation only.
- Pass `--feature-validator <path-to-feature_docs.py>` to `transition` or `close` when the default sibling validator is not available; the command must support `validate-contract`.
- At closure, invoke `$manage-feature-docs` to update each associated Feature Doc with durable behavior, decisions, risks, and verification evidence. Do not copy transient task logs into it.

## Commands

```bash
python3 <skill-directory>/scripts/dev_work.py init --repo <repo> --title <title> --type <feature|bugfix|change> --risk <low|medium|high> --features <feature-id> ...
python3 <skill-directory>/scripts/dev_work.py status --repo <repo> --id <work-id>
python3 <skill-directory>/scripts/dev_work.py validate --repo <repo> --id <work-id> [--gate <state>]
python3 <skill-directory>/scripts/dev_work.py transition --repo <repo> --id <work-id> --to <state>
python3 <skill-directory>/scripts/dev_work.py close --repo <repo> --id <work-id>
```

Run `validate` before and after a transition. Report the current state, failed gates, evidence, release handoff, and Feature Docs updated.
