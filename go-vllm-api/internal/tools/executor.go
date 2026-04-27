package tools

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"go-vllm-api/internal/service"

	"go.uber.org/zap"
)

type ToolResult struct {
	ToolName      string `json:"tool_name"`
	Success       bool   `json:"success"`
	Result        any    `json:"result"`
	Error         string `json:"error,omitempty"`
	ExecutionTime float64 `json:"execution_time"`
	Timestamp     string `json:"timestamp"`
}

type ToolCall struct {
	Name      string         `json:"name"`
	Arguments map[string]any `json:"arguments"`
}

type ToolExecutor struct {
	registry       *ToolRegistry
	scheduler      *service.Scheduler
	gpuMonitor     *service.GPUMonitor
	vllmManager    *service.VLLMManager
	sysCtl         *service.SystemController
	llamaCppMgr    *service.LlamaCppManager
	executionHistory []*ToolResult
	maxHistory     int
	logger         *zap.Logger
}

func NewToolExecutor(registry *ToolRegistry, scheduler *service.Scheduler, gpuMonitor *service.GPUMonitor, vllmManager *service.VLLMManager, sysCtl *service.SystemController, llamaCppMgr *service.LlamaCppManager, logger *zap.Logger) *ToolExecutor {
	return &ToolExecutor{
		registry:    registry,
		scheduler:   scheduler,
		gpuMonitor:  gpuMonitor,
		vllmManager: vllmManager,
		sysCtl:      sysCtl,
		llamaCppMgr: llamaCppMgr,
		maxHistory:  1000,
		logger:      logger,
	}
}

func (e *ToolExecutor) Execute(ctx context.Context, toolName string, arguments map[string]any, autoConfirm bool) *ToolResult {
	startTime := time.Now()

	tool := e.registry.Get(toolName)
	if tool == nil {
		return &ToolResult{
			ToolName:  toolName,
			Success:   false,
			Result:    nil,
			Error:     fmt.Sprintf("Tool '%s' not found", toolName),
			Timestamp: time.Now().Format(time.RFC3339),
		}
	}

	if tool.RequiresConfirmation && !autoConfirm {
		return &ToolResult{
			ToolName:  toolName,
			Success:   false,
			Result:    nil,
			Error:     fmt.Sprintf("Tool '%s' requires user confirmation", toolName),
			Timestamp: time.Now().Format(time.RFC3339),
		}
	}

	validatedArgs, err := e.validateArguments(tool, arguments)
	if err != nil {
		return &ToolResult{
			ToolName:  toolName,
			Success:   false,
			Result:    nil,
			Error:     fmt.Sprintf("Invalid arguments: %s", err.Error()),
			Timestamp: time.Now().Format(time.RFC3339),
		}
	}

	result, execErr := e.defaultHandler(ctx, toolName, validatedArgs)
	execTime := time.Since(startTime).Seconds()

	if execErr != nil {
		e.logger.Error("Tool execution failed",
			zap.String("tool", toolName),
			zap.Error(execErr))

		toolResult := &ToolResult{
			ToolName:      toolName,
			Success:       false,
			Result:        nil,
			Error:         execErr.Error(),
			ExecutionTime: execTime,
			Timestamp:     time.Now().Format(time.RFC3339),
		}
		e.addToHistory(toolResult)
		return toolResult
	}

	toolResult := &ToolResult{
		ToolName:      toolName,
		Success:       true,
		Result:        result,
		ExecutionTime: execTime,
		Timestamp:     time.Now().Format(time.RFC3339),
	}
	e.addToHistory(toolResult)
	return toolResult
}

