# 技术方案: 多源下载+模型搜索+显存优选+引擎管理+模型池

> ai-os 功能点14-18 技术设计与落地方案

---

## 1. 方案概述

### 1.1 需求范围

| 功能点 | 描述 | 优先级 |
|--------|------|--------|
| FP14: 多引擎支持 | vLLM+SGLang双引擎+动态切换+显存校验 | P1 |
| FP15: 多源模型下载 | HF/ModelScope/OpenXLab+断点续传+进度追踪 | P1 |
| FP16: 跨平台模型搜索 | 关键词搜索+自动解析参数量化+显存估算 | P1 |
| FP17: GPU显存智能优选 | 实时显存检测+自动筛选+推荐最优模型+一键下载加载 | P1 |
| FP18: 模型池统一管理 | 自动入库+统一查询+一键加载+配置同步 | P1 |

### 1.2 架构定位

新增功能全部在 **Python B端 (app-controller)** 实现，Go网关仅代理转发新增API。前端新增模型搜索/下载/显存优选页面。

```
前端新增页面 → Python新增路由 → Python新增核心模块 → 3大模型平台SDK
                    ↓                    ↓
              Go代理转发            torch.cuda / subprocess.Popen
```

### 1.3 与现有模块的关系

| 现有模块 | 关系 | 变更 |
|----------|------|------|
| `scheduler.py` | 调度入口 | 调用`ModelPoolManager`获取模型信息 |
| `model_switch_orchestrator.py` | 切换编排 | Phase2.5增加显存校验; 调用`LLMServiceManager` |
| `vllm_manager.py` | 模型扫描 | 保留扫描功能, 进程管理迁移到`LLMServiceManager` |
| `monitor.py` | GPU监控 | 补充`GPUMemoryChecker`精准检测 |
| `sys_ctl.py` | systemd控制 | 重构后被`LLMServiceManager`替代 |
| `routes/manage.py` | 管理路由 | 新增搜索/下载/模型池/显存优选路由 |

---

## 2. 核心模块设计

### 2.1 GPUMemoryManager — GPU显存智能管理器

**文件**: `app-controller/core/gpu_memory_manager.py`

```python
class GPUMemoryManager:
    """GPU显存精准检测+模型显存估算+显存优选推荐"""

    QUANT_COEFFICIENTS = {
        "4bit": 0.7, "int4": 0.7, "awq": 0.75, "gptq": 0.75,
        "8bit": 1.1, "int8": 1.1,
        "fp16": 2.0, "bf16": 2.0, "fp32": 4.0,
    }
    SAFETY_MARGIN_GB = 1.0

    @staticmethod
    def get_gpu_info() -> Dict[str, float]:
        """实时GPU显存(GB), 优先torch.cuda, 降级nvidia-smi"""
        # torch.cuda.mem_get_info() → (free, total)
        # 降级: subprocess nvidia-smi解析

    @staticmethod
    def estimate_model_memory(model_size_b: int, quant: str = "fp16") -> float:
        """自动估算模型显存需求(GB)"""
        # model_size_b × quant_coefficient + SAFETY_MARGIN_GB

    @staticmethod
    def is_enough(required_gb: float) -> bool:
        """检查可用显存是否足够"""
        # free >= required_gb

    @staticmethod
    def check_model_feasibility(required_gb: float) -> Dict:
        """模型显存可行性校验"""
        # {feasible, available, required, safety_margin, suggested_models}
```

**关键设计决策**:
- torch.cuda优先: 精准误差<5%, 不可用时降级nvidia-smi
- 85%安全水位线: `required < available * 0.85`才允许启动
- 可行性校验失败时返回建议可运行模型列表

### 2.2 MultiSourceModelHub — 多源模型仓库管理器

**文件**: `app-controller/core/model_hub.py`

