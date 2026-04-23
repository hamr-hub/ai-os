package v1

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"go-vllm-api/internal/model"
	"go-vllm-api/internal/proxy"
	"go-vllm-api/internal/service"

	"github.com/gin-gonic/gin"
)

type V1Handler struct {
	scheduler  *service.Scheduler
	gpuMonitor *service.GPUMonitor
	proxy      *proxy.VLLMProxy
	metrics    *service.MetricsCollector
	cache      *service.CacheService
}

func NewV1Handler(scheduler *service.Scheduler, gpuMonitor *service.GPUMonitor, proxy *proxy.VLLMProxy, metrics *service.MetricsCollector, cache *service.CacheService) *V1Handler {
	return &V1Handler{
		scheduler:  scheduler,
		gpuMonitor: gpuMonitor,
		proxy:      proxy,
		metrics:    metrics,
		cache:      cache,
	}
}

func (h *V1Handler) RegisterRoutes(rg *gin.RouterGroup) {
	v1 := rg.Group("/v1")
	{
		v1.GET("/models", h.ListModels)
		v1.GET("/models/:model_name", h.GetModelInfo)
		v1.POST("/chat/completions", h.ChatCompletions)
		v1.POST("/embeddings", h.CreateEmbeddings)
		v1.POST("/images/validate", h.ValidateImage)
		v1.POST("/images/upload", h.UploadImage)
		v1.GET("/images/info", h.GetImageInfo)
		v1.POST("/images/generations", h.GenerateImage)
		v1.GET("/status", h.GetStatus)
	}
}

func (h *V1Handler) ListModels(c *gin.Context) {
	refresh := c.Query("refresh") == "true"
	cacheKey := "api:v1:models"

	if !refresh {
		if cached := h.cache.Get(cacheKey); cached != nil {
			c.JSON(http.StatusOK, cached)
			return
		}
	}

	models := h.scheduler.GetAvailableModels()
	list := make([]model.ModelInfo, 0)
	for _, name := range models {
		mc := h.scheduler.GetModelConfig(name)
		info := model.ModelInfo{
			ID:     name,
			Object: "model",
			Running: h.scheduler.IsModelRunning(name),
			Port:   8000,
		}
		if mc != nil {
			info.SupportsImages = mc.SupportsImages
			info.Description = mc.Description
			info.Service = mc.Service
			info.Port = mc.Port
		}
		list = append(list, info)
	}

	result := model.ModelsListResponse{
		Object: "list",
		Data:   list,
	}
	h.cache.Set(cacheKey, result, 300)
	c.JSON(http.StatusOK, result)
}

func (h *V1Handler) GetModelInfo(c *gin.Context) {
	modelName := c.Param("model_name")
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}
	mc := h.scheduler.GetModelConfig(modelName)
	info := gin.H{
		"id":               modelName,
		"object":           "model",
		"running":          h.scheduler.IsModelRunning(modelName),
		"active_requests":  h.scheduler.GetActiveRequests(modelName),
		"supports_images":  h.scheduler.GetModelSupportsImages(modelName),
		"port":             h.scheduler.GetModelPort(modelName),
	}
	if mc != nil {
		info["description"] = mc.Description
		info["service"] = mc.Service
		info["required_memory"] = mc.RequiredMemory
		info["preload"] = mc.Preload
		info["keep_alive"] = mc.KeepAlive
	}
	c.JSON(http.StatusOK, info)
}

func (h *V1Handler) ChatCompletions(c *gin.Context) {
	start := time.Now()
	var req model.ChatCompletionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	modelName := req.Model
	stream := req.Stream
	statusCode := 200
	slotAcquired := false

	if modelName == "" || modelName == "default" {
		modelName = h.scheduler.GetDefaultModel()
		if modelName == "" {
			modelName = h.scheduler.GetCurrentModelName()
		}
		if modelName == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "No default model set and no model specified"})
			return
		}
	}

	defer func() {
		if slotAcquired {
			h.scheduler.ReleaseRequest(modelName)
		}
		duration := time.Since(start).Seconds()
		h.metrics.RecordRequest("/v1/chat/completions", statusCode, duration, service.WithModel(modelName))
	}()

	if !h.scheduler.IsModelAvailable(modelName) {
		statusCode = 404
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	if !h.scheduler.AcquireRequest(modelName) {
		active := h.scheduler.GetActiveRequests(modelName)
		limit := h.scheduler.GetConcurrencyLimit()
		queueLen := h.scheduler.GetQueueLength(modelName)
		if h.scheduler.IsQueueAvailable(modelName) {
			ok := h.scheduler.WaitForSlot(c.Request.Context(), modelName, 30*time.Second)
			if !ok {
				statusCode = 429
				c.JSON(http.StatusTooManyRequests, gin.H{
					"error":          "Too many requests",
					"active":         active,
					"limit":          limit,
					"queue_length":   queueLen,
				})
				return
			}
			slotAcquired = true
		} else {
			statusCode = 429
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":          "Too many requests",
				"active":         active,
				"limit":          limit,
				"queue_length":   queueLen,
			})
			return
		}
	} else {
		slotAcquired = true
	}

	if !h.scheduler.IsModelRunning(modelName) {
		ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
		if !ok {
			statusCode = 503
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": fmt.Sprintf("Failed to start model: %v", err)})
			return
		}
		time.Sleep(5 * time.Second)
	}

	port := h.scheduler.GetModelPort(modelName)
	vllmModelName := h.scheduler.GetModelPath(modelName)

	payload := make(map[string]interface{})
	data, _ := json.Marshal(req)
	json.Unmarshal(data, &payload)
	payload["model"] = vllmModelName

	if stream {
		ch, err := h.proxy.StreamChatCompletion(c.Request.Context(), port, payload)
		if err != nil {
			statusCode = 503
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
			return
		}

		chatID := fmt.Sprintf("chatcmpl-%s", randomHex(12))
		c.Header("Content-Type", "text/event-stream")
		c.Header("Cache-Control", "no-cache")
		c.Header("Connection", "keep-alive")

		c.Stream(func(w io.Writer) bool {
			evt, ok := <-ch
			if !ok {
				return false
			}
			if evt.Error != nil {
				return false
			}
			if evt.Done {
				doneChunk := map[string]interface{}{
					"id":      chatID,
					"object":  "chat.completion.chunk",
					"created": time.Now().Unix(),
					"model":   modelName,
					"choices": []map[string]interface{}{{"index": 0, "delta": map[string]interface{}{}, "finish_reason": "stop"}},
				}
				data, _ := json.Marshal(doneChunk)
				fmt.Fprintf(w, "data: %s\n\n", string(data))
				fmt.Fprintf(w, "data: [DONE]\n\n")
				return false
			}
			fmt.Fprintf(w, "%s\n", evt.Data)
			return true
		})
		statusCode = 200
		return
	}

	result, err := h.proxy.ChatCompletion(c.Request.Context(), port, payload)
	if err != nil {
		statusCode = 503
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}
	statusCode = 200
	c.JSON(http.StatusOK, result)
}

