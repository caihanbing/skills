# Validator Integrity Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the confirmed false-pass and false-block paths in the two repository-local development-management validators.

**Architecture:** Keep the existing Markdown contracts and CLI surface, adding a shared conceptual normalization layer inside each script. Validation proceeds from structure to references, state-specific evidence, catalog consistency, and Git freshness; legacy Feature Docs remain readable while new output follows the corrected contract.

**Tech Stack:** Python 3 standard library, `unittest`, Git CLI, Markdown templates.

**Spec:** The approved repair design in the user conversation on 2026-09-11.

## Global Constraints

- Do not add IDE, dashboard, CI, database, or external-service dependencies.
- Every production behavior change must have a regression test that failed before the change.
- Preserve existing CLI commands and legacy Feature Docs compatibility unless the corrected contract explicitly changes new-document output.
- Do not treat documentation-only changes as implementation changes in Git freshness checks.

---

### Task 1: Work Item structural and referential integrity

**Files:**
- Modify: `manage-dev-work/scripts/dev_work.py`
- Test: `manage-dev-work/tests/test_dev_work.py`

**Interfaces:**
- Extend `WorkItem` parsing with masked scan text while retaining raw text for writes.
- Add deterministic helpers for record IDs, deferred references, Feature Doc resolution, and work-index consistency.

- [x] **Step 1: Write failing tests** for duplicate record IDs, orphan VER→REQ, deferred references to missing DEC/WORK, and closeout references to missing Feature Docs.
- [x] **Step 2: Run the focused tests** and confirm each currently passes incorrectly.
- [x] **Step 3: Implement minimal structural/reference gates** and preserve the optional nature of empty `feature-ids`.
- [x] **Step 4: Run focused tests** and confirm all new tests pass.

### Task 2: Work Item parser, dates, index, and state evidence

**Files:**
- Modify: `manage-dev-work/scripts/dev_work.py`
- Modify: `manage-dev-work/assets/work-item-template.md`
- Test: `manage-dev-work/tests/test_dev_work.py`

**Interfaces:**
- Add `verification-basis` metadata and a deterministic implementation-worktree digest.
- Record the basis when entering `verifying`; require it to match at `handoff-ready` and `closed`.
- Use the numeric-last `REV-*` entry as the current review result and require its status to be `PASS` for medium/high risk.

- [x] **Step 1: Write failing tests** for fenced headings, future/inverted dates, stale work index, latest failed review, accepted-risk evidence, and stale verification basis.
- [x] **Step 2: Run focused tests** and confirm the old validator allows the invalid cases.
- [x] **Step 3: Implement masked parsing, date/index checks, status-specific risk checks, review semantics, and basis comparison.
- [x] **Step 4: Run focused tests** and confirm all new tests pass.

### Task 3: Feature Docs freshness and contract consistency

**Files:**
- Modify: `manage-feature-docs/scripts/feature_docs.py`
- Modify: `manage-feature-docs/references/document-contract.md`
- Test: `manage-feature-docs/tests/test_feature_docs_v2.py`

**Interfaces:**
- Generate and validate `HEAD <12-hex>; worktree-digest sha256:<64-hex>` for Git repositories.
- Keep `no-git; working-tree=unknown` valid for non-Git repositories.
- Keep `### 用户回归准备` accepted only as legacy content; remove it from the current contract.

- [x] **Step 1: Write failing tests** for short SHA rejection, same-dirty-state code changes, and contract/template consistency.
- [x] **Step 2: Run focused tests** and confirm the old validator accepts the invalid freshness cases.
- [x] **Step 3: Implement the fingerprint and strict SHA validation, excluding management documentation paths.
- [x] **Step 4: Run focused tests** and confirm all new tests pass.

### Task 4: Full regression and independent adversarial verification

**Files:**
- Test: `manage-dev-work/tests/test_dev_work.py`
- Test: `manage-feature-docs/tests/test_feature_docs.py`
- Test: `manage-feature-docs/tests/test_feature_docs_v2.py`

- [x] **Step 1: Run both complete test suites and Python compilation checks.**
- [x] **Step 2: Build temporary Git repositories and exercise stale basis, orphan reference, duplicate ID, and missing Feature Doc cases through the public CLI.**
- [x] **Step 3: Confirm the working tree diff contains only the approved implementation, tests, template, contract, plan, and Work Item changes.**

### Task 5: Canonical Feature Contract and final P1 hardening

**Files:**
- Modify: `manage-feature-docs/scripts/feature_docs.py`
- Modify: `manage-feature-docs/SKILL.md`
- Modify: `manage-feature-docs/references/document-contract.md`
- Modify: `manage-dev-work/scripts/dev_work.py`
- Modify: `manage-dev-work/SKILL.md`
- Test: `manage-feature-docs/tests/test_feature_docs_v2.py`
- Test: `manage-dev-work/tests/test_dev_work.py`

**Interfaces:**
- `feature_docs.py validate-contract --repo <repo> --id <feature-id>` validates one document without catalog/index checks.
- Work Item closeout invokes that command, using `--feature-validator` when the sibling script is unavailable.
- Structural Feature Doc validation accepts digest, legacy clean/dirty, and no-Git basis syntax; fresh rejects legacy dirty and no-Git evidence.

- [x] **Step 1: Write and run failing tests** for empty Feature Docs, invalid basis syntax, stale completed-change dates, legacy dirty fresh, and canonical CLI behavior.
- [x] **Step 2: Implement the canonical command and remove the duplicate closeout contract implementation.**
- [x] **Step 3: Update Skill/reference contracts and run the complete suites.**
