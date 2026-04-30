import pytest
from unittest.mock import Mock, patch, MagicMock
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
    def test_get_gpu_status_from_cache(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        monitor._status_cache = {
            "status": "available",
            "gpu_count": 1,
            "primary": {
                "name": "NVIDIA RTX 4090",
                "total_memory": 24564 * 1024 ** 2,
                "used_memory": 5000 * 1024 ** 2,
                "available_memory": 19564 * 1024 ** 2,
                "temperature": 65,
                "utilization": 30,
            },
            "all_gpus": [],
        }
        monitor._status_cache_time = __import__('datetime').datetime.now()

        status = monitor.get_gpu_status()

        assert status is not None
        assert status["status"] == "available"
        assert status["gpu_count"] == 1
        assert status["primary"]["name"] == "NVIDIA RTX 4090"

    @patch('subprocess.run')
    def test_get_gpu_status_no_cache(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True

        status = monitor.get_gpu_status()

        assert status is None

    @patch('subprocess.run')
    def test_get_gpu_status_nvidia_smi_failed(self, mock_run):
        mock_run.return_value.returncode = 1

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True

        status = monitor.get_gpu_status()
        assert status is None

    @patch('subprocess.run')
    def test_get_memory_usage_from_cache(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        monitor._status_cache = {
            "status": "available",
            "gpu_count": 1,
            "name": "NVIDIA RTX 4090",
            "total_memory": 24564 * 1024 ** 2,
            "used_memory": 5000 * 1024 ** 2,
            "available_memory": 19564 * 1024 ** 2,
            "primary": {
                "total_memory": 24564 * 1024 ** 2,
                "used_memory": 5000 * 1024 ** 2,
                "available_memory": 19564 * 1024 ** 2,
            },
        }
        monitor._status_cache_time = __import__('datetime').datetime.now()

        mem_info = monitor.get_memory_usage()

        assert mem_info is not None
        assert mem_info["total"] == 24564 * 1024 ** 2
        assert mem_info["used"] == 5000 * 1024 ** 2
        assert mem_info["available"] == 19564 * 1024 ** 2

    @patch('subprocess.run')
    def test_is_memory_available_from_cache(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = GPU_OUTPUT

        monitor = GPUMonitor()
        monitor._nvidia_smi_available = True
        monitor._status_cache = {
            "status": "available",
            "gpu_count": 1,
            "name": "NVIDIA RTX 4090",
            "total_memory": 24564 * 1024 ** 2,
            "used_memory": 5000 * 1024 ** 2,
            "available_memory": 19564 * 1024 ** 2,
            "primary": {
                "available_memory": 19564 * 1024 ** 2,
                "total_memory": 24564 * 1024 ** 2,
            },
        }
        monitor._status_cache_time = __import__('datetime').datetime.now()

        assert monitor.is_memory_available(10 * 1024 ** 3) is True
        assert monitor.is_memory_available(25 * 1024 ** 3) is False