```python
class MultiSourceModelHub:
    """HuggingFace / ModelScope / OpenXLab 三大平台搜索+下载"""

    def __init__(self, save_root: str = "/mnt/pve_models"):
        self.save_root = save_root
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    async def search_models(self, keyword: str, source: str = "modelscope", limit: int = 20) -> List[Dict]:
        """跨平台搜索模型, 返回{name, source, path, size_b, quant, required_gb, feasible}"""
        # source="all"时聚合3平台结果去重

    async def download_model(self, model_info: Dict, task_id: str) -> str:
        """多源下载模型, 返回本地路径"""
        # HF: snapshot_download(model_name, local_dir=..., resume_download=True)
        # MS: ms_snapshot_download(model_name, cache_dir=...)
        # OXL: oxl_model.download(model_name, output_dir=...)
        # 进度回调 → WebSocket广播

    @staticmethod
    def _parse_size(name: str) -> int:
        """从模型名解析参数大小(7B→7, 8B→8, 13B→13, 72B→72, 235B→235)"""

    @staticmethod
    def _parse_quant(name: str) -> str:
        """从模型名解析量化类型(4bit/int4/8bit/int8/fp16/awq/gptq/gguf)"""
```

**关键设计决策**:
- ModelScope首选: 国内速度最快, 无需代理
- HF国内镜像: `HF_ENDPOINT=https://hf-mirror.com` 自动加速
- 断点续传: `resume_download=True` 中断后自动续传
- 异步下载: asyncio Task + WebSocket进度推送
- 磁盘空间前置校验: 预估模型大小 vs 可用磁盘

### 2.3 DownloadTaskManager — 下载任务管理器

**文件**: `app-controller/core/download_manager.py`

```python
class DownloadTaskManager:
    """下载任务生命周期管理: 创建/进度/取消/完成回调"""

    def __init__(self, hub: MultiSourceModelHub, pool: ModelPoolManager):
        self.hub = hub
        self.pool = pool
        self.tasks: Dict[str, DownloadTask] = {}  # task_id → DownloadTask

    async def create_task(self, model_info: Dict, save_dir: str = None) -> str:
        """创建下载任务, 返回task_id"""
        # 1. 磁盘空间校验(预估大小 vs 可用)
        # 2. 检查模型是否已存在(跳过下载)
        # 3. 创建DownloadTask对象, asyncio.create_task执行

    async def get_status(self, task_id: str) -> Dict:
        """查询下载进度{task_id, status, progress_pct, speed_mbps, eta_seconds, downloaded_bytes, total_bytes}"""

    async def cancel_task(self, task_id: str) -> bool:
        """取消下载任务"""

    async def list_tasks(self) -> List[Dict]:
        """列出所有下载任务(含历史)"""

    def _on_download_complete(self, task_id: str, local_path: str):
        """下载完成回调: 1.注册到model_pool 2.更新config.yaml 3.广播完成事件"""
```

**关键设计决策**:
- asyncio Task: 异步下载不阻塞主线程
- 进度追踪: HF/MS SDK自带进度回调, 定期广播到WebSocket
- 磁盘水位: 85%告警, 95%终止下载
- 完成回调: 自动入库+配置更新+前端通知

### 2.4 ModelPoolManager — 模型池统一管理器

**文件**: `app-controller/core/model_pool.py`

```python
class ModelPoolManager:
    """模型池: 下载模型+本地扫描模型统一管理"""

    def __init__(self, model_base_path: str = "/mnt/pve_models"):
        self.model_base_path = model_base_path
        self.pool: Dict[str, ModelPoolEntry] = {}  # model_key → ModelPoolEntry

    async def scan_and_sync(self) -> None:
        """扫描本地模型目录, 同步到pool(与vllm_manager.ScanModels协调)"""

    async def register_from_download(self, model_info: Dict, local_path: str) -> str:
        """下载模型自动注册到pool"""

    async def register_from_search(self, model_info: Dict) -> str:
        """搜索结果注册到pool(仅元信息, 未下载)"""

    def get_pool_list(self) -> List[Dict]:
        """返回全部模型池列表"""

    def get_model_detail(self, model_key: str) -> Dict:
        """返回单模型详情(含来源/大小/量化/显存/本地路径/下载状态)"""

    async def load_model(self, model_key: str, engine: str = "vllm") -> Dict:
        """从模型池一键加载: 显存校验 → LLMServiceManager启动 → 验证就绪"""

    async def delete_model(self, model_key: str, remove_files: bool = False) -> bool:
        """从模型池删除(校验运行状态, 可选删除本地文件)"""

    async def sync_to_config(self) -> None:
        """模型池变更同步到config.yaml"""
```

