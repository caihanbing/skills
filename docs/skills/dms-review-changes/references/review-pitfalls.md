# dms-review-changes · anti-false-positive notes

> Used with `angles.md`. Records under-reporting/over-reporting lessons from this repo — when reviewing config classes / Spring assembly, verify per these, don't conclude from a single grep. All notes are historical real misreports; the verification steps are now mandatory. For general Alibaba/project guidelines see **repo root** `config/coding-guidelines/`.

## Config review: check both yml AND java @Configuration (don't grep yml only)

**Rule**: when reviewing config-class issues (thread pool / TaskScheduler / Executor / DataSource / WebMvcConfigurer / interceptor / HealthIndicator etc.), you MUST check both `application*.yml` AND java `@Configuration` `@Bean` definitions — never conclude from yml grep alone.

**Basis**: Spring Boot configures most infra via java `@Bean`, not yml:
- DataSource / pool → `@Bean DataSource` (multi-DS `DataSourceConfigIntensive` / `DataSourceConfigConsole`), NOT yml `spring.datasource`
- WebMvcConfigurer / interceptors / SecurityFilterChain → java config, not yml
- health components → `@Bean HealthIndicator`

**How to apply**:
- Investigating thread-pool / scheduler / datasource / interceptor / security-chain config: after grepping yml, MUST also grep java `@Configuration` relevant @Beans (`ThreadPoolTaskScheduler` / `TaskExecutor` / `DataSource` / `WebMvcConfigurer` / `SecurityFilterChain`)
- `@Scheduled` TaskScheduler: find a @Bean named `taskScheduler` (`ScheduledAnnotationBeanPostProcessor` auto-selects it)
- "yml not configured" ≠ "not configured" — java config may have; conversely "yml configured" also verify no java config override

## @Conditional assembly scope: condition isn't just enabled, also service dimension

**Rule**: `@AutoConfiguration` / `@ConditionalOnProperty` assembly scope — verify the condition distinguishes services (gateway vs business service), don't assume "only assembles in my service".

**Basis**: lossless-deploy `@AutoConfiguration` was initially only `@ConditionalOnProperty(discovery.enabled=true)`, but gateway also has `discovery.enabled=true` → gateway mis-assembled lossless listener (readiness red / deregister). Later added `@ConditionalOnProperty(dms.lossless-deploy.enabled=true)` with a dedicated switch to isolate; gateway doesn't configure that switch → not assembled.

**How to apply**:
- writing `@AutoConfiguration` for a specific service, use a **dedicated switch** (e.g. `dms.xxx.enabled`) not a generic one (`discovery.enabled`), to avoid unrelated services mis-assembling
- reviewing `@ConditionalOnProperty`, verify the condition value distribution across **each service's** yml (grep all `application*.yml`), confirm only target service configures it
- shared infra (dms-base etc.) autoconfig especially — it's loaded by all dependent services

## Secret review: ENC(...) is encrypted, not plaintext — don't false-report

**Rule**: jasypt `ENC(...)` wrapped values are encrypted, not plaintext secrets.

**Basis**: this repo's all profiles' password/ak/sk use ENC encryption (application.yml/dev/staging/local/test-neimeng all ENC); Angle F's plaintext-secret scan will heavily hit ENC.

**How to apply**: `password: ENC(...)` skip (encrypted); only unwrapped plaintext literals (e.g. `password: changeme`, `password: HZzH+SGXZ2bp`) should be flagged as plaintext-secret findings.
