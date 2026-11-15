# CodeFree-O 执行与恢复

执行前检查 `codefree-o --version`、`codefree-o run --help` 和 `codefree-o models`；本机 1.10.1 支持 `--title`、JSON 事件和 `--session`。下面的 `$runner` 为本 skill 的 `scripts/runner.py` 绝对路径，`$record` 为仓库外私有运行目录。命令输出是摘要；原始事件、错误、交接和快照保存在该目录。运行记录可能包含源代码及敏感信息，应按本机保密要求管理。

首次准备：计划文件包含已确认计划及修订；验收、授权和验证参数填写具体内容。非 Git 目录必须传 `--paths-file` 指向每行一个项目相对文件路径的清单；Git 项目应指定仓库根目录。

`prepare --protect-paths-file <文件>` 可声明只读文件，每行一个项目相对路径，可声明尚不存在的文件；不能与任务目标重叠。只记录受保护文件的状态和摘要，不复制其内容；若在旧记录中后来新增保护，旧快照可能已经保存过该文件，需自行检查和保管。受保护文件变化后可记录阻塞，但不能通过、解除阻塞或继续派发。Git 忽略文件仅监测任务目标内的文件和显式保护项，其余忽略文件未覆盖。任务目标须为项目相对路径，不允许向上越界、`.git` 或符号链接路径。此检查与快照不构成执行沙箱。Git 子模块仓库目前不支持。

默认允许自动批准；若授权不覆盖自动批准，用 `prepare --no-auto-approve` 禁用，此时运行器拒绝派发，不提供交互审批。重新授权可用 `prepare --auto-approve`。旧 v2 记录未保存此开关时沿用默认；缺少任务摘要的旧记录须重新 `prepare`。运行器每轮校验计划及任务摘要，不能防止能够同时修改记录及摘要的本地用户篡改。

`--tasks-file` 是 UTF-8 JSON，形如：

```json
{"version":1,"tasks":[{"id":"T1","title":"校验空名称","goal":"拒绝空名称并返回明确错误","targets":["src/main.py"],"depends_on":[],"steps":["在保存前检查名称去除空白后是否为空","补充空名称测试"],"acceptance":["仅含空白的名称被拒绝且不会保存"],"verification":[{"command":"python3 -m unittest tests.test_names","expected":"全部测试通过，包括空名称用例"}]}]}
```

依赖只能引用之前的 ID。每项必须填写具体内容；运行器检查结构，Codex 负责核验内容是否足够具体。首次、计划更新和重建时运行器合成完整交接，普通续接的 handoff 应包含任务 ID、问题证据和复验要求。项目规则与已有修改保护细节放入首次和重建的 handoff。

```sh
python3 "$runner" prepare --record "$record" --project "$project_dir" --title "$task_title" --plan "$plan_file" --tasks-file "$tasks_file" --criteria "$criteria" --authorization "$authorization" --verify "$verify"
python3 "$runner" run --record "$record" --handoff "$handoff_file"
```

运行器解析 `glm5.3` 为模型列表中的唯一完整标识，也可用 `--model` 指定模型；不存在或歧义时停止，不替换模型。同一任务保持相同模型。新建会话以任务名传 `--title`，完成后在项目目录查询会话列表核对名称；续接始终使用确切 `--session`，不用 `--continue`。运行器默认传 `--auto`，派发前确认用户授权覆盖自动批准，交接不得扩大授权。等待进程结束，读取摘要，失败时检查原始证据。

每轮必须审查 `snapshots/baseline` 和本轮快照：比较 HEAD、暂存和工作区差异、未跟踪文件与内容，确认原有修改未被覆盖，并按验收项检查实际产物和验证结果。未确认保留时停止并报告，不记录通过或继续派发。审核完成后记录证据和有无实质进展，才能续接：

```sh
python3 "$runner" record-review --record "$record" --result failed --evidence "$review_evidence" --progress yes --baseline-reviewed
python3 "$runner" status --record "$record"
python3 "$runner" run --record "$record" --handoff "$feedback_file"
```

`--baseline-reviewed` 表示已实际核对用户既有改动，不能只凭模型报告填写。结果使用 `passed`、`failed` 或 `blocked`；进展用 `yes` 或 `no`。计划变更时再次执行 `prepare` 保存新版本；任务名称和项目必须一致。运行器发现轮次外工作区变化时停止，不能自动覆盖或重置。

正常运行后由审查标记的 `blocked`，在阻塞解除、工作区和只读保护文件与记录一致后，可用 `unblock --record "$record" --evidence "$reason"` 记录解除证据，再续接；运行错误仍须按下面的 `--retry` 或 `--rebuild` 流程恢复。连续三轮无进展、未审查和已完成任务不能通过 `unblock` 绕过限制。

进程中断后先通过 `status`、系统进程信息、日志和工作区确认原进程已结束且不会重复执行；PID 缺失时必须额外确认没有遗留进程。确认后使用 `status --record "$record" --reconcile --evidence "$reconciliation_evidence"` 保存中断快照；PID 缺失时还必须传 `--confirmed-no-process`，表明已独立确认没有遗留进程；审查该轮并记录结果。仅当确认原会话不可恢复且已保存证据时，使用 `run --record "$record" --handoff "$full_handoff" --rebuild --recovery-evidence "$reason"` 创建“任务名 · 恢复 N”会话；完整交接应包含计划、现状和历史结论。脚本不会自动判定会话不可恢复。

运行失败后先调查证据，不自动重建；如果原因已解除且原会话可用，记录审查后使用 `run --record "$record" --handoff "$feedback_file" --retry --recovery-evidence "$reason"` 续接原会话。连续三轮无实质进展时暂停。工作区基线保护需要 Codex 人工核对；脚本不能独立判断同一文件内用户修改是否被覆盖。不要根据退出码或事件中的模型回复直接判定验收通过。

运行器在每次派发、通过或失败审查、解除阻塞及更新已有计划前核验生效版本摘要；损坏时只允许记录 `blocked`，附带完整性错误，须恢复原件或另建任务。旧 v2 缺少任务摘要可通过重新 `prepare` 输入新清单迁移。每轮派发及通过审查前检查累计目标的符号链接，不能替代沙箱。授权文本仅供交接，不会自动解析；Codex 须确保文本和结构化开关一致。`run --auto` 为兼容参数，不能覆盖禁用设置。单轮运行没有自动超时。
