# AI OS 项目说明文档 (SOP)

## 1. 项目概述
AI OS 是一个基于 "外壳解耦，内核驱动" 架构的本地大模型管理平台。它将 UI 界面（AIClient-2-API）与推理控制逻辑（AI Controller）分离，解决了 vLLM 启动慢、显存易溢出、资源占用高、缺乏监控等痛点。

### 核心架构
1.  **入口层 (Node.js)**: `aiclient2api` - 提供 AI 对话 UI、用户鉴权、OpenAI 协议转发。
2.  **控制层 (Python)**: `app-controller` - 核心大脑，负责模型生命周期管理、显存监控、请求排队、健康检查。
3.  **管理后台 (Vue 3)**: `frontend` - 专门用于 GPU 监控、模型状态可视化及队列管理。
4.  **基础设施**: Redis (队列)、Systemd (服务管理)、nvidia-smi (监控)。
5.  **推理层**: vLLM 实例，执行实际 AI 推理。

---

## 2. 核心 SOP (标准作业程序)

### SOP 01: 快速环境搭建
1.  **基础依赖**: 确保系统已安装 NVIDIA 驱动、CUDA、Python 3.10+、Node.js 18+、Redis。
2.  **控制层安装**:
    ```bash
    cd app-controller && ./setup.sh
    ```
3.  **管理后台安装**:
    ```bash
    cd frontend && npm install
    ```
4.  **入口层安装**:
    ```bash
    cd aiclient2api && npm install
    ```
5.  **一键启动**:
    ```bash
    ./start.sh
    ```

### SOP 02: 启动开发环境
-   **控制层 (后端)**: `cd app-controller && ./start.sh`
-   **管理后台 (前端)**: `cd frontend && npm run dev`
-   **入口层 (UI)**: `cd aiclient2api && npm start`

### SOP 03: 添加/修改新模型
1.  **编辑配置**: 修改 `app-controller/config.yaml`。
    ```yaml
    models:
      My-New-Model:
        service: vllm-new-model  # 对应 systemd 服务名
        port: 8001               # 端口不可冲突
        required_memory: 20GB    # 显存预估
        preload: true            # 是否随机启动
        model_path: /path/to/model
    ```
2.  **创建服务**: 在 `systemd/` 下参考现有文件创建 `vllm-new-model.service`。
3.  **生效配置**:
    ```bash
    curl -X POST http://localhost:35000/manage/config/reload
    ```

### SOP 04: 生产环境部署 (Systemd)
1.  **同步服务文件**:
    ```bash
    sudo cp systemd/*.service /etc/systemd/system/
    sudo systemctl daemon-reload
    ```
2.  **启动核心服务**:
    ```bash
    sudo systemctl enable --now redis ai-controller
    ```
3.  **监控状态**:
    ```bash
    journalctl -u ai-controller -f
    ```

### SOP 05: 日常运维与监控
-   **检查 GPU**: `curl http://localhost:35000/manage/gpu`
-   **检查模型**: `curl http://localhost:35000/manage/models`
-   **手动启停**: `curl -X POST http://localhost:35000/manage/models/{name}/[start|stop]`
-   **查看日志**: `tail -f app-controller/logs/ai_controller.log`

### SOP 06: 模型评测与性能测试
1.  **运行自动化评测**: 
    ```bash
    curl -X POST http://localhost:35000/v1/test/model/My-Model
    ```
2.  **查看评测报告**: 
    ```bash
    curl http://localhost:35000/v1/test/reports
    ```

---

## 3. 常见问题排查 (Troubleshooting)

| 现象 | 可能原因 | 解决方法 |
| :--- | :--- | :--- |
| 请求 503 Service Unavailable | 显存不足或模型启动中 | 等待启动完成或关闭多余模型 |
| 渠道无法连接 | Base URL 配置错误 | 确保渠道 Base URL 为 `http://localhost:35001/v1` |
| 模型启动失败 | 路径错误或 CUDA 版本不匹配 | 检查 `config.yaml` 路径与 `nvidia-smi` |
| Redis 报错 | Redis 未启动 | `sudo systemctl start redis` |

---

## 4. 关键配置项说明
-   `concurrency_limit`: 全局并发限制，保护显存不崩。
-   `min_available_memory`: 最小保留显存，低于此值将禁止启动新模型。
-   `idle_timeout`: 模型空闲 X 秒后自动关闭（仅对非 `keep_alive` 模型有效）。
