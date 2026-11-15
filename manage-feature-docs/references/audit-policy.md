# Audit and Freshness Policy

Use structural validation for document shape, metadata, indexes, future dates, fenced Markdown, and local text/image links.

Use fresh validation when the task depends on current implementation evidence. It compares `code-basis` with the `impl-v2` effective implementation snapshot, excluding Feature Docs, Work Items and superpowers management documents. HEAD-based legacy bases require explicit re-audit and replacement; a clean format alone is not evidence of freshness.

Deterministic validation cannot prove that generic symbols, architecture explanations, or an `不适用` judgment are correct. Perform a semantic audit against current code, configuration, schema, and tests for those claims.
