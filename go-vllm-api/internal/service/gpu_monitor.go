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

type GPUProcess struct {
	Pid           int    `json:"pid"`
	Name          string `json:"name"`
	UsedGPUMemory int64  `json:"used_gpu_memory"`
}

type GPUInfo struct {
	Name              string        `json:"name"`
	Index             int           `json:"index"`
	TotalMemory       int64         `json:"total_memory"`
	UsedMemory        int64         `json:"used_memory"`
	AvailableMemory   int64         `json:"available_memory"`
	Temperature       int           `json:"temperature"`
	Utilization       int           `json:"utilization"`
	PowerDraw         int           `json:"power_draw"`
	PowerLimit        int           `json:"power_limit"`
	PowerPercent      int           `json:"power_percent"`
	FanSpeed          int           `json:"fan_speed"`
	ClockSM           int           `json:"clock_sm"`
	ClockMem          int           `json:"clock_mem"`
	MemoryUtilization int           `json:"memory_utilization"`
	EccErrors         int           `json:"ecc_errors"`
	ThrottleReasons   []string      `json:"throttle_reasons"`
	PersistenceMode   bool          `json:"persistence_mode"`
	PCIeRxThroughput  int           `json:"pcie_rx_throughput"`
	PCIeTxThroughput  int           `json:"pcie_tx_throughput"`
	Bar1TotalMemory   int64         `json:"bar1_total_memory"`
	Bar1UsedMemory    int64         `json:"bar1_used_memory"`
	Processes         []GPUProcess  `json:"processes"`
	VbiosVersion      string        `json:"vbios_version"`
	DriverVersion     string        `json:"driver_version"`
}

type VLLMMetricsData struct {
	VLLMAvailable        bool    `json:"vllm_available"`
	RunningRequests      int     `json:"running_requests"`
	WaitingRequests      int     `json:"waiting_requests"`
	GPUCacheUsage        float64 `json:"gpu_cache_usage"`
	CPUCacheUsage        float64 `json:"cpu_cache_usage"`
	GenerationThroughput float64 `json:"generation_throughput"`
	PromptThroughput     float64 `json:"prompt_throughput"`
	TimeToFirstToken     float64 `json:"time_to_first_token"`
	TimePerOutputToken   float64 `json:"time_per_output_token"`
	PrefixCacheHitRate   float64 `json:"prefix_cache_hit_rate"`
	ScrapedAt            string  `json:"scraped_at"`
}

type GPUStatus struct {
	Status           string           `json:"status"`
	GPUCount         int              `json:"gpu_count"`
	Name             string           `json:"name"`
	TotalMemory      int64            `json:"total_memory"`
	UsedMemory       int64            `json:"used_memory"`
	AvailableMemory  int64            `json:"available_memory"`
	Temperature      int              `json:"temperature"`
	Utilization      int              `json:"utilization"`
	PowerDraw        int              `json:"power_draw"`
	PowerLimit       int              `json:"power_limit"`
	PowerPercent     int              `json:"power_percent"`
	FanSpeed         int              `json:"fan_speed"`
	ClockSM          int              `json:"clock_sm"`
	ClockMem         int              `json:"clock_mem"`
	MemoryUtilization int             `json:"memory_utilization"`
	Primary          *GPUInfo         `json:"primary"`
	AllGPUs          []GPUInfo        `json:"all_gpus"`
	VLLMMetrics      *VLLMMetricsData `json:"vllm_metrics,omitempty"`
	DriverVersion    string           `json:"driver_version,omitempty"`
	ServerTime       string           `json:"serverTime,omitempty"`
}

var throttleReasonMap = map[uint64]string{
	0x00000001: "gpu_idle",
	0x00000002: "applications_clocks_setting",
	0x00000004: "sw_power_cap",
	0x00000008: "hw_thermal_slowdown",
	0x00000010: "sw_thermal_slowdown",
	0x00000020: "hw_power_brake_slowdown",
	0x00000040: "sw_power_brake_slowdown",
	0x00000080: "display_clocks_setting",
	0x00000100: "sw_power_sliding_window_slowdown",
	0x00000200: "hw_thermal_slowdown_vmin",
	0x00000400: "hw_thermal_slowdown_vrel",
}

