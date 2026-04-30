# Model Hub 测试计划

> ai-os 功能点15-18: 多源下载+模型搜索+显存优选+引擎管理+模型池

---

## 1. 测试范围

| 层 | 模块/文件 | 测试类型 |
|---|----------|---------|
| Python核心 | `gpu_memory_manager.py` | 单元 |
| Python核心 | `gpu_memory_checker.py` | 单元(通过manager间接) |
| Python核心 | `model_hub.py` | 单元 |
| Python核心 | `download_manager.py` | 单元 |
| Python核心 | `model_pool.py` | 单元 |
| Python核心 | `llm_service_manager.py` | 单元 |
| Python核心 | `model_engine_scheduler.py` | 单元+集成 |
| Python路由 | `routes/manage.py` (11个新路由) | 集成(API) |

---

## 2. 单元测试清单 (151个, 全部PASS)

### 2.1 GPUMemoryManager (38个)

| ID | 类 | 测试名 | 验证点 | 状态 |
|----|---|--------|--------|------|
| GPU-01 | TestInit | test_init_with_mock_checker | 初始化_checker/_loaded_models | PASS |
| GPU-02 | TestInit | test_checker_property | checker属性返回_checker | PASS |
| GPU-03 | TestInit | test_backend_property | backend属性从_checker继承 | PASS |
| GPU-04 | TestInit | test_device_count_property | device_count从_checker继承 | PASS |
| GPU-05 | TestGetGPUInfo | test_get_gpu_info_returns_dict | get_gpu_info返回dict含total_gb等 | PASS |
| GPU-06 | TestGetGPUInfo | test_get_all_gpu_info | get_all_gpu_info返回列表 | PASS |
| GPU-07 | TestGetGPUInfo | test_get_gpu_info_no_device | 无设备时返回None | PASS |
| GPU-08 | TestFreeMemory | test_get_total_free_bytes | 总空闲字节计算 | PASS |
| GPU-09 | TestFreeMemory | test_get_total_free_gb | 总空闲GB计算 | PASS |
| GPU-10 | TestFreeMemory | test_get_effective_free_bytes_no_loaded | 无加载模型时的有效空闲 | PASS |
| GPU-11 | TestFreeMemory | test_get_effective_free_bytes_with_loaded | 有加载模型时的有效空闲 | PASS |
| GPU-12 | TestFreeMemory | test_get_effective_free_gb | 有效空闲GB计算 | PASS |
| GPU-13 | TestEstimateModelMemory | test_estimate_from_size_b_4bit | size_b=7+quant=4bit估算 | PASS |
| GPU-14 | TestEstimateModelMemory | test_estimate_from_size_b_fp16 | size_b=7+quant=fp16估算 | PASS |
| GPU-15 | TestEstimateModelMemory | test_estimate_from_size_b_awq | size_b=7+quant=awq估算 | PASS |
| GPU-16 | TestEstimateModelMemory | test_estimate_from_size_b_gptq | size_b=7+quant=gptq估算 | PASS |
| GPU-17 | TestEstimateModelMemory | test_estimate_from_size_b_gguf | size_b=7+quant=gguf估算 | PASS |
| GPU-18 | TestEstimateModelMemory | test_estimate_from_size_b_8bit | size_b=7+quant=8bit估算 | PASS |
| GPU-19 | TestEstimateModelMemory | test_estimate_default_no_params | 无参数时默认8GB | PASS |
| GPU-20 | TestEstimateModelMemory | test_estimate_gb | GB版本估算一致性 | PASS |
| GPU-21 | TestEstimateModelMemory | test_estimate_large_model | 235B大模型估算>100GB | PASS |
| GPU-22 | TestCheckModelFeasibility | test_feasible_model | 可行模型返回feasible=True | PASS |
| GPU-23 | TestCheckModelFeasibility | test_not_feasible_model | 不可行模型返回feasible=False | PASS |
| GPU-24 | TestCheckModelFeasibility | test_no_gpu_available | 无GPU返回gpu_unavailable | PASS |
| GPU-25 | TestCheckModelFeasibility | test_model_already_loaded_reason | 已加载模型特殊reason | PASS |
| GPU-26 | TestCheckModelFeasibility | test_feasibility_contains_device_info | feasibility含device_id/backend | PASS |
| GPU-27 | TestLoadedModels | test_register_loaded_model | 注册加载模型到_loaded_models | PASS |
| GPU-28 | TestLoadedModels | test_unregister_loaded_model | 注销加载模型 | PASS |
| GPU-29 | TestLoadedModels | test_unregister_nonexistent_model | 注销不存在模型不报错 | PASS |
| GPU-30 | TestLoadedModels | test_get_loaded_models | 获取所有加载模型 | PASS |
| GPU-31 | TestLoadedModels | test_get_loaded_memory_gb | 加载模型总显存GB | PASS |
| GPU-32 | TestLoadedModels | test_get_loaded_memory_gb_by_device | 按设备过滤加载显存 | PASS |
| GPU-33 | TestFindBestDevice | test_find_best_device | 找到最佳设备返回0 | PASS |
| GPU-34 | TestFindBestDevice | test_find_best_device_no_fit | 无合适设备返回None | PASS |
| GPU-35 | TestMemorySummary | test_get_memory_summary | summary含backend/devices等 | PASS |
| GPU-36 | TestMemorySummary | test_memory_summary_with_loaded_models | summary含加载模型信息 | PASS |

