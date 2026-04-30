package v1

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"go-vllm-api/internal/model"
	"go-vllm-api/internal/pkg/utils"
	"go-vllm-api/internal/proxy"
	"go-vllm-api/internal/service"

	"github.com/gin-gonic/gin"
)

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

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

func (h *V1Handler) ensureModelReady(c *gin.Context, modelName string) error {
	if h.scheduler.IsModelRunning(modelName) {
		port := h.scheduler.GetModelPort(modelName)
		if err := h.proxy.WaitUntilReady(c.Request.Context(), port, 180*time.Second, 2*time.Second); err == nil {
			return nil
		}
	}

	ok, err := h.scheduler.StartModel(c.Request.Context(), modelName)
	if !ok {
		return fmt.Errorf("failed to start model: %w", err)
	}

	port := h.scheduler.GetModelPort(modelName)
	time.Sleep(8 * time.Second)
	if err := h.proxy.WaitUntilReady(c.Request.Context(), port, 300*time.Second, 3*time.Second); err != nil {
		return fmt.Errorf("model started but readiness probe failed: %w", err)
	}

	return nil
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
	list := make([]gin.H, 0)
	for _, name := range models {
		mc := h.scheduler.GetModelConfig(name)
		modelPath := ""
		if mc != nil {
			modelPath = mc.ModelPath
		}
		info := gin.H{
			"id":              name,
			"object":          "model",
			"running":         h.scheduler.IsModelRunning(name),
			"port":            h.scheduler.GetModelPort(name),
			"supports_images": h.scheduler.GetModelSupportsImages(name),
			"path_exists":     len(modelPath) > 0 && fileExists(modelPath),
		}
		if mc != nil {
			info["description"] = mc.Description
			info["service"] = mc.Service
			info["port"] = mc.Port
		}
		list = append(list, info)
	}

	result := gin.H{
		"object": "list",
		"data":   list,
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
		"id":              modelName,
		"object":          "model",
		"running":         h.scheduler.IsModelRunning(modelName),
		"active_requests": h.scheduler.GetActiveRequests(modelName),
		"supports_images": h.scheduler.GetModelSupportsImages(modelName),
		"port":            h.scheduler.GetModelPort(modelName),
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

	requestID, _ := c.Get("request_id")
	proxyCtx := proxy.ContextWithRequestID(c.Request.Context(), fmt.Sprintf("%v", requestID))

	modelName := req.Model
	stream := req.Stream
	statusCode := 200
	slotAcquired := false

	hasImage, totalImageSize := utils.CountImageContent(req)

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

	var promptTokens, completionTokens int64
	streamSlotAcquired := false

	defer func() {
		if slotAcquired {
			h.scheduler.ReleaseRequest(modelName)
		}
		if streamSlotAcquired {
			h.scheduler.ReleaseStreamSlot(modelName)
		}
		duration := time.Since(start).Seconds()
		h.metrics.RecordRequest("/v1/chat/completions", statusCode, duration,
			service.WithModel(modelName),
			service.WithImage(hasImage, int64(totalImageSize)),
			service.WithTokens(promptTokens, completionTokens, promptTokens+completionTokens))
	}()

	if !h.scheduler.IsModelAvailable(modelName) {
		statusCode = 404
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("Model not found: %s", modelName)})
		return
	}

	if hasImage && !utils.IsMultimodalModel(modelName) {
		statusCode = 400
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("Model %s does not support image inputs. Please use a multimodal model.", modelName)})
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
					"error":        "Too many requests",
					"active":       active,
					"limit":        limit,
					"queue_length": queueLen,
				})
				return
			}
			slotAcquired = true
		} else {
			statusCode = 429
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":        "Too many requests",
				"active":       active,
				"limit":        limit,
				"queue_length": queueLen,
			})
			return
		}
	} else {
		slotAcquired = true
	}

	if err := h.ensureModelReady(c, modelName); err != nil {
		statusCode = 503
		if h.scheduler.IsSwitchingInProgress() {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"error": "Model switch in progress, please wait",
				"retry_after": 5,
			})
		} else {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		}
		return
	}

	h.scheduler.MarkModelSelected(modelName)

	port := h.scheduler.GetModelPort(modelName)
	vllmModelName := h.scheduler.GetModelPath(modelName)

	payload := make(map[string]interface{})
	payloadData, _ := json.Marshal(req)
	json.Unmarshal(payloadData, &payload)
	payload["model"] = vllmModelName

	if stream {
		if !h.scheduler.AcquireStreamSlot(modelName) {
			statusCode = 429
			active := h.scheduler.GetStreamActiveCount(modelName)
			limit := h.scheduler.GetStreamConcurrencyLimit()
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":          "Too many streaming requests",
				"stream_active":  active,
				"stream_limit":   limit,
				"type":           "stream",
			})
			return
		}
		streamSlotAcquired = true

		streamCtx, streamCancel := context.WithTimeout(c.Request.Context(), h.scheduler.GetStreamMaxDuration())
		defer streamCancel()

		// Automatically include usage in streams
		if _, ok := payload["stream_options"]; !ok {
			payload["stream_options"] = map[string]interface{}{"include_usage": true}
		}

		ch, err := h.proxy.StreamChatCompletion(streamCtx, port, payload)
		if err != nil {
			statusCode = 503
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
			return
		}

		chatID := fmt.Sprintf("chatcmpl-%s", randomHex(12))
		c.Header("Content-Type", "text/event-stream")
		c.Header("Cache-Control", "no-cache")
		c.Header("Connection", "keep-alive")
		c.Header("X-Accel-Buffering", "no")

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

			// Try to parse usage from chunk
			if strings.HasPrefix(evt.Data, "data: ") {
				dataStr := strings.TrimPrefix(evt.Data, "data: ")
				var chunk map[string]interface{}
				if err := json.Unmarshal([]byte(dataStr), &chunk); err == nil {
					if usage, ok := chunk["usage"].(map[string]interface{}); ok {
						if p, ok := usage["prompt_tokens"].(float64); ok {
							promptTokens = int64(p)
						}
						if c, ok := usage["completion_tokens"].(float64); ok {
							completionTokens = int64(c)
						}
					}
				}
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

	// Record token usage for non-streaming
	if resMap, ok := result.(map[string]interface{}); ok {
		if usage, ok := resMap["usage"].(map[string]interface{}); ok {
			if p, ok := usage["prompt_tokens"].(float64); ok {
				promptTokens = int64(p)
			}
			if c, ok := usage["completion_tokens"].(float64); ok {
				completionTokens = int64(c)
			}
		}
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

	if err := h.ensureModelReady(c, modelName); err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}

	h.scheduler.MarkModelSelected(modelName)

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

	decoded, err := utils.DecodeBase64Image(req.ImageData)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": err.Error()})
		return
	}

	validation := utils.ValidateImageData(decoded)
	if validation.Valid {
		c.JSON(http.StatusOK, gin.H{
			"success":    true,
			"message":    "Image validation successful",
			"image_info": validation,
		})
	} else {
		c.JSON(http.StatusBadRequest, gin.H{
			"success":    false,
			"message":    validation.Error,
			"image_info": validation,
		})
	}
}

