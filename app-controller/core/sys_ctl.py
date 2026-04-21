import subprocess
import os
import json
import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from core.cache_service import cache_service

logger = logging.getLogger("ai_controller.sys_ctl")

class SystemController:
    def __init__(self):
        if os.name == 'nt':
            self._use_sudo = False
        else:
            self._use_sudo = os.geteuid() != 0 if hasattr(os, 'geteuid') else True
        
        self._restart_attempts: Dict[str, int] = {}
        self._last_restart_time: Dict[str, datetime] = {}
        self._max_restart_attempts = 3
        self._restart_cooldown = 60
        self._watchdog_enabled = False
        self._watchdog_tasks: Dict[str, asyncio.Task] = {}
    
    def _supports_systemctl(self) -> bool:
        return os.name != 'nt' and shutil.which('systemctl') is not None
    
    def _run_command(self, cmd: list) -> subprocess.CompletedProcess:
        actual_cmd = list(cmd)
        if self._use_sudo and os.name != 'nt':
            actual_cmd = ['sudo'] + actual_cmd
        logger.info("Running command: %s", ' '.join(actual_cmd))
        result = subprocess.run(actual_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("Command failed: %s rc=%s stderr=%s", ' '.join(actual_cmd), result.returncode, (result.stderr or '').strip())
        return result
    
    def _unsupported_result(self, stdout: str = '', stderr: str = 'systemctl not available') -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=['systemctl'], returncode=1, stdout=stdout, stderr=stderr)
    
    def start_service(self, service_name: str) -> bool:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when starting service: %s", service_name)
            return False
        result = self._run_command(['systemctl', 'start', service_name])
        return result.returncode == 0
    
    def stop_service(self, service_name: str) -> bool:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when stopping service: %s", service_name)
            return False
        result = self._run_command(['systemctl', 'stop', service_name])
        return result.returncode == 0
    
    def restart_service(self, service_name: str) -> bool:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when restarting service: %s", service_name)
            return False
        result = self._run_command(['systemctl', 'restart', service_name])
        return result.returncode == 0
    
    def get_service_status(self, service_name: str) -> str:
        cache_key = f"ai_controller:cache:service_status:{service_name}"
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
        
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when checking service: %s", service_name)
            return 'inactive'
        result = self._run_command(['systemctl', 'is-active', service_name])
        status = result.stdout.strip() if result.returncode == 0 else 'inactive'
        
        cache_service.set(cache_key, status, ttl_seconds=5)
        return status
    
    def is_service_running(self, service_name: str) -> bool:
        status = self.get_service_status(service_name)
        return status == 'active'
    
    def enable_service(self, service_name: str) -> bool:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when enabling service: %s", service_name)
            return False
        result = self._run_command(['systemctl', 'enable', service_name])
        return result.returncode == 0
    
    def disable_service(self, service_name: str) -> bool:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when disabling service: %s", service_name)
            return False
        result = self._run_command(['systemctl', 'disable', service_name])
        return result.returncode == 0
    
    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when reading service info: %s", service_name)
            return None
        result = self._run_command(['systemctl', 'show', service_name, '--json'])
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except Exception:
                logger.exception("Failed to parse service info: %s", service_name)
        return None
    
    def list_services(self, pattern: str = '') -> list:
        if not self._supports_systemctl():
            logger.warning("systemctl unsupported when listing services")
            return []
        result = self._run_command(['systemctl', 'list-units', '--type=service', '--all', '--json'])
        if result.returncode == 0:
            try:
                services = json.loads(result.stdout)
                if pattern:
                    return [s for s in services if pattern in s.get('id', '')]
                return services
            except Exception:
                logger.exception("Failed to parse service list")
        return []
    
    def get_process_info(self, port: int) -> Optional[Dict[str, Any]]:
        cache_key = f"ai_controller:cache:process_info:{port}"
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-s', 'TCP:LISTEN', '-F', 'pc'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                pid = None
                cmd = None
                for line in lines:
                    if line.startswith('p'):
                        pid = int(line[1:])
                    elif line.startswith('c'):
                        cmd = line[1:]
                if pid:
                    info = {'pid': pid, 'command': cmd}
                    cache_service.set(cache_key, info, ttl_seconds=10)
                    return info
        except Exception:
            logger.exception("Failed to get process info for port: %s", port)
        return None
    
    def get_restart_attempts(self, service_name: str) -> int:
        return self._restart_attempts.get(service_name, 0)
    
    def reset_restart_attempts(self, service_name: str):
        self._restart_attempts[service_name] = 0
    
    async def _can_restart(self, service_name: str) -> bool:
        last_time = self._last_restart_time.get(service_name)
        if last_time and (datetime.now() - last_time).total_seconds() < self._restart_cooldown:
            return False
        
        attempts = self._restart_attempts.get(service_name, 0)
        return attempts < self._max_restart_attempts
    
    async def try_restart_service(self, service_name: str) -> bool:
        if not await self._can_restart(service_name):
            return False
        
        self._last_restart_time[service_name] = datetime.now()
        self._restart_attempts[service_name] = self._restart_attempts.get(service_name, 0) + 1
        
        success = self.restart_service(service_name)
        if success:
            self.reset_restart_attempts(service_name)
        
        return success
    
    async def start_watchdog(self, service_name: str, check_interval: int = 5):
        if service_name in self._watchdog_tasks:
            self._watchdog_tasks[service_name].cancel()
        
        async def watchdog_loop():
            while True:
                try:
                    if not self.is_service_running(service_name):
                        await self.try_restart_service(service_name)
                except Exception:
                    logger.exception("Watchdog loop failed: %s", service_name)
                
                await asyncio.sleep(check_interval)
        
        self._watchdog_tasks[service_name] = asyncio.create_task(watchdog_loop())
        self._watchdog_enabled = True
    
    def stop_watchdog(self, service_name: str):
        task = self._watchdog_tasks.get(service_name)
        if task:
            task.cancel()
            del self._watchdog_tasks[service_name]
    
    def get_watchdog_status(self) -> Dict[str, bool]:
        status = {}
        for service_name, task in self._watchdog_tasks.items():
            status[service_name] = not task.done()
        return status
    
    def set_max_restart_attempts(self, attempts: int):
        self._max_restart_attempts = attempts
    
    def set_restart_cooldown(self, seconds: int):
        self._restart_cooldown = seconds
