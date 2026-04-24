package service

import (
	"context"
	"encoding/json"
	"runtime"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/mem"
	"go-vllm-api/internal/repository"
	"go.uber.org/zap"
)

type SystemStatusCollector struct {
	logger *zap.Logger
	redis  *repository.RedisRepo
}

type SystemStatusResult struct {
	Cpu       CpuStatus    `json:"cpu"`
	Memory    MemoryStatus `json:"memory"`
	Disk      DiskStatus   `json:"disk"`
	Timestamp string       `json:"timestamp"`
}

type SystemHistoryEntry struct {
	Timestamp     string  `json:"timestamp"`
	CpuPercent    float64 `json:"cpu_percent"`
	MemoryPercent float64 `json:"memory_percent"`
	DiskPercent   float64 `json:"disk_percent"`
	CpuCores      int     `json:"cpu_cores"`
	MemoryUsedMb  uint64  `json:"memory_used_mb"`
	MemoryTotalMb uint64  `json:"memory_total_mb"`
	DiskUsedGb    uint64  `json:"disk_used_gb"`
	DiskTotalGb   uint64  `json:"disk_total_gb"`
}

type CpuStatus struct {
	Percent       float64 `json:"percent"`
	Cores         int     `json:"cores"`
	CoresPhysical int     `json:"cores_physical"`
}

type MemoryStatus struct {
	TotalMb     uint64  `json:"total_mb"`
	AvailableMb uint64  `json:"available_mb"`
	UsedMb      uint64  `json:"used_mb"`
	Percent     float64 `json:"percent"`
}

type DiskStatus struct {
	TotalGb uint64  `json:"total_gb"`
	UsedGb  uint64  `json:"used_gb"`
	FreeGb  uint64  `json:"free_gb"`
	Percent float64 `json:"percent"`
}

func NewSystemStatusCollector(logger *zap.Logger, redis *repository.RedisRepo) *SystemStatusCollector {
	return &SystemStatusCollector{logger: logger, redis: redis}
}

func (s *SystemStatusCollector) GetSystemStatus() *SystemStatusResult {
	cpuPercent, err := cpu.Percent(1, false)
	if err != nil {
		s.logger.Error("get cpu percent", zap.Error(err))
		cpuPercent = []float64{0}
	}

	cpuCores := runtime.NumCPU()
	cpuPhysical, err := cpu.Counts(false)
	if err != nil {
		s.logger.Error("get cpu physical cores", zap.Error(err))
		cpuPhysical = cpuCores
	}

	memInfo, err := mem.VirtualMemory()
	if err != nil {
		s.logger.Error("get virtual memory", zap.Error(err))
		memInfo = &mem.VirtualMemoryStat{}
	}

	diskInfo, err := disk.Usage("/")
	if err != nil {
		s.logger.Error("get disk usage", zap.Error(err))
		diskInfo = &disk.UsageStat{}
	}

	return &SystemStatusResult{
		Cpu: CpuStatus{
			Percent:       cpuPercent[0],
			Cores:         cpuCores,
			CoresPhysical: cpuPhysical,
		},
		Memory: MemoryStatus{
			TotalMb:     memInfo.Total / (1024 * 1024),
			AvailableMb: memInfo.Available / (1024 * 1024),
			UsedMb:      memInfo.Used / (1024 * 1024),
			Percent:     memInfo.UsedPercent,
		},
		Disk: DiskStatus{
			TotalGb: diskInfo.Total / (1024 * 1024 * 1024),
			UsedGb:  diskInfo.Used / (1024 * 1024 * 1024),
			FreeGb:  diskInfo.Free / (1024 * 1024 * 1024),
			Percent: diskInfo.UsedPercent,
		},
		Timestamp: time.Now().Format(time.RFC3339),
	}
}

func (s *SystemStatusCollector) SaveSystemHistory() {
	status := s.GetSystemStatus()
	if s.redis == nil || !s.redis.IsConnected() {
		return
	}
	ctx := context.Background()
	key := "system:history"
	entry := SystemHistoryEntry{
		Timestamp:     status.Timestamp,
		CpuPercent:    status.Cpu.Percent,
		MemoryPercent: status.Memory.Percent,
		DiskPercent:   status.Disk.Percent,
		CpuCores:      status.Cpu.Cores,
		MemoryUsedMb:  status.Memory.UsedMb,
		MemoryTotalMb: status.Memory.TotalMb,
		DiskUsedGb:    status.Disk.UsedGb,
		DiskTotalGb:   status.Disk.TotalGb,
	}
	data, _ := json.Marshal(entry)
	s.redis.LPush(ctx, key, string(data))
	s.redis.LTrim(ctx, key, 0, 129599)
	s.redis.Expire(ctx, key, 30*24*time.Hour)
}

func (s *SystemStatusCollector) GetSystemHistory(limit int) []SystemHistoryEntry {
	if s.redis == nil || !s.redis.IsConnected() {
		return nil
	}
	ctx := context.Background()
	key := "system:history"
	items, err := s.redis.LRange(ctx, key, 0, int64(limit-1))
	if err != nil {
		return nil
	}
	var entries []SystemHistoryEntry
	for _, item := range items {
		var entry SystemHistoryEntry
		if err := json.Unmarshal([]byte(item), &entry); err == nil {
			entries = append(entries, entry)
		}
	}
	return entries
}