func decodeThrottleReasons(bits uint64) []string {
	if bits == 0 {
		return nil
	}
	var reasons []string
	for bit, name := range throttleReasonMap {
		if bits&bit != 0 {
			reasons = append(reasons, name)
		}
	}
	return reasons
}

type GPUMonitor struct {
	logger            *zap.Logger
	nvidiaSmiAvail    bool
	nvmlAvail         bool
	statusCache       *GPUStatus
	cacheTime         time.Time
	mu                sync.RWMutex
	cacheInterval     time.Duration
	cancel            context.CancelFunc
	fragmentationHist []float64
	memoryStrategy    string
	vllmMetrics       *VLLMMetricsData
	vllmMetricsTime   time.Time
	vllmPort          int
}

func NewGPUMonitor(logger *zap.Logger) *GPUMonitor {
	m := &GPUMonitor{
		logger:          logger,
		cacheInterval:   2 * time.Second,
		memoryStrategy:  "balanced",
		vllmPort:        8000,
	}
	m.nvmlAvail = m.initNVML()
	if m.nvmlAvail {
		logger.Info("NVML available, using NVML as primary GPU data source")
	} else {
		m.nvidiaSmiAvail = m.checkNvidiaSmi()
		if m.nvidiaSmiAvail {
			logger.Info("NVML not available, using nvidia-smi as fallback")
		} else {
			logger.Warn("no GPU monitoring available (neither NVML nor nvidia-smi)")
		}
	}
	return m
}

func (m *GPUMonitor) initNVML() bool {
	cmd := exec.Command("nvidia-smi", "--version")
	if err := cmd.Run(); err != nil {
		return false
	}
	return true
}

func (m *GPUMonitor) SetVLLMPort(port int) {
	m.vllmPort = port
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
			if m.vllmPort > 0 {
				if err := m.refreshVLLMMetrics(); err != nil {
					m.logger.Debug("refresh vLLM metrics", zap.Error(err))
				}
			}
		}
	}
}

func (m *GPUMonitor) refreshVLLMMetrics() error {
	url := fmt.Sprintf("http://localhost:%d/metrics", m.vllmPort)
	cmd := exec.Command("curl", "-s", "--max-time", "5", url)
	output, err := cmd.Output()
	if err != nil {
		return err
	}
	metrics := parsePrometheusText(string(output))
	if metrics != nil {
		m.mu.Lock()
		m.vllmMetrics = metrics
		m.vllmMetricsTime = time.Now()
		if m.statusCache != nil {
			m.statusCache.VLLMMetrics = metrics
		}
		m.mu.Unlock()
	}
	return nil
}

func parsePrometheusText(text string) *VLLMMetricsData {
	gaugeValues := map[string]float64{}
	histogramSums := map[string]float64{}

	metricKeys := map[string]string{
		"vllm:num_requests_running":             "running_requests",
		"vllm:num_requests_waiting":             "waiting_requests",
		"vllm:gpu_cache_usage_perc":             "gpu_cache_usage",
		"vllm:cpu_cache_usage_perc":             "cpu_cache_usage",
		"vllm:avg_generation_throughput":        "generation_throughput",
		"vllm:avg_prompt_throughput":            "prompt_throughput",
		"vllm:gpu_prefix_cache_hit_rate_perc":   "prefix_cache_hit_rate",
	}

	histogramKeys := map[string]string{
		"vllm:time_to_first_token_seconds":     "time_to_first_token",
		"vllm:time_per_output_token_seconds":   "time_per_output_token",
	}

	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		for metricKey, alias := range metricKeys {
			if strings.HasPrefix(line, metricKey+" ") || strings.HasPrefix(line, metricKey+"{") {
				re := regexp.MustCompile(`=([0-9.eE+-]+)`)
				match := re.FindStringSubmatch(line)
				if len(match) > 1 {
					if v, err := strconv.ParseFloat(match[1], 64); err == nil {
						gaugeValues[alias] = v
					}
				} else if !strings.Contains(line, "{") {
					parts := strings.Fields(line)
					if len(parts) >= 2 {
						if v, err := strconv.ParseFloat(parts[1], 64); err == nil {
							gaugeValues[alias] = v
						}
					}
				}
			}
		}
		for metricKey, alias := range histogramKeys {
			sumLine := metricKey + "_sum"
			if strings.HasPrefix(line, sumLine+" ") || strings.HasPrefix(line, sumLine+"{") {
				re := regexp.MustCompile(`=([0-9.eE+-]+)`)
				match := re.FindStringSubmatch(line)
				if len(match) > 1 {
					if v, err := strconv.ParseFloat(match[1], 64); err == nil {
						histogramSums[alias] = v
					}
				} else if !strings.Contains(line, "{") {
					parts := strings.Fields(line)
					if len(parts) >= 2 {
						if v, err := strconv.ParseFloat(parts[1], 64); err == nil {
							histogramSums[alias] = v
						}
					}
				}
			}
		}
	}

	if len(gaugeValues) == 0 && len(histogramSums) == 0 {
		return nil
	}

	data := &VLLMMetricsData{
		VLLMAvailable:        true,
		RunningRequests:      int(gaugeValues["running_requests"]),
		WaitingRequests:      int(gaugeValues["waiting_requests"]),
		GPUCacheUsage:        gaugeValues["gpu_cache_usage"],
		CPUCacheUsage:        gaugeValues["cpu_cache_usage"],
		GenerationThroughput: gaugeValues["generation_throughput"],
		PromptThroughput:     gaugeValues["prompt_throughput"],
		TimeToFirstToken:     histogramSums["time_to_first_token"],
		TimePerOutputToken:   histogramSums["time_per_output_token"],
		PrefixCacheHitRate:   gaugeValues["prefix_cache_hit_rate"],
		ScrapedAt:            time.Now().Format(time.RFC3339),
	}
	return data
}

