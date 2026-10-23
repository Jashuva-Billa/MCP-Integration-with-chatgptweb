"""
Skills System
=============
Discoverable, reusable workflow instructions for the autonomous coding agent.

Skills are Markdown files with YAML frontmatter located in:
  1. Global: ~/.mcp/skills/<name>/SKILL.md
  2. Project: <repo_root>/.mcp/skills/<name>/SKILL.md
  3. Environment override: MCP_SKILLS_DIR

Each SKILL.md has frontmatter:
  ---
  name: python-development
  description: Python project setup and development workflow
  version: 1.0.0
  activation: ["*.py", "requirements.txt", "pyproject.toml"]
  tags: [python, testing, linting]
  requires_profile: safe
  ---

The system supports:
  - Automatic discovery and metadata indexing
  - Skill selection by name, tag, or file pattern
  - Conflict resolution (project skills override global)
  - Version tracking
  - Validation (frontmatter required)
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp_server.skills")


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML-like frontmatter from a Markdown file."""
    meta: Dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            fm_block = text[3:end].strip()
            body = text[end + 3:].strip()
            for line in fm_block.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    # Simple list parsing: [a, b, c]
                    if val.startswith("[") and val.endswith("]"):
                        items = [v.strip().strip('"\'') for v in val[1:-1].split(",") if v.strip()]
                        meta[key] = items
                    elif val.lower() in {"true", "yes"}:
                        meta[key] = True
                    elif val.lower() in {"false", "no"}:
                        meta[key] = False
                    else:
                        meta[key] = val.strip('"\'')
    return meta, body


class Skill:
    def __init__(self, path: Path, source: str = "project") -> None:
        self.path = path
        self.source = source           # "global" | "project"
        self._content: Optional[str] = None
        self._meta: Optional[Dict[str, Any]] = None
        self._body: Optional[str] = None

    def _load(self) -> None:
        if self._content is None:
            self._content = self.path.read_text(encoding="utf-8", errors="replace")
            self._meta, self._body = _parse_frontmatter(self._content)

    @property
    def name(self) -> str:
        self._load()
        return str(self._meta.get("name", self.path.parent.name))

    @property
    def description(self) -> str:
        self._load()
        return str(self._meta.get("description", ""))

    @property
    def version(self) -> str:
        self._load()
        return str(self._meta.get("version", "1.0.0"))

    @property
    def tags(self) -> List[str]:
        self._load()
        t = self._meta.get("tags", [])
        return t if isinstance(t, list) else [str(t)]

    @property
    def activation_patterns(self) -> List[str]:
        self._load()
        p = self._meta.get("activation", [])
        return p if isinstance(p, list) else [str(p)]

    @property
    def requires_profile(self) -> str:
        self._load()
        return str(self._meta.get("requires_profile", "safe"))

    @property
    def body(self) -> str:
        self._load()
        return self._body or ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "activation_patterns": self.activation_patterns,
            "requires_profile": self.requires_profile,
            "source": self.source,
            "path": str(self.path),
        }


