# AI Controller API Documentation

## Overview
The AI Controller is a Python FastAPI service that manages local LLM models, provides GPU resource monitoring, and intelligent scheduling capabilities. It integrates seamlessly with AIClient-2-API (Node.js) to provide a complete AI service platform.

## Base URL
```
http://localhost:5000
```

## API Endpoints

### OpenAI Compatible APIs

#### Chat Completions
**POST** `/v1/chat/completions`

OpenAI-compatible chat completion endpoint with support for streaming and image inputs.

**Request Body:**
```json
{
  "model": "model-name",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": false,
  "max_tokens": 1000,
  "temperature": 0.7,
  "top_p": 1.0,
  "stop": [],
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0
}
```

**Image Support:**
Messages can include image content:
```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "What is in this image?"},
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
  }]
}
```

#### Image Generation
**POST** `/v1/images/generations`

OpenAI-compatible image generation endpoint.

**Request Body:**
```json
{
  "model": "dall-e-3",
  "prompt": "A beautiful sunset",
  "n": 1,
  "size": "1024x1024",
  "quality": "standard",
  "style": "vivid",
  "response_format": "url"
}
```

#### Embeddings
**POST** `/v1/embeddings`

OpenAI-compatible embedding endpoint.

**Request Body:**
```json
{
  "model": "embedding-model",
  "input": "Text to embed",
  "encoding_format": "float",
  "dimensions": 1024
}
```

#### List Models
**GET** `/v1/models`

Returns list of available models.

### Management APIs

#### GPU Management

**GET** `/manage/gpu`

Get detailed GPU status.

**GET** `/manage/gpu/summary`

Get GPU summary with history.

**GET** `/manage/gpu/history?count=60`

Get GPU history records.

**POST** `/manage/gpu/history/config`

Configure GPU history settings.

Query parameters:
- `enabled`: Enable/disable history
- `max_days`: Maximum days to keep

#### Model Management

**GET** `/manage/models`

Get status of all models.

**GET** `/manage/models/summary`

Get model summary for UI display.

**GET** `/manage/models/{model_name}/info`

Get detailed information about a specific model.

**POST** `/manage/models/{model_name}/start`

Start a model service.

**POST** `/manage/models/{model_name}/stop`

Stop a model service.

**POST** `/manage/models/{model_name}/switch`

Switch to a different model (handles memory management automatically).

#### Preload Management

**GET** `/manage/preload`

Get preload status.

**GET** `/manage/preload/status`

Get detailed preload status for all models.

**POST** `/manage/preload/{model_name}`

Preload and start a model.

**POST** `/manage/preload/{model_name}/enable`

Enable model preloading (auto-start on service start).

**POST** `/manage/preload/{model_name}/disable`

Disable model preloading.

**GET** `/manage/preload/all`

Preload all configured models.

#### Queue Management

**GET** `/manage/queue`

Get queue status for all models.

#### Configuration

**GET** `/manage/config`

Get current configuration.

**POST** `/manage/config/reload`

Reload configuration from config.yaml.

#### Metrics & Monitoring

**GET** `/manage/metrics`

Get service metrics.

**POST** `/manage/metrics/reset`

Reset metrics counters.

**GET** `/health`

Health check endpoint.

**GET** `/health/detailed`

Detailed health check with scores.

**GET** `/metrics`

Prometheus metrics endpoint.

**GET** `/metrics/metadata`

Prometheus metrics metadata.

#### System Status

**GET** `/manage/system/status`

Get system status (CPU, memory, disk).

#### Integration APIs

**GET** `/api/v1/status`

Node.js integration status check endpoint. Returns comprehensive status of the AI Controller service for AIClient-2-API.

**Response:**
```json
{
  "service": "ai-controller",
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "gpu": {
    "available": true,
    "memory_mb": 24576,
    "used_mb": 8192,
    "utilization_percent": 45
  },
  "models": {
    "model-name": {
      "available": true,
      "running": true,
      "preloaded": false,
      "port": 8000,
      "supports_images": false,
      "active_requests": 2,
      "can_accept": true
    }
  },
  "queue": {
    "concurrency_limit": 32
  }
}
```

### WebSocket

**WS** `/ws/monitor`

WebSocket endpoint for real-time monitoring updates.

## Error Handling

All endpoints return standardized error responses:

```json
{
  "error": "Error message",
  "code": 404,
  "timestamp": "2024-01-01T00:00:00",
  "path": "/v1/chat/completions",
  "details": {}
}
```

### Error Types

| Error Code | Exception | Description |
|------------|-----------|-------------|
| 404 | ModelNotFoundException | Model not found |
| 429 | TooManyRequestsException | Too many concurrent requests |
| 503 | InsufficientMemoryException | Insufficient GPU memory |
| 503 | ModelServiceUnavailableException | Model service unavailable |
| 504 | ServiceStartTimeoutException | Service failed to start within timeout |

## Configuration

Edit `config.yaml` to configure models and settings:

```yaml
models:
  model-name:
    service: vllm
    port: 8000
    required_memory: 40GB
    preload: false
    keep_alive: false
    model_path: /path/to/model
    supports_images: false
    description: "Model description"

settings:
  concurrency_limit: 32
  min_available_memory: 4GB
  request_timeout: 120
  model_start_timeout: 120
  preload_timeout: 300
  idle_timeout: 600
  gpu_memory_utilization: 0.92
  default_memory_strategy: balanced
```

## Service Management

### Using Makefile

```bash
make install       # Install dependencies
make run           # Run service
make status        # Check service status
make gpu           # Get GPU status
make models        # Get model status
make health        # Health check
make logs          # View logs
make restart       # Restart service
```

### Using systemd

```bash
sudo systemctl start aiclient-python
sudo systemctl stop aiclient-python
sudo systemctl restart aiclient-python
sudo systemctl status aiclient-python
journalctl -u aiclient-python -f
```
