# dms-review-changes · finder angle full text (high 7 finders / xhigh·max 10, cleanup merged into 1 finder, F splits F1/F2)

> On fan-out, each finder's prompt **inlines its full angle text** (not just the title). A-E + 6 cleanup are general review angles; F/G/H are this-repo project-specific angles. Cleanup ground rules live inside the Cleanup angles section; verify criteria + sweep focus below.

## Correctness angles

### Angle A — line-by-line diff scan

Read every hunk in the diff, line by line. Then read the enclosing function for each hunk — bugs in unchanged lines of a touched function are in scope (the PR re-exposes or fails to fix them). For every line ask: what input, state, timing, or platform makes this line wrong? Look for inverted/wrong conditions, off-by-one, null/undefined deref, missing await, falsy-zero checks, wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

### Angle B — removed-behavior auditor

For every line the diff DELETES or replaces, name the invariant or behavior it enforced, then search the new code for where that invariant is re-established. If you cannot find it, that is a candidate: a removed guard, a dropped error path, a narrowed validation, a deleted test that was covering a real case.

### Angle C — cross-file tracer

For each function the diff changes, find its callers (search for the symbol) and check whether the change breaks any call site: a new precondition, a changed return shape, a new exception, a timing/ordering dependency. Also check callees: does a parallel change in the same PR make a call unsafe?

### Angle D — language-pitfall specialist

Scan for the classic pitfalls of the diff language/framework — for example: JS falsy-zero, == coercion, closure-captured loop var; Python mutable default args, late-binding closures; Go nil-map write, range-var capture; SQL injection; timezone/DST drift; float equality. Flag any instance the diff introduces.

### Angle E — wrapper/proxy correctness

When the PR adds or modifies a type that wraps another (cache, proxy, decorator, adapter): check that every method routes to the wrapped instance and not back through a registry/session/global — e.g. a caching provider holding a delegate field that resolves IDs via session.get(...) instead of delegate.get(...) will re-enter the cache or recurse. Also check that the wrapper forwards all the methods the callers actually use.

### Angle F — project security

> xhigh/max split into 2 finders: **F1** = injection / access-control & auth / RCE & deserialization; **F2** = crypto & secrets / data exposure / config & deps. high runs a single finder over all 6 categories; medium checks them inline in the main agent; low does not run this angle.

For injection: SQL — user input reaching column-value `${}` concatenation; dynamic table/database/column names and ORDER BY/GROUP BY concatenation require tracing the input source, allowed identifiers or trusted metadata, validation, and rejection path before the SQL sink. Sharding or multi-database use does not itself exclude injection risk; a guard must reject disallowed input and actually terminate that path. Assess applicable mandatory SQL rules separately from exploitability; existing usage does not establish a rule exemption. Also check LIKE %xxx%, missing pagination, UPDATE/DELETE without WHERE; command/SpEL/OGNL injection (user input into Runtime.exec / SpEL parse / OGNL eval); path traversal (user input into file paths); XXE (XML parser with external entities enabled).

For access control & auth: tenant isolation — confirm tenant filtering in the actual SQL/filter for each query/update/delete touching data (a tenantId parameter on the signature is NOT enough), flag resource-ID direct-pass without ownership check (instanceId/orderId passed to queryById), flag batch ops that authenticate only login not per-ID; JWT — signature/expiry/algo verified (reject `alg: none`, pin algorithm); session regenerated on login (no fixation); vertical privilege checks (admin/role-gated ops — logged-in ≠ authorized).

For fail-open guards (injection + access-control): a whitelist / path-validator / permission check protects only if it is fail-closed — its rejection actually aborts the path before the sink. It is fail-open (NOT a guard), and the tainted value still reaches the sink, when the rejection is dropped by any mechanism — a throw swallowed by an outer catch that logs and continues (e.g. "validation failed … request will continue", observation/compat mode), a boolean the caller reads but does not abort on, a check that runs where it cannot block (async task nobody joins, annotation on a param the entry point does not `@Valid`), or the validator's own body catching its exception / returning early on a null-blank dependency. Read the caller's disposition of the rejection AND whether the body can reject this value at all — not just that a validator exists; ignore the code's self-labels (an "observation-mode" catch of a security check is still fail-open). Same rule as "a tenantId on the signature is not enough". When all hold, the swallow is the finding: anchor `line` at the drop point; put the validator, tainted parameter, sink, and the line where control resumes past the drop into `failure_scenario` as `file:line`. Do NOT flag rejections that actually abort (rethrow, caller returns on the error, narrower catch not covering the guard's exception); another fail-closed check exempts only if it blocks the same value.

