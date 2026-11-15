# 功能档案管理

<!-- feature-id: manage-feature-docs -->
<!-- feature-title: 功能档案管理 -->
<!-- feature-aliases: 功能技术档案, Feature Docs -->
<!-- feature-status: active -->
<!-- feature-summary: 以仓库证据创建、查找、核验和维护稳定功能的技术档案。 -->
<!-- last-verified: 2026-11-15 -->
<!-- code-basis: impl-v2 sha256:4e62b7660c1d9a0a997c92869e7fdbf67913e09db2cf16ca839ecf7fb45f00e9 -->

## 快速上下文

`manage-feature-docs` 通过 Skill 指令和本地 Python 工具维护每个稳定功能的一份技术档案，为跨会话恢复上下文提供入口。代码、配置、模型和测试仍是实现事实的依据；结构校验通过不能证明档案内容真实。

入口是 `manage-feature-docs/SKILL.md`，用户显式调用后按请求选择读取、归档更新或审计；实质研发工作转交 `manage-dev-work`，完成验证后再归档。档案和目录分别位于 `docs/features/<feature-id>.md` 与 `docs/features/index.md`。

## 目标与边界

### 目标

- 以可核验的当前实现建立稳定功能的持久技术上下文。
- 支持查找、初始化、增量维护及结构和实现快照核验。

### 范围内

- 从代码、配置、测试和需求证据恢复上下文，识别漂移、约束和未解决问题。
- 维护档案元数据、固定章节、功能索引、决策与简洁变更记录。
- 在旧档案已有用户回归准备章节时按旧契约核验；当前交接信息属于 Work Item。

### 范围外

- 代替需求决策、实现功能、执行部署或证明业务行为正确。
- 为同一稳定功能的修复或迭代新建任务级档案。
- 自动认证使用者、进行外部服务同步或作为不可抵赖审计系统。

### 不变量

- 一个稳定功能对应一个档案；跨功能变化分别维护受影响档案。
- 未解决的阻塞性业务或技术选择须先调查并向用户澄清；仅用户明确同意延期的非阻塞事项可记录为待确认。
- 不覆盖已有档案；写入内容以完成的实现及验证证据为准，并同步元数据与索引。

## 业务行为

- 支持前后端功能上下文；适用时在既有章节记录界面入口、交互状态、响应式与可访问性证据。档案维护按 `manage-feature-docs/references/diagram-routing.md` 有条件调用 `archify`；涉及未提交源码的证据图延期。

- `manage-feature-docs/agents/openai.yaml` 设置 `allow_implicit_invocation: false`，Skill 面向显式调用。
- 首选用户指定仓库，否则使用当前 Git 根目录；按 ID、标题、别名和正文检索并读取可能匹配项。
- 只读请求不修改文件；审计对照实现识别漂移，只有用户要求修复时才修改；已完成工作可归档或更新。
- Skill 指令要求遇到影响行为、接口、数据、安全或验收的多种合理解释时，先提出选项并等待明确决定；该门禁由执行者落实，不由 CLI 自动判断。
- 用户回归的服务操作和临时发布事实放在关联 Work Item；新档案不增加旧版 `用户回归准备` 章节。

## 架构与代码地图

- `manage-feature-docs/SKILL.md`：操作选择、澄清门禁、证据采集与交接流程。
- `manage-feature-docs/assets/feature-doc-template.md` 和 `references/document-contract.md`：固定章节、元数据与记录契约；`references/audit-policy.md` 规定新鲜度和语义审计边界。
- `manage-feature-docs/scripts/feature_docs.py`：档案发现、模板初始化、索引重建、结构及 Git 快照校验。
- `manage-feature-docs/scripts/package_skill.py`：生成技能 ZIP，按允许的顶层目录筛选文件并排除符号链接、缓存及本地元数据。
- `manage-dev-work/scripts/dev_work.py` 的 `canonical_feature_validation_errors`：关闭关联 Work Item 时调用本 Skill 的 `validate-contract`。
- `manage-feature-docs/tests/` 与 `evals/scenarios.md`：自动化测试和代表性行为评测场景。

## API、事件与任务

### 档案 CLI

- `python3 manage-feature-docs/scripts/feature_docs.py init --repo <目录> --id <ID> --title <标题> [--aliases <别名> ...]`：独占创建模板并更新索引，输出两个路径；拒绝非法 ID、危险元数据、重复 ID 或已存在目标。模板初始含占位符，必须人工补全。
- `find --repo <目录> [--query <查询>]`：按 ID、标题、别名和正文的匹配分数排序，输出制表符分隔的分数、元数据和路径；无匹配返回非零状态。
- `validate --repo <目录> [--id <ID>] [--mode structural|fresh]`：检查目标档案或全部档案，并检查重复 ID、索引与本地链接；`fresh` 额外对照 Git 基线。
- `validate-contract --repo <目录> --id <ID> [--mode structural|fresh]`：检查指定档案契约及可选快照，不检查目录或索引完整性；被 `manage-dev-work` 调用。
- `snapshot --repo <目录>` 输出 v2 实现摘要；`sync-index --repo <目录>` 根据现有档案元数据重建索引托管块，保留块外内容。成功输出路径，校验成功输出 `OK`；错误输出至标准错误并返回非零状态。

