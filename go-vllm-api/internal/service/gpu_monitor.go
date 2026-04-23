package service

import (
	"context"
	"fmt"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

type GPUInfo struct {
	Name              string `json:"name"`
	TotalMemory       int64  `json:"total_memory"`
	UsedMemory        int64  `json:"used_memory"`
	AvailableMemory   int64  `json:"available_memory"`
	Temperature       int    `json:"temperature"`
	Utilization       int    `json:"utilization"`
	PowerDraw         int    `json:"power_draw"`
	PowerLimit        int    `json:"power_limit"`
	PowerPercent      int    `json:"power_percent"`
	FanSpeed          int    `json:"fan_speed"`
	ClockSM           int    `json:"clock_sm"`
	ClockMem          int    `json:"clock_mem"`
	MemoryUtilization int    `json:"memory_utilization"`
}

type GPUStatus struct {
	Status           string    `json:"status"`
	GPUCount         int       `json:"gpu_count"`
	Name             string    `json:"name"`
	TotalMemory      int64     `json:"total_memory"`
	UsedMemory       int64     `json:"used_memory"`
	AvailableMemory  int64     `json:"available_memory"`
	Temperature      int       `json:"temperature"`
	Utilization      int       `json:"utilization"`
	PowerDraw        int       `json:"power_draw"`
	PowerLimit       int       `json:"power_limit"`
	PowerPercent     int       `json:"power_percent"`
	FanSpeed         int       `json:"fan_speed"`
	ClockSM          int       `json:"clock_sm"`
	ClockMem         int       `json:"clock_mem"`
	MemoryUtilization int      `json:"memory_utilization"`
	Primary          *GPUInfo  `json:"primary"`
	AllGPUs          []GPUInfo `json:"all_gpus"`
	ServerTime       string    `json:"serverTime,omitempty"`
}

type GPUMonitor struct {
	logger            *zap.Logger
	nvidiaSmiAvail    bool
	statusCache       *GPUStatus
	cacheTime         time.Time
	mu                sync.RWMutex
	cacheInterval     time.Duration
	cancel            context.CancelFunc
	fragmentationHist []float64
	memoryStrategy    string
}

func NewGPUMonitor(logger *zap.Logger) *GPUMonitor {
	m := &GPUMonitor{
		logger:          logger,
		cacheInterval:   2 * time.Second,
		memoryStrategy:  "balanced",
	}
	m.nvidiaSmiAvail = m.checkNvidiaSmi()
	if m.nvidiaSmiAvail {
		m.logger.Info("nvidia-smi available")
	} else {
		m.logger.Warn("nvidia-smi not available, GPU monitoring disabled")
	}
	return m
}

func (m *GPUMonitor) checkNvidiaSmi() bool {
	cmd := exec.Command("nvidia-smi", "--version")
	if err := cmd.Run(); err != nil {
		return false
	}
	return true
}

func (m *GPUMonitor) Start(ctx context.Context) {
	ctx, m.cancel = context.WithCancel(ctx)
	go m.updateLoop(ctx)
	m.logger.Info("GPU monitor started")
}

func (m *GPUMonitor) Stop() {
	if m.cancel != nil {
		m.cancel()
	}
	m.logger.Info("GPU monitor stopped")
}

func (m *GPUMonitor) updateLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(m.cacheInterval):
			if err := m.refreshCache(); err != nil {
				m.logger.Error("refresh GPU cache", zap.Error(err))
			}
		}
	}
}

func (m *GPUMonitor) refreshCache() error {
	if !m.nvidiaSmiAvail {
		m.mu.Lock()
		m.statusCache = nil
		m.mu.Unlock()
		return nil
	}

	cmd := exec.Command("nvidia-smi",
		"--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem",
		"--format=csv,noheader,nounits")
	output, err := cmd.Output()
	if err != nil {
		m.mu.Lock()
		m.statusCache = nil
		m.mu.Unlock()
		return err
	}

	gpus, err := m.parseOutput(string(output))
	if err != nil || len(gpus) == 0 {
		m.mu.Lock()
		m.statusCache = nil
		m.mu.Unlock()
		return err
	}

	primary := gpus[0]
	status := &GPUStatus{
		Status:            "available",
		GPUCount:          len(gpus),
		Name:              primary.Name,
		TotalMemory:       primary.TotalMemory,
		UsedMemory:        primary.UsedMemory,
		AvailableMemory:   primary.AvailableMemory,
		Temperature:       primary.Temperature,
		Utilization:       primary.Utilization,
		PowerDraw:         primary.PowerDraw,
		PowerLimit:        primary.PowerLimit,
		PowerPercent:      primary.PowerPercent,
		FanSpeed:          primary.FanSpeed,
		ClockSM:           primary.ClockSM,
		ClockMem:          primary.ClockMem,
		MemoryUtilization: primary.MemoryUtilization,
		Primary:           &primary,
		AllGPUs:           gpus,
	}

	m.mu.Lock()
	m.statusCache = status
	m.cacheTime = time.Now()
	m.mu.Unlock()
	return nil
}

