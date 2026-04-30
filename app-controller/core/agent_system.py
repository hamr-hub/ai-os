import asyncio
import logging
import time
import os
import uuid
import subprocess
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("ai_controller.agent_system")

_COMMAND_TIMEOUT = 30
_MAX_HISTORY = 100

_ALLOWED_COMMANDS = {
    "nvidia-smi": True,
    "ps": True,
    "top": True,
    "free": True,
    "df": True,
    "ls": True,
    "cat": True,
    "grep": True,
    "python": True,
    "pip": True,
    "docker": True,
    "systemctl": True,
    "journalctl": True,
    "curl": True,
    "wget": True,
    "tar": True,
    "unzip": True,
    "chmod": True,
    "chown": False,
    "rm": False,
    "shutdown": False,
    "reboot": False,
    "mkfs": False,
    "dd": False,
}

_BLOCKED_PREFIXES = ["rm -rf /", "dd if=", "mkfs", "shutdown", "reboot", ":(){ :|:& };:"]


@dataclass
class AgentCommand:
    command_id: str
    command: str
    status: str = "pending"
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout_seconds: int = _COMMAND_TIMEOUT
    async_task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command": self.command,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "timeout_seconds": self.timeout_seconds,
        }


class AgentSystem:

    def __init__(self, config=None, sse_push=None):
        self._config = config
        self._sse_push = sse_push
        self._commands: Dict[str, AgentCommand] = {}
        self._history: List[AgentCommand] = []
        self._max_concurrent = 5
        self._active_count = 0
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if not self._semaphore:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    def validate_command(self, command: str) -> Dict:
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return {"valid": False, "reason": "empty_command"}

        base_cmd = cmd_parts[0]
        if os.path.isabs(base_cmd):
            basename = os.path.basename(base_cmd)
        else:
            basename = base_cmd

        allowed = _ALLOWED_COMMANDS.get(basename)
        if allowed is None:
            return {"valid": False, "reason": "command_not_allowed", "command": basename}
        if allowed is False:
            return {"valid": False, "reason": "command_blocked", "command": basename}

        cmd_lower = command.lower()
        for prefix in _BLOCKED_PREFIXES:
            if cmd_lower.startswith(prefix.lower()):
                return {"valid": False, "reason": "dangerous_pattern", "pattern": prefix}

        if self._config and hasattr(self._config, 'feature_flags'):
            blocked = self._config.feature_flags.get("agent_blocked_commands", [])
            if basename in blocked:
                return {"valid": False, "reason": "blocked_by_config", "command": basename}

        return {"valid": True, "command": command}

    async def execute_command(
        self, command: str, timeout: int = _COMMAND_TIMEOUT,
    ) -> Dict:
        validation = self.validate_command(command)
        if not validation["valid"]:
            return {
                "command_id": None,
                "status": "rejected",
                "reason": validation["reason"],
                "command": command,
            }

        command_id = str(uuid.uuid4())[:12]
        cmd_obj = AgentCommand(
            command_id=command_id,
            command=command,
            timeout_seconds=timeout,
        )
        self._commands[command_id] = cmd_obj
        self._push_event("agent_command_created", cmd_obj)

        async with self._get_semaphore():
            cmd_obj.status = "running"
            cmd_obj.started_at = time.time()
            self._active_count += 1
            self._push_event("agent_command_started", cmd_obj)

            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout,
                    )
                    cmd_obj.exit_code = proc.returncode
                    cmd_obj.stdout = stdout_bytes.decode('utf-8', errors='replace')[:8192]
                    cmd_obj.stderr = stderr_bytes.decode('utf-8', errors='replace')[:4096]
                    cmd_obj.status = "completed"
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    cmd_obj.status = "timeout"
                    cmd_obj.stderr = f"Command timed out after {timeout}s"
                    cmd_obj.exit_code = -1

            except Exception as e:
                cmd_obj.status = "error"
                cmd_obj.stderr = str(e)
                cmd_obj.exit_code = -1
            finally:
                cmd_obj.completed_at = time.time()
                self._active_count -= 1
                self._push_event("agent_command_completed", cmd_obj)
                self._add_to_history(cmd_obj)

        return cmd_obj.to_dict()

    def get_command_result(self, command_id: str) -> Optional[Dict]:
        cmd = self._commands.get(command_id)
        if not cmd:
            return None
        return cmd.to_dict()

    def cancel_command(self, command_id: str) -> Dict:
        cmd = self._commands.get(command_id)
        if not cmd:
            return {"cancelled": False, "reason": "not_found"}
        if cmd.status in ("completed", "error", "timeout"):
            return {"cancelled": False, "reason": f"already_{cmd.status}"}
        if cmd.async_task and not cmd.async_task.done():
            cmd.async_task.cancel()
        cmd.status = "cancelled"
        return {"cancelled": True, "command_id": command_id}

    def list_commands(self, status_filter: Optional[str] = None) -> List[Dict]:
        cmds = self._commands.values()
        if status_filter:
            cmds = [c for c in cmds if c.status == status_filter]
        return [c.to_dict() for c in sorted(cmds, key=lambda c: c.created_at)]

    def get_history(self, limit: int = 20) -> List[Dict]:
        return [c.to_dict() for c in self._history[-limit:]]

    def get_stats(self) -> Dict:
        by_status = {}
        for c in self._commands.values():
            by_status[c.status] = by_status.get(c.status, 0) + 1
        return {
            "total_commands": len(self._commands),
            "active_count": self._active_count,
            "max_concurrent": self._max_concurrent,
            "by_status": by_status,
        }

    def _add_to_history(self, cmd: AgentCommand):
        self._history.append(cmd)
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]
        self._commands.pop(cmd.command_id, None)

    def _push_event(self, event_type: str, cmd: AgentCommand):
        payload = {
            "type": event_type,
            "command_id": cmd.command_id,
            "command": cmd.command,
            "status": cmd.status,
        }
        if self._sse_push:
            try:
                self._sse_push.push_event("agent", payload)
            except Exception as e:
                logger.warning("SSE push failed: %s", e)

    async def get_system_info(self) -> Dict:
        results = {}
        basic_cmds = [
            ("hostname", "hostname"),
            ("uptime", "uptime"),
            ("memory", "free -h"),
            ("disk", "df -h /"),
            ("cpu", "nproc"),
            ("gpu", "nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader"),
            ("load", "cat /proc/loadavg"),
            ("processes", "ps aux --sort=-%mem | head -10"),
        ]
        for key, cmd in basic_cmds:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                results[key] = stdout.decode('utf-8', errors='replace').strip()
            except Exception as e:
                results[key] = f"error: {e}"
        return results


