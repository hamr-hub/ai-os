import os
from typing import Optional


def resolve_config_path(explicit_path: Optional[str] = None) -> str:
    env_path = os.getenv("CONFIG_PATH") or os.getenv("AI_OS_CONFIG")
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_root = os.path.dirname(os.path.dirname(__file__))
    candidates = [
        explicit_path,
        env_path,
        os.path.join(repo_root, "config.yaml"),
        os.path.join(app_root, "config.yaml"),
        os.path.join(os.getcwd(), "config.yaml"),
    ]

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return env_path or explicit_path or candidates[2]
