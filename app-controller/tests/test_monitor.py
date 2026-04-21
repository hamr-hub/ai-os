import pytest
from unittest.mock import Mock, patch
from core.monitor import GPUMonitor

GPU_OUTPUT = "NVIDIA RTX 4090, 24564, 5000, 19564, 65, 30, 100, 450, 40, 2100, 10000"

class TestGPUMonitor:
    @patch('subprocess.run')
    def test_check_nvidia_smi_available(self, mock_run):
        mock_run.return_value.returncode = 0
        monitor = GPUMonitor()
        assert monitor._nvidia_smi_available is True

    @patch('subprocess.run')
    def test_check_nvidia_smi_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        monitor = GPUMonitor()
        assert monitor._nvidia_smi_available is False

    @patch('subprocess.run')
    def test_get_gpu_status_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT
        
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        
        status = monitor.get_gpu_status()
        
        assert status is not None
        assert status["status"] == "available"
        assert status["gpu_count"] == 1
        assert status["primary"]["name"] == "NVIDIA RTX 4090"
        assert status["primary"]["total_memory"] == 24564 * 1024 ** 2
        assert status["primary"]["used_memory"] == 5000 * 1024 ** 2
        assert status["primary"]["available_memory"] == 19564 * 1024 ** 2
        assert status["primary"]["temperature"] == 65
        assert status["primary"]["utilization"] == 30

    @patch('subprocess.run')
    def test_get_gpu_status_multiple_gpus(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = f"{GPU_OUTPUT}\nNVIDIA RTX 3090, 24564, 8000, 16564, 70, 40, 120, 350, 50, 1800, 9500"
        
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        
        status = monitor.get_gpu_status()
        
        assert status is not None
        assert status["gpu_count"] == 2
        assert len(status["all_gpus"]) == 2

    @patch('subprocess.run')
    def test_get_gpu_status_nvidia_smi_failed(self, mock_run):
        mock_run.return_value.returncode = 1
        
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        
        status = monitor.get_gpu_status()
        assert status is None

    @patch('subprocess.run')
    def test_get_gpu_status_uses_cache(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        mock_run.reset_mock()

        first = monitor.get_gpu_status()
        second = monitor.get_gpu_status()

        assert first is not None
        assert second is not None
        assert mock_run.call_count == 1

    @patch('subprocess.run')
    def test_get_memory_usage(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT
        
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        
        mem_info = monitor.get_memory_usage()
        
        assert mem_info is not None
        assert mem_info["total"] == 24564 * 1024 ** 2
        assert mem_info["used"] == 5000 * 1024 ** 2
        assert mem_info["available"] == 19564 * 1024 ** 2

    @patch('subprocess.run')
    def test_is_memory_available(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT
        
        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        
        assert monitor.is_memory_available(10 * 1024 ** 3) is True
        assert monitor.is_memory_available(25 * 1024 ** 3) is False
