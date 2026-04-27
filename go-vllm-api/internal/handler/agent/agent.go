package agent

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"go-vllm-api/internal/service"
	"go-vllm-api/internal/tools"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

type AgentHandler struct {
	scheduler   *service.Scheduler
	gpuMonitor  *service.GPUMonitor
	toolExecutor *tools.ToolExecutor
	toolRegistry *tools.ToolRegistry
	logger      *zap.Logger
	httpClient  *http.Client
}

type AgentMessage struct {
	Role       string                   `json:"role"`
	Content    string                   `json:"content"`
	ToolCalls  []map[string]any         `json:"tool_calls,omitempty"`
	ToolCallID string                   `json:"tool_call_id,omitempty"`
	Name       string                   `json:"name,omitempty"`
}

type AgentRequest struct {
	Model         string         `json:"model"`
	Messages      []AgentMessage `json:"messages"`
	Tools         []string       `json:"tools,omitempty"`
	MaxIterations int            `json:"max_iterations"`
	Stream        bool           `json:"stream"`
	AutoConfirm   bool           `json:"auto_confirm"`
}

type ToolCallRequest struct {
	Name      string         `json:"name"`
	Arguments map[string]any `json:"arguments"`
}

type ExecuteToolsRequest struct {
	Calls       []ToolCallRequest `json:"calls"`
	AutoConfirm bool              `json:"auto_confirm"`
}

func NewAgentHandler(scheduler *service.Scheduler, gpuMonitor *service.GPUMonitor, toolExecutor *tools.ToolExecutor, toolRegistry *tools.ToolRegistry, logger *zap.Logger) *AgentHandler {
	return &AgentHandler{
		scheduler:    scheduler,
		gpuMonitor:   gpuMonitor,
		toolExecutor: toolExecutor,
		toolRegistry: toolRegistry,
		logger:       logger,
		httpClient: &http.Client{
			Timeout: 120 * time.Second,
		},
	}
}

func (h *AgentHandler) RegisterRoutes(rg *gin.RouterGroup) {
	agent := rg.Group("/manage/agent")
	{
		agent.GET("/tools", h.ListTools)
		agent.GET("/tools/:tool_name", h.GetToolInfo)
		agent.POST("/execute", h.ExecuteTools)
		agent.POST("/execute/:tool_name", h.ExecuteSingleTool)
		agent.GET("/history", h.GetExecutionHistory)
		agent.DELETE("/history", h.ClearExecutionHistory)
		agent.POST("/chat", h.AgentChat)
	}
}

func (h *AgentHandler) ListTools(c *gin.Context) {
	categories := c.Query("categories")

	var toolsList []map[string]any
	if categories != "" {
		categoryList := strings.Split(categories, ",")
		for i, cat := range categoryList {
			categoryList[i] = strings.TrimSpace(cat)
		}
		toolsList = h.toolRegistry.GetOpenAITools(categoryList)
	} else {
		toolsList = h.toolRegistry.GetOpenAITools(nil)
	}

	c.JSON(http.StatusOK, gin.H{
		"tools":      toolsList,
		"categories": h.toolRegistry.GetCategories(),
		"count":      len(toolsList),
	})
}

func (h *AgentHandler) GetToolInfo(c *gin.Context) {
	toolName := c.Param("tool_name")
	tool := h.toolRegistry.Get(toolName)

	if tool == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Tool '%s' not found", toolName)})
		return
	}

	parameters := make([]map[string]any, 0, len(tool.Parameters))
	for _, p := range tool.Parameters {
		paramMap := map[string]any{
			"name":        p.Name,
			"type":        string(p.Type),
			"description": p.Description,
			"required":    p.Required,
		}
		if p.Default != nil {
			paramMap["default"] = p.Default
		}
		if len(p.Enum) > 0 {
			paramMap["enum"] = p.Enum
		}
		parameters = append(parameters, paramMap)
	}

	c.JSON(http.StatusOK, gin.H{
		"name":                 tool.Name,
		"description":          tool.Description,
		"parameters":           parameters,
		"category":             tool.Category,
		"dangerous":            tool.Dangerous,
		"requires_confirmation": tool.RequiresConfirmation,
		"openai_schema":        tool.ToOpenAIFunction(),
	})
}

