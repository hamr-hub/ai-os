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

type WSHandler struct {
	manager *service.WSManager
	logger  *zap.Logger
}

func NewWSHandler(manager *service.WSManager, logger *zap.Logger) *WSHandler {
	return &WSHandler{manager: manager, logger: logger}
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

	h.sendInitialStateSync(conn)

	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
}

func (h *WSHandler) sendInitialStateSync(conn *websocket.Conn) {
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

	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
}
