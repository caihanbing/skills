# Audit and Freshness Policy

Use structural validation for document shape, metadata, indexes, future dates, fenced Markdown, and local text/image links.

Use fresh validation when the task depends on current implementation evidence. It compares `code-basis` with the Git HEAD and implementation worktree state, excluding Feature Docs and Work Items that are changed only by documentation maintenance.

Deterministic validation cannot prove that generic symbols, architecture explanations, or an `不适用` judgment are correct. Perform a semantic audit against current code, configuration, schema, and tests for those claims.
