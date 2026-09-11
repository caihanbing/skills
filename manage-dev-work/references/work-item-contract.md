# Work Item Contract

Use only material IDs: `REQ-*` for acceptance-bearing requirements, `DEC-*` for durable decisions, and `RSK-*` for delivery risks.

Set impact values to `affected` or `none`; do not use `unknown` at the planning gate. For every affected dimension, document the implementation or mitigation in the relevant section. An `OPEN` decision or risk must include a concrete confirmation path before planning continues.

For `type=bugfix`, complete every field in `## Bug Fix 闭环`. The root cause and regression guard must be evidence-based, not inferred from the symptom alone.

Risk levels:

- `low`: no observable behavior, data, configuration, or security impact.
- `medium`: business logic, non-breaking API, or configuration change.
- `high`: database, deletion, permissions, transaction, concurrency, messaging, cross-service, or breaking compatibility impact.
