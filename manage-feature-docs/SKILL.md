---
name: manage-feature-docs
description: Use when explicitly invoked to create, locate, verify, read, or incrementally maintain repository-local backend feature documentation after requirements analysis, feature development, incremental changes, bug fixes, or document-drift audits.
---

# Manage Feature Docs

Maintain one evidence-backed technical document per stable feature. Treat the document as a context accelerator and the current code, configuration, schema, and tests as the source of truth. Never turn an unresolved product or technical decision into an assumption.

## Select the operation

Infer the requested operation from the prompt:

- **Read only**: restore and explain context without changing code or documentation.
- **Development request**: restore the relevant context, then route substantive analysis, implementation, or bug fixing to `$manage-dev-work`; return here only for durable knowledge closeout.
- **Archive or update**: document work already completed in the current session or worktree.
- **Audit**: validate structure and compare documented claims with the repository; change files only when the user requested repairs.

Respect an explicit read-only or analysis-only boundary. Do not create or update documentation in that mode.

## Enforce the clarification gate

Apply this hard gate during requirements analysis, feature development, incremental work, bug fixing, testing, document creation, and document updates.

1. Investigate discoverable facts first by reading the relevant code, configuration, schemas, tests, deployment definitions, and existing documents.
2. Treat an item as blocking when more than one plausible interpretation remains and the choice can affect requested behavior, interfaces, data, migrations, compatibility, security, permissions, concurrency, idempotency, service rollout, or acceptance criteria.
3. Stop before writing or changing code, tests, schemas, migrations, configuration, or feature documents that would encode one interpretation. Continue only read-only investigation that cannot commit the decision.
4. Ask the user the minimum focused questions needed to resolve every blocker. For each question, state:
   - the unresolved decision;
   - current evidence and why it does not decide the issue;
   - the concrete options and their impact;
   - a recommendation when evidence supports one.
5. Wait for an explicit answer. Resume only after the user selects an option, supplies a concrete value, provides a deterministic decision rule, or explicitly agrees to defer that specific item.

Do not bypass the gate by choosing an “industry standard,” “reasonable,” “temporary,” or “safe” default. A deadline, sunk work, an unavailable stakeholder, or a generic instruction to avoid questions does not resolve a specific ambiguity. Do not implement first and label the decision `待确认` afterward. Use `待确认` only when the user explicitly defers that item and the agreed scope can proceed without deciding it.

| Rationalization | Required response |
| --- | --- |
| “The release is urgent.” | Stop; urgency does not define behavior. |
| “This is the usual default.” | Stop; list the plausible defaults and ask. |
| “We can change it later.” | Stop; temporary behavior still becomes a contract. |
| “The user said not to ask questions.” | Stop; ask because the unresolved decision has not been answered. |
| “I will record it as pending.” | Stop; documentation does not authorize an implementation choice. |

Red flags include words such as “short-term,” “normal,” “appropriate,” “reasonable,” “later,” or “as usual” without measurable definitions. Encountering one means run the clarification gate before further writes.

## Resolve the repository and feature

1. Use a repository path explicitly supplied by the user. Otherwise use the Git root containing the current working directory; if no Git root exists, use the current workspace root.
2. Use `docs/features/index.md` as the catalog when it exists.
3. Run the bundled finder to search IDs, titles, aliases, and document contents:

   ```bash
   python3 <skill-directory>/scripts/feature_docs.py find --repo <repository-root> --query <feature-name-or-id>
   ```

4. Read every plausible match before selecting. Select automatically only when one feature is clearly identified. If multiple stable features remain plausible, use the clarification gate before any write.
5. If no document exists:
   - Report that fact for a read-only request and reconstruct context from the repository if requested.
   - Create a document only for a new stable feature or when the user requested archival.
6. Update each affected feature separately for cross-feature changes. Do not create a task-level document merely because one change spans several features.

## Restore context

1. Start with metadata, `快速上下文`, `目标与边界`, the sections relevant to the request, `关键决策`, and `已知问题与后续工作`.
2. Read the complete document only for an audit, a material drift finding, a major refactor, a compatibility-sensitive change, or an update that may touch several sections.
3. Follow only repository-local references relevant to the task. Never expose secrets from configuration, credentials, local environment files, or logs.
4. Inspect the current implementation before relying on a documented claim. Prioritize:
   - public APIs, events, jobs, and consumers;
   - schemas, migrations, persistence models, and compatibility rules;
   - core services and state transitions;
   - configuration, permissions, concurrency, and idempotency controls;
   - tests, fixtures, and documented verification commands;
   - current branch, HEAD, and worktree state.
5. Classify material findings as:
   - **已确认**: supported by current repository evidence;
   - **疑似漂移**: documentation conflicts with or no longer maps cleanly to current evidence;
   - **待确认**: neither the repository nor user-provided material establishes the claim.
6. For a read-only request, return the requested explanation plus that classification and make no edits. For continued work, pass every material drift or unknown through the clarification gate before depending on it.

## Create or update a document