func (h *AgentHandler) ExecuteTools(c *gin.Context) {
	var req ExecuteToolsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	calls := make([]tools.ToolCall, 0, len(req.Calls))
	for _, call := range req.Calls {
		calls = append(calls, tools.ToolCall{
			Name:      call.Name,
			Arguments: call.Arguments,
		})
	}

	results := h.toolExecutor.ExecuteBatch(c.Request.Context(), calls, req.AutoConfirm)

	resultList := make([]map[string]any, 0, len(results))
	allSuccess := true
	for _, r := range results {
		resultList = append(resultList, map[string]any{
			"tool_name":      r.ToolName,
			"success":        r.Success,
			"result":         r.Result,
			"error":          r.Error,
			"execution_time": r.ExecutionTime,
			"timestamp":      r.Timestamp,
		})
		if !r.Success {
			allSuccess = false
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"results": resultList,
		"success": allSuccess,
	})
}

func (h *AgentHandler) ExecuteSingleTool(c *gin.Context) {
	_ = c.Param("tool_name")
	var req ToolCallRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	autoConfirm := false
	result := h.toolExecutor.Execute(c.Request.Context(), req.Name, req.Arguments, autoConfirm)

	c.JSON(http.StatusOK, gin.H{
		"tool_name":      result.ToolName,
		"success":        result.Success,
		"result":         result.Result,
		"error":          result.Error,
		"execution_time": result.ExecutionTime,
		"timestamp":      result.Timestamp,
	})
}

func (h *AgentHandler) GetExecutionHistory(c *gin.Context) {
	limit := 100
	if l := c.Query("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}

	history := h.toolExecutor.GetHistory(limit)
	stats := h.toolExecutor.GetStatistics()

	historyList := make([]map[string]any, 0, len(history))
	for _, r := range history {
		historyList = append(historyList, map[string]any{
			"tool_name":      r.ToolName,
			"success":        r.Success,
			"result":         r.Result,
			"error":          r.Error,
			"execution_time": r.ExecutionTime,
			"timestamp":      r.Timestamp,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"history":    historyList,
		"statistics": stats,
	})
}

func (h *AgentHandler) ClearExecutionHistory(c *gin.Context) {
	h.toolExecutor.ClearHistory()
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "History cleared"})
}

func (h *AgentHandler) AgentChat(c *gin.Context) {
	var req AgentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	modelName := req.Model
	if modelName == "" {
		modelName = h.scheduler.GetDefaultModel()
	}
	if modelName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No model specified and no default set"})
		return
	}

	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	if !h.scheduler.IsModelRunning(modelName) {
		ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
		if !ok {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": fmt.Sprintf("Failed to start model: %v", err)})
			return
		}
		time.Sleep(5 * time.Second)
	}

	var toolsList []string
	if len(req.Tools) > 0 {
		toolsList = req.Tools
	}
	openAITools := h.toolRegistry.GetOpenAITools(toolsList)

	vllmPort := h.scheduler.GetModelPort(modelName)
	backendURL := fmt.Sprintf("http://localhost:%d", vllmPort)
	vllmModelName := h.scheduler.GetModelPath(modelName)
	if vllmModelName == "" {
		vllmModelName = modelName
	}

	h.logger.Info("agent chat request",
		zap.String("model", modelName),
		zap.String("vllm_model", vllmModelName),
		zap.String("backend_url", backendURL))

	if req.Stream {
		c.Header("Content-Type", "text/event-stream")
		c.Header("Cache-Control", "no-cache")
		c.Header("Connection", "keep-alive")
		c.Stream(func(w io.Writer) bool {
			ch := make(chan string, 1)
			go func() {
				h.agentStream(c.Request.Context(), backendURL, vllmModelName, req.Messages, openAITools, req.MaxIterations, req.AutoConfirm, ch)
				close(ch)
			}()

			for data := range ch {
				fmt.Fprint(w, data)
				if f, ok := w.(http.Flusher); ok {
					f.Flush()
				}
			}
			return false
		})
		return
	}

	result := h.agentCompletion(c.Request.Context(), backendURL, vllmModelName, req.Messages, openAITools, req.MaxIterations, req.AutoConfirm)
	c.JSON(http.StatusOK, result)
}