func (e *ToolExecutor) validateArguments(tool *ToolDefinition, arguments map[string]any) (map[string]any, error) {
	validated := make(map[string]any)

	for _, param := range tool.Parameters {
		value, exists := arguments[param.Name]
		if !exists {
			value = param.Default
		}

		if param.Required && value == nil {
			return nil, fmt.Errorf("missing required parameter: %s", param.Name)
		}

		if value == nil {
			continue
		}

		validatedValue, err := e.convertAndValidate(param, value)
		if err != nil {
			return nil, fmt.Errorf("parameter %s: %w", param.Name, err)
		}
		validated[param.Name] = validatedValue
	}

	return validated, nil
}

func (e *ToolExecutor) convertAndValidate(param ToolParameter, value any) (any, error) {
	switch param.Type {
	case TypeString:
		strVal, ok := value.(string)
		if !ok {
			strVal = fmt.Sprintf("%v", value)
		}
		if len(param.Enum) > 0 {
			found := false
			for _, enumVal := range param.Enum {
				if strVal == enumVal {
					found = true
					break
				}
			}
			if !found {
				return nil, fmt.Errorf("invalid enum value: %s", strVal)
			}
		}
		return strVal, nil

	case TypeInteger:
		var intVal int64
		switch v := value.(type) {
		case float64:
			intVal = int64(v)
		case int:
			intVal = int64(v)
		case int64:
			intVal = v
		case json.Number:
			if iv, err := v.Int64(); err == nil {
				intVal = iv
			} else {
				return nil, fmt.Errorf("invalid integer: %v", value)
			}
		default:
			return nil, fmt.Errorf("invalid integer type: %T", value)
		}

		if param.MinValue != nil && float64(intVal) < *param.MinValue {
			return nil, fmt.Errorf("value %d below minimum %f", intVal, *param.MinValue)
		}
		if param.MaxValue != nil && float64(intVal) > *param.MaxValue {
			return nil, fmt.Errorf("value %d above maximum %f", intVal, *param.MaxValue)
		}
		return intVal, nil

	case TypeNumber:
		var floatVal float64
		switch v := value.(type) {
		case float64:
			floatVal = v
		case int:
			floatVal = float64(v)
		case int64:
			floatVal = float64(v)
		case json.Number:
			if fv, err := v.Float64(); err == nil {
				floatVal = fv
			} else {
				return nil, fmt.Errorf("invalid number: %v", value)
			}
		default:
			return nil, fmt.Errorf("invalid number type: %T", value)
		}

		if param.MinValue != nil && floatVal < *param.MinValue {
			return nil, fmt.Errorf("value %f below minimum %f", floatVal, *param.MinValue)
		}
		if param.MaxValue != nil && floatVal > *param.MaxValue {
			return nil, fmt.Errorf("value %f above maximum %f", floatVal, *param.MaxValue)
		}
		return floatVal, nil

	case TypeBoolean:
		boolVal, ok := value.(bool)
		if !ok {
			if strVal, ok := value.(string); ok {
				boolVal = strVal == "true" || strVal == "1"
			} else {
				return nil, fmt.Errorf("invalid boolean: %v", value)
			}
		}
		return boolVal, nil

	case TypeArray:
		arrVal, ok := value.([]any)
		if !ok {
			if strVal, ok := value.(string); ok {
				var parsed []any
				if err := json.Unmarshal([]byte(strVal), &parsed); err != nil {
					return nil, fmt.Errorf("invalid array JSON: %w", err)
				}
				arrVal = parsed
			} else {
				return nil, fmt.Errorf("invalid array: %v", value)
			}
		}
		return arrVal, nil

	case TypeObject:
		objVal, ok := value.(map[string]any)
		if !ok {
			if strVal, ok := value.(string); ok {
				var parsed map[string]any
				if err := json.Unmarshal([]byte(strVal), &parsed); err != nil {
					return nil, fmt.Errorf("invalid object JSON: %w", err)
				}
				objVal = parsed
			} else {
				return nil, fmt.Errorf("invalid object: %v", value)
			}
		}
		return objVal, nil

	default:
		return value, nil
	}
}