Read [references/document-contract.md](references/document-contract.md) before creating or updating a feature document. Read [references/regression-handoff.md](references/regression-handoff.md) only when user regression is required. Read [references/audit-policy.md](references/audit-policy.md) for an audit or `--mode fresh` validation.

### Create a new feature document

1. Choose a stable lowercase kebab-case feature ID. Prefer an established domain or code identifier; do not transliterate unpredictably between sessions.
2. Initialize from the bundled template:

   ```bash
   python3 <skill-directory>/scripts/feature_docs.py init --repo <repository-root> --id <feature-id> --title <feature-title> --aliases <alias-one> <alias-two>
   ```

3. Refuse to overwrite an existing document. If a related document already exists, update it instead.
4. Replace every `FEATURE_DOCS:REPLACE` marker with verified content, `待确认：<reason>`, or `不适用：<reason>`.
5. Follow the section order, fixed subheadings, record shapes, and writing style in the document contract. Do not improvise a different format for each feature.

### Update an existing feature document

1. Preserve the feature ID and filename unless the user explicitly requests a migration.
2. Rewrite the current-state sections so they describe the implementation after the completed work. Do not accumulate obsolete snapshots in the body.
3. Preserve still-relevant decisions and known constraints. Correct stale claims or label unresolved drift explicitly.
4. Append only a concise, durable change-history entry: date, behavioral or architectural change, reason, compatibility impact, and verification evidence. Do not copy a commit diff or debugging transcript.
5. Update the document metadata and the matching `docs/features/index.md` row together.
6. Normalize an older document to the current contract when touching it, while preserving verified content and useful history.

### Establish evidence and completion state

1. Use requirements and current-session decisions for intent; use code, schemas, configuration, tests, and command results for implementation facts.
2. Record repository-relative paths and symbol names. Avoid line-number references because they drift quickly.
3. Record the verification date, HEAD commit when available, and whether the worktree was dirty. Never imply that uncommitted work belongs to the recorded commit.
4. Record failed or skipped tests accurately. Mark incomplete work as incomplete; never present it as delivered.
5. Route genuine unknowns through the clarification gate. Record `待确认` only after the user explicitly agrees to defer the item.

## Validate before handoff

Run validation after every creation or update:

```bash
python3 <skill-directory>/scripts/feature_docs.py validate --repo <repository-root> --id <feature-id> --mode structural
```

Use `--mode fresh` to compare `code-basis` with the current Git implementation state. Run `sync-index --repo <repository-root>` after batch metadata edits. Do not repair unrelated user-authored prose merely to make it stylistically uniform.

## Prepare user regression handoff

For legacy Feature Docs only, preserve durable testing commands and environment limitations. Current release, service restart, and user-regression handoff belong to the associated Work Item.

1. Inspect deployment manifests, service definitions, build files, runtime configuration, migrations, queues, scheduled jobs, caches, and repository deployment guidance.
2. Identify every affected service or component and every known unaffected neighboring service.
3. For each affected service, state the exact required action: no action, rebuild, update, deploy, reload, restart, or rolling restart. Give the required order and dependency conditions.
4. State database migrations, configuration or feature-flag changes, cache invalidation, message-consumer handling, data preparation, and other prerequisites. Explicitly state when each category requires no action.
5. Give executable regression steps and observable expected results. Separate commands from expected behavior.
6. If service ownership, topology, commands, order, or prerequisites cannot be established from repository evidence, use the clarification gate. Never invent deployment or restart instructions.
7. Record the confirmed handoff only in the Work Item `## 用户回归` section; do not duplicate transient release facts into a Feature Doc.

In the final response, report:

- documents created or updated;
- evidence and tests used;
- validation result;
- whether user regression is required, plus affected and unaffected services, exact update/restart order, prerequisites, steps, and expected results;
- remaining drift, unknowns, failed checks, or incomplete work.

## Guardrails

- Preserve unrelated documentation and user changes.
- Do not overwrite a pre-existing document during initialization.
- Do not create a second document for a bug fix or iteration of the same stable feature.
- Do not update documentation before implementation and verification reach the state described in it.
- Do not continue through a blocking ambiguity or treat a generic default as user confirmation.
- Do not ask the user to regress without a confirmed service update/restart handoff.
- Do not claim completeness solely because the structural validator passes.
- Do not copy the style of a pre-existing document when it conflicts with the current contract and template.
- Do not commit documentation unless the user explicitly requests a commit.

## Common explicit prompts

- `使用 $manage-feature-docs 为“订单取消”功能创建技术档案，并基于当前代码和测试核验。`
- `使用 $manage-feature-docs 读取 order-cancellation 的档案，结合当前代码说明已确认、疑似漂移和待确认的信息；只分析，不修改文件。`
- `使用 $manage-feature-docs 先恢复“订单取消”的上下文，完成增量需求和测试后更新原档案，不要创建新档案。`
- `使用 $manage-feature-docs 修复重复退款问题，完成验证后更新所属功能的并发、幂等和测试说明。`
- `使用 $manage-feature-docs 记录本次修复；如果需要我回归，请明确列出要更新或重启的服务、顺序、前置条件和预期结果。`