func (h *V1Handler) UploadImage(c *gin.Context) {
	file, err := c.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "No file uploaded"})
		return
	}

	if file.Size > int64(model.MaxImageSizeBytes) {
		c.JSON(http.StatusRequestEntityTooLarge, gin.H{
			"success": false,
			"message": fmt.Sprintf("Image size exceeds maximum allowed size of %dMB", model.MaxImageSizeMB),
		})
		return
	}

	f, err := file.Open()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "Failed to open file"})
		return
	}
	defer f.Close()

	buf := new(bytes.Buffer)
	buf.ReadFrom(f)
	contents := buf.Bytes()

	validation := utils.ValidateImageData(contents)
	if validation.Valid {
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Image uploaded successfully",
			"image_info": gin.H{
				"width":        validation.Width,
				"height":       validation.Height,
				"format":       validation.Format,
				"size_bytes":   validation.SizeBytes,
				"filename":     file.Filename,
				"content_type": file.Header.Get("Content-Type"),
			},
		})
	} else {
		c.JSON(http.StatusBadRequest, gin.H{
			"success":    false,
			"message":    validation.Error,
			"image_info": validation,
		})
	}
}

func (h *V1Handler) GetImageInfo(c *gin.Context) {
	cached := h.cache.Get("api:v1:images:info")
	if cached != nil {
		c.JSON(http.StatusOK, cached)
		return
	}
	result := gin.H{
		"max_size_mb":       model.MaxImageSizeMB,
		"max_dimensions":    fmt.Sprintf("%dx%d", model.MaxWidth, model.MaxHeight),
		"supported_formats": getSupportedFormats(),
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

	if err := h.ensureModelReady(c, req.Model); err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}

	port := h.scheduler.GetModelPort(req.Model)
	payload := map[string]interface{}{
		"prompt":          req.Prompt,
		"n":               req.N,
		"size":            req.Size,
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
		Status: func() string {
			if gpuStatus != nil {
				return "healthy"
			}
			return "degraded"
		}(),
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
