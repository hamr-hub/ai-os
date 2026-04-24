import json
import os
import time
from typing import Dict, Any, Optional

STATE_FILE = "/tmp/ai_os_state.json"
PID_DIR = "/tmp/ai_os_pids"

class StateManager:
    @staticmethod
    def get_state() -> Dict[str, Any]:
        if not os.path.exists(STATE_FILE):
            StateManager.save_state(StateManager.get_default_state())
        
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return StateManager.get_default_state()

    @staticmethod
    def get_default_state() -> Dict[str, Any]:
        return {
            "vllm": {
                "status": "stopped",
                "current_model": None,
                "loading_start": 0,
                "loading_target_duration": 5,
                "error": None
            },
            "gpu": {
                "name": "NVIDIA GeForce RTX 4090",
                "vram_total_mb": 24576,
                "vram_used_mb": 450,
                "temperature": 42,
                "utilization": 0,
                "power_draw": 30
            },
            "faults": {
                "oom_on_load": False,
                "hang_on_load": False,
                "crash_after_start": False
            }
        }

    @staticmethod
    def save_state(state: Dict[str, Any]):
        state["last_update"] = time.time()
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    @staticmethod
    def update_vllm_status():
        """根据当前时间和加载目标，自动转换状态"""
        state = StateManager.get_state()
        if "vllm" not in state:
            state = StateManager.get_default_state()
        
        vllm = state["vllm"]
        
        if vllm["status"] == "loading":
            elapsed = time.time() - vllm["loading_start"]
            
            if state.get("faults", {}).get("hang_on_load"):
                return # 模拟死锁，永不完成
                
            if state.get("faults", {}).get("oom_on_load") and elapsed > 5:
                vllm["status"] = "error"
                vllm["error"] = "Out of Memory"
                StateManager.save_state(state)
                return

            if elapsed >= vllm.get("loading_target_duration", 10):
                vllm["status"] = "active"
                if state.get("faults", {}).get("crash_after_start"):
                    # 如果模拟启动后崩溃，则在短 时间内设回 stopped
                    vllm["status"] = "stopped"
                    vllm["error"] = "Process crashed unexpectedly"
                StateManager.save_state(state)

if __name__ == "__main__":
    StateManager.update_vllm_status()
