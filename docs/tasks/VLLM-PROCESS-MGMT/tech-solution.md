# 技术方案: vLLM Python 进程管理替代 systemd

## 1. 背景 & 目标

当前项目存在两套 vLLM 引擎管理方式并存的问题：
- **systemd 方式**: `vllm_manager.py` + `scheduler.py` + `model_switch_orchestrator.py` + Go `scheduler.go` 全部通过 `systemctl start/stop/restart vllm-aiclient` 管理
- **subprocess 方式**: `llm_service_manager.py` + `model_engine_scheduler.py` 使用 `subprocess.Popen` 管理

问题:
1. vLLM 命令使用旧版 `python -m vllm.entrypoints.openai.api_server`，而非 vLLM v1 推荐的 `vllm serve`
2. systemd 依赖导致进程管理不够灵活（无法多引擎并行、环境变量注入受限）
3. start_vllm_aiclient.sh 的复杂环境变量配置无法动态注入
4. 两套方案并存增加维护负担

**目标**: 统一为 subprocess 进程管理模式，使用 `vllm serve` 命令，移除 systemd 依赖。

## 2. 范围 & 不做

**做**:
- 升级 vLLM 启动命令为 `vllm serve`
- 迁移 start_vllm_aiclient.sh 环境变量到 Python 配置注入
- 统一进程管理为 subprocess.Popen
- 进程健康检查和守护
- Go 后端适配（HTTP API 替代 systemctl）

**不做**:
- Docker/K8s 部署方式
- 前端 UI 变更
- vLLM 离线推理 Python API

## 3. 核心设计

### 3.1 vLLM 命令升级

| 项目 | 旧命令 | 新命令 |
|------|--------|--------|
| CLI | `python -m vllm.entrypoints.openai.api_server` | `vllm serve` |
| 模型指定 | `--model <path>` | 直接传入 `<path>` 作为 positional arg |
| Host | 默认绑定所有 | 需显式 `--host 0.0.0.0` |
| Attention | 不支持环境变量 | `VLLM_ATTENTION_BACKEND` 环境变量 |

`vllm serve` 是 vLLM v1 推荐的启动方式，自动支持 V1 engine 和聊天模板检测。

### 3.2 环境变量迁移

从 `start_vllm_aiclient.sh` 迁移到 `LLMServiceManager._build_vllm_env()`:

```python
VLLM_ENV_VARS = {
    "VLLM_USE_V1": "1",
    "NCCL_P2P_DISABLE": "1",
    "NCCL_SOCKET_REUSEPORT": "1",
    "NCCL_ASYNC_ERROR_HANDLING": "1",
    "NCCL_IB_DISABLE": "1",
    "CUDA_MANAGED_FORCE_DEVICE_ALLOC": "1",
    "OMP_NUM_THREADS": "16",
    "VLLM_NO_FLASHINFER": "1",
    "FLASHINFER_DISABLE": "1",
}
```

加上从 config.yaml 注入的: `HF_ENDPOINT`, `VLLM_ATTENTION_BACKEND` (per model).

### 3.3 进程生命周期

```
START:  Popen(cmd, env=env, stdout=log, stderr=log) → wait_for_ready(120s, /v1/models)
HEALTH: asyncio background task 每5s: poll() + http /v1/models
RESTART: SIGINT→wait(15s)→SIGKILL → start → wait_for_ready
STOP:   SIGINT → wait(15s) → SIGKILL → cleanup → GPU unregister
SWITCH: stop_old → GPU_unregister → sleep(3s) → start_new → wait_for_ready → GPU_register
```

### 3.4 进程守护

替代 systemd `Restart=always`，在 ModelEngineScheduler 中添加 asyncio 健康检查循环：

```python
async def _health_watcher_loop(self):
    while True:
        for name, svc in self._llm_mgr.list_services():
            if svc["status"] == "stopped" and svc.get("engine_type") == "vllm":
                # 进程异常退出，尝试自动重启
                if self._llm_mgr.get_restart_count(name) < 3:
                    self._llm_mgr.auto_restart(name)
        await asyncio.sleep(5)
```

### 3.5 Go 后端适配

Go `scheduler.go` 当前通过 `systemctl` 管理进程。改为通过 HTTP API 调用 Python 后端:

```go
// 旧: sysCtl.RestartService("vllm-aiclient")
// 新: callPythonAPI("POST", "/manage/engines/switch", body)
```

## 4. 方案流程图

```mermaid
flowchart TD
    A[用户/Go后端请求] --> B{操作类型}
    B -->|start| C[LLMServiceManager.start_service]
    B -->|stop| D[LLMServiceManager.stop_service]
    B -->|switch| E[ModelEngineScheduler.switch_engine]
    B -->|health| F[LLMServiceManager.check_health]
    
    C --> C1[_build_vllm_command: vllm serve]
    C --> C2[_build_vllm_env: 环境变量注入]
    C --> C3[subprocess.Popen]
    C3 --> C4[wait_for_ready: /v1/models]
    
    D --> D1[SIGINT]
    D --> D2{15s 内退出?}
    D2 -->|是| D3[cleanup]
    D2 -->|否| D4[SIGKILL]
    D4 --> D3
    
    E --> E1[stop existing service]
    E --> E2[GPU unregister]
    E --> E3[start new service]
    E --> E4[wait_for_ready]
    E --> E5[GPU register]
    
    F --> F1[process.poll() == None?]
    F --> F2[HTTP GET /v1/models == 200?]
```

## 5. 风险与验证

| 风险 | 等级 | 缓解策略 |
|------|------|----------|
| vLLM worker 子进程不跟随 SIGINT | P0 | stop_service 使用 process group kill (os.killpg) |
| GPU 显存未释放 | P0 | 增加强制清理: killpg + sleep + nvidia-smi 验证 |
| 进程僵尸/泄漏 | P1 | 健康检查循环 + cleanup_all on shutdown |
| vllm serve 命令兼容性 | P1 | 保留 fallback 到 python -m 入口 |
| Go 后端 API 调用失败 | P1 | Go 侧增加 fallback 到 systemctl |

## 6. 待确认项

- vLLM venv 路径是否需要动态配置 (当前硬编码 /root/ai-suite/vllm_env)
- Go 后端是否需要保留 systemctl fallback
- 多 GPU 场景下 CUDA_VISIBLE_DEVICES 如何注入
