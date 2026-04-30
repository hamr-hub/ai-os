# 任务计划: 多源下载+模型搜索+显存优选+引擎管理+模型池

> 基于 tech-solution.yaml 生成，来源: docs/tasks/model-hub/tech-solution.yaml

---

## P0 任务（核心模块，测试优先）

### T0-1: GPUMemoryManager 单元测试
- **文件**: `app-controller/tests/test_gpu_memory_manager.py`
- **验证**: get_gpu_info/estimate_model_memory/is_enough/check_model_feasibility
- **关键用例**: 4bit≈6GB/8bit≈9GB/fp16≈15GB + torch.cuda降级nvidia-smi

### P0-1: 实现 GPUMemoryManager → **依赖 T0-1**
- **文件**: `app-controller/core/gpu_memory_manager.py`
- **DoD**: torch.cuda精准检测+降级nvidia-smi+85%安全水位线+10种量化系数

### T0-2: MultiSourceModelHub 单元测试
- **文件**: `app-controller/tests/test_model_hub.py`
- **验证**: _parse_size/_parse_quant/search_models/download_model
- **关键用例**: 7B→7/235B→235 + 4bit/int4/awq/gptq量化解析

### P0-2: 实现 MultiSourceModelHub → **依赖 T0-2**
- **文件**: `app-controller/core/model_hub.py`
- **DoD**: HF/MS/OXL三平台搜索+下载+HF镜像+source=all聚合去重

### T0-3: DownloadTaskManager 单元测试
- **文件**: `app-controller/tests/test_download_manager.py`
- **验证**: create_task/get_status/cancel_task/磁盘校验

### P0-3: 实现 DownloadTaskManager → **依赖 T0-3**
- **文件**: `app-controller/core/download_manager.py`
- **DoD**: asyncio异步下载+磁盘85%告警95%终止+并发3限制+完成回调入库

### T0-4: ModelPoolManager 单元测试
- **文件**: `app-controller/tests/test_model_pool.py`
- **验证**: scan_and_sync/register/load/delete/sync_to_config

### P0-4: 实现 ModelPoolManager → **依赖 T0-4**
- **文件**: `app-controller/core/model_pool.py`
- **DoD**: 下载入库+搜索入库+本地扫描同步+一键加载+config双向同步

### T0-5: LLMServiceManager 单元测试
- **文件**: `app-controller/tests/test_llm_service_manager.py`
- **验证**: build_command(vLLM+SGLang)/stop_service优雅停止

### P0-5: 实现 LLMServiceManager → **依赖 T0-5**
- **文件**: `app-controller/core/llm_service_manager.py`
- **DoD**: subprocess.Popen进程管理+vLLM+SGLang命令构造+3次自动重启兜底

### T0-6: ModelEngineScheduler 单元测试
- **文件**: `app-controller/tests/test_model_engine_scheduler.py`
- **验证**: show_gpu/search/select_best_model/download_and_load/switch_engine

### P0-6: 实现 ModelEngineScheduler → **依赖 T0-6**
- **文件**: `app-controller/core/model_engine_scheduler.py`
- **DoD**: 统一调度入口+显存优选+搜索下载+模型池+引擎切换

---

## P1 任务（路由+集成+前端）

### P1-1: Python路由扩展 → **依赖 P0-6**
- **文件**: `app-controller/routes/manage.py`
- **11个新路由**: search/recommend/memory-check/download系列/pool系列

### P1-2: WebSocket /ws/download → **依赖 P0-3**
- **文件**: `app-controller/routes/websocket.py`

### P1-3: deps.py注册新模块 → **依赖 P0全部**
- **文件**: `app-controller/core/deps.py`

### P1-4: requirements.txt → **无依赖**
- **5个新依赖**: huggingface-hub/modelscope/openxlab/torch/psutil

### P1-5: config.yaml扩展 → **无依赖**
- engines/download配置段+模型engine_type/source字段

### P1-6: orchestrator Phase2.5 → **依赖 P0-1, P0-5**
- **文件**: `app-controller/core/model_switch_orchestrator.py`

### P1-7: scheduler调用Pool → **依赖 P0-4**
- **文件**: `app-controller/core/scheduler.py`

### P1-8: Go代理路由 → **依赖 P1-1**
- **文件**: `go-vllm-api/internal/handler/manage/manage.go`

### P1-9: Go config结构体 → **依赖 P1-5**
- **文件**: `go-vllm-api/internal/config/config.go`

### P1-10: 前端types+API → **依赖 P1-1**
- **文件**: `frontend/src/types/index.ts`, `frontend/src/api/client.ts`

### P1-11: 前端3个composables → **依赖 P1-10**

### P1-12: 前端7个组件 → **依赖 P1-11**

### P1-13: 前端2个页面+路由+侧边栏 → **依赖 P1-12**

---

## 测试命令
```bash
cd app-controller && python -m pytest tests/ -v
cd frontend && npx vue-tsc --noEmit
```

## 总计: 6个测试任务 + 6个P0代码任务 + 13个P1代码任务 = 25个任务
