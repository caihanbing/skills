# Legacy User Regression Handoff

This reference is for auditing or normalizing legacy Feature Docs that already contain `### 用户回归准备`. Do not add this section to new or normally updated Feature Docs; current release, restart, and user-regression handoff belongs to the associated Work Item.

Keep `## 测试与验证 > ### 用户回归准备` with these fields in this exact order:

1. `是否需要用户回归` — `是` or `否`.
2. `需更新、部署或重启的服务`.
3. `无需操作的服务`.
4. `操作顺序`.
5. `前置条件` — migration, configuration, flags, cache, consumer, and test data.
6. `回归步骤与预期结果`.

Inspect deployment manifests, service definitions, runtime configuration, queues, and repository deployment guidance. Do not leave unresolved language in this section; ask the user when topology or commands cannot be proved. State explicit no-action evidence for unaffected services.
