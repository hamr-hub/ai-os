# 研究发现

## 背景
ai-os 项目新增 Model Hub 功能: 多源下载+模型搜索+显存优选+引擎管理+模型池

## 关键发现

### 发现 1: 现有项目架构清晰
- **来源**: 项目探索
- **内容**: Go网关(C端流量) + Python B端(管控) + Vue3前端 三层架构, 新增功能全部在Python B端实现
- **影响**: 新模块与现有模块协调(scheduler/vllm_manager/orchestrator), Go仅代理转发

### 发现 2: 现有GPU监控已有NVML实现
- **来源**: app-controller/core/monitor.py (997行)
- **内容**: NVMLCollector+nvidia-smi已实现GPU状态采集, GPUMemoryManager需补充torch.cuda精准检测
- **影响**: GPUMemoryManager复用monitor.py的基础数据, 增加torch.cuda精准层

### 发现 3: 现有vllm_manager已有模型扫描
- **来源**: app-controller/core/vllm_manager.py (1298行)
- **内容**: ScanModels扫描/mnt/pve_models, 聚合模型组, 启停服务
- **影响**: ModelPoolManager需与ScanModels协调, 避免重复扫描; 进程管理部分迁移到LLMServiceManager

### 发现 4: 前端已有完整的模型管理+GPU管理页面
- **来源**: frontend/src/views/
- **内容**: ModelManagement.vue(2653行) + GPUManage.vue(869行) + Dashboard.vue
- **影响**: 新增ModelSearchView/ModelPoolView独立页面, 不修改现有页面

### 发现 5: 依赖注入容器(deps.py)管理所有单例
- **来源**: app-controller/core/deps.py
- **内容**: 所有服务实例通过deps单例注入, 新模块需注册
- **影响**: 新模块需在deps.py注册为单例

## 研究问题
1. torch.cuda与现有pynvml依赖是否冲突? → 不冲突, torch.cuda是补充层
2. modelscope SDK下载API签名? → ms_snapshot_download(model_id, cache_dir=...)
3. HF国内镜像配置方式? → os.environ["HF_ENDPOINT"]="https://hf-mirror.com"

## 技术笔记
- monitor.py NVMLCollector已在deps.py注册为单例, GPUMemoryManager可引用其数据
- vllm_manager.py ScanModels通过/mnt/pve_models扫描config.json/safetensors/tokenizer
- model_switch_orchestrator.py 4阶段原子切换已有完整回滚+session+WS机制
- config_watcher.py fsnotify+SIGHUP配置热加载机制已完整
- 前端api/client.ts双axios实例(client+v1Client), 新增API方法加入client实例

## 参考资料
- docs/agent/prd.md - 功能点14-18完整PRD
- docs/agent/tech-solution-model-hub.md - 技术方案
- docs/agent/architecture.md - 架构设计