For crypto & secrets: plaintext credentials in sensitive fields (passwords, tokens, keys — anything meant to stay private) assigned a literal (high-entropy string, real-secret shape, `host:port:user:pwd`); weak algorithms (MD5/SHA1 for passwords, DES/ECB); `Random`/`Math.random` for security tokens (use `SecureRandom`); TLS bypasses (trust-all `TrustManager`, disabled hostname verifier). Scan `application*.yml` / `*.properties` / `*.java`. **`ENC(...)` is jasypt-encrypted, not plaintext — never report it**; this repo wraps every profile's password/ak/sk that way, so an un-filtered plaintext scan is almost all false positives (see `references/review-pitfalls.md`).

For RCE & deserialization: unsafe Java `ObjectInputStream.readObject` on untrusted input; SpEL/eval/YAML deserialization of user-controlled content; unchecked reflection/class-loading from input.

For data exposure: secrets/PII returned in API responses (passwords hashed not echoed, sensitive fields masked); internal details/stack traces in error responses; debug/actuator endpoints exposed in prod without auth; credentials/secrets logged in plaintext.

For config & dependencies: CORS too permissive (`*` origin with credentials); known-vulnerable dependencies; Flyway `*.sql` lock risk (ADD COLUMN without default, ADD INDEX, MODIFY/DROP COLUMN on large tables), naming `V\d{12}__.+\.sql` + rollback (`-- rollback:` or `U__` file).

### Angle G — project concurrency (async ThreadLocal / lock / restart recovery)

For `CompletableFuture.supplyAsync`/`runAsync`/thread-pool: check executor passed (default commonPool affects global); loop-join head-of-line blocking; async task body depending on caller ThreadLocal (`@Transactional` transaction, MyBatis `SqlSession`, MDC traceId, `SecurityContext`) — new threads do not inherit these, causing transaction failure, SQL session error, log trace broken, auth context missing.

For `catch(Throwable)` in async tasks: check terminal state (EXCEPTION/FAILED) is written to DB — not just whether `future.complete()` is called (complete but no DB terminal state → task stuck ONGOING, drain/sweeper misjudge). Check heartbeat/executor_id/status-write started on ALL paths (including retry/exception branches) — a path missing heartbeat → long task killed by zombie sweeper short threshold.

For locks (`@DistributedLock`/`tryLock`/`RLock`/`synchronized`): read the Aspect/lock implementation, confirm acquire-failure strategy (throw vs fast-return) and lock granularity (key forgeable/bypassable). Check lease time vs worst-case scan duration.

For instance-field `Set`/`Map`/`Cache` (in-memory state): check what happens on app restart (key loss → duplicate DB records, idempotency failure, duplicate charge). Distinguish: `public static final` immutable config sets are NOT runtime state.

### Angle H — project Spring AOP / gray-release fail-closed

For `@ConditionalOnBean`/`@ConditionalOnMissingBean`: is the depended-on bean created by another `@AutoConfiguration`? Is there explicit `@AutoConfiguration(before/after)` or `@AutoConfigureOrder`? Without explicit ordering → auto-configuration classes load by FQN lexicographic order → depended-on bean may not exist yet → condition false → bean silently fails to assemble. Check: is there a guard test for assembly order?

For `@Aspect` pointcuts: does `@Around`/`@Pointcut` actually match the target method? Is the target call through Spring proxy — same-class internal `this.xxx()` self-invocation bypasses proxy, aspect fails; class must be Spring bean, method must not be final/private (CGLIB cannot proxy).

For constructor injection: A→B→A circular dependency (especially with `@Lazy`).

