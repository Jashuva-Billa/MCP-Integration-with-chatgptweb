import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.session import session_manager
from app.core.security import security_engine

def list_functions(file_path: str) -> Dict[str, Any]:
    """
    List all functions and methods defined in a source file, including argument signatures and line numbers.
    Uses AST parser for Python and regex pattern matching for JavaScript/TypeScript/other languages.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(file_path)
        if not resolved.is_file():
            return {"error": f"File '{file_path}' not found."}

        content = resolved.read_text(encoding="utf-8", errors="replace")
        functions = []

        if resolved.suffix.lower() == ".py":
            try:
                tree = ast.parse(content, filename=str(resolved))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args]
                        functions.append({
                            "name": node.name,
                            "type": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                            "line": node.lineno,
                            "args": args,
                            "docstring": ast.get_docstring(node) or ""
                        })
            except Exception as pe:
                return {"error": f"Failed to parse Python AST: {pe}"}
        else:
            # Generic regex parser for JS/TS/Go/Rust
            patterns = [
                r"(?:function\s+([a-zA-Z0-9_$]+)\s*\((.*?)\))",
                r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>",
                r"(?:def|fn|func)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)"
            ]
            for idx, line in enumerate(content.splitlines(), start=1):
                for pat in patterns:
                    m = re.search(pat, line)
                    if m:
                        name = m.group(1)
                        params = m.group(2).strip() if len(m.groups()) > 1 and m.group(2) else ""
                        functions.append({
                            "name": name,
                            "line": idx,
                            "args": [p.strip() for p in params.split(",") if p.strip()],
                            "snippet": line.strip()
                        })
                        break

        repo_root = session_manager.get_active_repo_path()
        return {
            "file": str(resolved.relative_to(repo_root)).replace("\\", "/"),
            "total_functions": len(functions),
            "functions": functions
        }
    except Exception as e:
        return {"error": str(e)}

def list_classes(file_path: str) -> Dict[str, Any]:
    """
    List all classes defined in a source file, including base classes, methods, and line numbers.
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(file_path)
        if not resolved.is_file():
            return {"error": f"File '{file_path}' not found."}

        content = resolved.read_text(encoding="utf-8", errors="replace")
        classes = []

        if resolved.suffix.lower() == ".py":
            try:
                tree = ast.parse(content, filename=str(resolved))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        bases = [b.id if isinstance(b, ast.Name) else getattr(b, 'attr', 'Base') for b in node.bases]
                        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        classes.append({
                            "name": node.name,
                            "line": node.lineno,
                            "bases": bases,
                            "methods": methods,
                            "docstring": ast.get_docstring(node) or ""
                        })
            except Exception as pe:
                return {"error": f"Failed to parse Python AST: {pe}"}
        else:
            patterns = [
                r"class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?",
                r"struct\s+([a-zA-Z0-9_]+)",
                r"type\s+([a-zA-Z0-9_]+)\s+struct"
            ]
            for idx, line in enumerate(content.splitlines(), start=1):
                for pat in patterns:
                    m = re.search(pat, line)
                    if m:
                        name = m.group(1)
                        base = m.group(2) if len(m.groups()) > 1 and m.group(2) else ""
                        classes.append({
                            "name": name,
                            "line": idx,
                            "bases": [base] if base else [],
                            "snippet": line.strip()
                        })
                        break

        repo_root = session_manager.get_active_repo_path()
        return {
            "file": str(resolved.relative_to(repo_root)).replace("\\", "/"),
            "total_classes": len(classes),
            "classes": classes
        }
    except Exception as e:
        return {"error": str(e)}

def get_file_structure(file_path: str) -> Dict[str, Any]:
    """
    Get a high-level summary of a file's code structure (imports, classes, methods, top-level functions).
    """
    try:
        resolved = security_engine.sanitize_and_resolve_path(file_path)
        if not resolved.is_file():
            return {"error": f"File '{file_path}' not found."}

        content = resolved.read_text(encoding="utf-8", errors="replace")
        imports = []
        functions = []
        classes = []

        if resolved.suffix.lower() == ".py":
            try:
                tree = ast.parse(content, filename=str(resolved))
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        names = [n.name for n in node.names]
                        imports.append(f"from {mod} import {', '.join(names)}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append({"name": node.name, "line": node.lineno})
                    elif isinstance(node, ast.ClassDef):
                        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        classes.append({"name": node.name, "line": node.lineno, "methods": methods})
            except Exception as pe:
                return {"error": f"AST parse error: {pe}"}
        else:
            # Fallback
            fn_res = list_functions(file_path)
            cls_res = list_classes(file_path)
            functions = fn_res.get("functions", [])
            classes = cls_res.get("classes", [])

        repo_root = session_manager.get_active_repo_path()
        return {
            "file": str(resolved.relative_to(repo_root)).replace("\\", "/"),
            "imports": imports,
            "classes": classes,
            "top_level_functions": functions,
            "total_lines": len(content.splitlines())
        }
    except Exception as e:
        return {"error": str(e)}

def find_symbol(name: str, path: str = ".") -> Dict[str, Any]:
    """
    Search for definition of a class, function, or symbol across the active repository.
    """
    try:
        from app.tools.search import search_code
        # Search for class or def/function declarations
        queries = [f"def {name}", f"class {name}", f"function {name}", f"const {name} =", f"type {name}"]
        found = []
        for q in queries:
            res = search_code(query=q, path=path, case_sensitive=True, max_results=20)
            for item in res.get("results", []):
                found.append({
                    "symbol": name,
                    "file": item["file"],
                    "line": item["line"],
                    "definition": item["match"],
                    "context": item.get("context", [])
                })
        return {
            "symbol": name,
            "total_definitions": len(found),
            "definitions": found
        }
    except Exception as e:
        return {"error": str(e)}

def find_references(symbol: str, path: str = ".") -> Dict[str, Any]:
    """
    Find occurrences and references of a symbol across the active repository.
    """
    from app.tools.search import search_code
    return search_code(query=symbol, path=path, case_sensitive=True, max_results=50)