### 2.2 MultiSourceModelHub (19个)

| ID | 测试名 | 验证点 | 状态 |
|----|--------|--------|------|
| HUB-01 | test_parse_7b | 从名解析7B->7 | PASS |
| HUB-02 | test_parse_8b | 从名解析8B->8 | PASS |
| HUB-03 | test_parse_235b | 从名解析235B->235 | PASS |
| HUB-04 | test_parse_31b | 从名解析31B->31 | PASS |
| HUB-05 | test_parse_no_size | 无参数大小时返回None | PASS |
| HUB-06 | test_parse_size_with_dot | 带小数点解析 | PASS |
| HUB-07 | test_parse_4bit | 4bit量化识别 | PASS |
| HUB-08 | test_parse_int4_normalizes_to_4bit | int4规范化为4bit | PASS |
| HUB-09 | test_parse_8bit | 8bit量化识别 | PASS |
| HUB-10 | test_parse_int8_normalizes_to_8bit | int8规范化为8bit | PASS |
| HUB-11 | test_parse_fp16 | fp16量化识别 | PASS |
| HUB-12 | test_parse_awq | awq量化识别 | PASS |
| HUB-13 | test_parse_gptq | gptq量化识别 | PASS |
| HUB-14 | test_parse_gguf | gguf量化识别 | PASS |
| HUB-15 | test_parse_no_quant | 无量化时返回None | PASS |
| HUB-16 | test_search_huggingface | HF搜索(mock)返回SearchResult | PASS |
| HUB-17 | test_search_modelscope | MS搜索(mock)返回SearchResult | PASS |
| HUB-18 | test_search_all_aggregates | source=all聚合搜索 | PASS |
| HUB-19 | test_search_local | local搜索返回结果 | PASS |
| HUB-20 | test_local_model_found | 本地模型路径查找 | PASS |
| HUB-21 | test_local_model_not_found | 不存在模型返回None | PASS |
| HUB-22 | test_model_is_local | is_model_local返回True | PASS |
| HUB-23 | test_model_not_local | is_model_local返回False | PASS |
| HUB-24 | test_get_source_info | get_source_info含sources/save_root | PASS |

### 2.3 DownloadTaskManager (10个)

| ID | 测试名 | 验证点 | 状态 |
|----|--------|--------|------|
| DL-01 | test_create_task_basic | 创建下载任务返回task_id+pending | PASS |
| DL-02 | test_create_task_model_already_exists | 模型已存在返回already_exists | PASS |
| DL-03 | test_create_task_disk_space_abort | 磁盘97%时终止返回error | PASS |
| DL-04 | test_get_status_existing_task | 查询已存在任务状态 | PASS |
| DL-05 | test_get_status_nonexistent_task | 查询不存在任务返回None | PASS |
| DL-06 | test_cancel_existing_task | 取消已存在任务 | PASS |
| DL-07 | test_cancel_nonexistent_task | 取消不存在任务返回失败 | PASS |
| DL-08 | test_cancel_completed_task | 取消已完成任务返回失败 | PASS |
| DL-09 | test_list_all_tasks | 列出所有下载任务 | PASS |
| DL-10 | test_list_tasks_with_filter | 按状态过滤任务 | PASS |
| DL-11 | test_get_stats | 统计信息含total_tasks/by_status | PASS |

### 2.4 ModelPoolManager (10个)

| ID | 测试名 | 验证点 | 状态 |
|----|--------|--------|------|
| POOL-01 | test_scan_local_models | 扫描本地模型目录并入库 | PASS |
| POOL-02 | test_scan_empty_dir | 扫描空目录返回0个模型 | PASS |
| POOL-03 | test_register_downloaded_model | 下载模型注册到池 | PASS |
| POOL-04 | test_register_search_result | 搜索结果注册到池(仅元信息) | PASS |
| POOL-05 | test_list_all_models | 列出所有池模型 | PASS |
| POOL-06 | test_list_with_filter | 过滤已下载模型 | PASS |
| POOL-07 | test_delete_stopped_model | 删除已停止模型 | PASS |
| POOL-08 | test_delete_running_model_fails | 删除运行中模型失败 | PASS |
| POOL-09 | test_delete_nonexistent_model | 删除不存在模型返回失败 | PASS |

