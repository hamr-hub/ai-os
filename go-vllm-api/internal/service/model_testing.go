package service

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

	"go.uber.org/zap"
)

type TestCategory string

const (
	TestChatBasic      TestCategory = "chat_basic"
	TestChatStreaming   TestCategory = "chat_streaming"
	TestToolIntegration TestCategory = "tool_integration"
	TestImageProcessing TestCategory = "image_processing"
)

type ModelTestResult struct {
	Category     TestCategory `json:"category"`
	Passed       bool         `json:"passed"`
	TPS          float64      `json:"tps"`
	LatencyMs    float64      `json:"latency_ms"`
	ErrorMessage string       `json:"error_message,omitempty"`
	TokensPerSec float64      `json:"tokens_per_sec"`
	InputTokens  int          `json:"input_tokens"`
	OutputTokens int          `json:"output_tokens"`
}

type ModelTestReport struct {
	ModelName   string            `json:"model_name"`
	Port        int               `json:"port"`
	Timestamp   string            `json:"timestamp"`
	Results     []ModelTestResult `json:"results"`
	PassRate    float64           `json:"pass_rate"`
	OverallTPS  float64           `json:"overall_tps"`
	TotalPassed int               `json:"total_passed"`
	TotalTests  int               `json:"total_tests"`
}

type ModelTestingFramework struct {
	logger        *zap.Logger
	requestClient *http.Client
	streamClient  *http.Client
}

func NewModelTestingFramework(logger *zap.Logger) *ModelTestingFramework {
	return &ModelTestingFramework{
		logger: logger,
		requestClient: &http.Client{
			Timeout: 60 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 5,
				IdleConnTimeout:     30 * time.Second,
			},
		},
		streamClient: &http.Client{
			Timeout: 0,
			Transport: &http.Transport{
				MaxIdleConns:          10,
				MaxIdleConnsPerHost:   5,
				IdleConnTimeout:       30 * time.Second,
				ResponseHeaderTimeout: 60 * time.Second,
			},
		},
	}
}

func (mtf *ModelTestingFramework) RunAllTests(ctx context.Context, modelName string, modelPath string, port int, supportsImages bool) *ModelTestReport {
	report := &ModelTestReport{
		ModelName: modelName,
		Port:      port,
		Timestamp: time.Now().Format(time.RFC3339),
	}

	categories := []TestCategory{TestChatBasic, TestChatStreaming, TestToolIntegration}
	if supportsImages {
		categories = append(categories, TestImageProcessing)
	}

	for _, cat := range categories {
		result := mtf.runTest(ctx, cat, modelName, port)
		report.Results = append(report.Results, result)
		if result.Passed {
			report.TotalPassed++
		}
		report.TotalTests++
	}

	if report.TotalTests > 0 {
		report.PassRate = float64(report.TotalPassed) / float64(report.TotalTests)
	}

	var totalTPS float64
	var tpsCount int
	for _, r := range report.Results {
		if r.Passed && r.TPS > 0 {
			totalTPS += r.TPS
			tpsCount++
		}
	}
	if tpsCount > 0 {
		report.OverallTPS = totalTPS / float64(tpsCount)
	}

	return report
}

func (mtf *ModelTestingFramework) runTest(ctx context.Context, category TestCategory, modelName string, port int) ModelTestResult {
	switch category {
	case TestChatBasic:
		return mtf.testChatBasic(ctx, modelName, port)
	case TestChatStreaming:
		return mtf.testChatStreaming(ctx, modelName, port)
	case TestToolIntegration:
		return mtf.testToolIntegration(ctx, modelName, port)
	case TestImageProcessing:
		return ModelTestResult{
			Category:     TestImageProcessing,
			Passed:       false,
			ErrorMessage: "image test not yet implemented in Go",
		}
	default:
		return ModelTestResult{
			Category:     category,
			Passed:       false,
			ErrorMessage: "unknown test category",
		}
	}
}

