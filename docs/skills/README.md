# Skills 使用说明

团队成员按需选择阶段 Skill；有公共契约依赖的阶段须随包安装对应引用文件，无须先运行总入口。

本仓库的 skill 遵循 [Agent Skills 开放标准](https://agentskills.io/)，公共流程与角色正文可供多种 AI 编码工具使用；调用方式、模型和权限由当前使用的工具配置，文件能加载不等于这些配置已生效。

## 开发入口与阶段

普通 DMS 对话按当前进度选用 Skill，也可显式调用；不要求每次启动全流程。已批准实施持续推进，业务、关键方案和最终验收由成员决定。已授权范围、状态与完成条件见 [工作流契约](dms-dev/references/workflow-contract.md)。

| Skill | 何时使用 | 主要输出 |
| --- | --- | --- |
| [dms-dev](dms-dev/SKILL.md) | 需求、修复或继续工作需要确定当前阶段 | 下一项必要能力与操作范围 |
| [dms-grill-me](dms-grill-me/SKILL.md) | 业务语义或关键取舍尚待明确 | 有依据的决定与待决问题 |
| [dms-spec-check](dms-spec-check/SKILL.md) | 编写/复查方案 | 范围、歧义和验收核对 |
| [dms-systematic-debugging](dms-systematic-debugging/SKILL.md) | 根因不明的错误、构建或集成异常 | 根因证据、相称修复与验证 |

需求已清楚但缺少足以实施的设计时，由主会话依据实际项目形成接口、数据、异常及兼容设计，再交 dms-spec-check 检查；不新增设计 Skill，也不直接以任务清单代替设计。

任务安排、实施和恢复由主会话直接承接，沿用已有方案、公共契约和进度记录；不要求单独的规划或执行 Skill。计划模式由成员选择。

清楚小任务用简短任务说明；已有设计和有效决定直接承接，探索以结论、证据和限制结束，不自动扩成实现。独立审查、提交说明和只读问答保持各自范围。实现/修复自动按 dms-test-gate 分级，宿主强制限制优先；Skill/规则修改按语义和影响选择内容核对或对应行为验证，详见工作流契约，纯 Markdown 后缀不是豁免理由。

阶段独立使用也按 [DMS 项目依据](dms-dev/references/dms-project-context.md) 选择模块、调用链、数据/租户边界及原规范，保留等级与适用条件；接口、数据模型或失败语义变化时同步原设计、任务和检查目标。交付面向开发、代码审查和测试人员，具体资料按工作流契约准备。

安装公共契约及项目依据导航 `dms-dev/references/`，导航引用的规范与源码来自目标项目；委派、恢复与证据格式按阶段渐进加载。团队方法只维护这一套公共源，各工具按下方安装方式使用相同名称和内容；运行文件与项目依赖以[交付清单](package-manifest.json)为准，验证范围见[验证状态](#验证状态)。

## 技能列表

### dms-review-changes

代码审查 skill。审查正式项目实现及直接相关的测试、SQL、构建/运行配置；发布脚本、原型及其演示代码、独立文档不适用，混合变更只审查适用部分，范围与[研发流程必做项](../code-quality/研发流程必做项.md#二开发)一致。按力度执行检查及适用的复核，输出高/中/低分级问题与单测覆盖率摘要；报告中的流程按实际完成的步骤填写，不自动改代码。

- 源文件：`dms-review-changes/SKILL.md` + `dms-review-changes/references/`（`angles.md` 角度全文、`review-pitfalls.md` 判定不成立的判据笔记、按需读取的 `mr-output.md`）
- 前置依赖：`config/coding-guidelines/` 目录（阿里规约 + 项目自定义规约 + 灰度发布规范）

**用法示例**（以下以自然语言明确调用；快捷命令以当前工具实际支持为准）：

```text
# 1. 审查当前未提交的变更，包含暂存、未暂存和未跟踪文件（默认行为，无需确认目标分支）
使用 dms-review-changes

# 2. 指定力度：low / medium / high（默认）/ xhigh / max。越高角度越多，xhigh 起多一轮查漏
使用 dms-review-changes xhigh

# 3. 调并发（团队默认 3，并发高了国产模型会 429），请求适用的 JVM 覆盖率证据（可复用有效的成功结果）
使用 dms-review-changes high c=2 cov

# 4. 确认 MR 目标分支（默认推荐 releases），按 PASS 或已确认的 N/A 结果生成标题与描述
使用 dms-review-changes mr

# 5. 指定其他建议目标，仍须先确认；同一 MR 复审沿用已确认目标，目标变化时重新确认
使用 dms-review-changes --base test

# 6. 除上述参数外，其余文字当范围提示原样传给 finder，不改变 diff 的取法
使用 dms-review-changes 重点看 apps/das-console 的权限判定
```

合并前或明确要求整分支审查时，同样先确认目标分支，再比较该目标与待审提交；默认调用只覆盖未提交变更。报告注明基线、待审提交及另行检查的未提交变更，不能把本地未提交的修复计为 MR 已修复。N/A 文案可依据明确选定的未提交候选生成，注明范围和状态，不代表合并验收通过。

**默认输出**：高/中/低分级问题（位置/场景/建议）+ 测试范围与证据 + 单测覆盖率摘要。不适用时说明原因，不生成“审查通过”报告或虚假的零问题摘要。带 `mr` 或明确要求 MR 标题/描述（包括草稿）时，报告须给出 `审查结论`：有适用代码须取得 `PASS`；已确认整个范围无适用代码的 `N/A` 也可输出文案，无需另批例外；`FAIL`、`INCONCLUSIVE` 仍不输出，草稿同样受限。混合变更不能整体按 N/A 跳过代码检查，具体条件见 [MR 输出规则](dms-review-changes/references/mr-output.md)。通过后有**这次不改**的问题时另附审查记录的 MR 评论文本（结论按[审查记录规范](../code-quality/审查记录规范.md)三选一）。没有评论正文时，也须在回复中说明“不适用”及原因，或“审查已完成但无记录项”；状态说明不写入 MR 标题、描述或评论正文。

测试范围分析先从已确定的需求、变更和源码中形成初步场景，随原有审查补充，对照测试输入、断言和实际执行证据；小改动简述，不额外完整调查一遍。缺少需求时标明推断或待确认，不把已有实现、有测试文件或高覆盖率写成场景已验证。测试规范缺口须核对要求、适用阶段和实际缺口；测试证据缺陷须说明目标与断言的具体问题。low 仅列建议，medium 自核、high 及以上独立复核后仅将已确认项计数，疑似或证据不足不计数；实现正确性问题仍按原规则处理。不依赖外部测试范围 Skill，也不自动补测试或触发 dms-test-gate。

JaCoCo 仍按需运行并复用有效结果。类级行覆盖率只作参考，不能直接判断“新增代码覆盖率 ≥ 80%”；本节应用/业务共享库范围保留现行80%及计量规则。职责、验收方法和报告交付边界统一按[任务契约](dms-dev/references/task-contract.md#新增代码覆盖率)，发布编排的行为门禁不扩成本节代码审查范围。缺必需范围或报告证据仍写未验证；发现方法不可靠的新证据时按契约重新评估。没有数值不填无代码 N/A，不能将 BUILD SUCCESS 当作测试通过。

### dms-commit-msg

按本仓库 Conventional Commits 规范生成中文 commit message。**只输出文本，不执行 `git commit`**。

- 源文件：`dms-commit-msg/SKILL.md`（无外部依赖）
- 约束了六个合法类型（`feat`/`fix`/`refactor`/`perf`/`docs`/`chore`）、中文业务域名称（工程设施沿用仓库名称）、标题概括主要变更内容及其原因或影响、正文按需说明主要净变化，并强制读取实际 diff 而非只看 `--stat`
- 输出前对照 diff 核对主要净变化是否完整表达，并逐项确认描述的依据和变更对象是否可查

```text
# 描述当前改动（有暂存内容时只描述暂存部分）
使用 dms-commit-msg

# 相对基线只写净变化，避免把"改了又改回去"的部分写进去
使用 dms-commit-msg --base origin/releases
```

改动跨多个不相关主题时会建议怎么拆成多个 commit；有未 `git add` 的文件会单独提醒。

**装好之后不用记着敲 `dms-commit-msg`**：它的 `description` 就是给自动触发用的，你说"提交一下"、"帮我写个 commit message"，AI 该自己用它。这是有意的——规范如果得靠人每次记得调用，就等于没有规范。反过来说，**如果你发现它在你准备提交时没被用上，那是这个 skill 的问题，请反馈**（实测过一次：描述写得跟已有规则重复时，模型看不出加载它的理由，于是从不触发）。

### dms-test-gate（试用中）

在已授权实现/修复中按上下文或显式调用，核对关键场景、测试有效性、真实结果和必要复审。规则修订 `test-gate-2026-10-25-r3` 的完整要求在 [主规则](dms-test-gate/SKILL.md)；三个质量动作不绑定固定表格、人员或审批。可行性实验与正式交付按[工作流契约](dms-dev/references/workflow-contract.md#授权与阶段)区分完成条件，不把实验完成称为正式门禁通过。

| 档 | 验证重点 |
| --- | --- |
| L0 | 内容及适用格式核对，不跑不适用的代码门禁 |
| L1 | 相关基线、前后行为对照及受影响回归 |
| L2 | 改变的行为、重要边界/失败场景、直接不变量及受影响回归，不自动委派 |
| L3 | 对应真实入口/集成证据及一次综合独立复审 |

项目规则或本次明确要求的独立复审继续执行，不能靠定档绕过。按真实职责选择默认门禁：应用/业务共享库保留现行80%，发布、部署、运维编排及专用辅助逻辑按行为、风险和适用集成证据验收，可信覆盖率作辅助；不按语言或目录豁免。显式数值约定、报告交付及获准迁移按任务契约核对。必需测试身份、参数及真实结果须完整核对，构建成功不能替代测试通过。

主会话先从需求、批准决定和契约形成场景，再写目标测试；实现现状不能单独决定业务期望。普通任务清单或一张表即可，状态流转/条件组合影响结论时再展开；复杂业务或明确遗漏风险才委派独立场景分析。已有测试承认后补顺序并重新核对需求。

缺陷修复优先复现或旧失败/新通过；新行为核对独立期望下的精确结果与重要边界；重构核对基线和行为一致。具体漏检、断言歧义、其他校验掩盖目标或 mock 替掉机制时补证，仍不足才定向注入，不逐格强制变异。反事实操作限获准隔离副本。

综合复审在新的只读上下文检查需求、实现、测试和原始结果。同版本、同范围、职责完整时，一次可满足测试充分性、L3 和交付审查；不默认调用 dms-review-changes 的整套委派。原始需求和决定保存一次，普通复审可查源并接收增量；原始问题、失败和处置保留。相关变化撤销最终结论，按 [任务契约](dms-dev/references/task-contract.md) 重验受影响部分，再核完整清单与最终快照。

`dms-test-gate/agents/` 保留两项可选专职能力：

| 能力 | 适用时机与边界 |
| --- | --- |
| Test Analyst（测试分析者） | 确有必要的独立场景分析；实际只读，不接触本次目标测试 |
| Test Reviewer（测试评审者） | 本次明确要求严格测试盲审；判断所需完整材料内联，隔离待审实现，禁用全部工具 |

角色文件是材料契约，不是生效的权限配置；启用时核实际隔离及宿主调用许可，内置旧角色不因项目源更新而改变。可选能力不可用不阻断普通流程；本次已要求的独立分析、综合复审或严格盲审缺失仍不得通过。普通复审不能冒充旧盲审 PASS。

```text
执行 dms-test-gate
执行 dms-test-gate 为 XxxServiceImpl 的状态流转改动补测试
```

只读请求不因选用 Skill 获得测试副作用授权。待决先查既有依据，仍实质影响业务、权限或验收才询问，只暂停依赖部分；必要期望、证据或复审缺失保持 INCONCLUSIVE，实际失败保留 FAIL。历史结论保留原版本，不因新规则追溯改判。后续真实使用分别观察必要目标是否漏掉、无效委派/重跑是否减少，不用文件校验证明效果。

### dms-security-review

安全专项审查。只找**本次改动新引入**的、有真实利用路径的漏洞（注入、认证授权绕过、密钥与加密、反序列化/XSS、数据泄露），不做通用代码审查，也不报既有问题。

- 源文件：`dms-security-review/SKILL.md`（无外部依赖）
- **正文不是团队原创**：取自 Claude Code 内置 `/security-review` 的提示词，保留原有安全判据，仅将误报过滤中的命令工具称谓通用化
- 团队另补了变更材料采集：内置版由 CLI 在运行时把 git status、变更文件清单、commits、完整 diff 四段拼进提示词，脱离 CLI 就没有这四段，所以补了「第一步：取变更」让 skill 自己去取。这一步顺带纳入未跟踪文件：它们不在任何 diff 里，新增的类还没 `git add` 时，整轮审查会得出"没有变更"

```text
# 审查当前分支相对上游的变更
使用 dms-security-review

# 指定基线
使用 dms-security-review --base origin/releases
```

**流程是两段式**：先起一个子任务找候选漏洞，再对每条候选各起一个并行子任务做误报过滤，过滤子任务给 1-10 的置信度，低于 8 的直接丢弃。没有子任务机制的工具按同样顺序单线跑这几步即可，只损失并行度。它的产出通常很短，偏向"宁可漏报，不要淹没在误报里"，与 `dms-review-changes` high+ 的 recall 取向正好相反。

**和 `dms-review-changes` 的分工**：`dms-review-changes` 的 F 角度也查注入、越权、RCE，但它是通用审查的一部分，判据是本仓库的高危模式（租户越权、灰度 fail-closed 等），且倾向多报。`dms-security-review` 只做安全、判据更严、成本更低。日常提交走 `dms-review-changes` 就够；**改动碰到鉴权、对外接口、SQL 拼接、反序列化、加密时再单独跑一次这个**，两者的漏报方向不同，叠着跑才有意义。

**安装前检查同名技能或内置命令**：确认实际加载的是团队版本；已有同名入口时，按当前工具的机制避免覆盖或加载歧义，不因名称相同就认定判据一致。

**已知的一处原文瑕疵**：HARD EXCLUSIONS 里编号 `16` 出现了两次（"Regex DOS concerns" 和 "Insecure documentation"）。这是原文如此，保留未改——改了就不再是原文，而这个编号不影响任何判据的含义。

## 加规则的门槛

这些 skill 有个天然的膨胀方向：每翻一次车就往文件里加一条禁令。加十条之后，文件变长、每次调用都要读，而模型的判断力被换成了词匹配——没列举到的情况照样翻车。

所以新出现的翻车案例**先用来检验既有判据够不够**：多数情况下是判据没被执行，不是判据缺失，这种要改的是判据的位置或措辞，不是加一条。只有当一个案例**无法由任何既有判据推出、且反复发生**时，才加新条款。加的时候：

- 能写正向判据就不写禁令——判据能迁移到没列举过的情况，禁令只挡住列出来的那几个
- 能解释原因就不列词表——列了词表，模型就只查那几个词
- 模型自己推得出来的推论不写，保留必要的前提和判据即可

## 双份同步约定

`docs/skills/` 是团队 skill 的**唯一源**（进版本库，团队共享）。优化团队 Skill 时先更新这里的源文件，再按本次授权范围更新安装副本；核对完整 diff，按仓库约定确认提交说明后提交。

公共源只保留通用描述、参数、职责和证据要求。特定工具的模型、调用接口、权限配置和自动触发控制留在本地适配层，不能反向写入公共规则。同步时保留有效的工具权限限制，单独核对运行环境配置；不得用通用角色契约覆盖已生效的受限角色配置。

提交前检查 Skill 正文、附属角色、参考文件与本说明，确认没有固定厂商、模型别名、专有工具调用或仅某个工具识别的执行规则。记录版本、预期收益与验证证据；静态检查、实际加载和真实任务效果分别说明。

## 安装方式

### 同一份源与交付范围

Claude Code、Codex、OpenCode 共用 `docs/skills/` 下同一套源文件，名称、正文和相对链接原样安装。当前包包含 **8 个 Skill、20 份运行文件**：8 份 `SKILL.md`、10 份参考文档和 2 份可选角色契约。精确文件列表及内容指纹以[交付清单](package-manifest.json)的 `runtime_files` 为准；验证记录和历史适配材料不复制到运行目录。

默认安装到 **DMS 仓库根目录下的项目级目录**。Skill 通过相对路径读取仓库源码和规范，当前包不适合直接放进个人全局目录。清单的 `project_documents` 列出须随同一仓库版本交付的配套规范及指纹，包含《设计文档组织与归档规范》《研发流程必做项》等；文件留在仓库原位置，不另复制或改写到 Skill 中。`project_context_files` 是按当前 checkout 读取的项目入口，不固定业务源码版本。

从发布者指定的仓库提交、标签或完整交付包获取同一批运行文件、使用说明、清单及配套规范；发布者应特别核对未跟踪的新规范。当前业务分支或清单中的 `source_head` 不代表完整材料已经发布。仅分发 20 份运行文件的压缩包不包含这些项目依赖。`package_id` 标识运行内容，`delivery_revision` 标识本次交付说明及依赖清单；说明更新不改变未修改的运行包身份。安装后从新会话核对实际来源，发现问题先修订团队源，再原样同步。

### 验证状态

本版已完成文件、引用和安装命令的文件操作核对，安装目录与调用约定依据官方文档。Codex、Claude Code 已取得部分本机发现证据；OpenCode 的发现尚未确认，三种工具的实际调用、自动选择和完整研发流程均未完成验收。可选测试角色的实际权限隔离也须由使用环境另行核对。

### 选择发现目录

以下均相对于 DMS 仓库根目录；目录及调用约定于 2026-11-04 核对官方文档，已验证及未验证范围见上方[验证状态](#验证状态)。

| 工具 | 项目级目录 | 明确调用的示例 |
| --- | --- | --- |
| [Claude Code](https://code.claude.com/docs/en/skills) | `.claude/skills/` | `/dms-dev`，或自然语言说明要使用 `dms-dev` |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `.agents/skills/` | `$dms-dev`，或自然语言说明要使用 `dms-dev` |
| [OpenCode](https://opencode.ai/v2/docs/skills/) | `.opencode/skills/`；也支持上面两种项目目录 | 自然语言说明要使用 `dms-dev`，由 `skill` 工具加载 |

[OpenCode 1](https://opencode.ai/docs/skills/) 和 [OpenCode 2](https://opencode.ai/v2/docs/skills/) 均说明支持这三种项目目录；本包的名称与目录一致，使用两者都支持的 `name`、`description` 及普通 Markdown 引用。模型接入和权限配置应查所用版本的官方说明，不能把两个版本的配置示例混用，也不随 Skill 包下发个人接入设置。

为 OpenCode 准备环境时，若项目已有 `.claude/skills/` 或 `.agents/skills/`，可直接复用，不必复制第三份。确需同时为 Claude Code 和 Codex 安装时，两处均从同一清单复制并校验；核对实际加载来源，不让同名的不同版本依赖加载顺序。安装前盘点项目及个人目录中的同名入口和旧团队版本；保留个人修改，按来源处理冲突，不整目录覆盖。各工具的模型、权限和子任务配置由成员环境管理，不写入公共 Skill 正文。

### 首次安装与文件核对

需要 Python 3 标准库。在 DMS 仓库根目录执行下面命令，将 `.claude/skills` 换成上表选定的目录。脚本先校验源、配套规范及目标冲突，再只复制清单内文件；任一目标 Skill 目录已存在就停止。安装过程不修改项目规范或用户配置。

```sh
python3 - install .claude/skills <<'PY'
from pathlib import Path
import hashlib
import json
import shutil
import sys

action, directory = sys.argv[1:]
if action not in {"install", "check"}:
    raise SystemExit("操作只支持 install 或 check")
if directory not in {".claude/skills", ".agents/skills", ".opencode/skills"}:
    raise SystemExit("请使用表中的项目级目录，并在仓库根目录执行")
root = Path.cwd()
manifest = json.loads((root / "docs/skills/package-manifest.json").read_text(encoding="utf-8"))
target = root / directory
if root not in target.resolve().parents:
    raise SystemExit("目标目录链接到了仓库之外，请使用项目内目录")

def verify(path, expected):
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"文件缺失或版本不符：{path}")

for item in manifest["runtime_files"]:
    verify(root / item["source"], item["sha256"])
for item in manifest["project_documents"]:
    verify(root / item["path"], item["sha256"])
for relative in manifest["project_context_files"]:
    if not (root / relative).is_file():
        raise SystemExit(f"缺少项目入口：{relative}")

if action == "install":
    conflicts = [name for name in manifest["skills"]
                 if (target / name).exists() or (target / name).is_symlink()]
    if conflicts:
        raise SystemExit("目标已存在，先按更新步骤处理：" + ", ".join(conflicts))
    for item in manifest["runtime_files"]:
        destination = target / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / item["source"], destination)

expected_files = {item["path"] for item in manifest["runtime_files"]}
actual_files = {str(path.relative_to(target)).replace("\\", "/")
                for name in manifest["skills"] for path in (target / name).rglob("*")
                if path.is_file()}
if actual_files != expected_files:
    raise SystemExit("安装目录存在缺失或多余文件，请对照清单核对")
for item in manifest["runtime_files"]:
    verify(target / item["path"], item["sha256"])
print(f"文件核对通过：{len(manifest['skills'])} 个 Skill，{len(expected_files)} 份文件，{manifest['package_id']}")
PY
```

已安装后，将命令首行的 `install` 改为 `check`，保持其余内容不变，即可只读核对源、依赖和安装文件。源文件、清单或项目依赖不匹配时，保留本地修改并取得匹配的完整交付，不改指纹绕过校验；复制中断或安装副本不符时，先备份并移走本次目录，再重新安装。校验通过前不要开始使用。

### 更新与撤销

1. 结束正在使用旧版的任务，保存已有安装清单和个人修改。按旧清单将本包所属的 Skill 目录移到技能发现目录之外的备份位置，例如 `.dms-dev/skill-backups/<日期>/`；同时保留对应项目规范版本。没有旧清单时，先核对来源和内容，仅归档确认属于旧团队包的目录；个人同名或来源不明的目录先保留，确认处理方式后再安装。其他 Skill、工具配置和常驻规则保持原样。
2. 更新同一批团队源、清单及配套规范，再运行上述 `install` 和 `check`。旧包已删除或改名的团队入口也按原清单归档，不能混用新旧入口。首次接入时没有旧目录就不需要备份。
3. 需要撤销时，先保存安装后产生的个人修改，将本次安装的目录移出发现路径，再恢复备份的团队目录与清单；配套规范按版本逐项核对并保留他人后续改动，不回滚整个工作区。重开会话核对来源。没有备份的首次安装只移走本次新增目录。

### 加载确认与试用

文件校验通过后，在项目根目录及实际使用的业务子目录分别开启新会话，用下面的只读请求确认来源和引用：

```text
列出当前可用的 8 个团队 dms- Skill 及实际来源路径，读取 dms-dev 引用的工作流契约和 DMS 项目依据导航，确认能找到仓库规范。只读核对，不修改文件或执行开发任务。
```

结合工具的技能列表和实际读取记录核对结果，不仅依据助手口头确认。随后在获准试用任务中，检查自然语言是否选择必要阶段、明确小改动是否直接承接、修复是否连接实际测试及适用审查；单独的审查或提交说明请求应保持其范围。记录工具版本、实际模型、包身份、入口、结果及缺口。文件一致、实际加载和研发效果分别记录，已验证的一个工具不能替代另外两个工具的运行证据。通用入口与各阶段用法见本文前面的说明。

`dms-test-gate/agents/` 的两个文件是可选专职角色契约。普通流程可使用主会话场景分析及适用的综合独立复审；启用专职能力时，另按当前工具配置并核对其只读、材料隔离或全部工具禁用要求。文件复制不代表权限生效，未满足条件的角色不能宣称可用；主会话自核不替代必需独立复审。

工具的能力和配置以其当前官方文档及实际结果为准；其他工具支持相同格式时可以沿用这套源与校验方法，再核对发现目录和权限，不另维护改写版。
