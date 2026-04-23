package service

import (
	"runtime"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/mem"
	"go.uber.org/zap"
)

type SystemStatusCollector struct {
	logger *zap.Logger
}

type SystemStatusResult struct {
	Cpu       CpuStatus    `json:"cpu"`
	Memory    MemoryStatus `json:"memory"`
	Disk      DiskStatus   `json:"disk"`
	Timestamp string       `json:"timestamp"`
}

type CpuStatus struct {
	Percent      float64 `json:"percent"`
	Cores        int     `json:"cores"`
	CoresPhysical int    `json:"cores_physical"`
}

type MemoryStatus struct {
	TotalMb      uint64  `json:"total_mb"`
	AvailableMb  uint64  `json:"available_mb"`
	UsedMb       uint64  `json:"used_mb"`
	Percent      float64 `json:"percent"`
}

type DiskStatus struct {
	TotalGb uint64  `json:"total_gb"`
	UsedGb  uint64  `json:"used_gb"`
	FreeGb  uint64  `json:"free_gb"`
	Percent float64 `json:"percent"`
}

func NewSystemStatusCollector(logger *zap.Logger) *SystemStatusCollector {
	return &SystemStatusCollector{logger: logger}
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
