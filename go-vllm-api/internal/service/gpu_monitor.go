package service

import (
	"context"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/NVIDIA/go-nvml/pkg/nvml"
	"go.uber.org/zap"
)

type GPUProcess struct {
	Pid           int    `json:"pid"`
	Name          string `json:"name"`
	UsedGPUMemory int64  `json:"used_gpu_memory"`
}

type GPUInfo struct {
	Name              string       `json:"name"`
	Index             int          `json:"index"`
	TotalMemory       int64        `json:"total_memory"`
	UsedMemory        int64        `json:"used_memory"`
	AvailableMemory   int64        `json:"available_memory"`
	Temperature       int          `json:"temperature"`
	Utilization       int          `json:"utilization"`
	PowerDraw         int          `json:"power_draw"`
	PowerLimit        int          `json:"power_limit"`
	PowerPercent      int          `json:"power_percent"`
	FanSpeed          int          `json:"fan_speed"`
	ClockSM           int          `json:"clock_sm"`
	ClockMem          int          `json:"clock_mem"`
	MemoryUtilization int          `json:"memory_utilization"`
	EccErrors         int          `json:"ecc_errors"`
	ThrottleReasons   []string     `json:"throttle_reasons"`
	PersistenceMode   bool         `json:"persistence_mode"`
	PCIeRxThroughput  int          `json:"pcie_rx_throughput"`
	PCIeTxThroughput  int          `json:"pcie_tx_throughput"`
	Bar1TotalMemory   int64        `json:"bar1_total_memory"`
	Bar1UsedMemory    int64        `json:"bar1_used_memory"`
	Processes         []GPUProcess `json:"processes"`
	VbiosVersion      string       `json:"vbios_version"`
	DriverVersion     string       `json:"driver_version"`
	PerformanceState  string       `json:"performance_state"`
	GPUEncUtilization int          `json:"gpu_enc_utilization"`
	GPUDecUtilization int          `json:"gpu_dec_utilization"`
	JpgUtilization    int          `json:"jpg_utilization"`
	OfaUtilization    int          `json:"ofa_utilization"`
}

type VLLMMetricsData struct {
	VLLMAvailable         bool    `json:"vllm_available"`
	RunningRequests       int     `json:"running_requests"`
	WaitingRequests       int     `json:"waiting_requests"`
	SchedulingRequests    int     `json:"scheduling_requests,omitempty"`
	GPUCacheUsage         float64 `json:"gpu_cache_usage"`
	CPUCacheUsage         float64 `json:"cpu_cache_usage"`
	RequestThroughput     float64 `json:"request_throughput"`
	PromptThroughput      float64 `json:"prompt_throughput"`
	GenerationThroughput  float64 `json:"generation_throughput"`
	TimeToFirstTokenP50   float64 `json:"time_to_first_token_p50"`
	TimeToFirstTokenP95   float64 `json:"time_to_first_token_p95"`
	TimeToFirstToken      float64 `json:"time_to_first_token"`
	TimePerOutputTokenP50 float64 `json:"time_per_output_token_p50"`
	TimePerOutputTokenP95 float64 `json:"time_per_output_token_p95"`
	TimePerOutputToken    float64 `json:"time_per_output_token"`
	PrefixCacheHitRate    float64 `json:"prefix_cache_hit_rate"`
	ScrapedAt             string  `json:"scraped_at"`
}

type GPUStatus struct {
	Status            string           `json:"status"`
	GPUCount          int              `json:"gpu_count"`
	Name              string           `json:"name"`
	TotalMemory       int64            `json:"total_memory"`
	UsedMemory        int64            `json:"used_memory"`
	AvailableMemory   int64            `json:"available_memory"`
	Temperature       int              `json:"temperature"`
	Utilization       int              `json:"utilization"`
	PowerDraw         int              `json:"power_draw"`
	PowerLimit        int              `json:"power_limit"`
	PowerPercent      int              `json:"power_percent"`
	FanSpeed          int              `json:"fan_speed"`
	ClockSM           int              `json:"clock_sm"`
	ClockMem          int              `json:"clock_mem"`
	MemoryUtilization int              `json:"memory_utilization"`
	Primary           *GPUInfo         `json:"primary"`
	AllGPUs           []GPUInfo        `json:"all_gpus"`
	VLLMMetrics       *VLLMMetricsData `json:"vllm_metrics,omitempty"`
	DriverVersion     string           `json:"driver_version,omitempty"`
	ServerTime        string           `json:"serverTime,omitempty"`
}

