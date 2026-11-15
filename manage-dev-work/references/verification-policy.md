# Verification and Review

Each `REQ-*` must have implementation and verification evidence before handoff. Record failed or skipped checks with cause and remaining risk.

Medium and high risk work requires `REV-*` status `PASS`. Review only the affected impact dimensions: correctness, scope, failures, concurrency, transaction boundaries, security, compatibility, migration, performance, observability, and tests.

Do not treat completed implementation as verification evidence.

For Git work, use `snapshot --repo <repo>` and record the resulting `impl-v2` value in each PASS verification and review record's `证据基线`. Complete checks against that exact state; if the snapshot changes, repeat affected checks and user regression before handoff. The matching digest cannot prove that a person ran a command or performed a review.