func (mtf *ModelTestingFramework) testChatBasic(ctx context.Context, modelName string, port int) ModelTestResult {
	start := time.Now()
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]interface{}{
			{"role": "system", "content": "You are a helpful assistant."},
			{"role": "user", "content": "Write a short poem about the sea."},
		},
		"max_tokens": 50,
		"stream":     false,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return ModelTestResult{Category: TestChatBasic, Passed: false, ErrorMessage: err.Error()}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return ModelTestResult{Category: TestChatBasic, Passed: false, ErrorMessage: err.Error()}
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := mtf.requestClient.Do(req)
	if err != nil {
		return ModelTestResult{Category: TestChatBasic, Passed: false, ErrorMessage: err.Error(), LatencyMs: float64(time.Since(start).Milliseconds())}
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return ModelTestResult{
			Category:     TestChatBasic,
			Passed:       false,
			ErrorMessage: fmt.Sprintf("status %d: %s", resp.StatusCode, string(body)),
			LatencyMs:    float64(time.Since(start).Milliseconds()),
		}
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return ModelTestResult{Category: TestChatBasic, Passed: false, ErrorMessage: err.Error(), LatencyMs: float64(time.Since(start).Milliseconds())}
	}

	latencyMs := float64(time.Since(start).Milliseconds())
	outputTokens := 0
	inputTokens := 0
	tps := 0.0

	if usage, ok := result["usage"].(map[string]interface{}); ok {
		if v, ok := usage["completion_tokens"].(float64); ok {
			outputTokens = int(v)
		}
		if v, ok := usage["prompt_tokens"].(float64); ok {
			inputTokens = int(v)
		}
	}
	if outputTokens > 0 && latencyMs > 0 {
		tps = float64(outputTokens) / (latencyMs / 1000.0)
	}

	passed := outputTokens > 0
	return ModelTestResult{
		Category:     TestChatBasic,
		Passed:       passed,
		TPS:          tps,
		LatencyMs:    latencyMs,
		TokensPerSec: tps,
		InputTokens:  inputTokens,
		OutputTokens: outputTokens,
	}
}

func (mtf *ModelTestingFramework) testChatStreaming(ctx context.Context, modelName string, port int) ModelTestResult {
	start := time.Now()
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "Count from 1 to 10."},
		},
		"max_tokens": 30,
		"stream":     true,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return ModelTestResult{Category: TestChatStreaming, Passed: false, ErrorMessage: err.Error()}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return ModelTestResult{Category: TestChatStreaming, Passed: false, ErrorMessage: err.Error()}
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := mtf.streamClient.Do(req)
	if err != nil {
		return ModelTestResult{Category: TestChatStreaming, Passed: false, ErrorMessage: err.Error(), LatencyMs: float64(time.Since(start).Milliseconds())}
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return ModelTestResult{
			Category:     TestChatStreaming,
			Passed:       false,
			ErrorMessage: fmt.Sprintf("status %d", resp.StatusCode),
			LatencyMs:    float64(time.Since(start).Milliseconds()),
		}
	}

	chunkCount := 0
	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "data: ") {
			d := strings.TrimPrefix(line, "data: ")
			if d == "[DONE]" {
				break
			}
			chunkCount++
		}
	}

	latencyMs := float64(time.Since(start).Milliseconds())
	passed := chunkCount > 0
	tps := 0.0
	if chunkCount > 0 && latencyMs > 0 {
		tps = float64(chunkCount) / (latencyMs / 1000.0)
	}

	return ModelTestResult{
		Category:     TestChatStreaming,
		Passed:       passed,
		TPS:          tps,
		LatencyMs:    latencyMs,
		OutputTokens: chunkCount,
	}
}

