# 研发过程管理

<!-- feature-id: manage-dev-work -->
<!-- feature-title: 研发过程管理 -->
<!-- feature-aliases: 研发流程管理, development work management -->
<!-- feature-status: active -->
<!-- feature-summary: 面向仓库本地研发工作的 Work Item 生命周期、质量门禁与 Feature Docs Closeout。 -->
<!-- last-verified: 2026-09-14 -->
<!-- code-basis: HEAD 154afc22215f; worktree-digest sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 -->

## 快速上下文

`manage-dev-work` 将一次短生命周期研发工作建模为仓库本地 Markdown Work Item，并通过 CLI 对需求、决策、风险、实现、验证、审查、发布和用户回归进行阶段门禁。主要入口是 `manage-dev-work/SKILL.md` 与 `manage-dev-work/scripts/dev_work.py`；数据写入 `docs/work-items/WORK-YYYYMMDD-NNN.md`，并由 `docs/work-items/index.md` 提供目录。

当前实现是 repository-local 的主动 Skill，依赖 Python 标准库和 Git CLI，不连接运行时服务、数据库或外部工单系统。最重要的约束是 `handoff-ready` 不等于 `closed`：进入 `verifying` 时记录实现快照，交付和关闭时必须仍匹配；存在关联 Feature ID 时，关闭还要调用 `manage-feature-docs` 的 canonical `validate-contract`。

## 目标与边界

### 目标

- 为一次研发工作提供可恢复、可审计的短期状态记录。
- 在进入计划、实现、验证、交付和关闭前，阻止缺少需求、证据、风险处理或回归信息的 Work Item 前进。
- 将已完成工作的持久化知识交接到稳定 Feature Doc，而不是把 Work Item 变成第二份功能档案。
- 用 Git 实现验证快照的新鲜度检查，使验证结论对应明确的实现状态。

### 范围内

- 创建、查询、结构校验、阶段迁移和关闭 `docs/work-items` 下的 Work Item。
- 管理 `intake`、`clarified`、`planned`、`implementing`、`verifying`、`handoff-ready`、`closed` 及异常状态的迁移关系。
- 校验 `REQ-*`、`DEC-*`、`RSK-*`、`VER-*`、`REV-*` 记录、变更影响 14 个维度、风险等级和用户回归交接字段。
- 在 `verifying` 保存 `verification-basis`，在交付/关闭前检查实现工作区指纹和 Git HEAD。
- 对关联 Feature Doc 调用 sibling 或 `--feature-validator` 指定的 canonical validator；Git 仓库使用 fresh，非 Git 工作区使用 structural 校验。
- 自动创建和同步 Work Item 索引，并屏蔽 fenced Markdown 中的伪元数据、标题和记录。

### 范围外

- 编写或修改业务代码、数据库迁移、运行时配置和部署系统。
- 自动创建提交、分支、Pull Request、CI 流程、Dashboard、指标系统或外部工单。
- 认证、授权、审批签名、远程协作锁和分布式队列。
- 代替用户确认真实服务上的发布、重启或用户回归结果。

### 不变量

- Work Item ID 使用 `WORK-YYYYMMDD-NNN`，Feature ID 使用小写 kebab-case；文件名必须分别与 ID 匹配。
- 元数据块必须紧邻一级标题且字段唯一；必需二级标题、记录 ID 和固定结构不能缺失或重复。
- 计划阶段每个影响维度恰好出现一次，值只能是 `affected` 或 `none`；被标记为 `affected` 的维度必须满足对应最低风险等级。
- `VER-*` 只能引用已声明的 `REQ-*`；已验证需求必须有匹配的 `PASS` 验证记录；延期需求必须引用已解决/延期的决策和另一个真实 Work Item。
- `handoff-ready` 与 `closed` 使用进入 `verifying` 时记录的实现快照；管理文档本身不计入实现工作区指纹。
- 有 `feature-ids` 时，关闭证据必须按相同顺序列出每个 Feature ID，且每个文档都必须通过 canonical Feature Docs 合约校验。