### 技能打包 CLI

- `python3 manage-feature-docs/scripts/package_skill.py --skill-dir <目录> --output <ZIP路径>`：要求技能目录包含 `SKILL.md`，输出位置必须在技能目录外；ZIP 以技能目录名为顶层目录。调用者负责选择输出路径。
- 不涉及 HTTP API、事件、消费者或后台任务；以上为本地命令接口。

## 数据模型与迁移

- 每份 Markdown 标题后连续保存 `feature-id`、`feature-title`、`feature-aliases`、`feature-status`、`feature-summary`、`last-verified`、`code-basis`；状态为 `planned`、`active`、`deprecated` 或 `retired`。
- `feature-id` 为小写 kebab-case，须与文件名一致；索引托管块由全部档案的元数据生成。章节、决策、已知问题与历史记录形状见 `references/document-contract.md`。
- 新基线为 `impl-v2 sha256:<digest>`，覆盖实际实现路径、内容、类型和执行模式；structural 兼容旧 HEAD 格式和非 Git 标记，fresh 拒绝旧格式与非 Git 工作区。稀疏检出、skip-worktree、稀疏索引和子模块 assume-unchanged 拒绝生成可信快照；空目录、忽略的未跟踪文件与外部运行产物不在快照范围。
- 无数据库、数据库索引或迁移；触及旧档案时按当前契约规范化并保留有效历史。

## 核心流程

1. 确定仓库，运行 `find` 并阅读可能相关的档案；有多个合理功能归属时先澄清。
2. 对照当前代码、配置、测试、Git 状态及需求证据，区分已确认、疑似漂移和未知；阻塞性选择在写入前解决。
3. 使用 `init` 创建或更新已有档案，替换占位符，按当前实现维护章节、决策、问题和简洁历史。
4. 同步索引；运行 structural 和需要当前实现证据时的 fresh 校验，并人工核查内容语义。
5. 实质研发任务的发布与回归交接写入 Work Item；结束时报告证据、验证结果及剩余限制。

## 异常与边界条件

- 目标文件或 ID 已存在 — `init` 拒绝覆盖 — 检查并维护已有档案。
- 索引标记不匹配或重复 — 初始化或同步失败 — 修复标记后重试；初始化在索引写入异常时删除新建档案。
- 元数据、章节、日期、占位符或本地链接不合约 — 校验报错 — 修正文档或索引后重试。
- 实际实现内容改变 — fresh 报告基线不匹配 — 重新对照实现并记录新基线。
- 非 Git 工作区 — structural 支持 `no-git; working-tree=unknown`，fresh 失败 — 不能声称已建立 Git 实现快照。
- 非唯一或不明确的功能归属 — Skill 要求用户澄清 — CLI 的查找排序不能代替归属判断。

## 并发与幂等

- `init` 使用独占创建并检查已有 ID，重复初始化不会覆盖目标；索引和普通文本更新使用临时文件及 `os.replace` 做单文件原子替换。
- 档案与索引不是跨文件事务，且没有进程锁；并发初始化或索引重建可能竞争，进程中断也可能造成索引暂时不一致，可检查后运行 `sync-index` 恢复。
- `implementation_snapshot.py` 对有效实现路径、类型、模式和内容计算摘要，排除 `docs/features/`、`docs/work-items/` 和 `docs/superpowers/`；该快照不构成分布式幂等保证。

## 安全与权限

- 文件系统和 Git 操作以当前用户权限执行；无应用层认证、授权或租户隔离。Skill 要求避免将配置、凭据、环境文件和日志中的秘密写入档案。
- 初始化拒绝空白标题并规范化首尾空白，限制 ID 与元数据中的换行、管道符和注释结束符；本地 Markdown 链接检查屏蔽 fenced 和匹配的行内代码，拒绝解析到仓库外的目标；核验日期严格使用 `YYYY-MM-DD`。正文没有通用机密扫描或 HTML 清洗。
- 打包排除符号链接及本地元数据；档案本身受仓库访问权限保护，没有签名或防篡改审计。

## 配置与依赖

- CLI 与打包脚本使用 Python 标准库；Git 快照功能依赖 Git CLI，模板路径由脚本位置确定。
- 默认位置和结构由 `SKILL.md`、`assets/feature-doc-template.md` 与 `references/document-contract.md` 定义；无服务配置、数据库、消息队列、缓存或外部网络依赖。
- Work Item 关闭时默认使用同级 Feature Docs 校验脚本，也可通过 `--feature-validator` 指定；Git 仓库使用 fresh，非 Git 使用 structural。

## 可观测性与运维

- 命令通过标准输出返回路径、匹配结果或 `OK`，校验和执行错误写入标准错误；排障可检查档案、索引、Git 状态及 CLI 错误。
- 无常驻服务、指标、追踪、告警或健康检查。档案维护不要求服务部署、重启、数据库迁移、缓存清理或消息消费者操作。
- 结构和 fresh 校验是确定性检查，无法证明符号含义、架构描述或不适用判断正确；须对照源码和测试进行语义审计。