func (m *GPUMonitor) refreshCache() error {
	if !m.nvidiaSmiAvail && !m.nvmlAvail {
		m.mu.Lock()
		m.statusCache = nil
		m.mu.Unlock()
		return nil
	}

	gpus := m.collectGPUData()
	if len(gpus) == 0 {
		m.mu.Lock()
		m.statusCache = nil
		m.mu.Unlock()
		return fmt.Errorf("no GPU data collected")
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
		DriverVersion:     primary.DriverVersion,
	}

	m.mu.Lock()
	if m.vllmMetrics != nil {
		status.VLLMMetrics = m.vllmMetrics
	}
	m.statusCache = status
	m.cacheTime = time.Now()
	m.mu.Unlock()
	return nil
}

func (m *GPUMonitor) collectGPUData() []GPUInfo {
	basicGPUs := m.collectViaNvidiaSmi()
	if len(basicGPUs) == 0 {
		return nil
	}

	enhancedData := m.collectEnhancedViaNvidiaSmi()

	for i := range basicGPUs {
		basicGPUs[i].Index = i
		if enhanced, ok := enhancedData[i]; ok {
			basicGPUs[i].EccErrors = enhanced.EccErrors
			basicGPUs[i].ThrottleReasons = enhanced.ThrottleReasons
			basicGPUs[i].PersistenceMode = enhanced.PersistenceMode
			basicGPUs[i].PCIeRxThroughput = enhanced.PCIeRxThroughput
			basicGPUs[i].PCIeTxThroughput = enhanced.PCIeTxThroughput
			basicGPUs[i].Bar1TotalMemory = enhanced.Bar1TotalMemory
			basicGPUs[i].Bar1UsedMemory = enhanced.Bar1UsedMemory
			basicGPUs[i].Processes = enhanced.Processes
			basicGPUs[i].VbiosVersion = enhanced.VbiosVersion
			basicGPUs[i].DriverVersion = enhanced.DriverVersion
		}
	}
	return basicGPUs
}

func (m *GPUMonitor) collectViaNvidiaSmi() []GPUInfo {
	cmd := exec.Command("nvidia-smi",
		"--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem",
		"--format=csv,noheader,nounits")
	output, err := cmd.Output()
	if err != nil {
		m.logger.Error("nvidia-smi query failed", zap.Error(err))
		return nil
	}
	gpus, err := m.parseOutput(string(output))
	if err != nil || len(gpus) == 0 {
		return nil
	}
	return gpus
}