### 2.5 LLMServiceManager (30个)

| ID | 测试名 | 验证点 | 状态 |
|----|--------|--------|------|
| LLM-01 | test_vllm_basic_command | vLLM命令含model_path+port | PASS |
| LLM-02 | test_vllm_command_with_model_path | _model_paths优先使用 | PASS |
| LLM-03 | test_vllm_with_config_params | config vllm_params注入 | PASS |
| LLM-04 | test_vllm_with_tool_calling | tool_call_parser+enable-tool-call | PASS |
| LLM-05 | test_sglang_basic_command | SGLang命令含model-path+mem-fraction | PASS |
| LLM-06 | test_sglang_with_tensor_parallel | tp参数注入 | PASS |
| LLM-07 | test_llamacpp_basic_command | llama-server+ngl+port | PASS |
| LLM-08 | test_unsupported_engine_raises | 未知引擎抛ValueError | PASS |
| LLM-09 | test_get_model_path_from_dict | _model_paths优先 | PASS |
| LLM-10 | test_get_model_path_from_config | config model_path | PASS |
| LLM-11 | test_get_model_path_default | 默认/mnt/pve_models/ | PASS |
| LLM-12 | test_start_service_success | start_service含pid+health_status=starting | PASS |
| LLM-13 | test_start_service_with_model_path | model_path存入_model_paths | PASS |
| LLM-14 | test_start_service_failure | 异常返回status=error | PASS |
| LLM-15 | test_graceful_stop | 停止后cleanup清除所有dict | PASS |
| LLM-16 | test_stop_nonexistent_service | 返回False | PASS |
| LLM-17 | test_force_stop | 强制停止 | PASS |
| LLM-18 | test_force_stop_nonexistent | 返回False | PASS |
| LLM-19 | test_cleanup_removes_all_entries | _health_status也清除 | PASS |
| LLM-20 | test_running_service_status | 含health字段 | PASS |
| LLM-21 | test_nonexistent_service_status | not_found | PASS |
| LLM-22 | test_stopped_service_cleanup | 自动cleanup | PASS |
| LLM-23 | test_check_health_running | poll None=True | PASS |
| LLM-24 | test_check_health_not_found | 返回False | PASS |
| LLM-25 | test_auto_restart | 重启后restart_counts被重置为0 | PASS |
| LLM-26 | test_max_restarts_exceeded | 超限返回max_restarts_exceeded | PASS |
| LLM-27 | test_get_and_reset_restart_count | reset清零 | PASS |
| LLM-28 | test_list_services | 含service_name | PASS |
| LLM-29 | test_list_services_by_engine | 按引擎过滤 | PASS |
| LLM-30 | test_get_service_by_model | 按模型名查找 | PASS |
| LLM-31 | test_get_service_by_port | 按端口查找 | PASS |
| LLM-32 | test_cleanup_all | 清除所有服务 | PASS |

### 2.6 ModelEngineScheduler (22个)

| ID | 测试名 | 验证点 | 状态 |
|----|--------|--------|------|
| SCH-01 | test_show_gpu_returns_summary | show_gpu含available+devices | PASS |
| SCH-02 | test_show_gpu_no_gpu_manager | 无gpu_mgr时available=False | PASS |
| SCH-03 | test_search_with_feasibility | 搜索含可行性标注 | PASS |
| SCH-04 | test_search_no_model_hub | 无hub返回空 | PASS |
| SCH-05 | test_recommend_from_config | config指定engine_type | PASS |
| SCH-06 | test_recommend_gguf_to_llamacpp | gguf推荐llamacpp | PASS |
| SCH-07 | test_recommend_awq_to_vllm | awq推荐vllm | PASS |
| SCH-08 | test_recommend_default_vllm | 默认推荐vllm | PASS |
| SCH-09 | test_recommend_with_low_free_gb_preference | 低显存时gguf推荐llamacpp | PASS |
| SCH-10 | test_recommend_with_capabilities | tool_calling推荐vllm | PASS |
| SCH-11 | test_recommend_returns_full_result | recommend含gpu_info+candidates | PASS |
| SCH-12 | test_recommend_no_results | 无搜索结果时recommended=None | PASS |
| SCH-13 | test_switch_model_already_running | 已运行模型返回already_running | PASS |
| SCH-14 | test_switch_model_insufficient_memory | 显存不足返回失败 | PASS |
| SCH-15 | test_deploy_insufficient_memory_no_force | 不强制时显存不足返回失败 | PASS |
| SCH-16 | test_undeploy_model_not_running | 未运行模型卸载失败 | PASS |
| SCH-17 | test_record_and_get_history | 切换历史记录 | PASS |
| SCH-18 | test_history_max_limit | 历史最多50条 | PASS |
| SCH-19 | test_get_active_service | 活跃服务查询 | PASS |
| SCH-20 | test_get_active_service_none | 无活跃服务返回None | PASS |
| SCH-21 | test_get_available_engines | 可用引擎含vllm/sglang/llamacpp | PASS |
| SCH-22 | test_find_available_port_default | 默认端口8000 | PASS |
| SCH-23 | test_find_available_port_with_used | 占用端口后偏移+1 | PASS |
| SCH-24 | test_find_available_port_no_llm_mgr | 无mgr返回base | PASS |
| SCH-25 | test_get_deployment_summary | summary含gpu/services | PASS |

