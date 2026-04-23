package service

import (
	"encoding/json"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"go.uber.org/zap"
)

type WSManager struct {
	connections map[*websocket.Conn]bool
	channels    map[string]map[*websocket.Conn]bool
	logger      *zap.Logger
	mu          sync.Mutex
	history     []WSEvent
	maxHistory  int
}

type WSEvent struct {
	Channel   string `json:"channel"`
	Data      interface{} `json:"data"`
	Timestamp string `json:"timestamp"`
}

func NewWSManager(logger *zap.Logger) *WSManager {
	return &WSManager{
		connections: make(map[*websocket.Conn]bool),
		channels:    make(map[string]map[*websocket.Conn]bool),
		logger:      logger,
		maxHistory:  100,
	}
}

func (m *WSManager) Connect(conn *websocket.Conn, channel string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.connections[conn] = true
	if m.channels[channel] == nil {
		m.channels[channel] = make(map[*websocket.Conn]bool)
	}
	m.channels[channel][conn] = true
	m.logger.Info("ws connected", zap.String("channel", channel))
}

func (m *WSManager) Disconnect(conn *websocket.Conn, channel string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.connections, conn)
	if m.channels[channel] != nil {
		delete(m.channels[channel], conn)
	}
	conn.Close()
	m.logger.Info("ws disconnected", zap.String("channel", channel))
}

func (m *WSManager) Broadcast(channel string, data interface{}) {
	m.mu.Lock()
	conns := m.channels[channel]
	var toRemove []*websocket.Conn
	for conn := range conns {
		msg, err := json.Marshal(data)
		if err != nil {
			toRemove = append(toRemove, conn)
			continue
		}
		if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			toRemove = append(toRemove, conn)
		}
	}
	for _, conn := range toRemove {
		delete(m.connections, conn)
		delete(m.channels[channel], conn)
		conn.Close()
	}
	m.mu.Unlock()

	m.history = append(m.history, WSEvent{
		Channel:   channel,
		Data:      data,
		Timestamp: time.Now().Format(time.RFC3339),
	})
	if len(m.history) > m.maxHistory {
		m.history = m.history[len(m.history)-m.maxHistory:]
	}
}

func (m *WSManager) BroadcastStatus(gpuSummary, modelStatus interface{}) {
	m.Broadcast("monitor", map[string]interface{}{
		"gpu":    gpuSummary,
		"models": modelStatus,
	})
}

func (m *WSManager) GetConnectionStats() map[string]interface{} {
	m.mu.Lock()
	defer m.mu.Unlock()
	total := len(m.connections)
	channels := make(map[string]int)
	for ch, conns := range m.channels {
		channels[ch] = len(conns)
	}
	return map[string]interface{}{
		"total_connections": total,
		"channels":          channels,
		"history_size":      len(m.history),
	}
}