func (m *GPUMonitor) parseOutput(output string) ([]GPUInfo, error) {
	var gpus []GPUInfo
	lines := strings.Split(strings.TrimSpace(output), "\n")
	for _, line := range lines {
		info, err := m.parseLine(line)
		if err != nil {
			continue
		}
		gpus = append(gpus, info)
	}
	return gpus, nil
}

var whitespaceRe = regexp.MustCompile(`\s+`)

func (m *GPUMonitor) parseLine(line string) (GPUInfo, error) {
	parts := strings.Split(line, ",")
	if len(parts) < 6 {
		return GPUInfo{}, fmt.Errorf("insufficient fields: %d", len(parts))
	}

	totalMB, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
	usedMB, _ := strconv.Atoi(strings.TrimSpace(parts[2]))
	freeMB, _ := strconv.Atoi(strings.TrimSpace(parts[3]))
	temp, _ := strconv.Atoi(strings.TrimSpace(parts[4]))
	util, _ := strconv.Atoi(strings.TrimSpace(parts[5]))

	powerDraw := 0.0
	powerLimit := 0.0
	if len(parts) > 6 {
		powerDraw, _ = strconv.ParseFloat(strings.TrimSpace(parts[6]), 64)
	}
	if len(parts) > 7 {
		powerLimit, _ = strconv.ParseFloat(strings.TrimSpace(parts[7]), 64)
	}
	fanSpeed := 0
	if len(parts) > 8 {
		fanSpeed, _ = strconv.Atoi(strings.TrimSpace(parts[8]))
	}
	clockSM := 0
	if len(parts) > 9 {
		clockSM, _ = strconv.Atoi(strings.TrimSpace(parts[9]))
	}
	clockMem := 0
	if len(parts) > 10 {
		clockMem, _ = strconv.Atoi(strings.TrimSpace(parts[10]))
	}

	powerPercent := 0
	if powerLimit > 0 {
		powerPercent = int(powerDraw / powerLimit * 100)
	}
	memUtilPercent := 0
	if totalMB > 0 {
		memUtilPercent = int(float64(usedMB) / float64(totalMB) * 100)
	}

	return GPUInfo{
		Name:              strings.TrimSpace(parts[0]),
		TotalMemory:       int64(totalMB) * 1024 * 1024,
		UsedMemory:        int64(usedMB) * 1024 * 1024,
		AvailableMemory:   int64(freeMB) * 1024 * 1024,
		Temperature:       temp,
		Utilization:       util,
		PowerDraw:         int(powerDraw),
		PowerLimit:        int(powerLimit),
		PowerPercent:      powerPercent,
		FanSpeed:          fanSpeed,
		ClockSM:           clockSM,
		ClockMem:          clockMem,
		MemoryUtilization: memUtilPercent,
	}, nil
}

func (m *GPUMonitor) GetStatus() *GPUStatus {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.statusCache != nil {
		status := *m.statusCache
		status.ServerTime = time.Now().Format(time.RFC3339)
		return &status
	}
	return nil
}

func (m *GPUMonitor) GetMemoryUsage() *MemoryInfo {
	status := m.GetStatus()
	if status == nil {
		return nil
	}
	return &MemoryInfo{
		Total:     status.TotalMemory,
		Used:      status.UsedMemory,
		Available: status.AvailableMemory,
	}
}

type MemoryInfo struct {
	Total     int64 `json:"total"`
	Used      int64 `json:"used"`
	Available int64 `json:"available"`
}

func (m *GPUMonitor) IsMemoryAvailable(required int64) bool {
	mem := m.GetMemoryUsage()
	if mem == nil {
		return false
	}
	return mem.Available >= required
}

func (m *GPUMonitor) SetMemoryStrategy(strategy string) {
	valid := map[string]bool{"conservative": true, "balanced": true, "aggressive": true}
	if valid[strategy] {
		m.memoryStrategy = strategy
	}
}

func (m *GPUMonitor) GetRecommendedUtilization() float64 {
	strategies := map[string]float64{
		"conservative": 0.80,
		"balanced":     0.90,
		"aggressive":   0.95,
	}
	v, ok := strategies[m.memoryStrategy]
	if !ok {
		return 0.90
	}
	return v
}
