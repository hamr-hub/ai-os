ENGINE_PARAM_SCHEMA = {
    "vllm": {
        "groups": [
            {
                "name": "核心参数",
                "params": [
                    {"key": "gpu_memory_utilization", "type": "float", "default": 0.9, "min": 0.1, "max": 0.99, "description": "GPU显存利用率", "cli_arg": "--gpu-memory-utilization"},
                    {"key": "max_model_len", "type": "int", "default": 32768, "min": 512, "description": "最大模型上下文长度", "cli_arg": "--max-model-len"},
                    {"key": "max_num_seqs", "type": "int", "default": 256, "min": 1, "description": "最大并发序列数", "cli_arg": "--max-num-seqs"},
                    {"key": "max_num_batched_tokens", "type": "int", "default": 16384, "min": 1, "description": "最大批量token数", "cli_arg": "--max-num-batched-tokens"},
                    {"key": "tensor_parallel_size", "type": "int", "default": 1, "min": 1, "description": "张量并行度(多GPU)", "cli_arg": "--tensor-parallel-size"},
                ],
            },
            {
                "name": "模型加载",
                "params": [
                    {"key": "dtype", "type": "str", "default": "auto", "choices": ["auto", "float16", "bfloat16", "float32"], "description": "模型数据类型", "cli_arg": "--dtype"},
                    {"key": "quantization", "type": "str", "default": None, "choices": ["awq", "gptq", "fp8", "bitsandbytes", "gguf", None], "description": "量化方法", "cli_arg": "--quantization"},
                    {"key": "load_format", "type": "str", "default": "auto", "choices": ["auto", "pt", "safetensors", "npcache", "dummy", "gguf"], "description": "模型加载格式", "cli_arg": "--load-format"},
                    {"key": "trust_remote_code", "type": "bool", "default": False, "description": "允许远程代码执行", "cli_arg": "--trust-remote-code"},
                    {"key": "revision", "type": "str", "default": None, "description": "模型版本/分支", "cli_arg": "--revision"},
                ],
            },
            {
                "name": "性能优化",
                "params": [
                    {"key": "enable_chunked_prefill", "type": "bool", "default": True, "description": "分块预填充", "cli_arg": "--enable-chunked-prefill"},
                    {"key": "enable_prefix_caching", "type": "bool", "default": False, "description": "前缀缓存(降低重复prompt延迟)", "cli_arg": "--enable-prefix-caching"},
                    {"key": "swap_space", "type": "int", "default": 4, "min": 0, "description": "CPU交换空间大小(GB)", "cli_arg": "--swap-space"},
                    {"key": "enforce_eager", "type": "bool", "default": False, "description": "强制eager模式(禁用CUDA graph)", "cli_arg": "--enforce-eager"},
                    {"key": "kv_cache_dtype", "type": "str", "default": "auto", "choices": ["auto", "fp8_e5m2", "fp8_e4m3"], "description": "KV缓存数据类型", "cli_arg": "--kv-cache-dtype"},
                ],
            },
            {
                "name": "功能开关",
                "params": [
                    {"key": "tool_call_parser", "type": "str", "default": None, "choices": ["hermes", "mistral", "gemma4", "qwen", None], "description": "工具调用解析器", "cli_arg": "--tool-call-parser"},
                    {"key": "enable_tool_call", "type": "bool", "default": False, "description": "启用工具调用", "cli_arg": "--enable-tool-call"},
                    {"key": "limit_mm_per_prompt", "type": "int", "default": 10, "min": 1, "description": "每prompt多模态内容限制", "cli_arg": "--limit-mm-per-prompt"},
                    {"key": "served_model_name", "type": "str", "default": None, "description": "服务模型别名", "cli_arg": "--served-model-name"},
                    {"key": "download_dir", "type": "str", "default": None, "description": "模型下载目录", "cli_arg": "--download-dir"},
                ],
            },
            {
                "name": "注意力后端",
                "params": [
                    {"key": "attention_backend", "type": "str", "default": None, "choices": ["FLASH_ATTN", "TRITON_ATTN", "XFORMERS_ATTN", None], "description": "注意力计算后端", "cli_arg": "--attention-backend"},
                ],
            },
            {
                "name": "LoRA",
                "params": [
                    {"key": "enable_lora", "type": "bool", "default": False, "description": "启用LoRA适配器", "cli_arg": "--enable-lora"},
                    {"key": "max_loras", "type": "int", "default": 1, "min": 1, "description": "最大LoRA数量", "cli_arg": "--max-loras"},
                    {"key": "max_lora_rank", "type": "int", "default": 16, "min": 1, "description": "最大LoRA秩", "cli_arg": "--max-lora-rank"},
                ],
            },
        ],
    },
    "sglang": {
        "groups": [
            {
                "name": "核心参数",
                "params": [
                    {"key": "mem_fraction_static", "type": "float", "default": 0.9, "min": 0.1, "max": 0.99, "description": "GPU静态显存分配比例(等价vllm gpu_memory_utilization)", "cli_arg": "--mem-fraction-static"},
                    {"key": "context_length", "type": "int", "default": None, "min": 512, "description": "最大上下文长度(None=从模型config读取)", "cli_arg": "--context-length"},
                    {"key": "tp_size", "type": "int", "default": 1, "min": 1, "description": "张量并行度", "cli_arg": "--tp"},
                    {"key": "dp_size", "type": "int", "default": 1, "min": 1, "description": "数据并行度", "cli_arg": "--dp-size"},
                ],
            },
            {
                "name": "HTTP服务",
                "params": [
                    {"key": "host", "type": "str", "default": "0.0.0.0", "description": "服务监听地址", "cli_arg": "--host"},
                    {"key": "port", "type": "int", "default": 30000, "min": 1, "max": 65535, "description": "服务监听端口", "cli_arg": "--port"},
                    {"key": "served_model_name", "type": "str", "default": None, "description": "服务模型别名", "cli_arg": "--served-model-name"},
                ],
            },
            {
                "name": "模型加载",
                "params": [
                    {"key": "trust_remote_code", "type": "bool", "default": False, "description": "允许远程代码执行", "cli_arg": "--trust-remote-code"},
                    {"key": "load_format", "type": "str", "default": "auto", "choices": ["auto", "pt", "safetensors", "npcache", "dummy", "gguf", "bitsandbytes", "fastsafetensors"], "description": "模型加载格式", "cli_arg": "--load-format"},
                    {"key": "dtype", "type": "str", "default": "auto", "choices": ["auto", "float16", "bfloat16", "float32"], "description": "模型数据类型", "cli_arg": "--dtype"},
                    {"key": "quantization", "type": "str", "default": None, "choices": ["awq", "fp8", "gptq", "marlin", "bitsandbytes", "gguf", "modelopt", None], "description": "量化方法", "cli_arg": "--quantization"},
                    {"key": "kv_cache_dtype", "type": "str", "default": "auto", "choices": ["auto", "fp8_e5m2", "fp8_e4m3", "bf16"], "description": "KV缓存数据类型", "cli_arg": "--kv-cache-dtype"},
                    {"key": "revision", "type": "str", "default": None, "description": "模型版本/分支", "cli_arg": "--revision"},
                    {"key": "is_embedding", "type": "bool", "default": False, "description": "是否为嵌入模型", "cli_arg": "--is-embedding"},
                ],
            },
            {
                "name": "调度与内存",
                "params": [
                    {"key": "max_running_requests", "type": "int", "default": None, "min": 1, "description": "最大同时运行请求数", "cli_arg": "--max-running-requests"},
                    {"key": "max_total_tokens", "type": "int", "default": None, "min": 1, "description": "最大总token预算", "cli_arg": "--max-total-tokens"},
                    {"key": "chunked_prefill_size", "type": "int", "default": None, "description": "分块预填充大小(-1禁用,0自动)", "cli_arg": "--chunked-prefill-size"},
                    {"key": "schedule_policy", "type": "str", "default": "fcfs", "choices": ["fcfs", "priority", "random", "dfs"], "description": "调度策略", "cli_arg": "--schedule-policy"},
                    {"key": "page_size", "type": "int", "default": None, "description": "KV缓存页面大小", "cli_arg": "--page-size"},
                ],
            },
            {
                "name": "性能优化",
                "params": [
                    {"key": "disable_radix_cache", "type": "bool", "default": False, "description": "禁用Radix树缓存(SGLang核心优化)", "cli_arg": "--disable-radix-cache"},
                    {"key": "disable_overlap_schedule", "type": "bool", "default": False, "description": "禁用重叠调度(批处理优化)", "cli_arg": "--disable-overlap-schedule"},
                    {"key": "enable_torch_compile", "type": "bool", "default": False, "description": "启用torch.compile加速", "cli_arg": "--enable-torch-compile"},
                    {"key": "disable_cuda_graph", "type": "bool", "default": False, "description": "禁用CUDA graph", "cli_arg": "--disable-cuda-graph"},
                    {"key": "enable_prefix_caching", "type": "bool", "default": False, "description": "启用前缀缓存(通过Radix树)", "cli_arg": None, "note": "SGLang默认启用Radix缓存"},
                ],
            },
            {
                "name": "功能开关",
                "params": [
                    {"key": "tool_call_parser", "type": "str", "default": None, "choices": ["qwen", "glm", "hermes", "pythonic", None], "description": "工具调用解析器", "cli_arg": "--tool-call-parser"},
                    {"key": "enable_multimodal", "type": "bool", "default": None, "description": "启用多模态(None=自动检测)", "cli_arg": "--enable-multimodal"},
                    {"key": "reasoning_parser", "type": "str", "default": None, "description": "思维链解析器", "cli_arg": "--reasoning-parser"},
                    {"key": "watchdog_timeout", "type": "float", "default": 300, "min": 10, "description": "看门狗超时(秒)", "cli_arg": "--watchdog-timeout"},
                    {"key": "skip_server_warmup", "type": "bool", "default": False, "description": "跳过服务预热", "cli_arg": "--skip-server-warmup"},
                ],
            },
            {
                "name": "日志与监控",
                "params": [
                    {"key": "log_level", "type": "str", "default": "info", "choices": ["debug", "info", "warning", "error", "critical"], "description": "日志级别", "cli_arg": "--log-level"},
                    {"key": "enable_metrics", "type": "bool", "default": False, "description": "启用Prometheus指标", "cli_arg": "--enable-metrics"},
                    {"key": "download_dir", "type": "str", "default": None, "description": "模型下载目录", "cli_arg": "--download-dir"},
                ],
            },
            {
                "name": "LoRA",
                "params": [
                    {"key": "enable_lora", "type": "bool", "default": None, "description": "启用LoRA适配器", "cli_arg": "--enable-lora"},
                    {"key": "max_lora_rank", "type": "int", "default": None, "description": "最大LoRA秩", "cli_arg": "--max-lora-rank"},
                    {"key": "max_loras_per_batch", "type": "int", "default": 8, "min": 1, "description": "每批最大LoRA数", "cli_arg": "--max-loras-per-batch"},
                    {"key": "lora_paths", "type": "str", "default": None, "description": "LoRA路径(JSON或逗号分隔)", "cli_arg": "--lora-paths"},
                ],
            },
        ],
    },
    "llamacpp": {
        "groups": [
            {
                "name": "核心参数",
                "params": [
                    {"key": "n_gpu_layers", "type": "int", "default": -1, "description": "GPU层数(-1=全部)", "cli_arg": "-ngl"},
                    {"key": "ctx_size", "type": "int", "default": 4096, "min": 128, "description": "上下文窗口大小", "cli_arg": "-c"},
                    {"key": "n_threads", "type": "int", "default": None, "description": "CPU线程数(None=自动)", "cli_arg": "-t"},
                    {"key": "batch_size", "type": "int", "default": 512, "min": 1, "description": "批处理大小", "cli_arg": "-b"},
                ],
            },
            {
                "name": "服务配置",
                "params": [
                    {"key": "host", "type": "str", "default": "0.0.0.0", "description": "监听地址", "cli_arg": "--host"},
                    {"key": "port", "type": "int", "default": 8200, "min": 1, "max": 65535, "description": "监听端口", "cli_arg": "--port"},
                    {"key": "flash_attn", "type": "bool", "default": False, "description": "启用Flash Attention", "cli_arg": "--flash-attn"},
                    {"key": "mlock", "type": "bool", "default": False, "description": "锁定模型在内存中", "cli_arg": "--mlock"},
                    {"key": "no_mmap", "type": "bool", "default": False, "description": "禁用mmap加载", "cli_arg": "--no-mmap"},
                ],
            },
            {
                "name": "采样参数(服务端默认)",
                "params": [
                    {"key": "temp", "type": "float", "default": 0.8, "min": 0, "max": 2, "description": "默认采样温度", "cli_arg": "--temp"},
                    {"key": "top_k", "type": "int", "default": 40, "min": 1, "description": "Top-K采样", "cli_arg": "--top-k"},
                    {"key": "top_p", "type": "float", "default": 0.95, "min": 0, "max": 1, "description": "Top-P采样", "cli_arg": "--top-p"},
                    {"key": "repeat_penalty", "type": "float", "default": 1.1, "min": 1, "max": 2, "description": "重复惩罚系数", "cli_arg": "--repeat-penalty"},
                ],
            },
            {
                "name": "功能开关",
                "params": [
                    {"key": "embedding", "type": "bool", "default": False, "description": "启用嵌入模式", "cli_arg": "--embedding"},
                    {"key": "metrics", "type": "bool", "default": False, "description": "启用指标端点", "cli_arg": "--metrics"},
                    {"key": "alias", "type": "str", "default": None, "description": "模型别名", "cli_arg": "--alias"},
                ],
            },
        ],
    },
}
