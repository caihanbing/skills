---
name: dms-review-changes
description: Review DMS project implementation changes for correctness, security, project coding guidelines, and applicable coverage. Use for maintained application/shared-library code, related tests, SQL migrations, and build/runtime configuration under the project review requirements. Exclude release scripts, design prototypes and their demonstration code, UI/UX/design reviews, and standalone documentation reviews, including explicit dms-review-changes requests limited to those artifacts.
---

# Code Review (project-specialized)

> Canonical source: `docs/skills/dms-review-changes/` (+ `references/`) in the dms-console repo. No version field — **git history is the version**; for a copied install, verify the loaded path and the source/content identity in its package manifest; preserve documented host adaptations.

Arguments: `[low|medium|high|xhigh|max] [c=N] [cov] [mr] [--base <ref>]`.

Multi-angle review (effort level + finder fan-out + 1-vote verify + sweep + ranked), plus project-specific F/G/H + jacoco + Alibaba guidelines. high+ is **recall-biased**: prefer over-reporting to missing a real bug.

## Scope

This skill follows the currently effective instructions, including applicable `AGENTS.md` files. For team-rule findings, start with `config/coding-guidelines/coding-guidelines.md`, `docs/code-quality/研发流程必做项.md`, and team requirements explicitly specified by the user for this task; read related rule files only as needed. A versioned directory is not itself a set of mandatory rules, and an unshared personal preference is not a team violation.

- Review maintained project implementation code and its directly related tests, SQL migrations, and build/runtime configuration. Determine scope by the artifact's role in the application or shared libraries, not its extension or mere presence in Git.
- Exclude release scripts, design prototypes, mockups, and their demonstration code, including interactive HTML/CSS/JS, as well as standalone design/document reviews. Documentation may still provide context for in-scope project behavior. Apply this boundary to both tracked and untracked changes; in mixed changes, pass only the project-code portion to finders and coverage checks.
- Explicit `dms-review-changes` invocation uses the same scope. If no in-scope project code remains, report `N/A` and skip the code-review phases; do not report a passed code review. For this outcome with `mr` or an explicit MR-text request, follow the N/A path in [MR output rules](references/mr-output.md) and include `MR 评论（审查记录）：不适用，本次变更不在代码审查范围内。` in the reply, outside the MR text. A commit or PR/MR preparation request alone does not trigger this skill; applicable project-code merge requirements still apply.

## effort level (5 levels)

| level | mode | finders (correctness + project + cleanup) | perAngle | report target | sweep |
|------|------|------|------|------|------|
| low | inline | hunk-visible bugs | — | — | no |
| medium | inline | A/B/C + F/G/H + cleanup | ≤6 | 8 | no |
| **high (default)** | workflow fan-out | A/B/C + F/G/H + cleanup | ≤6 | 10 | no |
| xhigh | workflow fan-out | A-E + F1/F2 + G/H + cleanup | ≤8 | 15 | yes |
| max | workflow (deeper reasoning) | same as xhigh | ≤8 | 15 | yes |

Default high; small changes → low/medium (inline fast), large → high+. **F/G/H run at medium+** (this-repo high-risk); F splits into F1 (injection/access-control/RCE) + F2 (crypto/data-exposure/config) at xhigh/max to avoid 6 categories crowding the candidate budget, single F at medium/high (low runs no F/G/H at all — its row is hunk-visible bugs only). inline (low/medium) is main-agent single-pass, no fan-out/sweep. low: no verify; medium: inline self-verify (main agent re-checks each candidate against verify criteria, no sub-agent fan-out). The cleanup finder's candidate cap = 6 sub-angles × perAngle (high 36 / xhigh·max 48), not a shared ≤perAngle — merging six lenses into one finder must not shrink their combined budget.

**No auto-editing**. A read-only request authorizes inspection; compile/jacoco or other commands that write outputs need matching execution authorization. Never infer permission for deploy/DDL/data mutation/business requests from a review request.