**数据模型**:
```python
class ModelPoolEntry:
    model_key: str          # Qwen2.5-7B-Instruct
    name: str               # 原始模型名(Qwen/Qwen2.5-7B-Instruct)
    source: str             # local / hf / ms / oxl
    local_path: str         # /mnt/pve_models/Qwen2.5-7B-Instruct
    size_b: int             # 参数大小(7)
    quant: str              # fp16 / 4bit / 8bit / gguf
    required_gb: float      # 估算显存需求
    downloaded: bool        # 是否已下载到本地
    download_task_id: str   # 关联下载任务ID(未完成时)
    registered_at: float    # 注册时间戳
    is_running: bool        # 当前是否正在运行
```

### 2.5 LLMServiceManager — 统一引擎进程管理器

**文件**: `app-controller/core/llm_service_manager.py` (已在PRD第8节定义)

```python
class LLMServiceManager:
    """统一管理 vLLM / SGLang 进程生命周期"""

    def start_service(self, engine_type: str, model_path: str, port: int, params: dict) -> subprocess.Popen:
        """启动引擎进程"""
        # vLLM: python -m vllm.entrypoints.openai.api_server --model <path> --port <port> ...
        # SGLang: python -m sglang.launch_server --model-path <path> --port <port> ...

    def stop_service(self, process: subprocess.Popen, timeout: int = 30) -> bool:
        """停止引擎进程(优雅→强制)"""
        # SIGINT → 10s等待 → SIGKILL

    def restart_service(self, ...) -> subprocess.Popen:
        """重启引擎进程"""

    def get_service_status(self) -> dict:
        """查询引擎运行状态{engine_type, pid, port, model, uptime, health}"""

    def build_command(self, engine_type: str, model_path: str, port: int, params: dict) -> list[str]:
        """构造引擎启动命令"""
        # 引擎类型→参数模板映射
```

### 2.6 ModelEngineScheduler — 终极调度中心

**文件**: `app-controller/core/model_engine_scheduler.py`

```python
class ModelEngineScheduler:
    """统一调度: 显存优选 + 搜索下载 + 模型池 + 引擎切换"""

    def __init__(self, port: int = 8000):
        self.gpu = GPUMemoryManager()
        self.hub = MultiSourceModelHub()
        self.pool = ModelPoolManager()
        self.download_mgr = DownloadTaskManager(self.hub, self.pool)
        self.service = LLMServiceManager()
        self.current_engine = "vllm"

    def show_gpu(self) -> Dict:
        """显示GPU显存状态"""

    async def search(self, keyword: str, source: str = "modelscope") -> List[Dict]:
        """搜索模型, 附带显存可行性标注"""

    async def select_best_model(self, keyword: str, source: str = "modelscope") -> Optional[Dict]:
        """显存自动优选: 过滤显存不足 → 按模型大小降序 → 推荐最大可运行模型"""

    async def download_and_load(self, model_info: Dict, engine: str = "vllm") -> Dict:
        """下载模型并加载到引擎: 下载 → 入库 → 显存校验 → 启动引擎 → 验证"""

    async def switch_engine(self, engine: str) -> Dict:
        """切换推理引擎(vLLM ↔ SGLang): 停止旧引擎 → 显存校验 → 启动新引擎 → 验证"""
```

---

## 3. API设计

### 3.1 新增路由 (routes/manage.py扩展)