func (h *AgentHandler) agentCompletion(ctx context.Context, backendURL, modelName string, messages []AgentMessage, toolsList []map[string]any, maxIterations int, autoConfirm bool) map[string]any {
	openaiMessages := h.convertMessagesToOpenAI(messages)
	iteration := 0

	for iteration < maxIterations {
		iteration++

		payload := map[string]any{
			"model":       modelName,
			"messages":    openaiMessages,
			"tools":       toolsList,
			"tool_choice": "auto",
			"max_tokens":  2048,
		}

		data, err := h.postToVLLM(ctx, backendURL, "/v1/chat/completions", payload)
		if err != nil {
			return map[string]any{"error": fmt.Sprintf("Model API error: %s", err.Error())}
		}

		choices, ok := data["choices"].([]any)
		if !ok || len(choices) == 0 {
			return map[string]any{"error": "No choices in response"}
		}

		message, ok := choices[0].(map[string]any)["message"].(map[string]any)
		if !ok {
			return map[string]any{"error": "No message in response"}
		}

		toolCalls, hasToolCalls := message["tool_calls"].([]any)
		if !hasToolCalls || len(toolCalls) == 0 {
			return map[string]any{
				"id":        data["id"],
				"model":     modelName,
				"message":   message,
				"iterations": iteration,
				"finished":  true,
			}
		}

		openaiMessages = append(openaiMessages, message)

		calls := make([]tools.ToolCall, 0, len(toolCalls))
		for _, tc := range toolCalls {
			toolCall, ok := tc.(map[string]any)
			if !ok {
				continue
			}
			funcInfo, ok := toolCall["function"].(map[string]any)
			if !ok {
				continue
			}
			name, _ := funcInfo["name"].(string)
			argsStr, _ := funcInfo["arguments"].(string)

			var args map[string]any
			if argsStr != "" {
				if err := json.Unmarshal([]byte(argsStr), &args); err != nil {
					args = make(map[string]any)
				}
			} else {
				args = make(map[string]any)
			}

			calls = append(calls, tools.ToolCall{
				Name:      name,
				Arguments: args,
			})

			results := h.toolExecutor.ExecuteBatch(ctx, calls, autoConfirm)

			for i, result := range results {
				toolCallID := ""
				if i < len(toolCalls) {
					if tc, ok := toolCalls[i].(map[string]any); ok {
						toolCallID, _ = tc["id"].(string)
					}
				}

				content := ""
				if result.Success {
					if jsonData, err := json.Marshal(result.Result); err == nil {
						content = string(jsonData)
					} else {
						content = fmt.Sprintf("%v", result.Result)
					}
				} else {
					if errData, err := json.Marshal(map[string]any{"error": result.Error}); err == nil {
						content = string(errData)
					} else {
						content = result.Error
					}
				}

				openaiMessages = append(openaiMessages, map[string]any{
					"role":         "tool",
					"tool_call_id": toolCallID,
					"content":      content,
				})
			}
		}
	}

	return map[string]any{"error": "Max iterations reached", "iterations": iteration}
}