## 业务行为

- 研发人员或 Agent 以 `init` 创建 `intake` 状态的 Work Item；模板预置一个需求、决策、风险、计划、验证、审查、发布、用户回归和长期知识提炼记录。
- `clarified` 要求不再存在 `BLOCKER` 决策；`planned` 还要求至少一个完整需求与验收标准、所有影响维度明确，以及开放决策/风险具有确认路径。
- `implementing` 只在计划存在且具体事项全部勾选完成后进入；`verifying` 要求实施证据完整，并写入实现验证快照。
- `handoff-ready` 要求需求验证证据、全部验证记录为 `PASS`、中高风险最新审查为 `PASS`、风险不再为 `OPEN`，并完成用户回归交接；高风险还必须有发布和回滚策略，bugfix 还必须完整记录根因、失败机制、修复和回归保护。
- `closed` 要求用户回归结果与“是否需要用户回归”一致，并完成长期 Feature Docs 证据和文档合约校验；用户回归需要真实用户确认通过时，CLI 不会代替确认。
- Markdown Work Item 是人与 CLI 共同消费的兼容接口；旧 Work Item 可在结构校验阶段缺少 `verification-basis`，但 Git 仓库的交付/关闭门禁仍要求新鲜验证基线。

## 架构与代码地图

- `manage-dev-work/SKILL.md` — 定义生命周期、澄清门、风险门、Feature Docs Closeout 规则和公开 CLI；调用方按此恢复或推进 Work Item。
- `manage-dev-work/scripts/dev_work.py` 的常量与 `WorkItem` — 定义状态、迁移、记录状态、风险等级、影响维度、元数据和回归字段。
- `manage-dev-work/scripts/dev_work.py: init_work_item`、`next_work_id`、`discover_work_items` — 校验输入、从模板生成 Work Item、发现同日序号并初始化目录。
- `manage-dev-work/scripts/dev_work.py: render_index`、`sync_index`、`work_index_errors` — 生成受标记包围的索引区块，校验目录与 Work Item 元数据是否一致。
- `manage-dev-work/scripts/dev_work.py: read_work_item`、`mask_fenced_blocks`、`structural_errors` — 读取文档、屏蔽 fenced Markdown，并执行元数据、标题、日期、记录 ID、类型和状态结构校验。
- `manage-dev-work/scripts/dev_work.py: gate_errors` — 按目标状态实施澄清、计划、实现、验证、交付和关闭门禁，并检查需求/验证/决策/风险之间的引用关系。
- `manage-dev-work/scripts/dev_work.py: implementation_worktree_digest`、`verification_basis` — 用 Git 状态、路径和文件内容摘要计算实现工作区指纹，并生成验证基线。
- `manage-dev-work/scripts/dev_work.py: canonical_feature_validation_errors` — 默认调用 `../manage-feature-docs/scripts/feature_docs.py validate-contract`；Git 使用 `fresh`，非 Git 使用 `structural`，也支持命令行覆盖 validator 路径。
- `manage-dev-work/scripts/dev_work.py: transition_work_item`、`validate_work_item`、`main` — 执行状态迁移、结构/门禁校验、字段更新和 CLI 输出；校验失败时不改变状态。
- `manage-dev-work/assets/work-item-template.md` — 初始化模板和固定记录形状；`references/workflow.md`、`work-item-contract.md`、`verification-policy.md`、`release-handoff.md` — 补充流程与证据契约。
- `manage-dev-work/tests/test_dev_work.py`、`tests/test_cross_skill_integration.py` — 覆盖状态机、质量门、快照新鲜度、Feature Doc Closeout 和 sibling validator 集成；`docs/work-items/*.md` — 当前已有的历史实施记录。

## API、事件与任务

### CLI 生命周期命令