For gray-release fail-closed: `@CheckScheduleEnv` — does the env check fail-closed (empty/exception → non-active env never executes; default-env [prod] still executes)? `active_scheduling_env` empty/exception → fail-closed defaults to `DEFAULT_ENV` (prod): prod still executes, non-active envs (gray etc.) do not. Schedule lock prefix `schedule:lock` consistency.

For code-config precondition: check how newly added configuration behaves when absent. Optional settings need a reasonable default or explicit disabled behavior; missing required settings must produce a clear error. Do not flag a missing default alone or use an empty value to conceal missing configuration. When code Javadoc/annotation declares a config prerequisite (register=false, warmup-seconds, `@ConditionalOnProperty` flag), grep config files to confirm it is actually configured and value matches. Mismatch → feature silently fails, double-registration, warmup-period traffic.

**Anti-false-positive notes** (see `references/review-pitfalls.md`): this repo configures most infra (DataSource / interceptors / `SecurityFilterChain`) via java `@Bean`, not yml — grepping yml alone risks misreporting config-as-absent (e.g. DataSource judged unconfigured by missing yml `spring.datasource`, when it's actually a java `@Bean`). Caveat: `@Scheduled` TaskScheduler is the exception — dms-console main service does NOT customize it (only `@EnableScheduling`), so it runs Spring Boot default poolSize=1 (single-thread); do NOT assume multi-threaded. And `@ConditionalOnProperty` assembly scope must be checked across **each service's** yml — a generic switch (e.g. `discovery.enabled`) assembles the bean on unintended services (gateway).

## Cleanup angles

### Cleanup ground rules (all six sub-angles)

Candidates use the same `file`/`line`/`summary` shape; in `failure_scenario`, state the concrete cost (what is duplicated, wasted, harder to maintain, misleading to the reader, or which applicable mandatory team rule is broken) instead of a crash. When one defect recurs, report it once per file with an occurrence count and 2-3 representative lines; spanning 3+ files, report the 2 most-affected files and state the total file count — never one candidate per occurrence, and never more than 2 of the perAngle budget for one repeated defect. Judge by concrete cost, not taste: naming style, comment density, formatting, and the codebase's own unwritten idioms (logic-delete `deleted=0/1`) are not findings — a documented, applicable mandatory team rule is the Conventions sub-angle's job and can support a finding with the rule evidence described below. Resolvable identifiers are not findings: resolvable in a stable public registry (CVE/RFC numbers, HTTP/SQL error codes) or in a tracked file that **defines** them (Flyway migration filenames; a doc that merely also uses the token explains nothing); a tracker/ticket ID stays only when supplementary — strike it and the sentence still reads — while a token that is the only carrier of meaning is a finding however ticket-shaped it looks. Summarize low-severity cleanup when needed; do not cut retained high/medium findings.

### Reuse

Flag new code that re-implements something the codebase already has — search shared/utility modules and files adjacent to the change, and name the existing helper to call instead.

### Simplification

Flag unnecessary complexity the diff adds: redundant or derivable state, copy-paste with slight variation, deep nesting, dead code left behind. Name the simpler form that does the same job.

### Efficiency

Flag wasted work the diff introduces: redundant computation or repeated I/O, independent operations run sequentially, blocking work added to startup or hot paths. For unnecessary retention by long-lived objects or captured environments, trace the actual references and lifetimes; a closure alone does not prove a leak. Name the cheaper alternative and the behavior and resource constraints it must preserve.

### Altitude

Check whether the change fixes the underlying cause at the right boundary. Prefer the smallest adequate fix, reusing an affected shared path; a special case alone does not justify a new abstraction.

### Readability

Three independent tests, one per paragraph below. Judge by reading the code, not by matching term lists; when unsure whether you understand a token from this repo's text or from your own prior knowledge, report it — verify refutes a resolvable token in one cheap step, but nothing downstream recovers a silent pass. Scope: names, string keys (`@Value`/config), javadoc, and comments this diff introduces or makes stale; untouched code and commit messages are out of scope.

For unresolvable references: a token that must bind to a definition (a config key, symbol, case ID, ticket) yet has only reference-hits — uses are not explanations: an `@Value` key nothing defines, `DAS_L0_1_`, `BDA-ZOMBIE-`, `（P0）`, review jargon (「按评审意见调整」). A token that merely names a thing (product, external system, domain noun — DCP, DTS) stays, evidenced by uses in files this diff did not touch, never by repetition inside the diff. If you understand a token only from having read a library's or this project's source and public docs do not define it, treat it as unresolvable. The defect is the opaque token, never the underscores or casing around it (naming style is Phase 4's guidelines check). Also the reverse: the diff deletes the only tracked explanation while surviving javadoc/comments still reference it; surviving code referencing a deleted symbol is Angle C's.

For name/behavior mismatch: a read-verb name (`query*` / `get*` / `list*` / `find*` / `check*` / `validate*` / `is*`) whose body writes state the caller did not hand it (persist, delete, mutate a field/cache/static), or a flag meaning the opposite of its name. Filling in an object passed as a parameter is an out-param idiom, not a mismatch. Read the body — provable, not taste. If callers trusting the name would corrupt data (hidden side effect, wrong limit), file it under Angle A/C as correctness, not here.

For misleading comments: comments this diff makes wrong — stale contracts, counts/limits contradicting the code, javadoc copy-pasted from another method, two files in this diff asserting opposite contracts about the same mechanism — judged only against code in this diff or its file. Config-prerequisite comments are Angle H's (it carries the `review-pitfalls.md` config notes this finder does not); never conclude a comment is wrong from a yml grep.

Name what the reader would wrongly conclude — or, for an unresolvable token, what they cannot determine without asking the author.

### Conventions (applicable team rules)

Follow currently effective instructions, including applicable `AGENTS.md` files, while assessing team violations from the main agent's Phase 0 rule evidence. The entrypoints are `config/coding-guidelines/coding-guidelines.md`, `docs/code-quality/研发流程必做项.md`, and team requirements explicitly specified by the user for this task; inspect related rule files as needed. Neither presence in Git nor an unshared personal preference makes a rule mandatory. Check the exact clause's authority (mandatory/recommended/reference), reviewed paths, task stage, and activation conditions. Plans and pilot targets do not establish an active enforcement rule.

Only flag a team-rule violation when you can name its source, quote the applicable mandatory clause, establish its applicability, and cite the exact code line that breaks it. Recommended/reference guidance may support a labeled suggestion, not a mandatory violation. Unclear authority or applicability stays 未核实 / 待确认 and does not enter issue counts or MR disposition requirements; continue independent analysis. If no applicable mandatory clause supports a violation, return no violation for this angle.

## Verify criteria

Dispatch: `test_evidence=true` → Test evidence criteria first, regardless of the originating angle; otherwise a candidate whose `angle` is one of the six cleanup sub-angles → Cleanup criteria; all others → Standard criteria (medium) or Recall-bias criteria (high+). Apply Team-rule applicability as well for claims of a rule violation. This dispatch and its retention rule win over any other conflicting clause below. Identify test-evidence candidates by their claim (a missing required test or defective test evidence), not just the marker; a missing marker must not route such a claim through ordinary recall-biased retention.

### Test evidence criteria

These criteria assess a test obligation or the evidence a test supplies, not whether the implementation necessarily has a runtime bug. Pass the relevant requirement, applicability, inspected tests, and inputs/assertions with the candidate. For a missing test, the business behavior alone is not an explicit obligation to add a unit test: establish the applicable testing requirement and review stage. For an assertion defect, compare the claimed target/contract with what the actual inputs/assertions establish; a name alone is insufficient.

- **CONFIRMED** — the testing requirement applies to this change and stage and the inspected evidence establishes its violation, or concrete inputs/assertions establish a defect in the claimed test evidence. Quote the supporting requirement or contract and the inspected code/test evidence. Do not require an implementation crash to confirm a testing-rule violation.
- **REFUTED** — evidence establishes that the obligation is inapplicable, or the inspected tests/assertions already provide the required evidence. Cite that evidence; names and aggregate coverage alone do not refute a gap.
- **PLAUSIBLE** — applicability, the expected behavior, or inspected material is insufficient to decide. State what remains unknown; absence of a matching filename is not confirmation.

Only CONFIRMED enters issue counts after main-agent verification at medium or independent verification at high+. At low, report these candidates only as recommendations without adding verification. PLAUSIBLE and incomplete verification remain recommendations/questions, not counted findings; REFUTED is excluded. Apply this rule through synthesis and MR summaries. Ordinary implementation correctness findings retain their existing criteria.

### Team-rule applicability (all angles)

For any claim of a rule violation, including a testing obligation, use the supplied source, quoted clause, authority, task stage, and applicability evidence. CONFIRMED requires an applicable mandatory clause and the exact violating code/test location; cite both. A recommendation or reference alone is not a mandatory violation. If authority or applicability is unresolved, keep the claim as 未核实 / 待确认 outside issue counts and MR disposition requirements, even if the general cleanup or recall-biased criteria would retain PLAUSIBLE. This does not block independent review or change the criteria for a separately evidenced implementation or test-assertion defect.

### Standard criteria

- **CONFIRMED** — can name the inputs/state that trigger it and the wrong output or crash. Quote the line.
- **PLAUSIBLE** — mechanism is real, trigger is uncertain (timing, env, config). State what would confirm it.
- **REFUTED** — factually wrong (code does not say that) or guarded elsewhere; quote the line that proves it. A guard refutes only if it is fail-closed: its rejection aborts the path before the flagged line — quote where it aborts (an uncaught throw aborts: quote the call line and state no enclosing frame catches that type). The validator's internal throw/false proves nothing on its own, and any refutation leaning on a validator/whitelist/permission check is judged by this test however it is phrased ("factually wrong" / "provably impossible" do not exempt it). If the rejection is instead dropped before the sink — swallowed by a logging catch, read but not acted on, run where it cannot block, or caught inside the validator — it is fail-open: grade the candidate CONFIRMED or PLAUSIBLE as normal and name the drop. To declare fail-open you must quote that drop point; mere doubt does not defeat a fail-closed abort that is quoted. Disposition not locatable → PLAUSIBLE, not REFUTED.

Keep CONFIRMED + PLAUSIBLE, drop REFUTED.

### Cleanup criteria (all six cleanup sub-angles)

Cleanup candidates need evidence of cost, not a crash. CONFIRMED: cite a compatible existing helper (Reuse), a simpler form that preserves behavior (Simplification), wasted work or unnecessary retention (Efficiency), a misplaced fix and the smallest adequate correction (Altitude), a misleading/unresolvable identifier or comment (Readability), or an applicable mandatory rule and violating line (Conventions). PLAUSIBLE: there is a concrete basis, but relevant facts, compatibility or benefit remain uncertain. REFUTED: evidence disproves the cost, shows it already handled/resolvable, or establishes a mere preference. Recommendations must preserve required behavior and stay within scope. For an aggregated candidate (occurrence count in `summary`), judge per representative line: any line standing → CONFIRMED, with refuted lines removed and the count adjusted; REFUTED only when every representative line falls.

### Recall-bias criteria

**PLAUSIBLE by default** — do not refute a candidate for being "speculative" or "depends on runtime state" when the state is realistic: concurrency races, nil/undefined on a rare-but-reachable path (error handler, cold cache, missing optional field), falsy-zero treated as missing, off-by-one on a boundary the code does not exclude, retry storms / partial failures, regex/allowlist that lost an anchor. These are PLAUSIBLE.

**REFUTED** only when constructible from the code: factually wrong (quote the actual line); provably impossible (type/constant/invariant — show it); already handled in this diff (cite the guard AND the line where its rejection aborts the path; a rejection dropped before the sink — swallowed by a logging catch, read but not acted on, run where it cannot block, or caught inside the validator — is fail-open and does not count, even when phrased as "factually wrong" or "provably impossible"; abort line not locatable → PLAUSIBLE); or pure style with no observable effect.

Keep CONFIRMED + PLAUSIBLE; a single non-REFUTED vote carries the finding (recall mode, don't drop on uncertainty).

## Sweep focus

moved/extracted code that dropped a guard or anchor; second-tier footguns (dataclass default evaluated once, `hash()` non-determinism, lock-scope shrink, predicate methods with side effects); setup/teardown asymmetry in tests; config defaults flipped. An aggregated cleanup entry in the verified list covers every occurrence of that defect in that file — do not re-report its other occurrences.