var throttleReasonMap = map[uint32]string{
	0:  "gpu_idle",
	1:  "applications_clocks_setting",
	2:  "sw_power_cap",
	3:  "hw_thermal_slowdown",
	4:  "sw_thermal_slowdown",
	5:  "hw_power_brake_slowdown",
	6:  "sw_power_brake_slowdown",
	7:  "display_clocks_setting",
	8:  "sw_power_sliding_window_slowdown",
	9:  "hw_thermal_slowdown_vmin",
	10: "hw_thermal_slowdown_vrel",
}

func decodeThrottleReasons(reasons uint64) []string {
	var result []string
	for reason, name := range throttleReasonMap {
		if uint64(reasons)&uint64(reason) != 0 {
			result = append(result, name)
		}
	}
	return result
}

type GPUMonitor struct {
	logger            *zap.Logger
	nvmlAvailable     bool
	nvmlInitialized   bool
	deviceCount       int
	devices           []nvml.Device
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
	driverVersion     string
}

func NewGPUMonitor(logger *zap.Logger) *GPUMonitor {
	m := &GPUMonitor{
		logger:         logger,
		cacheInterval:  2 * time.Second,
		memoryStrategy: "balanced",
		vllmPort:       8000,
	}

	ret := nvml.Init()
	if ret == nvml.SUCCESS {
		m.nvmlAvailable = true
		m.nvmlInitialized = true
		m.deviceCount, ret = nvml.DeviceGetCount()
		if ret != nvml.SUCCESS {
			logger.Error("Failed to get device count", zap.String("error", nvml.ErrorString(ret)))
			m.nvmlAvailable = false
			nvml.Shutdown()
		} else {
			for i := 0; i < m.deviceCount; i++ {
				device, ret := nvml.DeviceGetHandleByIndex(i)
				if ret != nvml.SUCCESS {
					logger.Error("Failed to get device handle", zap.Int("index", i), zap.String("error", nvml.ErrorString(ret)))
					continue
				}
				m.devices = append(m.devices, device)
			}
			version, ret := nvml.SystemGetDriverVersion()
			if ret == nvml.SUCCESS {
				m.driverVersion = version
			}
			logger.Info("NVML initialized successfully", zap.Int("device_count", m.deviceCount))
		}
	} else {
		logger.Warn("NVML initialization failed, falling back to nvidia-smi", zap.String("error", nvml.ErrorString(ret)))
		m.nvmlAvailable = false
	}

	return m
}