- **签名**：`python3 manage-dev-work/scripts/dev_work.py init|status|validate|transition|close --repo <repo> ...`。
- **输入**：`init` 接收 `--title`、`--type feature|bugfix|change`、`--risk low|medium|high`，可选 `--id` 和多个 `--features`；`status`/`validate`/`transition`/`close` 接收 Work Item ID，迁移命令还接收 `--to`，交付/关闭可接收 `--feature-validator`。
- **输出**：`init` 输出新文档和索引路径；`status` 输出制表符分隔的 ID、状态、风险和标题；成功校验/迁移输出 `OK`；失败以 `ERROR` 写入 stderr 并返回非零退出码。
- **错误**：仓库、ID、类型、风险、文件存在性、迁移关系、结构或目标状态门禁不满足时拒绝操作；`init` 不覆盖既有 Work Item。
- **消费者与兼容性**：研发人员、Agent、脚本和本地 CI 可直接调用；命令依赖固定的 Markdown 契约，不承诺 HTTP、RPC 或远程 API 兼容性。

### Work Item Markdown 契约

- **签名**：文件名为 `docs/work-items/WORK-YYYYMMDD-NNN.md`，一级标题后紧跟元数据；模板字段包括 `work-id`、`work-title`、`work-type`、`work-status`、`risk-level`、`feature-ids`、`created`、`updated`、`code-basis`，以及模板生成的 `verification-basis: pending`。
- **输入**：固定二级章节保存工作概述、范围与验收、变更影响、决策、风险、实施计划、实施记录、验证、代码审查、发布与回滚、用户回归、长期知识提炼和 Bug Fix 闭环。
- **输出**：CLI 根据这些字段返回状态、索引和门禁错误；关闭时读取长期知识提炼中的 Feature Docs 证据。
- **错误**：`REQ-*`、`VER-*`、`DEC-*`、`RSK-*`、`REV-*` ID 必须在单个 Work Item 内唯一；验证引用、延期关系、状态值和固定字段不满足合约时阻断推进。
- **消费者与兼容性**：`manage-dev-work` 负责短期交付状态，`manage-feature-docs` 负责稳定功能知识；`feature-ids` 使用逗号分隔的小写 kebab-case ID。

### Feature Docs Closeout 接口

- **签名**：`transition ... --to handoff-ready` 或 `close`；可选 `--feature-validator <path-to-feature_docs.py>`。
- **输入**：Work Item 的 `feature-ids` 与长期知识提炼中的 Feature Docs 列表，默认 validator 为仓库同级 `manage-feature-docs/scripts/feature_docs.py`，且该脚本必须支持 `validate-contract`。
- **输出**：每个关联 Feature Doc 的 canonical structural/fresh 校验结果；任一文档缺失、元数据不匹配、合约不完整或实现快照过期都会阻断关闭。
- **错误与兼容性**：Git 仓库关闭使用 `validate-contract --mode fresh`；非 Git 工作区仅使用 structural。`--feature-validator` 用于默认 sibling 路径不可用的仓库布局，不改变校验模式。

### 事件与后台任务

- 当前实现不发布领域事件、不消费消息、不启动定时任务或后台 worker；所有行为由一次 CLI 调用同步完成，并直接读写本地文件和调用 Git CLI。

## 数据模型与迁移

