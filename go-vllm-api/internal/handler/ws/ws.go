package ws

import (
	"net/http"

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

	for {
		_, _, err := conn.ReadMessage()
		if err != nil {
			break
		}
	}
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
