# CodeFree-O CLI

以下基于本机 1.10.1 的帮助和实际调用。使用前检查 `codefree-o --version`、`codefree-o run --help` 和 `codefree-o models`；版本差异以当前帮助为准。

`codefree-o models` 列出 `provider/model` 标识。完整标识先按精确值匹配；简写匹配忽略大小写、分隔符及常见显示后缀，仅在唯一匹配时使用实际列出的完整标识。2026-11-13 本机的 `glm5.3` 唯一对应 `codefree/GLM-5.3-TokenPlan`；每次重新核实，不能将此映射视为永久有效。列表存在不代表服务一定可用，调用失败时报告实际错误。

在项目绝对路径运行，使用标准输入发送交接正文：

```sh
codefree-o run --dir "$project_dir" --model "$model_id" --format json < "$handoff_file" > "$events_file" 2> "$errors_file"
```

JSON 事件包含 `sessionID`；保存并核对该值，用 `--session "$session_id"` 继续该具体会话，继续时仍传入相同 `--dir` 和 `--model`。不要用 `--continue` 代替具体会话 ID。等待进程退出并检查错误输出、JSON 事件和实际变更；事件中的模型回复和退出码不是验收证明。若无有效会话标识或恢复失败，保留证据并根据 skill 指示携带完整上下文开启新会话。

路径和参数应作为独立参数传递并正确引用；正文使用文件或标准输入，避免 shell 展开。`--auto` 会自动批准未明确拒绝的权限，仅当用户授权的执行范围和运行环境允许时使用；不得以此绕过授权。`--pure` 关闭外部插件，可在不影响任务能力时使用。遇到权限或交互阻塞时停止并报告，不要静默放宽权限。
