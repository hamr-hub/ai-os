# 引擎/模型交叉切换验收报告

日期：2026-05-14  
服务器：root@ubuntu.hamr.top:27144  
仓库：/root/ai-os  
控制器：http://127.0.0.1:35000  
验收目标：每次引擎或模型切换后，确认 OpenAI 兼容的 `/v1/models` 和 `/v1/chat/completions` 可访问并能正常对话。

## 验收前置

- 测试期间停止 `go-vllm-api`、`aiclient`、`nginx-30000`、`nginx`，避免外部入口自动切回默认 Gemma 模型。
- 保留 `ai-controller.service` 作为唯一编排入口。
- 切换异常后通过重启 controller 和清理残留推理进程恢复干净状态。
- chat 烟测统一使用短问题：`1+1 等于几？`，期望只返回 `2`。

## 本次配置调整

- `Qwen3.6-35B-A3B-NVFP4` 从 40K 长上下文验收参数收敛到 `max_model_len=8192`、`max_num_seqs=32`、`max_num_batched_tokens=4096`、`gpu_memory_utilization=0.75`。
- `settings.model_start_timeout` 从 `120` 提升到 `300`，避免 NVFP4 首次加载和 profiling 被启动窗口截断。
- `Qwen3.6-35B-A3B-Uncensored-GGUF-Q8` 改用 GGUF 内置 chat template，并设置 `chat_template_kwargs={"enable_thinking": false}`，避免强制 `chatml` 后输出思考标签。
- 新增 Qwen2.5 0.5B/1.5B 与 Qwen3 小模型配置，用于并发验收的独立端口和低显存参数。

## 切换结果

| 模型 | 引擎 | 端口 | 关键参数 | `/v1/models` | chat | 结论 |
|---|---:|---:|---|---|---|---|
| Gemma-4-31B-Abliterated | vLLM | 8000 | `max_model_len=40960`, `tool_call_parser=gemma4` | 200 | 返回 `你好` | 通过 |
| Qwen3.6-35B-A3B | SGLang | 8100 | `context_length=8192`, `disable_cuda_graph=true`, `chat_template_kwargs.enable_thinking=false` | 200 | 返回 `2`，约 9.34s | 通过 |
| Qwen3.6-35B-A3B-NVFP4 | vLLM | 8000 | `max_model_len=8192`, `moe_backend=cutlass`, `gpu_memory_utilization=0.75` | 200 | 返回 `2`，首次约 7.31s，复测约 1.22s | 通过 |
| Qwen3.6-35B-A3B-Uncensored | vLLM | 8001 | 原配置指向目录 | 未通过 | 未执行 | 失败：目录只有 GGUF 文件，无 `config.json` |
| Qwen3.6-35B-A3B-Uncensored-GGUF-Q8 | llama.cpp | 8200 | `n_batch=512`, `flash_attn=true`, `chat_template_kwargs.enable_thinking=false` | 200 | 返回 `2`，约 0.61s | 通过 |

## 发现的问题

- SGLang/Qwen 默认会暴露 thinking 风格内容，请求侧需要传 `chat_template_kwargs.enable_thinking=false`。
- NVFP4 模型在 vLLM 0.19 下首次加载和 profiling 超过 120 秒；不提高 `model_start_timeout` 会被误判为失败。
- `Qwen3.6-35B-A3B-Uncensored` 当前不能作为 vLLM HF 模型启动，因为 `/mnt/pve_models/Qwen3.6-35B-A3B-Uncensored` 仅包含 `.gguf` 权重。
- 控制器在端口占用或残留服务存在时可能分配动态端口，例如 vLLM Uncensored 返回 8001、llama.cpp 返回 8200；验收应以切换接口返回端口和 `/manage/engines/status` 为准。
- 外部入口服务恢复后会触发默认模型自动切换，受控验收时必须隔离这些服务。

## 结论

三类引擎均完成可对话验收：

- vLLM：Gemma 与 Qwen3.6 NVFP4 通过。
- SGLang：Qwen3.6 A3B 通过。
- llama.cpp：Qwen3.6 GGUF Q8 通过。

唯一未通过项是 `Qwen3.6-35B-A3B-Uncensored` 的 vLLM 配置，原因是模型路径与引擎类型不匹配，应改为 GGUF/llama.cpp 或补齐 HF 格式模型目录。
