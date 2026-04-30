import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from core.sys_ctl import SystemController
from core.cache_service import cache_service

class TestSystemController:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        # Clear cache before each test
        cache_service._clear_local_cache()
        yield
        # Clear cache after each test too
        cache_service._clear_local_cache()

    def test_init_windows(self):
        with patch('os.name', 'nt'):
            controller = SystemController()
            assert controller._use_sudo is False

    @pytest.mark.skipif(os.name == 'nt', reason="os.geteuid not available on Windows")
    def test_init_linux_non_root(self):
        # Current implementation does NOT set _use_sudo based on UID
        # It's always False by default
        with patch('os.name', 'posix'):
            with patch.object(os, 'geteuid', return_value=1000):
                controller = SystemController()
                # Implementation always sets _use_sudo to False by default
                assert controller._use_sudo is False

    @pytest.mark.skipif(os.name == 'nt', reason="os.geteuid not available on Windows")
    def test_init_linux_root(self):
        with patch('os.name', 'posix'):
            with patch.object(os, 'geteuid', return_value=0):
                controller = SystemController()
                assert controller._use_sudo is False

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_start_service_success(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.start_service("vllm")
        assert result is True
        mock_run.assert_called_once()

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_start_service_failure(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.start_service("vllm")
        assert result is False

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_stop_service(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.stop_service("vllm")
        assert result is True

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_restart_service(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.restart_service("vllm")
        assert result is True

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_get_service_status_active(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'active\n'
        mock_run.return_value = mock_result
        controller = SystemController()
        status = controller.get_service_status("vllm")
        assert status == "active"

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_get_service_status_inactive(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 3
        mock_result.stdout = 'inactive\n'
        mock_run.return_value = mock_result
        controller = SystemController()
        status = controller.get_service_status("vllm", use_cache=False)
        assert status == "inactive"

    @patch('os.path.exists', return_value=False)
    @patch('shutil.which', return_value=None)
    def test_get_service_status_without_systemctl(self, mock_which, mock_exists):
        controller = SystemController()
        status = controller.get_service_status("vllm", use_cache=False)
        assert status == "inactive"

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_is_service_running(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'active\n'
        mock_run.return_value = mock_result
        controller = SystemController()
        assert controller.is_service_running("vllm") is True

        mock_result.returncode = 3
        assert controller.is_service_running("vllm") is False

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_enable_service(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.enable_service("vllm")
        assert result is True

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_disable_service(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        controller = SystemController()
        result = controller.disable_service("vllm")
        assert result is True

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_get_service_info(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"Id": "vllm.service", "ActiveState": "active"}'
        mock_run.return_value = mock_result
        controller = SystemController()
        info = controller.get_service_info("vllm")
        assert info is not None
        assert info["Id"] == "vllm.service"

    @patch('os.path.exists', return_value=True)
    @patch('shutil.which', return_value='/bin/systemctl')
    @patch('core.sys_ctl.subprocess.run')
    def test_list_services(self, mock_run, mock_which, mock_exists):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '[{"id": "vllm.service"}]'
        mock_run.return_value = mock_result
        controller = SystemController()
        services = controller.list_services()
        assert len(services) == 1

    @patch('core.sys_ctl.subprocess.run')
    def test_get_process_info(self, mock_run):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "p1234\ncvllm"
        mock_run.return_value = mock_result
        controller = SystemController()
        info = controller.get_process_info(8000)
        assert info is not None
        assert info["pid"] == 1234
        assert info["command"] == "vllm"
