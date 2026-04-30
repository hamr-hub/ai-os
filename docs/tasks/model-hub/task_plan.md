# 任务计划: 多源下载+模型搜索+显存优选+引擎管理+模型池

## 目标
实现 ai-os 的 Model Hub 全功能: 6个核心Python模块 + 11个API路由 + Go代理 + 2个前端新页面

## 当前阶段
Phase 1

## 阶段规划

### Phase 1: Python核心模块实现
- [ ] GPUMemoryManager (gpu_memory_manager.py) - 显存精准检测+估算+校验
- [ ] MultiSourceModelHub (model_hub.py) - 多源搜索+下载
- [ ] DownloadTaskManager (download_manager.py) - 下载任务管理
- [ ] ModelPoolManager (model_pool.py) - 模型池管理
- [ ] LLMServiceManager (llm_service_manager.py) - 统一引擎进程管理
- [ ] ModelEngineScheduler (model_engine_scheduler.py) - 终极调度中心
- **Status:** pending

### Phase 2: Python路由扩展
- [ ] manage.py 新增11个路由(搜索/下载/模型池/显存优选)
- [ ] websocket.py 新增/ws/download频道
- [ ] deps.py 注册新模块单例
- [ ] requirements.txt 新增5个依赖
- **Status:** pending

### Phase 3: Go网关代理扩展
- [ ] manage.go 新增11个代理路由
- [ ] config.go 新增Engines/Download配置结构
- **Status:** pending

### Phase 4: 前端新页面+组件
- [ ] ModelSearchView.vue 搜索+下载+显存优选页面
- [ ] ModelPoolView.vue 模型池管理页面
- [ ] 7个新组件(SearchBar/SearchResultList/RecommendPanel/DownloadProgress/ModelPoolPanel等)
- [ ] 3个新composables(useModelSearch/useModelDownload/useModelPool)
- [ ] client.ts 新增11个API方法
- [ ] types/index.ts 新增4个类型定义
- [ ] router+sidebar 新增2个路由+菜单项
- **Status:** pending

### Phase 5: 集成测试+配置扩展
- [ ] config.yaml 新增engines/download配置段
- [ ] model_switch_orchestrator.py Phase2.5显存校验
- [ ] scheduler.py 调用ModelPoolManager
- **Status:** pending

## 关键问题
1. torch.cuda依赖是否与现有环境兼容? → 降级nvidia-smi兜底
2. HF/MS/OXL SDK版本兼容性? → 独立版本锁定
3. subprocess.Popen vs systemd稳定性? → 双轨并行+config开关
4. 前端新页面路由与现有导航协调? → Sidebar新增菜单项

## 决策记录
| 决策 | 理由 |
|------|------|
| torch.cuda优先,降级nvidia-smi | 精准误差<5%,不可用时降级 |
| subprocess.Popen替代systemd | 进程级精准管控,可降级回systemd |
| ModelScope首选下载源 | 国内速度最快,无需代理 |
| 新增模块独立,旧模块保留 | 可插拔,config开关降级 |

## 错误记录
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
|      |         |         |

## 备注
- 技术方案详见 docs/agent/tech-solution-model-hub.md
- PRD详见 docs/agent/prd.md 功能点14-18
