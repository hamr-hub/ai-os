# 模型下载与测评报告

日期：2026-05-14  
范围：3B 以下小模型下载、参数配置、并发部署、OpenAI chat 接口验收。

## 下载验收

| 模型 | 来源 | task_id | 本地路径 | 权重文件 | 状态 |
|---|---|---|---|---:|---|
| Qwen/Qwen2.5-0.5B-Instruct | ModelScope | `99a9920d-a54` | `/mnt/pve_models/Qwen2.5-0.5B-Instruct` | `model.safetensors` 988,097,824 bytes | completed |
| Qwen/Qwen2.5-1.5B-Instruct | ModelScope | `363fa559-21a` | `/mnt/pve_models/Qwen2.5-1.5B-Instruct` | `model.safetensors` 3,087,467,144 bytes | completed |

说明：两个模型参数量均小于 3B。1.5B 权重约 2.88 GiB，仍低于 3 GiB。

## 小模型参数

| 模型 | 端口 | vLLM 参数 | 设计目的 |
|---|---:|---|---|
| Qwen2.5-0.5B-Instruct | 8112 | `gpu_memory_utilization=0.12`, `max_model_len=4096`, `max_num_seqs=8`, `max_num_batched_tokens=2048` | 极小文本模型，低显存常驻 |
| Qwen2.5-1.5B-Instruct | 8113 | `gpu_memory_utilization=0.16`, `max_model_len=4096`, `max_num_seqs=8`, `max_num_batched_tokens=2048` | 小文本模型，并发常驻 |
| Qwen3-0.6B | 8110 | 同 0.5B 级别低显存参数 | 预留并发槽位 |
| Qwen3-VL-2B-Instruct | 8111 | `gpu_memory_utilization=0.18`, `max_num_seqs=4` | 预留多模态小模型槽位 |

注：本次实际并发运行使用两个通过下载接口落盘且权重完整的 Qwen2.5 模型。

## 并发运行验收

部署接口：`POST /manage/hub/deploy`

| 模型 | 端口 | controller 状态 | `/v1/models` | chat 复测 | 结论 |
|---|---:|---|---|---|---|
| Qwen2.5-0.5B-Instruct | 8112 | healthy | 200，模型 id 为本地路径 | 返回 `2`，约 0.03s | 通过 |
| Qwen2.5-1.5B-Instruct | 8113 | healthy | 200，模型 id 为本地路径 | 返回 `2`，约 0.03s | 通过 |

并发状态：

- controller `running_count=2`。
- 运行服务：`vllm-Qwen2.5-0.5B-Instruct`、`vllm-Qwen2.5-1.5B-Instruct`。
- GPU 记录加载模型：`Qwen2.5-0.5B-Instruct`、`Qwen2.5-1.5B-Instruct`。
- controller 估算 loaded memory：8GB；`nvidia-smi` 实际进程显存约 12GB + 16GB。

## 测评观察

- 两个小模型首次部署后均能立即通过 `/v1/models`，证明多实例端口和健康检查正常。
- 首轮 chat 在并发启动窗口内出现过 60 秒客户端超时；服务保持 healthy。随后用 `max_tokens=1` 和短 prompt 复测，两个 `/v1/chat/completions` 均快速返回 `2`。
- 0.5B completion 约 0.06s；1.5B completion 首次约 10.01s，chat 复测约 0.03s。
- 下载接口的任务列表能正确记录 completed 和 local_path；本次未发现最终权重缺失。

## 建议

- 小模型并发验收时先等待两个服务都 healthy，再执行 chat，可避免部署刚完成时的首轮请求超时。
- 将低显存参数保留在模型级配置中，避免小模型沿用全局 `gpu_memory_utilization=0.92`。
- 对 Qwen3 系列 thinking 模型统一在请求侧或模型参数侧明确 `enable_thinking=false`，保证验收输出稳定。