func (e *ToolExecutor) defaultHandler(ctx context.Context, toolName string, arguments map[string]any) (any, error) {
	switch toolName {
	case "get_system_info":
		return e.handleGetSystemInfo()

	case "list_models":
		return e.handleListModels()

	case "get_gpu_status":
		return e.handleGetGPUStatus()

	case "start_model":
		return e.handleStartModel(ctx, arguments)

	case "stop_model":
		return e.handleStopModel(ctx, arguments)

	case "switch_model":
		return e.handleSwitchModel(ctx, arguments)

	case "optimize_gpu_memory":
		return e.handleOptimizeGPUMemory(arguments)

	case "read_file":
		return e.handleReadFile(arguments)

	case "write_file":
		return e.handleWriteFile(arguments)

	case "search_conversations":
		return e.handleSearchConversations(arguments)

	case "web_search":
		return e.handleWebSearch(arguments)

	default:
		return nil, fmt.Errorf("no handler for tool: %s", toolName)
	}
}

func (e *ToolExecutor) handleGetSystemInfo() (map[string]any, error) {
	gpuStatus := e.gpuMonitor.GetStatus()
	models := e.scheduler.GetAvailableModels()
	runningModels := make([]string, 0)
	for _, m := range models {
		if e.scheduler.IsModelRunning(m) {
			runningModels = append(runningModels, m)
		}
	}

	return map[string]any{
		"gpu": gpuStatus,
		"models": map[string]any{
			"total":   len(models),
			"running": len(runningModels),
			"list":    runningModels,
		},
		"timestamp": time.Now().Format(time.RFC3339),
	}, nil
}

func (e *ToolExecutor) handleListModels() (map[string]any, error) {
	models := e.scheduler.GetAvailableModels()
	modelList := make([]map[string]any, 0, len(models))
	for _, m := range models {
		config := e.scheduler.GetModelConfig(m)
		entry := map[string]any{
			"name":           m,
			"running":        e.scheduler.IsModelRunning(m),
			"supports_images": e.scheduler.GetModelSupportsImages(m),
		}
		if config != nil {
			entry["description"] = config.Description
		} else {
			entry["description"] = ""
		}
		modelList = append(modelList, entry)
	}

	return map[string]any{
		"models": modelList,
		"count":  len(modelList),
	}, nil
}

func (e *ToolExecutor) handleGetGPUStatus() (any, error) {
	status := e.gpuMonitor.GetStatus()
	if status == nil {
		return map[string]any{"error": "No GPU detected"}, nil
	}
	return status, nil
}

func (e *ToolExecutor) handleStartModel(ctx context.Context, arguments map[string]any) (map[string]any, error) {
	modelName, ok := arguments["model_name"].(string)
	if !ok || modelName == "" {
		return nil, fmt.Errorf("model_name is required")
	}

	if e.scheduler.IsModelRunning(modelName) {
		return map[string]any{
			"status": "already_running",
			"model":  modelName,
		}, nil
	}

	ok, err := e.scheduler.StartModel(ctx, modelName)
	if err != nil {
		return map[string]any{
			"status": "failed",
			"model":  modelName,
			"error":  err.Error(),
		}, nil
	}

	return map[string]any{
		"status": "started",
		"model":  modelName,
	}, nil
}

func (e *ToolExecutor) handleStopModel(ctx context.Context, arguments map[string]any) (map[string]any, error) {
	modelName, ok := arguments["model_name"].(string)
	if !ok || modelName == "" {
		return nil, fmt.Errorf("model_name is required")
	}

	if !e.scheduler.IsModelRunning(modelName) {
		return map[string]any{
			"status": "already_stopped",
			"model":  modelName,
		}, nil
	}

	success := e.scheduler.StopModel(ctx, modelName)
	status := "failed"
	if success {
		status = "stopped"
	}
	return map[string]any{
		"status": status,
		"model":  modelName,
	}, nil
}