```python
# 模型搜索
@router.get("/models/search")
async def search_models(keyword: str, source: str = "modelscope", limit: int = 20):
    """跨平台搜索模型, 结果含显存估算和可行性"""

# 显存优选推荐
@router.get("/gpu/recommend")
async def recommend_model(keyword: str, source: str = "modelscope"):
    """根据显存自动推荐最优模型"""

# 显存校验
@router.post("/gpu/memory-check/{model_name}")
async def check_model_memory(model_name: str):
    """指定模型显存可行性校验"""

# 模型下载
@router.post("/models/download")
async def start_download(model_name: str, source: str, save_dir: str = None):
    """启动下载任务, 返回task_id"""

@router.get("/models/download/{task_id}/status")
async def download_status(task_id: str):
    """查询下载进度"""

@router.delete("/models/download/{task_id}")
async def cancel_download(task_id: str):
    """取消下载任务"""

@router.get("/models/downloads")
async def list_downloads():
    """列出所有下载任务"""

# 模型池
@router.get("/models/pool")
async def pool_list():
    """模型池列表"""

@router.get("/models/pool/{model_key}")
async def pool_detail(model_key: str):
    """模型池单模型详情"""

@router.post("/models/pool/{model_key}/load")
async def pool_load(model_key: str, engine: str = "vllm"):
    """一键加载: 显存校验→引擎启动→验证"""

@router.delete("/models/pool/{model_key}")
async def pool_delete(model_key: str, remove_files: bool = False):
    """从模型池删除"""
```

### 3.2 Go网关代理 (go-vllm-api handler/manage.go扩展)

新增路由代理转发到Python:
```go
// 模型搜索与下载系列(代理到Python)
manageGroup.GET("/models/search", proxyPythonManage)
manageGroup.GET("/gpu/recommend", proxyPythonManage)
manageGroup.POST("/gpu/memory-check/:model", proxyPythonManage)
manageGroup.POST("/models/download", proxyPythonManage)
manageGroup.GET("/models/download/:task_id/status", proxyPythonManage)
manageGroup.DELETE("/models/download/:task_id", proxyPythonManage)
manageGroup.GET("/models/downloads", proxyPythonManage)
manageGroup.GET("/models/pool", proxyPythonManage)
manageGroup.GET("/models/pool/:model_key", proxyPythonManage)
manageGroup.POST("/models/pool/:model_key/load", proxyPythonManage)
manageGroup.DELETE("/models/pool/:model_key", proxyPythonManage)
```

### 3.3 WebSocket新增频道

```python
# routes/websocket.py 扩展
@router.websocket("/ws/download")
async def download_ws(websocket: WebSocket):
    """下载进度实时推送频道"""
    # 事件: download_start / download_progress / download_complete / download_error / download_cancelled
```

### 3.4 前端API Client扩展 (src/api/client.ts)

```typescript
// 新增API方法
searchModels(keyword: string, source: string, limit: number): Promise<SearchResult[]>
recommendModel(keyword: string, source: string): Promise<RecommendResult>
checkModelMemory(modelName: string): Promise<MemoryCheckResult>
startDownload(modelName: string, source: string, saveDir?: string): Promise<{task_id: string}>
getDownloadStatus(taskId: string): Promise<DownloadStatus>
cancelDownload(taskId: string): Promise<void>
listDownloads(): Promise<DownloadTask[]>
getPoolList(): Promise<PoolEntry[]>
getPoolDetail(modelKey: string): Promise<PoolEntryDetail>
loadFromPool(modelKey: string, engine: string): Promise<LoadResult>
deleteFromPool(modelKey: string, removeFiles: boolean): Promise<void>
```

---

## 4. 前端设计

### 4.1 新增页面: ModelSearchView.vue

**路由**: `/search` (新增)

**核心交互流程**:
```
搜索框输入关键词 → 选择平台(ModelScope/HF/OpenXLab/全平台)
  → 搜索结果列表(含: 模型名/参数大小/量化/估算显存/显存可行性✅❌)
  → 显存优选一键推荐按钮(自动筛选可运行最优模型)
  → 选择模型 → 下载按钮(断点续传+进度条+速度+剩余时间)
  → 下载完成 → 一键加载按钮(显存校验→引擎启动→验证)
```