- **WorkItem 内存模型**：`WorkItem` 包含 `path`、原始 `text`、用于解析的 `scan_text` 和元数据字典；`read_work_item` 从 UTF-8 Markdown 构造该模型。
- **持久化模型**：一个 Work Item 对应一个 `WORK-*.md` 文件；元数据保存生命周期、类型、风险、Feature 关联和日期，正文保存固定章节与 `REQ/DEC/RSK/VER/REV` 记录。
- **索引模型**：`docs/work-items/index.md` 的 `manage-dev-work:index:start/end` 区块按 Work Item ID 排序生成；索引不是独立事实源，`sync_index` 可由文件重新构建。
- **状态与证据**：状态集合包含正常生命周期和 `blocked`、`cancelled`、`rolled-back` 异常状态；`verification-basis` 使用 `HEAD <12-hex-sha>; worktree-digest sha256:<64-hex>` 表示实现快照。
- **数据库与迁移**：不涉及数据库、表、索引、ORM 或数据迁移；兼容性通过 Markdown 结构校验和 legacy `verification-basis` 读取处理，不提供自动 schema migration。
- **关联数据**：`feature-ids` 只保存稳定 Feature ID，不复制 Feature Doc 正文；关闭时按 ID 解析 `docs/features/<feature-id>.md` 并调用 canonical validator。

## 核心流程

1. `init` 解析仓库，校验 Work Item ID、标题、类型、风险和 Feature IDs，从模板创建 `intake` 文档，并同步 `docs/work-items/index.md`。
2. `intake → clarified` 只允许在结构有效且没有 `BLOCKER` 决策时迁移；`blocked` 只能恢复到 `clarified` 或取消，异常路径不会自动绕过澄清。
3. `clarified → planned` 检查需求与验收标准、14 个影响维度、风险最低等级，以及开放决策/风险的确认路径。
4. `planned → implementing` 检查实施计划至少有一项且不存在未勾选项；`implementing` 允许在补充实现或处理失败验证后继续。
5. `implementing → verifying` 检查计划已完成或显式延期、需求已有实现证据，然后用 `verification_basis` 写入当前 Git HEAD 与实现工作区摘要。
6. `verifying → handoff-ready` 检查基线仍匹配，所有需求有验证证据，验证记录全部 `PASS`，中高风险最新审查通过，风险已处理，用户回归交接字段完整；高风险还检查发布/回滚策略。
7. `handoff-ready → closed` 检查用户回归结果（需要回归时必须是 `passed`，不需要时必须是 `not-required`）、Feature Docs 证据及每个关联文档的 canonical 校验；成功后更新状态、更新时间并同步索引。
8. 每次成功迁移都更新 `work-status` 和 `updated`；仅进入 `verifying` 时写入 `verification-basis`。任一门禁失败都返回错误，不更新 Work Item 状态。

## 异常与边界条件

- **仓库不存在或非目录 — 当前行为**：`ensure_repo` 拒绝；**恢复或风险**：提供可访问的仓库根路径，未产生文件副作用。
- **ID、标题、类型、风险或目标文件非法/重复 — 当前行为**：`init` 抛出可读错误；ID 必须符合正则，标题禁止换行、`-->` 和 `|`，既有文件不覆盖；**恢复或风险**：修正输入，避免覆盖既有记录。
- **状态迁移跳跃或异常状态路径非法 — 当前行为**：`transition_work_item` 返回 `invalid transition`；**恢复或风险**：按允许的相邻状态推进，失败验证/审查需回到 `implementing`。
- **元数据、固定章节、记录 ID、日期或索引结构不合约 — 当前行为**：结构校验报告缺失、重复、非法日期、标题/文件名不一致或索引过期；**恢复或风险**：修复对应 Markdown 后重新运行 `validate`，日期解析错误不会继续写入错误状态。
- **规划证据不足 — 当前行为**：缺少需求、验收、完整影响值、风险等级或开放决策/风险确认路径时阻断 `planned`；**恢复或风险**：补齐可核验事实，否则工作保持当前状态。
- **验证快照过期 — 当前行为**：实现文件、未跟踪嵌套文件、非管理 Markdown、非 ASCII 文件、重命名或 HEAD 改变会使 `verification-basis` 不匹配，阻断交付/关闭；**恢复或风险**：回到 `implementing` 完成变更后重新进入 `verifying`。
- **Feature Doc 缺失、ID 顺序不一致或 canonical 合约失败 — 当前行为**：交付阶段可暂不阻断，关闭阶段阻断并返回对应 Feature Doc 错误；**恢复或风险**：补齐稳定 Feature Doc、关闭证据并使用同一实现快照重新验证。
- **中高风险或 bugfix 证据不足 — 当前行为**：缺少通过审查、发布/回滚策略、风险处理、bugfix 闭环或真实回归结果时不能关闭；**恢复或风险**：补齐证据，避免把实现完成误当成验证完成。
- **关闭、取消或回滚 — 当前行为**：`closed`、`cancelled` 为终态，`rolled-back` 只能回到 `implementing` 或取消；**恢复或风险**：终态记录不可由该 CLI 再次迁移，需新建 Work Item 记录后续工作。