func (m *GPUMonitor) SetVLLMPort(port int) {
	m.vllmPort = port
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
	if m.nvmlInitialized {
		nvml.Shutdown()
		m.nvmlInitialized = false
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

var metricsHTTPClient = &http.Client{
	Timeout: 5 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        1,
		MaxIdleConnsPerHost: 1,
		IdleConnTimeout:     10 * time.Second,
	},
}

func (m *GPUMonitor) refreshVLLMMetrics() error {
	url := fmt.Sprintf("http://localhost:%d/metrics", m.vllmPort)
	resp, err := metricsHTTPClient.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("metrics endpoint returned %d", resp.StatusCode)
	}

	metrics := parsePrometheusText(string(body))
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

type histogramBucket struct {
	le    float64
	count uint64
}

func parsePrometheusText(text string) *VLLMMetricsData {
	gaugeValues := map[string]float64{}
	histogramBuckets := map[string][]histogramBucket{}
	histogramCounts := map[string]uint64{}
	histogramSums := map[string]float64{}

	metricKeys := map[string]string{
		"vllm:num_requests_running":             "running_requests",
		"vllm:num_requests_waiting":             "waiting_requests",
		"vllm:num_requests_swapped":             "scheduling_requests",
		"vllm:gpu_cache_usage_perc":             "gpu_cache_usage",
		"vllm:cpu_cache_usage_perc":             "cpu_cache_usage",
		"vllm:gpu_prefix_cache_hit_rate_perc":   "prefix_cache_hit_rate",
		"vllm:request_throughput":               "request_throughput",
		"vllm:prompt_token_throughput":          "prompt_throughput",
		"vllm:generation_token_throughput":      "generation_throughput",
		"vllm:avg_prompt_throughput_toks_s":     "prompt_throughput_toks_s",
		"vllm:avg_generation_throughput_toks_s": "generation_throughput_toks_s",
	}

	histogramKeys := map[string]string{
		"vllm:time_to_first_token_seconds":   "time_to_first_token",
		"vllm:time_per_output_token_seconds": "time_per_output_token",
		"vllm:e2e_request_latency_seconds":   "e2e_request_latency",
	}

	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		for metricKey, alias := range metricKeys {
			if strings.HasPrefix(line, metricKey+" ") || strings.HasPrefix(line, metricKey+"{") {
				if v := extractMetricValue(line); v != nil {
					gaugeValues[alias] = *v
				}
			}
		}

		for metricKey, alias := range histogramKeys {
			if strings.HasPrefix(line, metricKey+"_bucket ") || strings.HasPrefix(line, metricKey+"_bucket{") {
				if leStr, countStr := extractHistogramBucket(line); leStr != "" && countStr != "" {
					le, err1 := strconv.ParseFloat(leStr, 64)
					count, err2 := strconv.ParseUint(countStr, 10, 64)
					if err1 == nil && err2 == nil {
						histogramBuckets[alias] = append(histogramBuckets[alias], histogramBucket{le: le, count: count})
					}
				}
			}
			countLine := metricKey + "_count"
			if strings.HasPrefix(line, countLine+" ") || strings.HasPrefix(line, countLine+"{") {
				if v := extractMetricValue(line); v != nil {
					histogramCounts[alias] = uint64(*v)
				}
			}
			sumLine := metricKey + "_sum"
			if strings.HasPrefix(line, sumLine+" ") || strings.HasPrefix(line, sumLine+"{") {
				if v := extractMetricValue(line); v != nil {
					histogramSums[alias] = *v
				}
			}
		}
	}

	if len(gaugeValues) == 0 && len(histogramBuckets) == 0 && len(histogramCounts) == 0 {
		return nil
	}

	ttftP50, ttftP95 := calculatePercentiles(histogramBuckets["time_to_first_token"], histogramCounts["time_to_first_token"], histogramSums["time_to_first_token"])
	tpotP50, tpotP95 := calculatePercentiles(histogramBuckets["time_per_output_token"], histogramCounts["time_per_output_token"], histogramSums["time_per_output_token"])

	data := &VLLMMetricsData{
		VLLMAvailable:         true,
		RunningRequests:       int(gaugeValues["running_requests"]),
		WaitingRequests:       int(gaugeValues["waiting_requests"]),
		SchedulingRequests:    int(gaugeValues["scheduling_requests"]),
		GPUCacheUsage:         gaugeValues["gpu_cache_usage"],
		CPUCacheUsage:         gaugeValues["cpu_cache_usage"],
		PrefixCacheHitRate:    gaugeValues["prefix_cache_hit_rate"],
		RequestThroughput:     gaugeValues["request_throughput"],
		PromptThroughput:      gaugeValues["prompt_throughput"],
		GenerationThroughput:  gaugeValues["generation_throughput"],
		TimeToFirstTokenP50:   ttftP50,
		TimeToFirstTokenP95:   ttftP95,
		TimeToFirstToken:      ttftP50,
		TimePerOutputTokenP50: tpotP50,
		TimePerOutputTokenP95: tpotP95,
		TimePerOutputToken:    tpotP50,
		ScrapedAt:             time.Now().Format(time.RFC3339),
	}
	return data
}