**组件结构**:
```
ModelSearchView.vue
├── SearchBar.vue          # 搜索输入+平台选择+limit设置
├── SearchResultList.vue   # 搜索结果列表(含显存可行性标注)
├── RecommendPanel.vue     # 显存优选面板(可用显存+推荐模型)
├── DownloadProgress.vue   # 下载进度条(百分比+速度+ETA)
└── ModelPoolPanel.vue     # 模型池快速浏览(已下载模型+加载状态)
```

### 4.2 新增页面: ModelPoolView.vue

**路由**: `/pool` (新增)

**功能**: 模型池统一管理, 本地模型+下载模型列表, 一键加载/删除

### 4.3 侧边导航扩展 (Sidebar.vue)

新增2个菜单项:
- 模型搜索 (icon: search)
- 模型池 (icon: database)

### 4.4 Composables新增

```typescript
// src/composables/useModelSearch.ts
export function useModelSearch() {
  // searchModels(keyword, source, limit)
  // recommendModel(keyword, source)  // 显存优选
}

// src/composables/useModelDownload.ts
export function useModelDownload() {
  // startDownload(modelName, source)
  // downloadStatus(taskId)  // 轮询/WebSocket
  // cancelDownload(taskId)
}

// src/composables/useModelPool.ts
export function useModelPool() {
  // poolList()
  // loadFromPool(modelKey, engine)
  // deleteFromPool(modelKey)
}
```

### 4.5 TypeScript类型新增 (src/types/index.ts)

```typescript
interface SearchResult {
  name: string
  source: 'hf' | 'ms' | 'oxl'
  path: string
  size_b: number        // 参数大小(7/8/13/72)
  quant: string         // 量化类型
  required_gb: float    // 估算显存需求
  feasible: boolean     // 当前显存是否可运行
}

interface RecommendResult {
  recommended: SearchResult
  gpu_info: { total: float, used: float, free: float }
  candidates: SearchResult[]
}

interface DownloadTask {
  task_id: string
  model_name: string
  source: string
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled'
  progress_pct: float
  speed_mbps: float
  eta_seconds: float
  downloaded_bytes: number
  total_bytes: number
  local_path: string
}

interface PoolEntry {
  model_key: string
  name: string
  source: 'local' | 'hf' | 'ms' | 'oxl'
  local_path: string
  size_b: number
  quant: string
  required_gb: float
  downloaded: boolean
  is_running: boolean
}
```

---

## 5. 数据模型扩展

### 5.1 config.yaml扩展

```yaml
models:
  <model_name>:
    model_path: "/mnt/pve_models/Qwen2.5-7B-Instruct"
    engine_type: "vllm"              # vllm | sglang | llama_cpp
    port: 8000
    preload: false
    keep_alive: 300
    required_memory: 14
    source: "local"                  # local | hf | ms | oxl (新增)
    vllm_params: {...}
    sglang_params: {...}             # SGLang专属参数(新增)

engines:                              # 引擎全局配置(新增)
  vllm:
    command: "python -m vllm.entrypoints.openai.api_server"
    default_params:
      gpu_memory_utilization: 0.90
      max_model_len: 8192
  sglang:
    command: "python -m sglang.launch_server"
    default_params:
      mem_fraction_static: 0.88
      tp_size: 1

download:                             # 下载配置(新增)
  save_root: "/mnt/pve_models"
  hf_endpoint: "https://hf-mirror.com"
  disk_warning_pct: 85               # 磁盘85%告警
  disk_abort_pct: 95                 # 磁盘95%终止
  max_concurrent_downloads: 3        # 最大同时下载数
```

### 5.2 内存数据结构

```python
# DownloadTaskManager内存
download_tasks: Dict[str, DownloadTask]

# ModelPoolManager内存
model_pool: Dict[str, ModelPoolEntry]

# LLMServiceManager内存
engine_process: Optional[subprocess.Popen]
engine_type: str                      # "vllm" | "sglang"
current_model: str
```

---

## 6. 核心流程设计

### 6.1 搜索+下载+加载一键流程