## 并发与幂等

- `init` 使用独占创建并拒绝既有目标文件；Work Item ID、Feature ID、记录 ID 和影响维度的唯一性检查提供基本的重复提交保护。
- 状态更新与索引重写通过临时文件加 `os.replace` 的单文件原子替换完成；但 Work Item 文件和索引是两个独立写入，没有跨文件事务或进程锁。
- `implementation_worktree_digest` 读取 `git status --porcelain -z --untracked-files=all`，按状态、路径和文件内容摘要排序后计算指纹；排除 `docs/features/`、`docs/work-items/`、`docs/superpowers/`，因此维护管理文档不会使实现基线失效。
- 没有消息投递、重试、分布式锁或幂等键；幂等边界是稳定文件/记录 ID、拒绝覆盖和验证快照相等。并行调用时索引重建与状态迁移仍可能竞争。

## 安全与权限

- 当前没有应用层认证、授权、租户边界或审批签名；文件读写权限由操作系统，Git 子进程按当前用户权限执行。
- 工具不连接外部网络服务，也不负责读取或保存凭据、令牌和业务敏感数据；Work Item 正文仍可能包含用户写入的项目敏感信息，应按仓库权限管理。
- `init` 对标题和 ID 做最小格式/单行约束；Markdown 正文由仓库使用者维护，CLI 不对正文进行 HTML、命令或机密信息清洗。
- 决策、风险、验证、审查和回归字段构成可追溯记录，但当前没有不可抵赖审计日志或签名校验；恶意或越权写仓库的防护不在本 Skill 内。

## 配置与依赖

- 运行时依赖 Python 3 标准库；源码使用 `str | Path` 类型语法，运行环境需支持该语法。Git 仓库的 fresh 验证依赖 Git CLI；非 Git 工作区可完成 structural 路径。
- 默认目录约定为 `docs/work-items/`、`docs/features/` 和 `docs/superpowers/`；模板为 `manage-dev-work/assets/work-item-template.md`。
- Feature closeout 默认查找仓库同级 `manage-feature-docs/scripts/feature_docs.py`；可通过 `transition`/`close` 的 `--feature-validator` 指定替代脚本，但替代脚本必须提供 `validate-contract` 命令。
- 没有环境变量、配置文件、Feature Flag、数据库连接、缓存、消息队列或外部服务依赖；索引由 CLI 根据现有文件重建。

## 可观测性与运维

- 成功输出为路径、制表符状态摘要或 `OK`；失败输出以 `ERROR` 前缀写入 stderr，包含结构、门禁、引用、基线或 Feature Doc 校验原因。
- 没有指标、分布式追踪、结构化运行日志、告警或健康检查；排障入口是对应 Work Item、`docs/work-items/index.md`、`status`/`validate` 输出及 Git 状态。
- 当前 Skill 只修改仓库内 Markdown/Python/测试文件，不要求更新、部署、重载或重启任何运行时服务，也不要求数据库迁移、缓存失效或消息消费者处理。
- 用户回归、服务发布顺序和临时部署事实属于关联 Work Item 的 `## 用户回归`；当前 Feature Doc 遵循新契约，不复制瞬时回归交接段。

## 测试与验证

### 已执行