func (m *GPUMonitor) collectEnhancedViaNvidiaSmi() map[int]GPUInfo {
	result := map[int]GPUInfo{}

	driverCmd := exec.Command("nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits")
	driverOutput, err := driverCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(driverOutput)), "\n")
		for i, line := range lines {
			if existing, ok := result[i]; ok {
				existing.DriverVersion = strings.TrimSpace(line)
				result[i] = existing
			} else {
				result[i] = GPUInfo{DriverVersion: strings.TrimSpace(line)}
			}
		}
	}

	eccCmd := exec.Command("nvidia-smi", "--query-gpu=ecc.errors.corrected.volatile.total", "--format=csv,noheader,nounits")
	eccOutput, err := eccCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(eccOutput)), "\n")
		for i, line := range lines {
			eccErrors, _ := strconv.Atoi(strings.TrimSpace(line))
			if existing, ok := result[i]; ok {
				existing.EccErrors = eccErrors
				result[i] = existing
			} else {
				result[i] = GPUInfo{EccErrors: eccErrors}
			}
		}
	}

	throttleCmd := exec.Command("nvidia-smi", "--query-gpu=clocks_throttle_reasons", "--format=csv,noheader")
	throttleOutput, err := throttleCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(throttleOutput)), "\n")
		for i, line := range lines {
			reasons := parseThrottleReasonsFromCSV(strings.TrimSpace(line))
			if existing, ok := result[i]; ok {
				existing.ThrottleReasons = reasons
				result[i] = existing
			} else {
				result[i] = GPUInfo{ThrottleReasons: reasons}
			}
		}
	}

	pciCmd := exec.Command("nvidia-smi", "--query-gpu=pcie_rx_throughput.counter,pcie_tx_throughput.counter", "--format=csv,noheader,nounits")
	pciOutput, err := pciCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(pciOutput)), "\n")
		for i, line := range lines {
			parts := strings.Split(line, ",")
			rx := 0
			tx := 0
			if len(parts) >= 1 {
				rx, _ = strconv.Atoi(strings.TrimSpace(parts[0]))
			}
			if len(parts) >= 2 {
				tx, _ = strconv.Atoi(strings.TrimSpace(parts[1]))
			}
			if existing, ok := result[i]; ok {
				existing.PCIeRxThroughput = rx
				existing.PCIeTxThroughput = tx
				result[i] = existing
			} else {
				result[i] = GPUInfo{PCIeRxThroughput: rx, PCIeTxThroughput: tx}
			}
		}
	}

	persistenceCmd := exec.Command("nvidia-smi", "--query-gpu=persistence_mode", "--format=csv,noheader")
	persistenceOutput, err := persistenceCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(persistenceOutput)), "\n")
		for i, line := range lines {
			enabled := strings.TrimSpace(line) == "Enabled"
			if existing, ok := result[i]; ok {
				existing.PersistenceMode = enabled
				result[i] = existing
			} else {
				result[i] = GPUInfo{PersistenceMode: enabled}
			}
		}
	}

	vbiosCmd := exec.Command("nvidia-smi", "--query-gpu=vbios_version", "--format=csv,noheader")
	vbiosOutput, err := vbiosCmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(vbiosOutput)), "\n")
		for i, line := range lines {
			if existing, ok := result[i]; ok {
				existing.VbiosVersion = strings.TrimSpace(line)
				result[i] = existing
			} else {
				result[i] = GPUInfo{VbiosVersion: strings.TrimSpace(line)}
			}
		}
	}

	bar1Cmd := exec.Command("nvidia-smi", "--query-gpu=bar1_memory.used,bar1_memory.total", "--format=csv,noheader,nounits")
	bar1Output, err := bar1Cmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(bar1Output)), "\n")
		for i, line := range lines {
			parts := strings.Split(line, ",")
			bar1Used := int64(0)
			bar1Total := int64(0)
			if len(parts) >= 1 {
				v, _ := strconv.Atoi(strings.TrimSpace(parts[0]))
				bar1Used = int64(v) * 1024 * 1024
			}
			if len(parts) >= 2 {
				v, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
				bar1Total = int64(v) * 1024 * 1024
			}
			if existing, ok := result[i]; ok {
				existing.Bar1UsedMemory = bar1Used
				existing.Bar1TotalMemory = bar1Total
				result[i] = existing
			} else {
				result[i] = GPUInfo{Bar1UsedMemory: bar1Used, Bar1TotalMemory: bar1Total}
			}
		}
	}

	processes := m.collectGPUProcesses()
	for i, procs := range processes {
		if existing, ok := result[i]; ok {
			existing.Processes = procs
			result[i] = existing
		} else {
			result[i] = GPUInfo{Processes: procs}
		}
	}

	return result
}