```
用户输入关键词 → search_models(keyword, source)
  → 返回搜索结果列表(含size_b/quant/required_gb/feasible)
  → 用户点击"显存优选推荐" → select_best_model(keyword, source)
    → GPUMemoryManager.get_gpu_info()获取可用显存
    → 过滤feasible=False的模型
    → 按size_b降序排序 → 返回最大可运行模型
  → 用户点击"下载+加载" → download_and_load(model_info, engine)
    → DownloadTaskManager.create_task(model_info)
      → 磁盘空间校验(预估大小 vs 可用)
      → MultiSourceModelHub.download_model(model_info)
        → HF/MS/OXL SDK下载, resume_download=True
        → 进度回调 → WebSocket /ws/download 广播
    → 下载完成回调:
      → ModelPoolManager.register_from_download(model_info, local_path)
      → config.yaml更新(新增模型配置)
    → GPUMemoryManager.check_model_feasibility(required_gb)
      → 可行 → LLMServiceManager.start_service(engine, local_path, port)
      → 不可行 → 返回告警+建议可运行模型
    → LLMServiceManager._wait_ready() → 冒烟测试
    → 返回加载成功
```

### 6.2 显存校验集成到模型切换

```
现有4阶段 → 新增5阶段(Phase 2.5显存校验):
  Phase 1: 停止旧服务(不变)
  Phase 2: 强制清理进程(不变)
  Phase 2.5: 显存校验(新增)
    → GPUMemoryManager.get_gpu_info()
    → GPUMemoryManager.check_model_feasibility(target_model.required_memory)
    → 不可行 → 回滚 + 返回告警
  Phase 3: 启动新服务(调用LLMServiceManager)
  Phase 4: 冒烟测试(不变)
```

### 6.3 引擎切换流程

```
switch_engine("sglang")
  → LLMServiceManager.stop_service(current_process)
    → SIGINT → 10s等待 → SIGKILL
    → torch.cuda.empty_cache()
  → GPUMemoryManager.check_model_feasibility(required_memory)
  → LLMServiceManager.start_service("sglang", model_path, port, sglang_params)
  → _wait_ready() → 冒烟测试
  → WebSocket /ws/model-switch 广播切换进度
```

---

## 7. 实施计划

### 7.1 分阶段实施

| 阶段 | 内容 | 模块 | 预估工期 | 优先级 |
|------|------|------|----------|--------|
| Phase 1 | GPUMemoryManager显存精准检测+估算 | `gpu_memory_manager.py` | 2天 | P0 |
| Phase 2 | MultiSourceModelHub搜索+下载 | `model_hub.py` | 3天 | P0 |
| Phase 3 | DownloadTaskManager下载任务管理 | `download_manager.py` | 2天 | P1 |
| Phase 4 | ModelPoolManager模型池管理 | `model_pool.py` | 2天 | P1 |
| Phase 5 | LLMServiceManager引擎进程管理(subprocess替代systemd) | `llm_service_manager.py` | 3天 | P0 |
| Phase 6 | SGLang引擎支持 | `llm_service_manager.py`扩展 | 2天 | P1 |
| Phase 7 | ModelEngineScheduler统一调度中心 | `model_engine_scheduler.py` | 3天 | P0 |
| Phase 8 | Python路由扩展(manage.py新增11个路由) | `routes/manage.py` | 2天 | P1 |
| Phase 9 | Go网关代理路由扩展 | `handler/manage.go` | 1天 | P1 |
| Phase 10 | 前端ModelSearchView+ModelPoolView | 2个新页面+composables | 3天 | P1 |
| Phase 11 | 显存校验集成到model_switch_orchestrator(Phase 2.5) | `model_switch_orchestrator.py` | 1天 | P0 |
| Phase 12 | 移除旧模块(sys_ctl.py进程管理部分) | 清理 | 1天 | P2 |

**总工期**: 约23天 (可并行: Phase1-4 / Phase5-6 / Phase8-9)

### 7.2 依赖关系

```
Phase1(GPUMemory) ─→ Phase7(Scheduler) ─→ Phase11(集成切换)
Phase2(ModelHub) ─→ Phase3(Download) ─→ Phase4(Pool) ─→ Phase7(Scheduler)
Phase5(LLMService) ─→ Phase6(SGLang) ─→ Phase7(Scheduler)
Phase7(Scheduler) ─→ Phase8(路由) ─→ Phase9(Go代理) ─→ Phase10(前端)
```

