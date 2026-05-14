# 引擎切换加载测试报告

日期：2026-05-14  
服务器：root@ubuntu.hamr.top:27144  
仓库：/root/ai-os  
结果文件：`/tmp/aios_engine_load_test_20260514_051027.json`

## 测试方式

- 测试前停止 `go-vllm-api`、`aiclient`、`nginx-30000`、`nginx`，避免自动切回默认模型。
- 每个实际加载项测试前清理 `vllm serve`、`sglang.launch_server`、`llama-server` 残留进程，并重启 `ai-controller.service`。
- 通过 `/manage/engines/switch` 切换模型和引擎。
- 以 `/v1/models` 返回 200 作为加载成功标准。
- 加载成功后执行 `/v1/chat/completions`，提示词为 `1+1`，期望输出 `2`。

## 结果总览

- 配置模型总数：16
- 加载成功并可对话：6
- 预检失败，未实际启动：7
- 启动或切换失败：3

## 加载成功

| 模型 | 引擎 | 端口 | `/v1/models` 就绪耗时 | chat 结果 | 结论 |
|---|---|---:|---:|---|---|
| Gemma-4-31B-Abliterated | vLLM | 8000 | 178.6s | `2`，0.38s | 通过 |
| Qwen3.6-35B-A3B | SGLang | 8100 | 124.0s | `2`，26.55s | 通过 |
| Qwen3.6-35B-A3B-NVFP4 | vLLM | 8000 | 262.3s | `2`，7.24s | 通过 |
| Qwen2.5-0.5B-Instruct | vLLM | 8000 | 40.1s | 首轮 120s 超时；单独复测 `2`，0.23s | 通过，需二次复测确认 |
| Qwen2.5-1.5B-Instruct | vLLM | 8000 | 40.1s | `2`，0.35s | 通过 |
| Qwen3.6-35B-A3B-Uncensored-GGUF-Q8 | llama.cpp | 8200 | 50.2s | `2`，0.50s | 通过 |

## 未加载成功

| 模型 | 引擎 | 阶段 | 原因 |
|---|---|---|---|
| llama-3.3-70b-exl2-6_5 | vLLM | 启动失败 | vLLM 0.19 报错：`Unknown quantization method: exl2` |
| llama-3.3-70b-exl2-8_0 | vLLM | 切换失败 | 控制器返回 `409 insufficient_gpu_memory` |
| qwen2.5-72b-exl2-8_0 | vLLM | 切换失败 | 控制器返回 `409 insufficient_gpu_memory` |
| Qwen3-0.6B | vLLM | 预检失败 | 本地目录缺少权重文件 |
| Qwen3-VL-2B-Instruct | vLLM | 预检失败 | 本地目录缺少权重文件 |
| Qwen3.6-35B-A3B-Uncensored | vLLM | 预检失败 | 目录缺少 `config.json`，不是 HF 格式；实际只有 GGUF 权重 |
| Qwen3-235B-A22B-Instruct-2507-AWQ | vLLM | 预检失败 | `required_memory=120GB`，超过 GPU 95.59GB |
| midnight-miqu-103b-5.0bpw | vLLM | 预检失败 | `required_memory=100GB`，超过 GPU 95.59GB |
| llama-3.3-70b-8.0bpw | vLLM | 预检失败 | 目录缺少 `config.json`，不是 HF 格式 |
| llama-3.3-70b-abliterated-gguf | vLLM | 预检失败 | 目录缺少 `config.json`，当前配置为 vLLM，不适配 GGUF 目录 |

## 结论

当前不是所有模型都能加载成功。可稳定切换并加载成功的是 Gemma、Qwen3.6 SGLang、Qwen3.6 NVFP4、Qwen2.5 0.5B/1.5B、Qwen3.6 GGUF/llama.cpp。

需要修复的方向：

- 给 `Qwen3-0.6B`、`Qwen3-VL-2B-Instruct` 补齐本地权重文件后再测。
- 将 GGUF 目录类模型改为 llama.cpp 配置，或补齐 HF 格式目录。
- EXL2 模型不能直接用当前 vLLM 0.19 加载；需要换支持 EXL2 的引擎，或转换为 vLLM 支持的量化格式。
- 80GB 级模型触发显存校验失败，需要降低上下文/并发/KV 配置，或使用更大显存/多卡策略。