func extractMetricValue(line string) *float64 {
	if strings.Contains(line, "}") {
		idx := strings.Index(line, "}")
		valuePart := strings.TrimSpace(line[idx+1:])
		if valuePart != "" {
			if v, err := strconv.ParseFloat(valuePart, 64); err == nil {
				return &v
			}
		}
	} else if !strings.Contains(line, "{") {
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			if v, err := strconv.ParseFloat(parts[1], 64); err == nil {
				return &v
			}
		}
	}
	return nil
}

func extractHistogramBucket(line string) (string, string) {
	re := regexp.MustCompile(`le="([^"]+)"`)
	leMatch := re.FindStringSubmatch(line)
	if leMatch == nil {
		return "", ""
	}
	leStr := leMatch[1]

	if strings.Contains(line, "}") {
		idx := strings.Index(line, "}")
		valuePart := strings.TrimSpace(line[idx+1:])
		if valuePart != "" {
			return leStr, valuePart
		}
	} else if !strings.Contains(line, "{") {
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			return leStr, parts[1]
		}
	}
	return "", ""
}

func calculatePercentiles(buckets []histogramBucket, totalCount uint64, sum float64) (float64, float64) {
	if len(buckets) == 0 {
		return 0, 0
	}

	sort.Slice(buckets, func(i, j int) bool {
		return buckets[i].le < buckets[j].le
	})

	p50 := interpolatePercentile(buckets, 50, totalCount)
	p95 := interpolatePercentile(buckets, 95, totalCount)

	if p50 == 0 && totalCount > 0 {
		p50 = sum / float64(totalCount)
	}
	if p95 == 0 && totalCount > 0 {
		p95 = sum / float64(totalCount)
	}

	return p50, p95
}

func interpolatePercentile(buckets []histogramBucket, percentile float64, totalCount uint64) float64 {
	if totalCount == 0 || len(buckets) == 0 {
		return 0
	}

	targetCount := float64(percentile) / 100.0 * float64(totalCount)

	for i := 1; i < len(buckets); i++ {
		if buckets[i].count >= uint64(targetCount) && buckets[i-1].count < uint64(targetCount) {
			countDelta := float64(buckets[i].count - buckets[i-1].count)
			if countDelta == 0 {
				return buckets[i].le
			}
			rank := targetCount - float64(buckets[i-1].count)
			fraction := rank / countDelta
			bucketWidth := buckets[i].le - buckets[i-1].le
			return buckets[i-1].le + fraction*bucketWidth
		}
	}

	if buckets[len(buckets)-1].count < uint64(targetCount) {
		return buckets[len(buckets)-1].le
	}

	return 0
}