_MAX_SESSIONS = 50
_MAX_MESSAGES_PER_SESSION = 200


@dataclass
class AgentSession:
    session_id: str
    title: str = ""
    model: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    archived: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "model": self.model,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
        }

    def to_dict_full(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["messages"] = self.messages
        return d


class AgentSessionManager:

    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}

    def create_session(self, title: str = "", model: Optional[str] = None) -> AgentSession:
        if len(self._sessions) >= _MAX_SESSIONS:
            oldest = min(self._sessions.values(), key=lambda s: s.updated_at)
            self._sessions.pop(oldest.session_id, None)
        session_id = str(uuid.uuid4())[:12]
        session = AgentSession(session_id=session_id, title=title, model=model)
        self._sessions[session_id] = session
        logger.info("Created agent session %s", session_id)
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        return self._sessions.get(session_id)

    def list_sessions(self, archived: Optional[bool] = None) -> List[Dict]:
        sessions = list(self._sessions.values())
        if archived is not None:
            sessions = [s for s in sessions if s.archived == archived]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return [s.to_dict() for s in sessions]

    def add_message(self, session_id: str, role: str, content: str, **kwargs) -> Optional[AgentSession]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        msg = {"role": role, "content": content, "timestamp": time.time()}
        msg.update(kwargs)
        session.messages.append(msg)
        if len(session.messages) > _MAX_MESSAGES_PER_SESSION:
            session.messages = session.messages[-_MAX_MESSAGES_PER_SESSION:]
        session.updated_at = time.time()
        if not session.title and role == "user" and len(session.messages) <= 2:
            session.title = content[:50]
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions.pop(session_id)
            return True
        return False

    def archive_session(self, session_id: str) -> Optional[AgentSession]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.archived = True
        session.updated_at = time.time()
        return session

    def get_session_messages(self, session_id: str, limit: int = 100) -> Optional[List[Dict]]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session.messages[-limit:]

    def clear_session_messages(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.messages = []
        session.updated_at = time.time()
        return True