- `python3 -m unittest discover -s manage-dev-work/tests -p 'test*.py'` — 49/49 通过；覆盖生命周期迁移、风险与影响门禁、记录引用、快照新鲜度、Feature Doc Closeout 和异常状态。
- `python3 -m unittest discover -s manage-feature-docs/tests -p 'test*.py'` — 45/45 通过；覆盖被依赖的 Feature Doc 结构、日期、链接、索引和 fresh/structural 合约。
- `python3 -m unittest discover -s tests -p 'test*.py'` — 1/1 通过；覆盖 `manage-dev-work` 调用 sibling canonical Feature validator 的跨 Skill 集成。
- `python3 -m py_compile manage-dev-work/scripts/dev_work.py manage-feature-docs/scripts/feature_docs.py` — 通过；两份核心脚本可编译。
- `python3 manage-feature-docs/scripts/feature_docs.py validate --repo /Users/caihanbing/dev/skills --id manage-dev-work --mode structural` — 通过；当前 Feature Doc 满足结构、元数据、固定章节、历史和本地链接契约。
- `python3 manage-feature-docs/scripts/feature_docs.py validate --repo /Users/caihanbing/dev/skills --id manage-dev-work --mode fresh` — 通过；`HEAD 154afc22215f` 与实现工作区摘要匹配，管理文档变更被正确排除。
- `git diff --check` — 通过；当前文档改动无空白错误。

### 未执行

- 多进程并发初始化、迁移和索引重建测试 — 现有测试未覆盖文件锁或跨文件事务；并行写入风险已记录在“并发与幂等”和“已知问题与后续工作”。
- 真实服务部署、重启、消息消费和用户回归 — 当前 Skill 没有运行时服务或外部拓扑，因此本档案不要求此类回归。
- 多版本 Python/Git 矩阵和非 Git 生产式工作流 — 当前验证基于本机 Python 3、Git 仓库和仓库内自动化测试，剩余兼容性需在目标环境单独执行。

## 关键决策

### DEC-001 — 以仓库本地 Work Item 管理短期交付

- **决定**：使用一个 `docs/work-items/WORK-*.md` 记录单个短期研发工作，并用固定章节和 CLI 状态机推进。
- **原因**：让需求、证据、风险、发布和回归状态可跨会话恢复，同时保持实现轻量、可审阅和可版本控制。
- **取舍**：不提供外部系统同步、图形化界面或服务端并发协调；并行协作能力依赖仓库与 Git 工作流。
- **证据**：`manage-dev-work/SKILL.md`、`assets/work-item-template.md`、`scripts/dev_work.py` 的 WorkItem/状态常量和 `docs/work-items/index.md`。

### DEC-002 — 以验证快照约束交付与关闭

- **决定**：进入 `verifying` 时记录 `HEAD` 与实现工作区摘要，`handoff-ready`/`closed` 必须匹配；管理文档目录不计入摘要。
- **原因**：阻止在验证后修改实现却继续沿用旧验证结论，同时允许 Feature/Work 文档在知识收尾阶段更新。
- **取舍**：Git 仓库获得强新鲜度保证；legacy Work Item 仍可做 structural 校验，但 Git 交付/关闭需要补齐新基线。
- **证据**：`scripts/dev_work.py` 的 `implementation_worktree_digest`、`verification_basis`、`gate_errors`，以及 `test_rejects_stale_verification_basis` 和相关 Git 回归测试。

### DEC-003 — Feature Closeout 复用 canonical 合约校验器

- **决定**：关闭关联 Feature 时调用 `manage-feature-docs` 的 `validate-contract`；Git 使用 `fresh`，非 Git 使用 `structural`，默认 sibling 不可用时接受 `--feature-validator`。
- **原因**：避免两套 Skill 各自实现一份文档规则，并确保长期功能知识与实现快照一致。
- **取舍**：关闭门禁依赖 Feature Doc 已存在且可解析；没有关联 Feature ID 的纯流程 Work Item 不触发逐 Feature 校验，但仍需填写关闭知识证据。
- **证据**：`scripts/dev_work.py: canonical_feature_validation_errors`、`manage-dev-work/SKILL.md` Closeout 规则、`tests/test_cross_skill_integration.py` 和 Feature fresh 测试。

