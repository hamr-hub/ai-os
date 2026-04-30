package ws

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"go-vllm-api/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"go.uber.org/zap"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type GPUMonitorAccessor interface {
	GetStatus() *service.GPUStatus
}

type SchedulerAccessor interface {
	GetAvailableModels() []string
	IsModelRunning(model string) bool
	GetModelPort(model string) int
	GetModelService(model string) string
	GetActiveRequests(model string) int
	IsModelPreloaded(model string) bool
	GetCurrentModelName() string
	GetDefaultModel() string
	IsSwitchingInProgress() bool
	GetStreamActiveCount(model string) int
}

type WSHandler struct {
	manager    *service.WSManager
	logger     *zap.Logger
	gpuMonitor GPUMonitorAccessor
	scheduler  SchedulerAccessor
}

func NewWSHandler(manager *service.WSManager, logger *zap.Logger) *WSHandler {
	return &WSHandler{manager: manager, logger: logger}
}

func NewWSHandlerWithState(manager *service.WSManager, logger *zap.Logger, gpuMonitor GPUMonitorAccessor, scheduler SchedulerAccessor) *WSHandler {
	return &WSHandler{manager: manager, logger: logger, gpuMonitor: gpuMonitor, scheduler: scheduler}
}

func (h *WSHandler) RegisterRoutes(rg *gin.RouterGroup) {
	rg.GET("/ws/monitor", h.Monitor)
	rg.GET("/ws/model-switch", h.ModelSwitch)
}

func (h *WSHandler) ModelSwitch(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		h.logger.Error("ws upgrade", zap.Error(err))
		return
	}
	h.manager.Connect(conn, "model_switch")
	defer h.manager.Disconnect(conn, "model_switch")

	h.sendSwitchStateSync(conn)

	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
}

func (h *WSHandler) sendSwitchStateSync(conn *websocket.Conn) {
	baseURL := os.Getenv("PYTHON_BACKEND_URL")
	if baseURL == "" {
		baseURL = "http://192.168.7.103:35000"
	}

	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(baseURL + "/manage/switch/status")
	if err != nil {
		h.logger.Debug("failed to fetch switch status for state sync", zap.Error(err))
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		h.logger.Debug("switch status returned non-OK", zap.Int("status", resp.StatusCode))
		return
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.logger.Debug("failed to read switch status body", zap.Error(err))
		return
	}

	var statusData map[string]interface{}
	if err := json.Unmarshal(body, &statusData); err != nil {
		h.logger.Debug("failed to parse switch status", zap.Error(err))
		return
	}

	isSwitching, _ := statusData["is_switching"].(bool)
	session := statusData["session"]

	stateSyncMsg := map[string]interface{}{
		"type":         "switch_state_sync",
		"timestamp":    time.Now().Format(time.RFC3339),
		"session":      session,
		"is_switching": isSwitching,
	}

	data, err := json.Marshal(stateSyncMsg)
	if err != nil {
		h.logger.Debug("failed to marshal state sync message", zap.Error(err))
		return
	}

	if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
		h.logger.Debug("failed to send state sync message", zap.Error(err))
		return
	}

	h.logger.Info("ws model-switch state sync sent",
		zap.Bool("is_switching", isSwitching),
		zap.String("session", fmt.Sprintf("%v", session)),
	)
}

func (h *WSHandler) Monitor(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		h.logger.Error("ws upgrade", zap.Error(err))
		return
	}
	h.manager.Connect(conn, "monitor")
	defer h.manager.Disconnect(conn, "monitor")

	h.sendMonitorStateSync(conn)

	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
}

func (h *WSHandler) sendMonitorStateSync(conn *websocket.Conn) {
	if h.gpuMonitor == nil || h.scheduler == nil {
		return
	}

	gpuStatus := h.gpuMonitor.GetStatus()
	models := h.scheduler.GetAvailableModels()
	modelStatus := make(map[string]interface{})
	for _, m := range models {
		modelStatus[m] = map[string]interface{}{
			"running":         h.scheduler.IsModelRunning(m),
			"port":            h.scheduler.GetModelPort(m),
			"service":         h.scheduler.GetModelService(m),
			"active_requests": h.scheduler.GetActiveRequests(m),
			"preloaded":       h.scheduler.IsModelPreloaded(m),
		}
	}

	stateSyncMsg := map[string]interface{}{
		"type":          "monitor_state_sync",
		"timestamp":     time.Now().Format(time.RFC3339),
		"current_model": h.scheduler.GetCurrentModelName(),
		"default_model": h.scheduler.GetDefaultModel(),
		"switching":     h.scheduler.IsSwitchingInProgress(),
	}

	if gpuStatus != nil {
		stateSyncMsg["gpu"] = map[string]interface{}{
			"status":            gpuStatus.Status,
			"name":              gpuStatus.Name,
			"utilization":       gpuStatus.Utilization,
			"temperature":       gpuStatus.Temperature,
			"power_draw":        gpuStatus.PowerDraw,
			"power_limit":       gpuStatus.PowerLimit,
			"memory_utilization": gpuStatus.MemoryUtilization,
			"used_memory":       gpuStatus.UsedMemory,
			"available_memory":  gpuStatus.AvailableMemory,
			"total_memory":      gpuStatus.TotalMemory,
		}
	}

	stateSyncMsg["models"] = modelStatus

	data, err := json.Marshal(stateSyncMsg)
	if err != nil {
		h.logger.Debug("failed to marshal monitor state sync", zap.Error(err))
		return
	}

	if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
		h.logger.Debug("failed to send monitor state sync", zap.Error(err))
		return
	}

	h.logger.Info("ws monitor state sync sent")
}
