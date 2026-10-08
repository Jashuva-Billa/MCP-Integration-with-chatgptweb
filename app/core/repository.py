import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from app.config import settings

logger = logging.getLogger("mcp_server.repository")

class RepositoryManager:
    """
    Manages the external registry of local workspaces.
    Stores and validates repository paths, metadata, and enabled status.
    Guarantees non-destructive removal (never deletes physical directories).
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or settings.REPOSITORIES_CONFIG_PATH).resolve()
        self._lock = threading.Lock()

    def _read_raw(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            # Check for fallback yaml if json does not exist
            yaml_path = self.config_path.with_suffix(".yaml")
            if yaml_path.exists():
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        return data.get("repositories", {})
                except Exception as e:
                    logger.warning(f"Failed to read legacy YAML configuration: {e}")
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                if self.config_path.suffix.lower() == ".json":
                    data = json.load(f)
                    return data.get("repositories", {})
                else:
                    data = yaml.safe_load(f) or {}
                    return data.get("repositories", {})
        except Exception as e:
            logger.error(f"Error loading repository configuration from {self.config_path}: {e}")
            return {}

    def _write_raw(self, repos: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                if self.config_path.suffix.lower() == ".json":
                    json.dump({"repositories": repos}, f, indent=2, ensure_ascii=False)
                else:
                    yaml.safe_dump({"repositories": repos}, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving repository configuration to {self.config_path}: {e}")
            raise

    def list_repositories(self) -> List[Dict[str, Any]]:
        """Lists all registered repositories, checking their physical existence on disk."""
        with self._lock:
            raw_repos = self._read_raw()
            
        result = []
        for name, data in raw_repos.items():
            if isinstance(data, str):
                path_str = data
                desc = ""
                enabled = True
            else:
                path_str = data.get("path", "")
                desc = data.get("description", "")
                enabled = data.get("enabled", True)

            p = Path(path_str).resolve()
            result.append({
                "name": name,
                "path": str(p),
                "description": desc,
                "enabled": enabled,
                "exists_on_disk": p.exists() and p.is_dir()
            })
        return result

    def get_repository(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single repository configuration by name."""
        with self._lock:
            raw_repos = self._read_raw()
            
        if name not in raw_repos:
            return None
            
        data = raw_repos[name]
        if isinstance(data, str):
            p = Path(data).resolve()
            return {"name": name, "path": str(p), "description": "", "enabled": True, "exists_on_disk": p.exists() and p.is_dir()}
        else:
            p = Path(data.get("path", "")).resolve()
            return {
                "name": name,
                "path": str(p),
                "description": data.get("description", ""),
                "enabled": data.get("enabled", True),
                "exists_on_disk": p.exists() and p.is_dir()
            }

    def add_repository(self, name: str, path: str, description: str = "", enabled: bool = True) -> Dict[str, Any]:
        """Registers a new repository. Validates directory existence."""
        resolved = Path(path).resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"Path '{path}' does not exist or is not a valid directory on disk.")

        with self._lock:
            repos = self._read_raw()
            repos[name] = {
                "path": str(resolved),
                "description": description or f"Repository at {resolved}",
                "enabled": enabled
            }
            self._write_raw(repos)

        logger.info(f"Registered repository '{name}' -> {resolved}")
        return {
            "name": name,
            "path": str(resolved),
            "description": description,
            "enabled": enabled
        }

    def remove_repository(self, name: str) -> bool:
        """
        Removes a repository from the registry ONLY.
        NEVER deletes or modifies the physical directory on disk.
        """
        with self._lock:
            repos = self._read_raw()
            if name not in repos:
                return False
            del repos[name]
            self._write_raw(repos)

        logger.info(f"Unregistered repository '{name}' from registry. Physical directory was untouched.")
        return True

repository_manager = RepositoryManager()
