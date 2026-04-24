# AI Controller API Documentation

## Overview
The AI Controller is a Python FastAPI service that manages local LLM models, provides GPU resource monitoring, and intelligent scheduling capabilities. It integrates seamlessly with AIClient-2-API (Node.js) to provide a complete AI service platform.

## Base URL
```
http://localhost:35000
```

## API Endpoints

### OpenAI Compatible APIs

#### Chat Completions
**POST** `/v1/chat/completions`

OpenAI-compatible chat completion endpoint with support for streaming and image inputs.

#### Image Generation
**POST** `/v1/images/generations`

OpenAI-compatible image generation endpoint.

#### Embeddings
**POST** `/v1/embeddings`

OpenAI-compatible embedding endpoint.

#### List Models
**GET** `/v1/models`

Returns list of available models.

### Management APIs

#### GPU Management

**GET** `/manage/gpu`
Get detailed GPU status.

**GET** `/manage/gpu/summary`
Get GPU summary with history (defaults to last 60 points).

**GET** `/manage/gpu/history?count=60`
Get GPU history records from server-side persistence.

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
Switch to a different model.

#### Token Statistics & History

**GET** `/manage/token/stats`
Get current token usage statistics for all models.

**GET** `/manage/token/history?count=60`
Get historical token usage records from server-side persistence.

#### System Monitoring

**GET** `/manage/system/status`
Get current system status (CPU, memory, disk).
Query Parameters:
- `include_history`: (optional) Boolean, include historical data in response.
- `history_count`: (optional) Number of history points to include.

**GET** `/manage/system/history?count=60`
Get historical system status records (CPU, memory utilization) from server-side persistence.

#### Configuration

**GET** `/manage/config`
Get current configuration.

**PUT** `/manage/config`
Update configuration dynamically.

**POST** `/manage/config/reload`
Reload configuration from config.yaml.

#### Metrics & Health

**GET** `/manage/metrics`
Get service-level metrics.

**POST** `/manage/metrics/reset`
Reset metrics counters.

**GET** `/health/alert`
Get comprehensive health score and alert status.

#### Cache Management

**GET** `/manage/cache/status`
Get internal cache status and statistics.

**POST** `/manage/cache/refresh`
Refresh specific or all caches.

### Integration APIs

**GET** `/api/v1/status`
Node.js integration status check endpoint.

### WebSocket

**WS** `/ws/monitor`
WebSocket endpoint for real-time monitoring updates (GPU, model status).

## Error Handling

Standardized error responses:
```json
{
  "error": "Error message",
  "code": 404,
  "timestamp": "ISO-TIMESTAMP",
  "path": "/requested/path"
}
```

## Service Management

The service can be managed via `systemctl` or the provided `Makefile`. History data is persisted in Redis for cross-session continuity.