## 测试与验证

### 已执行

- 本轮 `manage-feature-docs` 72 项、`manage-dev-work` 70 项及跨 Skill 2 项测试通过；Feature Docs 在 Python 3.8 和 3.14 均通过。
- 隔离 Git 仓库中的双 Skill CLI 完整关闭流程及独立 CRLF 状态链检查通过；Skill 格式校验通过。

### 未执行

- `manage-feature-docs/evals/scenarios.md` 中的模型行为评测 — 本次未运行评测执行器；自动化单元测试不能证明模型始终遵守 Skill 指令。
- 多进程并发写入和多版本 Python/Git 矩阵 — 本次未执行；并发竞争及环境兼容性仍受现有测试范围限制。

## 关键决策

### 按稳定功能维护当前状态

- **决定**：每个稳定功能维护一份档案，任务过程及临时回归交接由 Work Item 承载。
- **原因**：使档案可用于恢复长期上下文，同时避免历史任务堆积掩盖当前实现。
- **取舍**：跨功能改动需要分别核对各档案；临时交接需查看关联 Work Item。
- **证据**：`manage-feature-docs/SKILL.md`、`references/document-contract.md`。

### 以共享契约和 Git 基线校验归档

- **决定**：CLI 提供结构及 fresh 校验，Work Item 通过 `validate-contract` 复用档案校验。
- **原因**：统一文档格式，并检查归档是否对应当前有效实现内容。
- **取舍**：Git 快照不能替代语义审计；非 Git 工作区不能通过 fresh。
- **证据**：`feature_docs.py` 的 `fresh_git_errors`、`command_validate_contract`，以及 `dev_work.py` 的 `canonical_feature_validation_errors`。

## 已知问题与后续工作

### 并发更新缺少跨文件事务

- **影响**：多个进程同时写入时，档案与索引可能不一致或丢失索引更新。
- **当前处理**：目标独占创建，索引用单文件原子替换；可检查档案后重新同步索引。
- **后续动作**：出现并发写入需求时，再明确锁或事务策略并验证竞争场景。

### 校验不证明语义与执行者行为

- **影响**：结构有效、基线新鲜的档案仍可能包含错误解释；CLI 不能落实澄清门禁或验证实际部署。
- **当前处理**：Skill 要求对照实现和测试核验，行为评测场景单独维护。
- **后续动作**：维护档案时继续执行语义审计；如需证明模型行为，另行运行行为评测并记录结果。

## 变更记录

### 2026-11-15 — 修复权限与 Markdown 边界

- **状态**：已完成
- **变化**：保留现有文件 POSIX mode，保护 fenced 示例与换行，并收紧标题、日期及行内代码链接检查。
- **原因**：防止权限意外收窄、示例被误改和无效输入误判。
- **兼容性**：不改变 CLI、状态机或快照协议；ACL、所有者和扩展属性不作保留保证。
- **验证**：72、70、2 项测试，Python 3.8/3.14 Feature Docs 测试、独立 CRLF 状态链及 Git 关闭流程通过。

### 2026-11-15 — 修复阶段门与稀疏快照

- **状态**：已完成
- **变化**：拆分实施与验证计划门；拒绝稀疏检出与子模块隐藏状态；转义 Feature 索引。
- **原因**：修正流程时序和快照漏检，避免不安全的目录输出。
- **兼容性**：完整检出保留 v2 算法；稀疏检出须改用完整工作树。
- **验证**：两个 Skill 65、63 项和仓库级 2 项测试通过；干净 ZIP 解包测试与 Git 关闭流程通过。

### 2026-11-15 — 修复快照与验证证据

- **状态**：已完成
- **变化**：使用 v2 有效实现快照、验证证据绑定及显式迁移，修复 CLI 输入和索引故障恢复。
- **原因**：避免管理文档提交误报与过期 PASS 证据放行。
- **兼容性**：旧 HEAD 基线仍可结构读取；Git fresh 与交付要求重新核验并使用 v2。
- **验证**：两个 Skill 分别 58、63 项测试，跨 Skill 2 项测试及独立审查通过；模型端到端评测未运行。

### 2026-11-15 — 接入研发专项技能路由

- **状态**：已完成
- **变化**：接入条件式专项路由，扩展前后端档案记录指引。
- **原因**：提高研发与功能知识维护效率。
- **兼容性**：保留 CLI、固定章节与快照算法；专项技能按需发现。
- **验证**：两个 Skill 测试 45 项和 49 项、跨 Skill 测试 1 项通过；路由进行了静态独立复核。

### 2026-11-15 — 创建功能档案管理档案

- **状态**：已完成
- **变化**：记录 Skill 流程、CLI 契约、数据格式、集成和限制，并登记功能索引。
- **原因**：为功能档案管理能力建立可跨会话恢复的技术上下文。
- **兼容性**：仅新增档案并更新索引，不改变 Skill、CLI 或运行时服务。
- **验证**：审阅 Skill、模板、参考政策、脚本和测试；相关 45 项、49 项及跨 Skill 1 项测试通过。
