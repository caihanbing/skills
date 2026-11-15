# Feature Document Schema

Keep one current-state document per stable feature at `docs/features/<feature-id>.md`. Feature Docs are evidence-backed context, not the source of truth and not a task log.

## Metadata and index

Place the following contiguous metadata block immediately after the title:

```markdown
<!-- feature-id: order-cancellation -->
<!-- feature-title: 订单取消 -->
<!-- feature-aliases: 取消订单, cancel-order -->
<!-- feature-status: active -->
<!-- feature-summary: 在受控条件下取消订单。 -->
<!-- last-verified: 2026-09-06 -->
<!-- code-basis: impl-v2 sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef -->
```

Use `planned`, `active`, `deprecated`, or `retired`. Keep `docs/features/index.md` aligned with this metadata; use `sync-index` for batch edits.

Fresh validation requires `impl-v2 sha256:<64-hex>`, computed by `snapshot --repo <root>`. It captures effective implementation paths, content, type and executable mode while excluding management documents; staging or committing unchanged content does not invalidate it. Sparse checkouts, sparse indexes and skip-worktree entries, including in submodules, are unsupported and fail closed; use a complete checkout. Submodule assume-unchanged entries also fail closed. Empty directories, ignored untracked files and external runtime artifacts are outside the snapshot and require separate verification when relevant. Structural validation continues to read legacy HEAD formats, but fresh validation requires explicit review and replacement with v2. Preserve HEAD and dirty-state provenance separately in prose. Snapshot errors and dirty or unverifiable submodules fail closed.

For a workspace without Git, `no-git; working-tree=unknown` is valid structural metadata. Fresh validation cannot establish an implementation snapshot and therefore fails.

## Required structure and style

Preserve this exact order of level-two headings:

1. `快速上下文`
2. `目标与边界` with `目标`、`范围内`、`范围外`、`不变量`
3. `业务行为`
4. `架构与代码地图`
5. `API、事件与任务`
6. `数据模型与迁移`
7. `核心流程`
8. `异常与边界条件`
9. `并发与幂等`
10. `安全与权限`
11. `配置与依赖`
12. `可观测性与运维`
13. `测试与验证` with `已执行`、`未执行`
14. `关键决策`
15. `已知问题与后续工作`
16. `变更记录`

Write concise Chinese current-state prose. Use backticks for paths, symbols, commands, configuration keys, and protocol fields. Use bullets for facts, numbered lists for flows, and tables only for repeated fields. Use `待确认：<原因与确认方式>` only after the user explicitly defers a non-blocking item.

For frontend features, use existing sections to record evidenced entry points, user flows, loading/empty/error states, responsive and accessibility behavior, and verification where applicable. Link the design system and durable visual artifacts rather than duplicating them. Backend-only features need no UI-specific content. Do not add or reorder required headings.

## Evidence and updates

Anchor material claims with repository-relative paths, symbols, tests, migrations, or commands. Do not include secrets, large source excerpts, or fragile line numbers.

Update current-state sections after each completed change. Preserve only durable decisions and append concise change entries with status, change, reason, compatibility, and verification. Bug fixes and incremental changes update the existing Feature Doc; cross-feature changes update each affected document.