func parseThrottleReasonsFromCSV(csv string) []string {
	if csv == "No" || csv == "Active" || csv == "" {
		if csv == "Active" {
			return []string{"throttling_active"}
		}
		return nil
	}
	parts := strings.Split(csv, "+")
	var reasons []string
	for _, p := range parts {
		name := strings.TrimSpace(p)
		if name != "" && name != "No" {
			reasons = append(reasons, name)
		}
	}
	return reasons
}

func (m *GPUMonitor) collectGPUProcesses() map[int][]GPUProcess {
	cmd := exec.Command("nvidia-smi", "--query-compute-apps=pid,gpu_name,used_gpu_memory", "--format=csv,noheader,nounits")
	output, err := cmd.Output()
	if err != nil {
		return nil
	}

	gpuProcesses := map[int][]GPUProcess{}
	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	for _, line := range lines {
		parts := strings.Split(line, ",")
		if len(parts) < 3 {
			continue
		}
		pid, _ := strconv.Atoi(strings.TrimSpace(parts[0]))
		name := strings.TrimSpace(parts[1])
		memKB, _ := strconv.Atoi(strings.TrimSpace(parts[2]))
		if pid == 0 {
			continue
		}

		cmdline := getProcessCmdline(pid)
		if cmdline != "" {
			name = cmdline
		}

		proc := GPUProcess{
			Pid:           pid,
			Name:          name,
			UsedGPUMemory: int64(memKB) * 1024,
		}

		gpuIdx := 0
		gpuProcesses[gpuIdx] = append(gpuProcesses[gpuIdx], proc)
	}
	return gpuProcesses
}

