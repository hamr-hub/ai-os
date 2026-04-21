import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from core.sys_ctl import SystemController

class TestSystemController:
    def test_init_windows(self):
        with patch('os.name', 'nt'):
            controller = SystemController()
            assert controller._use_sudo is False

    @pytest.mark.skipif(os.name == 'nt', reason="os.geteuid not available on Windows")
    def test_init_linux_non_root(self):
        with patch('os.name', 'posix'):
            with patch.object(os, 'geteuid', return_value=1000):
                controller = SystemController()
                assert controller._use_sudo is True

    @pytest.mark.skipif(os.name == 'nt', reason="os.geteuid not available on Windows")
    def test_init_linux_root(self):
        with patch('os.name', 'posix'):
            with patch.object(os, 'geteuid', return_value=0):
                controller = SystemController()
                assert controller._use_sudo is False

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_start_service_success(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        controller = SystemController()
        result = controller.start_service("vllm-gemma")
        assert result is True
        mock_run.assert_called_once()

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_start_service_failure(self, mock_run, mock_which):
        mock_run.return_value.returncode = 1
        controller = SystemController()
        result = controller.start_service("vllm-gemma")
        assert result is False

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_stop_service(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        controller = SystemController()
        result = controller.stop_service("vllm-gemma")
        assert result is True

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_restart_service(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        controller = SystemController()
        result = controller.restart_service("vllm-gemma")
        assert result is True

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_get_service_status_active(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "active\n"
        controller = SystemController()
        status = controller.get_service_status("vllm-gemma")
        assert status == "active"

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_get_service_status_inactive(self, mock_run, mock_which):
        mock_run.return_value.returncode = 3
        controller = SystemController()
        status = controller.get_service_status("vllm-gemma")
        assert status == "inactive"

    @patch('shutil.which', return_value=None)
    def test_get_service_status_without_systemctl(self, mock_which):
        controller = SystemController()
        status = controller.get_service_status("vllm-gemma")
        assert status == "inactive"

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_is_service_running(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "active\n"
        controller = SystemController()
        assert controller.is_service_running("vllm-gemma") is True
        
        mock_run.return_value.returncode = 3
        assert controller.is_service_running("vllm-gemma") is False

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_enable_service(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        controller = SystemController()
        result = controller.enable_service("vllm-gemma")
        assert result is True

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_disable_service(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        controller = SystemController()
        result = controller.disable_service("vllm-gemma")
        assert result is True

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_get_service_info(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"Id": "vllm-gemma.service", "ActiveState": "active"}'
        controller = SystemController()
        info = controller.get_service_info("vllm-gemma")
        assert info is not None
        assert info["Id"] == "vllm-gemma.service"

    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('subprocess.run')
    def test_list_services(self, mock_run, mock_which):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '[{"id": "vllm-gemma.service"}, {"id": "vllm-llama.service"}]'
        controller = SystemController()
        services = controller.list_services()
        assert len(services) == 2

    @patch('subprocess.run')
    def test_get_process_info(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "p1234\ncvllm"
        controller = SystemController()
        info = controller.get_process_info(8000)
        assert info is not None
        assert info["pid"] == 1234
        assert info["command"] == "vllm"