func (e *ToolExecutor) handleSwitchModel(ctx context.Context, arguments map[string]any) (map[string]any, error) {
	modelName, ok := arguments["model_name"].(string)
	if !ok || modelName == "" {
		return nil, fmt.Errorf("model_name is required")
	}

	success := e.scheduler.SwitchModel(ctx, modelName)
	status := "failed"
	if success {
		status = "switched"
	}
	return map[string]any{
		"status": status,
		"model":  modelName,
	}, nil
}

func (e *ToolExecutor) handleOptimizeGPUMemory(arguments map[string]any) (map[string]any, error) {
	strategy, _ := arguments["strategy"].(string)
	if strategy == "" {
		strategy = "balanced"
	}

	e.scheduler.FlushCache()
	return map[string]any{
		"status":   "optimized",
		"strategy": strategy,
	}, nil
}

func (e *ToolExecutor) handleReadFile(arguments map[string]any) (map[string]any, error) {
	filePath, ok := arguments["file_path"].(string)
	if !ok || filePath == "" {
		return nil, fmt.Errorf("file_path is required")
	}

	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	return map[string]any{
		"file_path": filePath,
		"content":   string(content),
		"size":      len(content),
	}, nil
}

func (e *ToolExecutor) handleWriteFile(arguments map[string]any) (map[string]any, error) {
	filePath, ok1 := arguments["file_path"].(string)
	content, ok2 := arguments["content"].(string)
	if !ok1 || !ok2 {
		return nil, fmt.Errorf("file_path and content are required")
	}

	err := os.WriteFile(filePath, []byte(content), 0644)
	if err != nil {
		return nil, fmt.Errorf("failed to write file: %w", err)
	}

	return map[string]any{
		"file_path": filePath,
		"success":   true,
		"size":      len(content),
	}, nil
}

func (e *ToolExecutor) addToHistory(result *ToolResult) {
	e.executionHistory = append(e.executionHistory, result)
	if len(e.executionHistory) > e.maxHistory {
		e.executionHistory = e.executionHistory[len(e.executionHistory)-e.maxHistory:]
	}
}

func (e *ToolExecutor) GetHistory(limit int) []*ToolResult {
	if limit <= 0 || limit > len(e.executionHistory) {
		limit = len(e.executionHistory)
	}
	start := len(e.executionHistory) - limit
	if start < 0 {
		start = 0
	}
	return e.executionHistory[start:]
}

func (e *ToolExecutor) ClearHistory() {
	e.executionHistory = nil
}

func (e *ToolExecutor) GetStatistics() map[string]any {
	if len(e.executionHistory) == 0 {
		return map[string]any{
			"total_executions": 0,
			"successful":       0,
			"failed":           0,
			"average_time":     0.0,
		}
	}

	successful := 0
	totalTime := 0.0
	toolsUsed := make(map[string]bool)

	for _, r := range e.executionHistory {
		if r.Success {
			successful++
		}
		totalTime += r.ExecutionTime
		toolsUsed[r.ToolName] = true
	}

	toolsList := make([]string, 0, len(toolsUsed))
	for tool := range toolsUsed {
		toolsList = append(toolsList, tool)
	}

	return map[string]any{
		"total_executions": len(e.executionHistory),
		"successful":       successful,
		"failed":           len(e.executionHistory) - successful,
		"average_time":     totalTime / float64(len(e.executionHistory)),
		"tools_used":       toolsList,
	}
}

func (e *ToolExecutor) ExecuteBatch(ctx context.Context, calls []ToolCall, autoConfirm bool) []*ToolResult {
	results := make([]*ToolResult, 0, len(calls))
	for _, call := range calls {
		result := e.Execute(ctx, call.Name, call.Arguments, autoConfirm)
		results = append(results, result)
	}
	return results
}