---

## 8. 依赖安装

### 8.1 Python新增依赖

```bash
pip install huggingface-hub modelscope openxlab torch psutil
```

### 8.2 requirements.txt扩展

```
huggingface-hub>=0.20.0
modelscope>=1.9.0
openxlab>=0.1.0
torch>=2.0.0          # 显存精准检测(GPU版本)
psutil>=5.9.0         # 进程管理
```

### 8.3 Docker Compose调整

Python容器需增加模型下载存储卷映射:
```yaml
ai-controller:
  volumes:
    - /mnt/pve_models:/mnt/pve_models  # 已存在
    - ./models_download:/mnt/pve_models_downloaded  # 新下载模型可选目录
  environment:
    - HF_ENDPOINT=https://hf-mirror.com
```

---

## 9. 风险与兜底

### 9.1 技术风险

| 风险 | 影响 | 兜底方案 |
|------|------|----------|
| torch.cuda依赖冲突 | GPUMemoryManager无法加载 | 降级到nvidia-smi解析(<5%误差可接受) |
| HF/MS/OXL SDK版本不兼容 | 下载/搜索功能异常 | 各SDK独立版本锁定; 异常时降级到单一平台 |
| subprocess.Popen不如systemd稳定 | 引擎进程异常退出 | 3次自动重启兜底; config开关可降级回systemd |
| SGLang命令行参数与vLLM不兼容 | 引擎切换后参数丢失 | 引擎类型→参数模板映射; config.yaml sglang_params独立配置 |
| 多平台搜索结果去重 | 同一模型多平台重复 | 按模型名规范去重(去除平台前缀); 优先本地已有版本 |
| 大模型下载中断 | 断点续传失败 | resume_download=True; 失败后重试3次; 清理不完整下载 |
| 下载速度慢 | 用户体验差 | ModelScope首选(国内最快); HF镜像加速; 显示速度+ETA |

### 9.2 运维风险

| 风险 | 影响 | 兜底方案 |
|------|------|----------|
| 磁盘空间耗尽 | 服务崩溃 | 磁盘水位85%告警/95%终止下载; 下载前前置校验 |
| 模型池与config.yaml不一致 | 调度逻辑冲突 | 每次变更自动同步config; 启动时校验一致性 |
| 下载任务积压 | 内存占用 | max_concurrent_downloads=3限制; 完成后清理任务记录 |

---

## 10. 测试方案

### 10.1 单元测试

| 模块 | 测试重点 |
|------|----------|
| GPUMemoryManager | 显存获取(torch.cuda+nvidia-smi降级); 估算公式正确性; 可行性校验边界 |
| MultiSourceModelHub | 搜索结果解析; 模型名→参数大小/量化解析; 多源下载路径构造 |
| DownloadTaskManager | 任务创建/进度/取消/完成回调; 磁盘校验; 并发限制 |
| ModelPoolManager | 注册/查询/加载/删除; config.yaml同步; 状态校验 |
| LLMServiceManager | 命令构造(vLLM/SGLang); 进程启停; 异常重启; 健康检查 |

### 10.2 集成测试

| 测试场景 | 验证点 |
|----------|--------|
| 搜索→下载→加载全链路 | 搜索结果正确 → 下载断点续传 → 入库 → 显存校验 → 引擎启动 → 验证就绪 |
| 显存优选推荐 | 可用显存 → 过滤不可行 → 排序 → 推荐最优 → 一键下载加载 |
| 引擎切换 vLLM→SGLang | 停止旧引擎 → 显存校验 → 启动SGLang → 冒烟测试 → 切换成功 |
| 模型切换含显存校验 | Phase2.5显存校验 → 不可行回滚 → 可行继续Phase3 |
| 下载中断续传 | 下载50%中断 → 重试 → 100%完成 → 入库成功 |

---

## 11. 文件变更清单

### 11.1 Python新增文件