> Finders and verifiers use independent contexts with the tools needed for read-only inspection. **Each prompt MUST include the READ-ONLY constraint** "do NOT create/modify/delete files"; restrict tools where the host supports it. Before fan-out, read `references/angles.md` (A-H + cleanup angle full text incl. Cleanup ground rules + verify criteria + sweep focus) + `references/review-pitfalls.md` (anti-false-positive notes: config-assembly for H, `ENC(...)` secrets for F — inlined by the F and H finders; G has no note there). Each finder inlines its full angle text (not just the title); the cleanup finder inlines the whole Cleanup angles section including its ground rules.

**Tool adaptation**: for formal delivery or large changes, lead the review in a fresh main session without implementation history; use an independent subagent for small-scope rechecks. Use the host's available delegation mechanism and configured model; do not require a particular tool name or model alias. If delegation is unavailable, perform the applicable checks in the main context and disclose the fallback; do not describe self-checking as independent verification. Interpret the arguments listed above from the user's request.

## Runtime config (concurrency, coverage)

fan-out concurrency cap (covers Phase 1 finders **and** Phase 2 verifiers — verify fan-out is larger per-location, must be capped too) defaults to **3** (team-shared agents are mostly domestic models, 7 concurrent deadlocks/429 in practice); the `c=N` argument overrides. On 429/timeout → lower concurrency and retry; if still failing, main agent re-reads the angle text and re-scans that angle.

**jacoco**: obtain coverage evidence when reviewed Java behavior needs it under project requirements, or the `cov` argument explicitly requests applicable JVM coverage. Total changed-line count alone does not trigger Maven tests. Reuse successful results that still cover the reviewed implementation, tests, and relevant build/coverage configuration. Rerun affected checks when relevant inputs changed, tests failed, or an unresolved coverage risk needs new evidence. For non-Java-only scope, use relevant checks and report JVM coverage as not applicable.

## Phase 0 — Gather + test scope + jacoco

Choose the review range before collecting a diff:

- **Uncommitted changes (default)**: inspect `git diff --cached` and `git diff`, plus `git status --short` for untracked (`??`) files. Include in-scope staged, unstaged, and untracked changes; distinguish the index and working-tree contents when they differ. This mode needs no target-branch confirmation and makes no claim about the whole branch.
- **MR / whole-branch review**: use this mode for a pre-merge review, `mr`, an explicit whole-branch request, or `--base <ref>`. Recommend `releases` as the target, or present the user's proposed alternative. **Ask the user to confirm the target and wait for an explicit answer before resolving the baseline, collecting the review diff, or starting review phases.** Neither a default selection, `--base`, nor discovered MR metadata substitutes for confirmation. Reuse an explicitly confirmed target for subsequent reviews of the same MR; confirm again if the target changes.
- After confirmation, resolve the confirmed target ref and use `git diff <target-ref>...<source-commit>` for source-branch review. For an existing MR, use its actual source commit and ensure the target matches that MR; for an MR being prepared, use `HEAD` and identify it as the local source commit. If the confirmed ref or required MR commit cannot be resolved, report the missing evidence instead of substituting `@{upstream}`, `main`, or `HEAD~1`. Read full files from the selected review snapshot. Keep any additionally reviewed uncommitted changes separate; a local uncommitted fix does not resolve a finding in the MR commits.
- **N/A MR text before commit**: when confirming this outcome, include existing branch changes and the explicitly selected staged/worktree candidate. Identify the candidate separately as uncommitted and follow the [MR output rules](references/mr-output.md). An empty committed diff does not mean that the candidate has no changes; producing its text does not establish merge acceptance.
- **Merge acceptance (`mr` or explicitly requested)**: record the pre-merge target, source commit, and candidate/actual result (commit/tree and origin). Review `git diff <pre-merge-target> <merge-result>` and full files from that result; test scope includes complete conflict-resolution methods and directly affected entrypoints. Missing baselines/results or unresolved conflicts leave merge acceptance unverified.

Apply Scope to all selected paths, including untracked files in an uncommitted review; read in-scope new project classes and tests in full. If none remain, use the not-applicable outcome in Scope before coverage checks or finder work. Record the review mode, baseline/source/merge-result identities as applicable, and any separately reviewed uncommitted changes in the report's 审查范围.