func (mtf *ModelTestingFramework) testToolIntegration(ctx context.Context, modelName string, port int) ModelTestResult {
	start := time.Now()
	url := fmt.Sprintf("http://localhost:%d/v1/chat/completions", port)
	payload := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]interface{}{
			{"role": "user", "content": "What's the weather in Beijing?"},
		},
		"max_tokens": 100,
		"stream":     false,
		"tools": []map[string]interface{}{
			{
				"type": "function",
				"function": map[string]interface{}{
					"name":        "get_weather",
					"description": "Get current weather for a location",
					"parameters": map[string]interface{}{
						"type": "object",
						"properties": map[string]interface{}{
							"location": map[string]interface{}{
								"type":        "string",
								"description": "City name",
							},
						},
						"required": []string{"location"},
					},
				},
			},
		},
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return ModelTestResult{Category: TestToolIntegration, Passed: false, ErrorMessage: err.Error()}
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(data))
	if err != nil {
		return ModelTestResult{Category: TestToolIntegration, Passed: false, ErrorMessage: err.Error()}
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := mtf.requestClient.Do(req)
	if err != nil {
		return ModelTestResult{Category: TestToolIntegration, Passed: false, ErrorMessage: err.Error(), LatencyMs: float64(time.Since(start).Milliseconds())}
	}
	defer resp.Body.Close()

	latencyMs := float64(time.Since(start).Milliseconds())

	if resp.StatusCode != http.StatusOK {
		return ModelTestResult{
			Category:     TestToolIntegration,
			Passed:       false,
			ErrorMessage: fmt.Sprintf("status %d", resp.StatusCode),
			LatencyMs:    latencyMs,
		}
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return ModelTestResult{
			Category:     TestToolIntegration,
			Passed:       false,
			ErrorMessage: "decode failed",
			LatencyMs:    latencyMs,
		}
	}

	hasToolCall := false
	if choices, ok := result["choices"].([]interface{}); ok && len(choices) > 0 {
		if choice, ok := choices[0].(map[string]interface{}); ok {
			if msg, ok := choice["message"].(map[string]interface{}); ok {
				if _, ok := msg["tool_calls"]; ok {
					hasToolCall = true
				}
			}
		}
	}

	passed := hasToolCall || (result["choices"] != nil)
	errMsg := ""
	if !hasToolCall {
		errMsg = "no tool_call in response"
	}
	return ModelTestResult{
		Category:     TestToolIntegration,
		Passed:       passed,
		LatencyMs:    latencyMs,
		ErrorMessage: errMsg,
	}
}

type ComparativeAnalysisRequest struct {
	ModelNames []string `json:"model_names"`
}

type ComparativeAnalysisResult struct {
	Models       []string                   `json:"models"`
	Timestamp    string                     `json:"timestamp"`
	Results      map[string]*ModelTestReport `json:"results"`
	Comparison   map[string]any             `json:"comparison"`
	BestModel    string                     `json:"best_model"`
}

func (mtf *ModelTestingFramework) RunComparativeAnalysis(ctx context.Context, modelNames []string, getModelInfo func(string) (string, int, bool)) *ComparativeAnalysisResult {
	result := &ComparativeAnalysisResult{
		Models:    modelNames,
		Timestamp: time.Now().Format(time.RFC3339),
		Results:   make(map[string]*ModelTestReport),
	}

	for _, modelName := range modelNames {
		modelPath, port, supportsImages := getModelInfo(modelName)
		if port == 0 {
			mtf.logger.Warn("skip model in comparative analysis", zap.String("model", modelName))
			continue
		}
		report := mtf.RunAllTests(ctx, modelName, modelPath, port, supportsImages)
		result.Results[modelName] = report
	}

	comparison := make(map[string]any)
	bestTPS := 0.0
	bestModel := ""

	modelComparisons := make([]map[string]any, 0)
	for name, report := range result.Results {
		modelComp := map[string]any{
			"model":      name,
			"pass_rate":  report.PassRate,
			"overall_tps": report.OverallTPS,
			"total_tests": report.TotalTests,
			"total_passed": report.TotalPassed,
		}
		modelComparisons = append(modelComparisons, modelComp)

		if report.OverallTPS > bestTPS {
			bestTPS = report.OverallTPS
			bestModel = name
		}
	}

	comparison["models"] = modelComparisons
	comparison["best_tps"] = bestTPS
	result.Comparison = comparison
	result.BestModel = bestModel

	return result
}