func (h *V1Handler) CreateEmbeddings(c *gin.Context) {
	start := time.Now()
	var req model.EmbeddingRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	modelName := req.Model
	if !h.scheduler.IsModelAvailable(modelName) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	slotAcquired := false
	defer func() {
		if slotAcquired {
			h.scheduler.ReleaseRequest(modelName)
		}
		h.metrics.RecordRequest("/v1/embeddings", 200, time.Since(start).Seconds(), service.WithModel(modelName))
	}()

	if !h.scheduler.AcquireRequest(modelName) {
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "Too many requests"})
		return
	}
	slotAcquired = true

	if !h.scheduler.IsModelRunning(modelName) {
		ok, _ := h.scheduler.StartModel(c.Request.Context(), modelName)
		if !ok {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Failed to start model"})
			return
		}
		time.Sleep(5 * time.Second)
	}

	port := h.scheduler.GetModelPort(modelName)
	payload := map[string]interface{}{
		"model":           h.scheduler.GetModelPath(modelName),
		"input":           req.Input,
		"encoding_format": req.EncodingFormat,
	}
	if req.Dimensions != nil {
		payload["dimensions"] = *req.Dimensions
	}

	result, err := h.proxy.Embeddings(c.Request.Context(), port, payload)
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *V1Handler) ValidateImage(c *gin.Context) {
	var req model.ImageValidationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Image validation not yet implemented in Go"})
}

func (h *V1Handler) UploadImage(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"success": false, "message": "Image upload not yet implemented in Go"})
}

func (h *V1Handler) GetImageInfo(c *gin.Context) {
	cached := h.cache.Get("api:v1:images:info")
	if cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}
	result := gin.H{
		"max_size_mb":        model.MaxImageSizeMB,
		"max_dimensions":     fmt.Sprintf("%dx%d", model.MaxWidth, model.MaxHeight),
		"supported_formats":  getSupportedFormats(),
	}
	h.cache.Set("api:v1:images:info", result, 3600)
	c.JSON(http.StatusOK, result)
}

func (h *V1Handler) GenerateImage(c *gin.Context) {
	var req model.ImageGenerationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if !h.scheduler.IsModelAvailable(req.Model) {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", req.Model)})
		return
	}

	if !h.scheduler.IsModelRunning(req.Model) {
		ok, _ := h.scheduler.StartModel(c.Request.Context(), req.Model)
		if !ok {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Failed to start model"})
			return
		}
		time.Sleep(5 * time.Second)
	}

	port := h.scheduler.GetModelPort(req.Model)
	payload := map[string]interface{}{
		"prompt":          req.Prompt,
		"n":              req.N,
		"size":           req.Size,
		"response_format": req.ResponseFormat,
	}

	result, err := h.proxy.PostEndpoint(c.Request.Context(), port, "/v1/images/generations", payload)
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *V1Handler) GetStatus(c *gin.Context) {
	gpuStatus := h.gpuMonitor.GetStatus()
	models := h.scheduler.GetAvailableModels()
	running := 0
	for _, m := range models {
		if h.scheduler.IsModelRunning(m) {
			running++
		}
	}
	c.JSON(http.StatusOK, model.APIStatus{
		Status:          func() string { if gpuStatus != nil { return "healthy" }; return "degraded" }(),
		Timestamp:       time.Now().Format(time.RFC3339),
		GPUAvailable:    gpuStatus != nil,
		AvailableModels: len(models),
		RunningModels:   running,
		Models:          buildModelStatuses(models, h.scheduler),
	})
}

func buildModelStatuses(models []string, s *service.Scheduler) []map[string]interface{} {
	result := make([]map[string]interface{}, len(models))
	for i, m := range models {
		result[i] = map[string]interface{}{
			"name":    m,
			"running": s.IsModelRunning(m),
		}
	}
	return result
}

func getSupportedFormats() []string {
	formats := make([]string, 0, len(model.SupportedFormats))
	for f := range model.SupportedFormats {
		formats = append(formats, f)
	}
	return formats
}

func randomHex(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return hex.EncodeToString(b)
}
