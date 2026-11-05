## MR title and description (`mr` argument)

For `mr` or an explicit request for an MR title or description, first include **审查结论** in the reply. Use the confirmed MR range from Phase 0. **Applicable project code requires `PASS`; a confirmed `N/A` scope may also produce MR text. `FAIL` and `INCONCLUSIVE` block output, including drafts.**

Assign `PASS` only when all of the following hold for that MR snapshot:

- All selected in-scope paths and checks required at the chosen effort level are complete, including any required independent verification.
- Applicable mandatory checks, including required test and coverage checks, have successful evidence valid for the reviewed snapshot. Reuse valid evidence under the existing rules; zero findings or a completed review alone does not establish this condition. Evidence collection remains subject to the existing execution authorization.
- Every finding is fixed and rechecked, or has one of the three allowed final dispositions under the review-record rules below, supported by the required decisions and evidence. A proposed disposition is still pending; a disposition cannot waive a failed or unverified mandatory check.

Use `FAIL` for actual mandatory-check failures or unresolved findings requiring correction; use `INCONCLUSIVE` when review scope, required evidence, or a disposition remains incomplete or undecided. If both apply, report `FAIL` and retain the evidence gaps. Use `N/A` only for the Scope not-applicable outcome; it is not `PASS`.

Confirm N/A from the entire selected MR change set, including branch commits and any explicitly selected staged/worktree candidate. Incomplete or unclear scope is `INCONCLUSIVE`. Mixed changes require `PASS` for their applicable code; a documentation majority or file extension does not establish N/A.

For confirmed `N/A`, generate the title and description without another exception request. State why code review is not applicable outside the MR text; omit finding-count and coverage summaries rather than inventing zeros or a passed review. Before commit, identify the selected candidate as uncommitted. The text does not establish merge acceptance or waive other applicable checks.

For `FAIL` or `INCONCLUSIVE`, output only the review report and the blocking findings, pending decisions, or missing evidence. **Do not output an MR title, description, draft, or ready-to-paste template.** For decisions requiring a Reviewer, identify the pending items and the `待决定` record required by section 3 of `审查记录规范.md`; that transitional status does not satisfy this gate.

Bind `PASS` to the pre-merge target, source commit, reviewed merge result, and applicable evidence. Relevant changes require reassessing affected checks and a new conclusion; reuse evidence where implementation, tests and dependencies remain equivalent. Local uncommitted fixes do not resolve findings in the reviewed snapshot.

After `PASS` or confirmed `N/A`, append the MR title and description below. Only `PASS` carries finding counts from the latest applicable review; omit that summary for N/A. The three description elements follow `docs/code-quality/研发流程必做项.md`:

```markdown
<Title: 类型(模块): 描述 — use the commit-message format for the whole branch. For multiple commits, capture the main change; do not concatenate individual commit titles>

<Summary for PASS only: take the 高/中/低 counts from the report header; for N/A omit this line. Omit 审查结论, 审查力度, 审查范围, 审查流程, and 已核实判定不成立 from the MR>

**变更内容**：<Group by module, not by individual file>

**变更原因**：<Infer from the diff and commit messages>

**影响范围**：<Change size, whether business code is included, build/deployment/runtime impact, and database changes>
```

- If **变更原因** cannot be inferred, leave `<待补充>` and do not invent a reason. Do not interrupt the review to ask; the review runs as a batch.
- Follow the wording standards in `dms-commit-msg`: use terms a colleague taking over can locate in the repository, and avoid wording whose meaning is known only to the author.
- For findings deliberately left unchanged in this change, or verified as refuted, append a comment section after the description. Use `MR 评论（审查记录）` as the output section heading and `## 审查记录` as the comment body's heading. Follow `docs/code-quality/审查记录规范.md` for the format and criteria: issue + location + reason for the disposition + decision-maker (leave blank). Choose one of `判定不成立`, `待后续处理` (requires a task ID and owner), or `确认不处理`.
- Include only findings with a decision to leave them unchanged in this change. Being unfixed at review time does not itself establish that decision: keep those findings in the issue list, and put only decided non-fixes in the comment section.
- Put this section in MR comments only, not in the MR description. If a completed applicable code review has no such findings, omit the comment body and state `MR 评论（审查记录）：无，本次没有需要单独记录的判定或处置项。` in the reply, outside the MR title, description, and comment body. For N/A, use the Scope not-applicable reply instead, without a comment body.
