# Work Item Contract

Use only material IDs: `REQ-*` for acceptance-bearing requirements, `DEC-*` for durable decisions, and `RSK-*` for delivery risks.

Record IDs must be unique within a Work Item. `VER-*` references must resolve to a declared `REQ-*`; a deferred requirement must reference an existing resolved/deferred `DEC-*` and a different existing follow-up Work Item. When `feature-ids` is non-empty, every ID must resolve to a matching Feature Doc before closure.

`feature-ids` uses unique lowercase kebab-case IDs (`^[a-z0-9]+(?:-[a-z0-9]+)*$`), separated by commas in metadata and in the closeout evidence field.

At closeout, the canonical Feature Docs validator checks each associated document. Git repositories require `validate-contract --mode fresh`; non-Git repositories use `--mode structural` only.

The generated metadata includes `verification-basis: pending`. Transitioning into `verifying` records the current implementation Git snapshot; handoff and closure reject a changed snapshot. Legacy Work Items may omit this field during structural validation, but Git-backed handoff and closure require it.

Set impact values to `affected` or `none`; do not use `unknown` at the planning gate. For every affected dimension, document the implementation or mitigation in the relevant section. An `OPEN` decision or risk must include a concrete confirmation path before planning continues.

For `type=bugfix`, complete every field in `## Bug Fix 闭环`. The root cause and regression guard must be evidence-based, not inferred from the symptom alone.

Risk levels:

- `low`: no observable behavior, data, configuration, or security impact.
- `medium`: business logic, non-breaking API, or configuration change.
- `high`: database, deletion, permissions, transaction, concurrency, messaging, cross-service, or breaking compatibility impact.
