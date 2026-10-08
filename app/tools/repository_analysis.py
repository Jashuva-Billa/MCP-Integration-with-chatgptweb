import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Set
from app.core.session import session_manager
from app.core.security import security_engine

def analyze_repository() -> Dict[str, Any]:
    """
    Analyze the active workspace to automatically detect programming languages, frameworks, package managers,
    entry points, test frameworks, configuration files, Git state, and architectural overview.
    ChatGPT should run this when beginning work on an unfamiliar codebase.
    """
    try:
        repo_root = session_manager.get_active_repo_path()
        repo_name = session_manager.get_active_repo_name()

        languages: Set[str] = set()
        frameworks: Set[str] = set()
        package_managers: Set[str] = set()
        test_frameworks: Set[str] = set()
        entry_points: List[str] = []
        config_files: List[str] = []

        # Check top-level config files
        config_signatures = {
            "requirements.txt": ("Python", "pip"),
            "pyproject.toml": ("Python", "poetry/pip/uv"),
            "setup.py": ("Python", "setuptools"),
            "Pipfile": ("Python", "pipenv"),
            "package.json": ("JavaScript/TypeScript", "npm/yarn/pnpm"),
            "tsconfig.json": ("TypeScript", None),
            "Cargo.toml": ("Rust", "cargo"),
            "go.mod": ("Go", "go mod"),
            "pom.xml": ("Java", "maven"),
            "build.gradle": ("Java/Kotlin", "gradle"),
            "Dockerfile": (None, "docker"),
            "docker-compose.yml": (None, "docker-compose")
        }

        for fname, (lang, pm) in config_signatures.items():
            fpath = repo_root / fname
            if fpath.exists():
                config_files.append(fname)
                if lang:
                    languages.add(lang)
                if pm:
                    package_managers.add(pm)

        # Inspect package.json for JS/TS frameworks
        pkg_json = repo_root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "next" in deps:
                    frameworks.add("Next.js")
                if "react" in deps:
                    frameworks.add("React")
                if "vue" in deps:
                    frameworks.add("Vue")
                if "express" in deps:
                    frameworks.add("Express")
                if "fastify" in deps:
                    frameworks.add("Fastify")
                if "jest" in deps:
                    test_frameworks.add("Jest")
                if "vitest" in deps:
                    test_frameworks.add("Vitest")
                if "typescript" in deps:
                    languages.add("TypeScript")
            except Exception:
                pass

        # Inspect Python files / requirements for Python frameworks
        req_file = repo_root / "requirements.txt"
        if req_file.exists():
            try:
                req_text = req_file.read_text(encoding="utf-8").lower()
                if "fastapi" in req_text:
                    frameworks.add("FastAPI")
                if "flask" in req_text:
                    frameworks.add("Flask")
                if "django" in req_text:
                    frameworks.add("Django")
                if "streamlit" in req_text:
                    frameworks.add("Streamlit")
                if "pytest" in req_text:
                    test_frameworks.add("pytest")
            except Exception:
                pass

        # Inspect common entry points
        potential_entry_points = [
            "main.py", "app.py", "run.py", "server.py", "manage.py",
            "src/main.py", "src/app.py", "app/main.py",
            "index.ts", "src/index.ts", "index.js", "src/index.js", "server.js",
            "main.go", "src/main.rs"
        ]
        for ep in potential_entry_points:
            if (repo_root / ep).exists():
                entry_points.append(ep)

        # Check for tests directory
        if (repo_root / "tests").exists() or (repo_root / "test").exists():
            if not test_frameworks and "Python" in languages:
                test_frameworks.add("pytest/unittest")

        # Inspect Git branch & status
        git_branch = "unknown"
        git_clean = True
        try:
            b_res = subprocess.run(["git", "branch", "--show-current"], cwd=str(repo_root), capture_output=True, text=True, timeout=5)
            if b_res.returncode == 0 and b_res.stdout.strip():
                git_branch = b_res.stdout.strip()
            s_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo_root), capture_output=True, text=True, timeout=5)
            git_clean = len(s_res.stdout.strip()) == 0
        except Exception:
            pass

        # Read README snippet if available
        readme_summary = ""
        for r_name in ["README.md", "readme.md", "README.txt", "README"]:
            r_path = repo_root / r_name
            if r_path.exists():
                try:
                    lines = r_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    readme_summary = "\n".join(lines[:15]).strip()
                    break
                except Exception:
                    pass

        return {
            "repository": repo_name,
            "absolute_path": str(repo_root),
            "languages": sorted(list(languages)),
            "frameworks": sorted(list(frameworks)),
            "package_managers": sorted(list(package_managers)),
            "test_frameworks": sorted(list(test_frameworks)),
            "entry_points": entry_points,
            "configuration_files": config_files,
            "git": {
                "branch": git_branch,
                "clean_working_tree": git_clean
            },
            "readme_preview": readme_summary
        }
    except Exception as e:
        return {"error": str(e)}