class SkillsEngine:
    """
    Discovers, indexes, and serves skill definitions.
    Project skills take precedence over global skills with the same name.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}
        self._loaded = False

    def _discover_dirs(self) -> List[tuple[Path, str]]:
        dirs: List[tuple[Path, str]] = []

        # Environment override
        env_dir = os.environ.get("MCP_SKILLS_DIR", "")
        if env_dir and Path(env_dir).is_dir():
            dirs.append((Path(env_dir), "env"))
            return dirs

        # Global skills
        global_skills = Path.home() / ".mcp" / "skills"
        if global_skills.is_dir():
            dirs.append((global_skills, "global"))

        # Project skills (all registered repos)
        try:
            from app.core.repository import repository_manager
            for repo in repository_manager.list_repositories():
                if repo.get("exists_on_disk"):
                    skill_dir = Path(repo["path"]) / ".mcp" / "skills"
                    if skill_dir.is_dir():
                        dirs.append((skill_dir, "project"))
        except Exception:
            pass

        # Built-in skills shipped with this server
        builtin = Path(__file__).resolve().parent.parent.parent / "skills"
        if builtin.is_dir():
            dirs.append((builtin, "builtin"))

        return dirs

    def reload(self) -> None:
        """Re-scan all skill directories."""
        new_skills: Dict[str, Skill] = {}
        for base_dir, source in self._discover_dirs():
            for skill_file in sorted(base_dir.rglob("SKILL.md")):
                try:
                    skill = Skill(skill_file, source=source)
                    name = skill.name
                    # Project/env overrides global/builtin
                    if name not in new_skills or source in {"project", "env"}:
                        new_skills[name] = skill
                        logger.debug("Loaded skill '%s' from %s (%s)", name, skill_file, source)
                except Exception as exc:
                    logger.warning("Failed to load skill from %s: %s", skill_file, exc)

        self._skills = new_skills
        self._loaded = True
        logger.info("Skills engine: %d skill(s) loaded", len(self._skills))

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def list_skills(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available skills, optionally filtered by tag."""
        self._ensure_loaded()
        skills = list(self._skills.values())
        if tag:
            skills = [s for s in skills if tag.lower() in [t.lower() for t in s.tags]]
        return [s.to_dict() for s in sorted(skills, key=lambda s: s.name)]

    def get_skill(self, name: str) -> Optional[Skill]:
        self._ensure_loaded()
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Return the full SKILL.md content (frontmatter + body) for a skill."""
        skill = self.get_skill(name)
        if skill:
            return skill.path.read_text(encoding="utf-8", errors="replace")
        return None

    def select_for_context(self, file_patterns: List[str]) -> List[Skill]:
        """Return skills whose activation patterns match any supplied file path."""
        import fnmatch
        self._ensure_loaded()
        matched: List[Skill] = []
        for skill in self._skills.values():
            for pattern in skill.activation_patterns:
                if any(fnmatch.fnmatch(fp, pattern) or pattern.rstrip("/") in fp for fp in file_patterns):
                    matched.append(skill)
                    break
        return matched

    def select_for_task(self, task: str, file_paths: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """Choose relevant skills from task intent plus any known file paths."""
        self._ensure_loaded()
        text = (task or "").lower()
        rules = {
            "security-review": ("security", "vulnerab", "auth", "permission", "secret", "injection", "hardening", "threat"),
            "debugging-root-cause": ("debug", "bug", "error", "failing", "broken", "doesn't work", "latency", "crash", "trace"),
            "testing-tdd": ("test", "pytest", "coverage", "regression", "verify", "verification", "tdd"),
            "python-development": ("python", "pyproject", "pip", "pytest", "backend"),
            "typescript-javascript": ("typescript", "javascript", "node.js", "nodejs", "npm"),
            "frontend-development": ("frontend", "front-end", "ui", "css", "react", "layout", "overlay"),
            "java-backend": ("java", "spring", "maven", "gradle", "jvm"),
            "mcp-server-development": ("mcp", "model context protocol", "tool registration", "server tool"),
            "agentic-ai-langgraph": ("agent", "agentic", "langgraph", "langchain", "orchestration", "workflow"),
            "rag-vector-db": ("rag", "retrieval", "embedding", "vector database", "vector db"),
            "cicd-deployment": ("deploy", "deployment", "ci/cd", "pipeline", "docker", "kubernetes", "github actions"),
            "database-engineering": ("database", "sql", "schema", "migration", "query", "postgres"),
            "dependency-management": ("dependency", "dependencies", "upgrade package", "vulnerability scan"),
            "documentation-readme": ("readme", "documentation", "docs", "document"),
            "git-workflow": ("git", "commit", "push", "pull request", "branch", "merge", "github"),
            "performance-optimization": ("performance", "optimize", "optimization", "slow", "latency", "benchmark", "memory"),
            "production-readiness": ("production", "reliability", "observability", "monitoring", "scalability", "health check"),
            "refactoring-cleanup": ("refactor", "cleanup", "clean up", "duplicate", "dead code", "simplify"),
            "repo-exploration": ("inspect", "explore", "understand", "analyze repository", "architecture", "audit"),
            "api-design": ("api", "endpoint", "openapi", "graphql", "rest api"),
        }
        selected: Dict[str, str] = {}
        for name, keywords in rules.items():
            hits = [word for word in keywords if word in text]
            if hits and name in self._skills:
                selected[name] = f"Task intent matched: {', '.join(hits[:3])}"
        for skill in self.select_for_context(file_paths or []):
            selected.setdefault(skill.name, "File path matched skill activation pattern")
        # Every code change should include a test workflow; exploratory tasks should inspect first.
        if any(word in text for word in ("change", "implement", "add", "fix", "modify", "refactor", "build", "create")):
            if "testing-tdd" in self._skills:
                selected.setdefault("testing-tdd", "Default verification skill for code changes")
        if not selected and "repo-exploration" in self._skills:
            selected["repo-exploration"] = "Fallback skill for ambiguous tasks"
        return [{"name": name, "reason": reason} for name, reason in selected.items()]


# Singleton
skills_engine = SkillsEngine()