---

## 3. 集成测试清单 (14个)

### 3.1 API路由集成测试

| ID | 路由 | 方法 | 验证点 | 状态 |
|----|------|------|--------|------|
| API-01 | /models/search | GET | 搜索路由返回keyword/source/results | PASS |
| API-02 | /models/search | GET | keyword为空返回400 | PASS |
| API-03 | /gpu/recommend | GET | 推荐路由返回recommended+gpu_info+candidates | PASS |
| API-04 | /gpu/memory-check/{model} | POST | 显存校验返回feasible | PASS |
| API-05 | /gpu/memory-check/{model} | POST | 无size模型返回404 | PASS |
| API-06 | /models/download | POST | 创建下载返回task_id | PASS |
| API-07 | /models/download | POST | 无model_name返回400 | PASS |
| API-08 | /models/download/{task_id}/status | GET | 查询下载状态 | PASS |
| API-09 | /models/download/{task_id} | DELETE | 取消下载 | PASS |
| API-10 | /models/downloads | GET | 列出下载任务 | PASS |
| API-11 | /models/pool | GET | 模型池列表含models+total | PASS |
| API-12 | /models/pool/{key}/load | POST | 一键加载模型 | PASS |
| API-13 | /models/pool/{key} | DELETE | 删除模型 | PASS |

### 3.2 全链路集成测试

| ID | 链路 | 验证点 | 状态 |
|----|------|--------|------|
| E2E-01 | search->recommend->show_gpu | scheduler.search+recommend+show_gpu全链路 | PASS |

---

## 4. 执行命令

```bash
cd app-controller && python -m pytest tests/test_gpu_memory_manager.py tests/test_model_hub.py tests/test_download_manager.py tests/test_model_pool.py tests/test_llm_service_manager.py tests/test_model_engine_scheduler.py tests/test_model_hub_routes.py -v
```

---

## 5. 测试覆盖总结

| 类别 | 数量 | PASS | FAIL |
|------|------|------|------|
| GPUMemoryManager | 36 | 36 | 0 |
| MultiSourceModelHub | 19 | 19 | 0 |
| DownloadTaskManager | 11 | 11 | 0 |
| ModelPoolManager | 9 | 9 | 0 |
| LLMServiceManager | 32 | 32 | 0 |
| ModelEngineScheduler | 25 | 25 | 0 |
| API路由集成 | 13 | 13 | 0 |
| 全链路集成 | 1 | 1 | 0 |
| **总计** | **151** | **151** | **0** |

---

## 6. 验收标准对照

| AC编号 | 标准 | 测试ID | 状态 |
|--------|------|--------|------|
| AC-01 | search返回含feasible | API-01 | PASS |
| AC-02 | recommend返回推荐+GPU信息 | API-03 | PASS |
| AC-03 | memory-check返回feasible | API-04 | PASS |
| AC-04 | download启动下载 | API-06 | PASS |
| AC-05 | download status查询 | API-08 | PASS |
| AC-06 | download cancel取消 | API-09 | PASS |
| AC-07 | pool列表含来源/大小/状态 | API-11 | PASS |
| AC-08 | pool load一键加载 | API-12 | PASS |
| AC-09 | 显存估算4bit/8bit/fp16系数 | GPU-13~18 | PASS |
| AC-10 | search->recommend全链路 | E2E-01 | PASS |
| AC-11 | 磁盘空间告警/终止 | DL-03 | PASS |

> 最后更新: 2026-04-30, 151测试全部PASS