| 文件路径 | 行数估算 | 功能 |
|----------|----------|------|
| `app-controller/core/gpu_memory_manager.py` | ~80 | 显存精准检测+估算+校验 |
| `app-controller/core/model_hub.py` | ~120 | 多源搜索+下载 |
| `app-controller/core/download_manager.py` | ~150 | 下载任务管理 |
| `app-controller/core/model_pool.py` | ~100 | 模型池管理 |
| `app-controller/core/model_engine_scheduler.py` | ~200 | 统一调度中心 |

### 11.2 Python修改文件

| 文件路径 | 变更内容 |
|----------|----------|
| `app-controller/routes/manage.py` | 新增11个路由(搜索/下载/模型池/显存优选) |
| `app-controller/routes/websocket.py` | 新增/ws/download频道 |
| `app-controller/core/model_switch_orchestrator.py` | Phase2.5显存校验+调用LLMServiceManager |
| `app-controller/core/deps.py` | 注册新模块单例 |
| `app-controller/core/scheduler.py` | 调用ModelPoolManager获取模型信息 |
| `app-controller/requirements.txt` | 新增5个依赖 |
| `config.yaml` | 新增engines/download配置段 |

### 11.3 Go修改文件

| 文件路径 | 变更内容 |
|----------|----------|
| `go-vllm-api/internal/handler/manage/manage.go` | 新增11个代理路由 |
| `go-vllm-api/internal/config/config.go` | 新增Engines/Download配置结构 |

### 11.4 前端新增文件

| 文件路径 | 行数估算 | 功能 |
|----------|----------|------|
| `frontend/src/views/ModelSearchView.vue` | ~400 | 搜索+下载+显存优选页面 |
| `frontend/src/views/ModelPoolView.vue` | ~300 | 模型池管理页面 |
| `frontend/src/components/SearchBar.vue` | ~60 | 搜索输入+平台选择 |
| `frontend/src/components/SearchResultList.vue` | ~100 | 搜索结果列表 |
| `frontend/src/components/RecommendPanel.vue` | ~80 | 显存优选推荐面板 |
| `frontend/src/components/DownloadProgress.vue` | ~80 | 下载进度条 |
| `frontend/src/components/ModelPoolPanel.vue` | ~100 | 模型池面板 |
| `frontend/src/composables/useModelSearch.ts` | ~40 | 搜索composable |
| `frontend/src/composables/useModelDownload.ts` | ~50 | 下载composable |
| `frontend/src/composables/useModelPool.ts` | ~40 | 模型池composable |

### 11.5 前端修改文件

| 文件路径 | 变更内容 |
|----------|----------|
| `frontend/src/router/index.ts` | 新增/search和/pool路由 |
| `frontend/src/components/Sidebar.vue` | 新增2个菜单项 |
| `frontend/src/api/client.ts` | 新增11个API方法 |
| `frontend/src/types/index.ts` | 新增4个类型定义 |

---

## 12. 上线与回滚

### 12.1 上线步骤

1. 安装Python新依赖: `pip install huggingface-hub modelscope openxlab torch psutil`
2. 重启Python B端: `docker-compose restart ai-controller`
3. 重启Go网关: `docker-compose restart go-vllm-api` (新代理路由)
4. 前端构建部署: `pnpm build → nginx更新`
5. 验证搜索API: `curl /manage/models/search?keyword=qwen`
6. 验证显存检测: `curl /manage/gpu/memory-check`
7. 验证下载任务: `curl -X POST /manage/models/download -d '{"model_name":"Qwen/Qwen2-7B-Instruct","source":"modelscope"}'`

### 12.2 回滚方案

- 新模块独立, 旧模块不删除(仅sys_ctl.py进程管理部分)
- config开关: `download.enabled: false` → 关闭下载功能, 不影响现有功能
- Go代理路由: 请求Python失败时返回502, 不影响现有路由
- 前端: 新页面独立路由, 不影响现有页面
- LLMServiceManager: config `engine_manager_mode: systemd` → 降级回systemd模式

---

> 此技术方案基于 ai-os 项目现状设计, 与现有架构无缝集成, 新增模块独立可插拔