func (h *AgentHandler) agentStream(ctx context.Context, backendURL, modelName string, messages []AgentMessage, toolsList []map[string]any, maxIterations int, autoConfirm bool, ch chan<- string) {
	openaiMessages := h.convertMessagesToOpenAI(messages)
	iteration := 0

	for iteration < maxIterations {
		iteration++

		payload := map[string]any{
			"model":       modelName,
			"messages":    openaiMessages,
			"tools":       toolsList,
			"tool_choice": "auto",
			"max_tokens":  2048,
		}

		data, err := h.postToVLLM(ctx, backendURL, "/v1/chat/completions", payload)
		if err != nil {
			ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": err.Error()}))
			return
		}

		choices, ok := data["choices"].([]any)
		if !ok || len(choices) == 0 {
			ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": "No choices in response"}))
			return
		}

		message, ok := choices[0].(map[string]any)["message"].(map[string]any)
		if !ok {
			ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": "No message in response"}))
			return
		}

		toolCalls, hasToolCalls := message["tool_calls"].([]any)
		if !hasToolCalls || len(toolCalls) == 0 {
			payload["stream"] = true
			h.streamFromVLLM(ctx, backendURL, "/v1/chat/completions", payload, ch)
			return
		}

		ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{
			"type":  "tool_calls_start",
			"calls": len(toolCalls),
		}))

		openaiMessages = append(openaiMessages, message)

		for _, tc := range toolCalls {
			toolCall, ok := tc.(map[string]any)
			if !ok {
				continue
			}
			funcInfo, ok := toolCall["function"].(map[string]any)
			if !ok {
				continue
			}
			name, _ := funcInfo["name"].(string)
			argsStr, _ := funcInfo["arguments"].(string)
			tcID, _ := toolCall["id"].(string)

			ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{
				"type": "tool_executing",
				"name": name,
				"id":   tcID,
			}))

			var args map[string]any
			if argsStr != "" {
				if err := json.Unmarshal([]byte(argsStr), &args); err != nil {
					args = make(map[string]any)
				}
			} else {
				args = make(map[string]any)
			}

			result := h.toolExecutor.Execute(ctx, name, args, autoConfirm)

			ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{
				"type":    "tool_result",
				"name":    name,
				"id":      tcID,
				"success": result.Success,
				"result":  result.Result,
				"error":   result.Error,
			}))

			content := ""
			if result.Success {
				if jsonData, err := json.Marshal(result.Result); err == nil {
					content = string(jsonData)
				} else {
					content = fmt.Sprintf("%v", result.Result)
				}
			} else {
				if errData, err := json.Marshal(map[string]any{"error": result.Error}); err == nil {
					content = string(errData)
				} else {
					content = result.Error
				}
			}

			openaiMessages = append(openaiMessages, map[string]any{
				"role":         "tool",
				"tool_call_id": tcID,
				"content":      content,
			})
		}

		ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{
			"type":      "tool_calls_end",
			"calls":     len(toolCalls),
			"iteration": iteration,
		}))
	}

	ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": "Max iterations reached"}))
}

func (h *AgentHandler) postToVLLM(ctx context.Context, baseURL, path string, payload map[string]any) (map[string]any, error) {
	url := baseURL + path
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := h.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("VLLM returned status %d", resp.StatusCode)
	}

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return result, nil
}

func (h *AgentHandler) streamFromVLLM(ctx context.Context, baseURL, path string, payload map[string]any, ch chan<- string) {
	url := baseURL + path
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": err.Error()}))
		return
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payloadBytes))
	if err != nil {
		ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": err.Error()}))
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := h.httpClient.Do(req)
	if err != nil {
		ch <- fmt.Sprintf("data: %s\n\n", h.mustJSON(map[string]any{"error": err.Error()}))
		return
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "data: ") {
			ch <- line + "\n\n"
		}
	}
}

func (h *AgentHandler) convertMessagesToOpenAI(messages []AgentMessage) []map[string]any {
	result := make([]map[string]any, 0, len(messages))
	for _, msg := range messages {
		item := map[string]any{
			"role":    msg.Role,
			"content": msg.Content,
		}
		if len(msg.ToolCalls) > 0 {
			item["tool_calls"] = msg.ToolCalls
		}
		if msg.ToolCallID != "" {
			item["tool_call_id"] = msg.ToolCallID
		}
		if msg.Name != "" {
			item["name"] = msg.Name
		}
		result = append(result, item)
	}
	return result
}

func (h *AgentHandler) mustJSON(v any) string {
	data, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf(`{"error":"json marshal failed: %s"}`, err.Error())
	}
	return string(data)
}