**Applicable rule evidence**: identify the exact source and clause for the reviewed paths and task stage, distinguishing mandatory, recommended, and reference guidance and any activation conditions. Check the current entrypoints rather than promoting a recommendation, plan, or historical target to an effective requirement. Merge-blocking language also has pilot/acceptance conditions that must be established before claiming it is active. Pass the source, quoted clause, authority, stage, and applicability evidence to each finder or verifier assessing a rule-based claim, including testing-obligation claims, and use the same material in inline checks and synthesis. Cite the clause and violating code location in a finding. Unclear authority or applicability stays 未核实 / 待确认, outside confirmed mandatory violations, issue counts, and MR disposition requirements; continue independent review work.

**Test scope**: reuse the selected snapshot, requirements, diff, and code already inspected to identify the changed behavior and the initial scenarios needed to select relevant checks. Include applicable main paths, errors, boundaries, state transitions, and directly affected regression paths; do not enumerate unrelated test categories or complete a second cross-file investigation before Phase 1. At low, summarize from the code/tests already read and disclose the limits. Existing finders enrich the same analysis as they follow their assigned angles.

For each scenario, cite the requirement or contract behind the expected result; code alone establishes current behavior or an inference, not business acceptance. Unresolved expectations stay under 待确认 without blocking independent analysis. Read the relevant tests' inputs and assertions: a matching name or high coverage does not establish that the expected behavior is checked. Keep implementation presence, assertion coverage, and actual execution evidence distinct. Reuse this analysis for the report; no external test-scope skill, extra collector, separate report, dms-test-gate, or automatic test edits are required.

**Test-evidence candidates**: mark test-requirement gaps and defects in the evidence supplied by tests with `test_evidence=true`, using the existing candidate fields. For a missing required test, include the exact applicable requirement, its applicability to this change and review stage, and the tests inspected; an absent filename alone is insufficient. For a defective assertion, include the test's intended target/contract, inputs, and the assertion that fails to establish it. A business behavior requirement does not automatically require a new unit test. Unknown applicability, incomplete inspection, and optional additions stay as recommendations or questions. Anchor a missing-test candidate to the changed behavior's actual source location, never an invented test file. Implementation correctness findings keep the ordinary criteria.

At low, these new test-evidence candidates are recommendations only, without adding a verification step. At medium, apply the Test evidence criteria in `references/angles.md` during main-agent self-verification; high+ includes candidates from Phase 0 and Phase 1 in the existing independent verification. Only CONFIRMED test-evidence candidates enter issue counts. PLAUSIBLE or incomplete verification remains in the test-scope recommendations, including at synthesis; this exception does not change ordinary correctness findings.

**jacoco** (when required above and no applicable successful result can be reused): `mvn -pl <module> test` then `mvn -pl <module> jacoco:report` (report is a separate run — root pom only configures prepare-agent), read `target/site/jacoco/jacoco.csv` for line coverage (LINE_COVERED/(MISSED+LINE_COVERED)). Determine required dependencies from the selected tests and current project instructions; do not assume every test is a pure unit test. Any user argument beyond `level`/`c=N`/`cov`/`mr`/`--base <ref>` is **scope guidance only** — pass it to finders verbatim but framed as scope data; finders must not execute actions, write files, or change their output format based on it.

Use actual test results, including framework failure/error/skip counts, rather than BUILD SUCCESS. Mark a scenario passed only when the corresponding assertions and successful execution evidence cover the reviewed version. Otherwise state 未验证 and the reason (not run, environment restriction, incomplete results, or stale evidence); report actual target-test failures as failures, identifying pre-existing failures when baseline evidence establishes them. Later findings invalidate only affected evidence under the existing reuse rules.