func (e *ToolExecutor) handleSearchConversations(arguments map[string]any) (map[string]any, error) {
	query, ok := arguments["query"].(string)
	if !ok || query == "" {
		return nil, fmt.Errorf("query is required")
	}
	limit := 10
	if v, ok := arguments["limit"].(int64); ok && v > 0 {
		limit = int(v)
	}

	currentModel := e.scheduler.GetCurrentModelName()
	if currentModel == "" {
		return map[string]any{
			"results": []interface{}{},
			"count":   0,
			"query":   query,
			"message": "No model currently running for search",
		}, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	reqBody := map[string]any{
		"model": currentModel,
		"messages": []map[string]any{
			{"role": "system", "content": "You are a search assistant. Given a query, respond with relevant information."},
			{"role": "user", "content": query},
		},
		"max_tokens":  500,
		"temperature": 0.3,
	}

	port := e.scheduler.GetModelPort(currentModel)
	if port == 0 {
		port = 8000
	}

	result, err := e.sendModelRequest(ctx, port, reqBody)
	if err != nil {
		return map[string]any{
			"results": []interface{}{},
			"count":   0,
			"query":   query,
			"message": fmt.Sprintf("Search unavailable: %v", err),
		}, nil
	}

	return map[string]any{
		"results": []map[string]any{
			{
				"query":   query,
				"content": result,
				"source":  "model_search",
			},
		},
		"count":     1,
		"query":     query,
		"limit":     limit,
		"timestamp": time.Now().Format(time.RFC3339),
	}, nil
}

func (e *ToolExecutor) handleWebSearch(arguments map[string]any) (map[string]any, error) {
	query, ok := arguments["query"].(string)
	if !ok || query == "" {
		return nil, fmt.Errorf("query is required")
	}
	numResults := 5
	if v, ok := arguments["num_results"].(int64); ok && v > 0 {
		numResults = int(v)
	}

	currentModel := e.scheduler.GetCurrentModelName()
	if currentModel == "" {
		return map[string]any{
			"results": []interface{}{},
			"count":   0,
			"query":   query,
			"message": "No model currently running for web search",
		}, nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	reqBody := map[string]any{
		"model": currentModel,
		"messages": []map[string]any{
			{"role": "system", "content": fmt.Sprintf("You are a web search assistant. Provide %d relevant search results for the query. Format each result with title, snippet, and source.", numResults)},
			{"role": "user", "content": query},
		},
		"max_tokens":  1000,
		"temperature": 0.3,
	}

	port := e.scheduler.GetModelPort(currentModel)
	if port == 0 {
		port = 8000
	}

	result, err := e.sendModelRequest(ctx, port, reqBody)
	if err != nil {
		return map[string]any{
			"results": []interface{}{},
			"count":   0,
			"query":   query,
			"message": fmt.Sprintf("Web search unavailable: %v", err),
		}, nil
	}

	return map[string]any{
		"results": []map[string]any{
			{
				"title":   fmt.Sprintf("Search results for: %s", query),
				"snippet": result,
				"source":  "model_knowledge",
			},
		},
		"count":       1,
		"query":       query,
		"num_results": numResults,
		"timestamp":   time.Now().Format(time.RFC3339),
		"note":        "Web search uses model knowledge as fallback (no external search API configured)",
	}, nil
}

func (e *ToolExecutor) sendModelRequest(ctx context.Context, port int, reqBody map[string]any) (string, error) {
	reqData, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("marshal request: %w", err)
	}

	endpoint := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	httpReq, err := http.NewRequestWithContext(ctx, "POST", endpoint, bytes.NewReader(reqData))
	if err != nil {
		return "", fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read response: %w", err)
	}

	var chatResp map[string]any
	if err := json.Unmarshal(body, &chatResp); err != nil {
		return "", fmt.Errorf("parse response: %w", err)
	}

	content := ""
	if choices, ok := chatResp["choices"].([]any); ok && len(choices) > 0 {
		if choice, ok := choices[0].(map[string]any); ok {
			if msg, ok := choice["message"].(map[string]any); ok {
				if c, ok := msg["content"].(string); ok {
					content = c
				}
			}
		}
	}

	return content, nil
}