func getProcessCmdline(pid int) string {
	cmd := exec.Command("cat", fmt.Sprintf("/proc/%d/cmdline", pid))
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	cmdline := strings.ReplaceAll(string(output), "\x00", " ")
	cmdline = strings.TrimSpace(cmdline)
	if len(cmdline) > 100 {
		cmdline = cmdline[:100]
	}
	return cmdline
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

func (m *GPUMonitor) GetVLLMMetrics() *VLLMMetricsData {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.vllmMetrics != nil {
		result := *m.vllmMetrics
		return &result
	}
	return &VLLMMetricsData{VLLMAvailable: false}
}

func (m *GPUMonitor) GetGPUProcesses() []GPUProcess {
	status := m.GetStatus()
	if status == nil || status.Primary == nil {
		return nil
	}
	return status.Primary.Processes
}

func (m *GPUMonitor) GetEnhancedInfo() map[string]interface{} {
	status := m.GetStatus()
	if status == nil {
		return nil
	}
	enhanced := map[string]interface{}{
		"driver_version": status.DriverVersion,
		"gpu_count":      status.GPUCount,
		"gpus":           []map[string]interface{}{},
	}
	gpusList := make([]map[string]interface{}, 0)
	for _, gpu := range status.AllGPUs {
		gpuEnhanced := map[string]interface{}{
			"index":              gpu.Index,
			"name":               gpu.Name,
			"ecc_errors":         gpu.EccErrors,
			"throttle_reasons":   gpu.ThrottleReasons,
			"persistence_mode":   gpu.PersistenceMode,
			"pcie_rx_throughput": gpu.PCIeRxThroughput,
			"pcie_tx_throughput": gpu.PCIeTxThroughput,
			"bar1_total_memory":  gpu.Bar1TotalMemory,
			"bar1_used_memory":   gpu.Bar1UsedMemory,
			"vbios_version":      gpu.VbiosVersion,
			"processes":          gpu.Processes,
		}
		gpusList = append(gpusList, gpuEnhanced)
	}
	enhanced["gpus"] = gpusList
	return enhanced
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

func (m *GPUMonitor) GetHealthScore() float64 {
	status := m.GetStatus()
	if status == nil || status.Status != "available" {
		return 0.0
	}

	temp := status.Temperature
	memUtil := status.MemoryUtilization

	tempScore := 100.0
	if temp > 85 {
		tempScore = max(0, 100-(temp-85)*5)
	}

	memScore := 100.0
	if memUtil > 90 {
		memScore = max(0, 100-(memUtil-90)*10)
	}

	throttlePenalty := 0.0
	if status.Primary != nil {
		for _, r := range status.Primary.ThrottleReasons {
			if r == "hw_thermal_slowdown" || r == "sw_thermal_slowdown" {
				throttlePenalty = 50
				break
			}
		}
		if throttlePenalty == 0 && len(status.Primary.ThrottleReasons) > 0 {
			throttlePenalty = 10
		}
	}

	score := (tempScore*0.5 + memScore*0.5) - throttlePenalty
	return max(0, min(100, score))
}

func (m *GPUMonitor) DetectFragmentation() float64 {
	status := m.GetStatus()
	if status == nil {
		return 0.0
	}
	total := float64(status.TotalMemory)
	used := float64(status.UsedMemory)
	available := float64(status.AvailableMemory)
	if total <= 0 {
		return 0.0
	}
	fragmentation := (total - used - available) / total
	m.mu.Lock()
	m.fragmentationHist = append(m.fragmentationHist, fragmentation)
	if len(m.fragmentationHist) > 60 {
		m.fragmentationHist = m.fragmentationHist[len(m.fragmentationHist)-60:]
	}
	m.mu.Unlock()
	return fragmentation
}

func (m *GPUMonitor) GetAverageFragmentation() float64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	if len(m.fragmentationHist) == 0 {
		return 0.0
	}
	sum := 0.0
	for _, v := range m.fragmentationHist {
		sum += v
	}
	return sum / float64(len(m.fragmentationHist))
}

type GPUSummary struct {
	Status      string                 `json:"status"`
	Current     map[string]interface{} `json:"current"`
	HealthScore float64                `json:"health_score"`
	History     []interface{}          `json:"history"`
}

func (m *GPUMonitor) GetGPUSummary() *GPUSummary {
	status := m.GetStatus()
	if status == nil {
		return &GPUSummary{
			Status:      "unavailable",
			Current:     nil,
			HealthScore: 0.0,
			History:     []interface{}{},
		}
	}

	current := map[string]interface{}{
		"name":               status.Name,
		"gpu_count":          status.GPUCount,
		"utilization":        status.Utilization,
		"temperature":        status.Temperature,
		"power_draw":         status.PowerDraw,
		"power_limit":        status.PowerLimit,
		"power_percent":      status.PowerPercent,
		"memory_utilization": status.MemoryUtilization,
		"used_memory":        status.UsedMemory,
		"available_memory":   status.AvailableMemory,
		"total_memory":       status.TotalMemory,
		"fan_speed":          status.FanSpeed,
		"clock_sm":           status.ClockSM,
		"clock_mem":          status.ClockMem,
	}

	if status.Primary != nil {
		current["ecc_errors"] = status.Primary.EccErrors
		current["throttle_reasons"] = status.Primary.ThrottleReasons
		current["persistence_mode"] = status.Primary.PersistenceMode
		current["vbios_version"] = status.Primary.VbiosVersion
	}

	return &GPUSummary{
		Status:      "available",
		Current:     current,
		HealthScore: m.GetHealthScore(),
		History:     []interface{}{},
	}
}

type MemoryOptimizationStatus struct {
	Strategy              string  `json:"strategy"`
	Fragmentation         float64 `json:"fragmentation"`
	AvgFragmentation      float64 `json:"avg_fragmentation"`
	RecommendedUtilization float64 `json:"recommended_utilization"`
	LastFlush             string  `json:"last_flush"`
	FlushInterval         int     `json:"flush_interval"`
}

func (m *GPUMonitor) GetMemoryOptimizationStatus() *MemoryOptimizationStatus {
	return &MemoryOptimizationStatus{
		Strategy:              m.memoryStrategy,
		Fragmentation:         m.DetectFragmentation(),
		AvgFragmentation:      m.GetAverageFragmentation(),
		RecommendedUtilization: m.GetRecommendedUtilization(),
		FlushInterval:         300,
	}
}