func (m *GPUMonitor) refreshCache() error {
	if !m.nvmlAvailable {
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
		DriverVersion:     m.driverVersion,
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
	var gpus []GPUInfo
	for i, device := range m.devices {
		info := m.collectFromDevice(device, i)
		if info != nil {
			gpus = append(gpus, *info)
		}
	}
	return gpus
}

func (m *GPUMonitor) collectFromDevice(device nvml.Device, index int) *GPUInfo {
	name, ret := device.GetName()
	if ret != nvml.SUCCESS {
		m.logger.Error("Failed to get device name", zap.Int("index", index))
		return nil
	}

	memInfo, ret := device.GetMemoryInfo()
	if ret != nvml.SUCCESS {
		return nil
	}

	temp, ret := device.GetTemperature(nvml.TEMPERATURE_GPU)
	if ret != nvml.SUCCESS {
		temp = 0
	}

	utilRates, ret := device.GetUtilizationRates()
	if ret != nvml.SUCCESS {
		utilRates.Gpu = 0
	}

	powerDraw, ret := device.GetPowerUsage()
	if ret != nvml.SUCCESS {
		powerDraw = 0
	}
	powerLimit, ret := device.GetPowerManagementLimit()
	if ret != nvml.SUCCESS {
		powerLimit = 0
	}

	powerDrawW := int(powerDraw / 1000)
	powerLimitW := int(powerLimit / 1000)
	powerPercent := 0
	if powerLimit > 0 {
		powerPercent = int(powerDraw * 100 / powerLimit)
	}

	fanSpeed, ret := device.GetFanSpeed()
	if ret != nvml.SUCCESS {
		fanSpeed = 0
	}

	clockSM, ret := device.GetClockInfo(nvml.CLOCK_SM)
	if ret != nvml.SUCCESS {
		clockSM = 0
	}
	clockMem, ret := device.GetClockInfo(nvml.CLOCK_MEM)
	if ret != nvml.SUCCESS {
		clockMem = 0
	}

	totalMB := int(memInfo.Total / (1024 * 1024))
	usedMB := int(memInfo.Used / (1024 * 1024))
	memUtilPercent := 0
	if totalMB > 0 {
		memUtilPercent = int(usedMB * 100 / totalMB)
	}

	eccErrors, ret := device.GetTotalEccErrors(0, 0)
	if ret != nvml.SUCCESS {
		eccErrors = 0
	}

	throttleReasons, ret := device.GetCurrentClocksThrottleReasons()
	if ret != nvml.SUCCESS {
		throttleReasons = 0
	}

	persistenceMode, ret := device.GetPersistenceMode()
	if ret != nvml.SUCCESS {
		persistenceMode = nvml.FEATURE_DISABLED
	}

	rxThroughput, ret := device.GetPcieThroughput(nvml.PCIE_UTIL_RX_BYTES)
	if ret != nvml.SUCCESS {
		rxThroughput = 0
	}
	txThroughput, ret := device.GetPcieThroughput(nvml.PCIE_UTIL_TX_BYTES)
	if ret != nvml.SUCCESS {
		txThroughput = 0
	}

	bar1Info, ret := device.GetBAR1MemoryInfo()
	if ret != nvml.SUCCESS {
		bar1Info.Bar1Total = 0
		bar1Info.Bar1Used = 0
	}

	vbiosVersion, ret := device.GetVbiosVersion()
	if ret != nvml.SUCCESS {
		vbiosVersion = ""
	}

	perfState, ret := device.GetPerformanceState()
	perfStateStr := fmt.Sprintf("P%d", perfState)
	if ret != nvml.SUCCESS {
		perfStateStr = ""
	}

	encoderUtil, _, ret := device.GetEncoderUtilization()
	if ret != nvml.SUCCESS {
		encoderUtil = 0
	}

	decoderUtil, _, ret := device.GetDecoderUtilization()
	if ret != nvml.SUCCESS {
		decoderUtil = 0
	}

	jpgUtil, _, ret := device.GetJpgUtilization()
	if ret != nvml.SUCCESS {
		jpgUtil = 0
	}

	ofaUtil, _, ret := device.GetOfaUtilization()
	if ret != nvml.SUCCESS {
		ofaUtil = 0
	}

	processes := m.collectProcesses(device)

	return &GPUInfo{
		Name:              name,
		Index:             index,
		TotalMemory:       int64(memInfo.Total),
		UsedMemory:        int64(memInfo.Used),
		AvailableMemory:   int64(memInfo.Free),
		Temperature:       int(temp),
		Utilization:       int(utilRates.Gpu),
		PowerDraw:         powerDrawW,
		PowerLimit:        powerLimitW,
		PowerPercent:      powerPercent,
		FanSpeed:          int(fanSpeed),
		ClockSM:           int(clockSM),
		ClockMem:          int(clockMem),
		MemoryUtilization: memUtilPercent,
		EccErrors:         int(eccErrors),
		ThrottleReasons:   decodeThrottleReasons(throttleReasons),
		PersistenceMode:   persistenceMode == nvml.FEATURE_ENABLED,
		PCIeRxThroughput:  int(rxThroughput),
		PCIeTxThroughput:  int(txThroughput),
		Bar1TotalMemory:   int64(bar1Info.Bar1Total),
		Bar1UsedMemory:    int64(bar1Info.Bar1Used),
		Processes:         processes,
		VbiosVersion:      vbiosVersion,
		DriverVersion:     m.driverVersion,
		PerformanceState:  perfStateStr,
		GPUEncUtilization: int(encoderUtil),
		GPUDecUtilization: int(decoderUtil),
		JpgUtilization:    int(jpgUtil),
		OfaUtilization:    int(ofaUtil),
	}
}

func (m *GPUMonitor) collectProcesses(device nvml.Device) []GPUProcess {
	processes, ret := device.GetComputeRunningProcesses()
	if ret != nvml.SUCCESS {
		return nil
	}

	var result []GPUProcess
	for _, proc := range processes {
		if proc.Pid == 0 {
			continue
		}
		name := getProcessCmdline(int(proc.Pid))
		if name == "" {
			name = fmt.Sprintf("pid-%d", proc.Pid)
		}
		result = append(result, GPUProcess{
			Pid:           int(proc.Pid),
			Name:          name,
			UsedGPUMemory: int64(proc.UsedGpuMemory),
		})
	}
	return result
}

func getProcessCmdline(pid int) string {
	cmdlinePath := fmt.Sprintf("/proc/%d/cmdline", pid)
	data, err := os.ReadFile(cmdlinePath)
	if err != nil {
		return ""
	}
	cmdline := strings.ReplaceAll(string(data), "\x00", " ")
	cmdline = strings.TrimSpace(cmdline)
	if len(cmdline) > 100 {
		cmdline = cmdline[:100]
	}
	return cmdline
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
			"index":               gpu.Index,
			"name":                gpu.Name,
			"ecc_errors":          gpu.EccErrors,
			"throttle_reasons":    gpu.ThrottleReasons,
			"persistence_mode":    gpu.PersistenceMode,
			"pcie_rx_throughput":  gpu.PCIeRxThroughput,
			"pcie_tx_throughput":  gpu.PCIeTxThroughput,
			"bar1_total_memory":   gpu.Bar1TotalMemory,
			"bar1_used_memory":    gpu.Bar1UsedMemory,
			"vbios_version":       gpu.VbiosVersion,
			"processes":           gpu.Processes,
			"performance_state":   gpu.PerformanceState,
			"gpu_enc_utilization": gpu.GPUEncUtilization,
			"gpu_dec_utilization": gpu.GPUDecUtilization,
			"jpg_utilization":     gpu.JpgUtilization,
			"ofa_utilization":     gpu.OfaUtilization,
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
		tempScore = math.Max(0, float64(100-(temp-85)*5))
	}

	memScore := 100.0
	if memUtil > 90 {
		memScore = math.Max(0, float64(100-(memUtil-90)*10))
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
		current["performance_state"] = status.Primary.PerformanceState
		current["gpu_enc_utilization"] = status.Primary.GPUEncUtilization
		current["gpu_dec_utilization"] = status.Primary.GPUDecUtilization
	}

	return &GPUSummary{
		Status:      "available",
		Current:     current,
		HealthScore: m.GetHealthScore(),
		History:     []interface{}{},
	}
}

type MemoryOptimizationStatus struct {
	Strategy               string  `json:"strategy"`
	Fragmentation          float64 `json:"fragmentation"`
	AvgFragmentation       float64 `json:"avg_fragmentation"`
	RecommendedUtilization float64 `json:"recommended_utilization"`
	LastFlush              string  `json:"last_flush"`
	FlushInterval          int     `json:"flush_interval"`
}

func (m *GPUMonitor) GetMemoryOptimizationStatus() *MemoryOptimizationStatus {
	return &MemoryOptimizationStatus{
		Strategy:               m.memoryStrategy,
		Fragmentation:          m.DetectFragmentation(),
		AvgFragmentation:       m.GetAverageFragmentation(),
		RecommendedUtilization: m.GetRecommendedUtilization(),
		FlushInterval:          300,
	}
}