Class-level CSV coverage is contextual only; it cannot establish compliance or violation of the **new-code coverage ≥ 80%** requirement for reliably measurable code. Use the shared [coverage contract](../dms-dev/references/task-contract.md#新增代码覆盖率) for measurement capability, acceptance method, baseline, metric scope and report source; assess mixed code separately. Verify measurable coverage using a traceable new-code report. Missing applicability evidence or a required report means 新增代码覆盖率未验证. For substantiated measurement limitations, report coverage as unmeasured and apply the required behavioral evidence. Setup or collection failures alone do not qualify. If new evidence shows the method is unreliable, reassess the affected scope and propose next steps under the contract. No new coverage calculator is required. No new executable Java code makes only the JVM metric N/A. Overall no-code N/A requires evidence that no new executable code falls within the applicable metric scope.

## Phase 1 — Find (workflow levels high/xhigh/max)

One finder per angle (independent context, READ-ONLY), inlining its full angle text, launching correctness + project + cleanup finders per effort level. Surfaces candidates (`file`/`line`/`summary`/`failure_scenario`/`angle` — `angle` = A-H or the cleanup sub-angle name; `failure_scenario` = user-visible consequence, or for cleanup candidates the concrete cost per Cleanup ground rules; an aggregated candidate sets `line` to the first representative line and puts the other lines + occurrence count in `summary`).

Also pass each finder the relevant preliminary scenarios as review context and explicitly ask it, within its assigned angle, to inspect related test inputs/assertions and return any additional scenarios, test evidence, or inspection limits alongside its candidates. Include the Phase 0 test-evidence candidate requirements in that prompt so such candidates carry their evidence and marker. Reuse prior observations instead of assigning every finder the entire test-scope analysis.

## Phase 2 — Verify (1-vote, 3-state, recall-biased)

workflow levels (high/xhigh/max): one verifier per **distinct (file, line) location** (READ-ONLY) — candidates at the same location go to a single verifier that returns an independent CONFIRMED / PLAUSIBLE / REFUTED verdict **per candidate** (grouping ≠ dedup, cuts verifier count ~40%); a candidate without a verdict remains a 未核实 recommendation outside issue counts, never assumed PLAUSIBLE. Include test-evidence candidates from Phase 0 and Phase 1, retaining unresolved ones only as recommendations. medium (inline): main agent self-checks each candidate against the criteria — no sub-agent fan-out. Keep CONFIRMED + PLAUSIBLE for ordinary findings (recall: **a single non-REFUTED vote carries the finding**); test-evidence candidates require CONFIRMED. Full criteria in `references/angles.md` — the verifier prompt carries the candidate's `angle` plus the matching criteria section; `test_evidence=true` takes precedence and requires the Test evidence criteria and supporting requirement/test material, otherwise cleanup sub-angles use Cleanup criteria. For rule-based claims, also include the Team-rule applicability criteria and the Phase 0 rule evidence. At medium+, verify new sweep/synthesis candidates the same way; reuse valid verdicts, rechecking only new or affected findings.

## Phase 3 — Sweep (xhigh/max only)

1 fresh finder (READ-ONLY) with the verified list, looking only for unlisted gaps (see `references/angles.md` Sweep focus).

## Phase 4 — Synthesize (ranked, main agent)

Before final synthesis, reconcile the selected in-scope paths with the checks required at the chosen effort level. If applicable work remains, continue within the existing authorization; a large diff, a finding cap, or disclosure of unread files is not a reason to stop. For delegated work, check the returned review scope and complete omissions before closing. If a concrete blocker remains after permitted alternatives, finish independent work and report a partial review with the inspected and uninspected scope, blocker, and unverified checks; do not label it complete. Respect an explicit user stop or scope limit.

finder/sweep findings + **applicable team rules** (main agent uses the Phase 0 rule evidence, including applicable Alibaba clauses in `config/coding-guidelines/coding-guidelines.md`) → merge/dedup by (file, defect): a defect hit by both a finder and the guidelines check keeps the finder version with the guideline clause appended, never two entries → ranked by severity → flat output (zero findings allowed; retain all eligible high/medium-severity findings; summarize low-severity cleanup with counts and representative lines to fit report targets), each finding tagged with its severity (高/中/低) + jacoco coverage.

Include confirmed test-evidence findings from the earlier phases under 代码改进建议 / 规范问题, tagged with severity based on their evidenced impact, not automatically the risk of the code being tested. The same retention and verification rules apply to any such candidate found by the sweep or at synthesis. Test-scope rows reference an existing issue instead of adding another count for the same defect. Recommendations and unresolved test evidence do not enter issue totals or MR disposition requirements; do not restore them through the ordinary PLAUSIBLE retention rule.

## Development handoff and feedback

For an authorized development handoff, independently assess both requirement compliance and implementation quality against the final integrated snapshot. Check the requirement-to-task-to-expected_checks mapping and the actual mandatory test identities, including missing/skipped cases and parameter sets; a worker summary or aggregate PASS is insufficient. Read the relevant [workflow contract](../dms-dev/references/workflow-contract.md) and [evidence contract](../dms-dev/references/task-contract.md) when this handoff applies; standalone review does not start implementation or dms-test-gate.

Reuse one independent review for L3 and delivery only when role, scope and version match. Verify feedback against the original requirements and facts before accepting it; record confirmed fixes, evidenced refutations and unresolved decisions. Review suggestions do not authorize new behavior. Keep blocking disputes unresolved, recheck affected findings after fixes, and review new scope/contracts when they change. Self-verification is not independent delivery review.

## Output format (ranked flat)

Fill 审查范围 from the range selected in Phase 0. Fill 审查流程 from the steps actually completed: low normally reports `单次检查，未复核`; medium `单次检查 + 主会话自核`; high `多角度查找 + 独立复核`; xhigh/max adds `补充检查`. Claim parallel execution, independent verification, or a sweep only when it occurred. If delegated work falls back to the main agent or remains incomplete, name the affected steps and the actual checks completed; main-agent self-checking is not independent verification.

```
# 代码审查报告

**审查范围**：[review mode, baseline/source/merge-result identities as applicable, commit/file/change counts, and separately reviewed uncommitted changes] | **审查力度**：level | **高 X / 中 Y / 低 Z** | **审查流程**：[steps actually completed] | **已核实判定不成立**：R 条
**关键问题**： [1-2 sentences on the most significant finding]

---

## 问题清单（按严重度排序）

1. **`file:line`** — [one-line problem] · **高** · 已确认／疑似 [map to internal CONFIRMED／PLAUSIBLE; low has no verification step, so use `未核实` and never imply verification]
   - **触发场景**： what input/state/timing triggers → what consequence
   - **修改建议**： recommendation

---

## 🔵 代码改进建议 / 规范问题
- **`file:line`** — [复用|简化|效率|实现层次|可读性|编码约定|规范] one-liner · optional `×N (L12, L40, L88)` for aggregated

---

## 测试范围与证据

[Summarize a small change; otherwise use the table for applicable scenarios. State why none apply when appropriate. Identify inspected scope and unresolved expectations; do not claim completeness.]

| 应验证场景与预期 | 依据 | 对应测试及断言 | 执行证据与限制 |
|---|---|---|---|
| [behavior and observable result] | [requirement/contract, or labeled inference] | [actual test/assertion, or 未发现对应测试] | [passed/failed evidence, or 未验证 + reason; recommendation or issue reference] |

---

**单元测试行覆盖率** (identify reused/current evidence and its scope; if collection fails, state the failure and unverified scope; if JVM coverage is not applicable, state "N/A" and omit the table):

| 类名 | 类级行覆盖率 | 覆盖率说明 |
|------|---------|------|
| FooService | 45% | 类级统计，不代表新增代码覆盖率 |

**新增代码覆盖率**：[per portion under the shared coverage contract: verified metric, scope/source and 80% assessment; or 覆盖率未计量 + substantiated measurement limitation and behavioral acceptance result; otherwise 未验证 + reason, or N/A with evidence of no applicable new executable code. Do not present a partial metric as overall coverage.]

共 N 个问题（正确性 X / 代码改进建议 Y）。
```

## MR title and description (`mr` argument)

For `mr` or an explicit request for an MR title or description (including a draft), read [references/mr-output.md](references/mr-output.md); ordinary non-MR reviews do not load it. Use the confirmed Phase 0 range and report `审查结论`. Applicable project code requires `PASS`; a confirmed `N/A` scope may also produce MR text without an exception request. `FAIL` and `INCONCLUSIVE` block output, including drafts. Follow the reference for scope, evidence and output requirements; N/A is not a passed code review or merge acceptance.