### DEC-004 — 用显式影响与风险等级驱动质量门

- **决定**：计划阶段要求 14 个影响维度各出现一次并使用 `affected|none`；数据库、消息、安全、并发、事务和跨服务等高影响维度提升最低风险等级。
- **原因**：让数据、权限、并发、消息和兼容性风险不能以模糊值绕过计划门。
- **取舍**：文档填写成本更高，旧的 `unknown` 或重复维度记录不能继续推进；验证器不替用户判断实际影响，事实必须写入相关章节。
- **证据**：`scripts/dev_work.py` 的 `IMPACT_DIMENSIONS`、`HIGH_IMPACTS`、`MEDIUM_IMPACTS` 和 `gate_errors`，以及影响 cardinality 回归测试。

## 已知问题与后续工作

### ISSUE-001 — 跨文件写入没有并发事务

- **影响**：多个进程同时初始化或迁移时，Work Item 文件与 `index.md` 可能竞争；进程在两次写入之间退出时，索引可能暂时落后。
- **当前处理**：目标文件独占创建，单个文件更新/索引重写使用临时文件替换；可运行 `python3 manage-dev-work/scripts/dev_work.py` 对应命令或重新同步索引恢复一致性，但当前没有锁。
- **后续动作**：若未来要求并行 Agent 或多进程共享同一仓库，增加明确的锁/事务策略和竞争回归测试；在该需求确定前不扩大当前 Skill 边界。

### ISSUE-002 — 校验器不提供真实服务回归能力

- **影响**：CLI 只能验证仓库内记录和实现快照，不能证明部署拓扑、服务重启、消息流或终端用户行为。
- **当前处理**：所有 Work Item 仍需填写用户回归字段；当前仓库 Skill 变更明确记录为无运行时服务操作，真实发布事实留在关联 Work Item。
- **后续动作**：只有出现服务化集成需求时，才在 Work Item 中补充基于仓库证据的发布/回归交接，并另行设计外部系统集成。

## 变更记录

### 2026-09-14 — 创建“研发过程管理”功能档案

- **状态**：已完成
- **变化**：创建 `manage-dev-work` Feature Doc，并同步 `docs/features/index.md`，记录当前生命周期、CLI、门禁、快照、Closeout 和限制。
- **原因**：为稳定的研发过程管理 Skill 建立可跨会话恢复的证据型功能档案。
- **兼容性**：仅新增仓库本地管理文档，不改变 Skill 代码、CLI 参数、运行时服务或数据库；文档使用当前 Feature Docs 契约。
- **验证**：`manage-dev-work` 49/49、`manage-feature-docs` 45/45、跨 Skill 1/1、脚本编译、structural/fresh 校验和 `git diff --check` 均通过。

### 2026-09-11 — 收紧验证门禁并接入 Feature Closeout 新鲜度

- **状态**：已完成
- **变化**：引入实现工作区摘要和 `verification-basis`，强化记录引用、影响维度 cardinality、日期/索引/结构校验，并在 Git Closeout 调用 canonical Feature Docs fresh 校验。
- **原因**：保证长期 Feature 文档与实际实现快照一致，避免缺证据或过期基线误放行。
- **兼容性**：不引入运行时服务或第三方依赖；legacy 文档保留 structural 兼容路径，但 Git 交付/关闭对旧 dirty 基线更严格。
- **验证**：当前实现位于 `HEAD 154afc22215f`；对应 Work Item 与自动化测试覆盖过期快照、非法日期、孤立引用、缺失 Feature Doc、fenced Markdown 和跨 Skill 调用。
