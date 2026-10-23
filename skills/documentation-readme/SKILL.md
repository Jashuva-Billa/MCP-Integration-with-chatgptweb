---
name: documentation-readme
description: Documentation writing, README maintenance, and API documentation workflow
version: 1.0.0
activation: ["README.md", "docs/", "*.md"]
tags: [documentation, readme, docstrings, sphinx, mkdocs]
requires_profile: full
---

# Documentation and README Skill

## README Structure
1. **Title and badge line** (CI status, coverage, license).
2. **One-sentence description** of what the project does.
3. **Quick start** (3-5 commands to get running).
4. **Features** list.
5. **Configuration** reference.
6. **API** overview or link to full docs.
7. **Contributing** guide.
8. **License**.

## Docstrings (Python)
```python
def function(param: type) -> return_type:
    """One-line summary.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is invalid.
    """
```

## Generating Docs
1. Sphinx: `run_command("sphinx-apidoc -o docs/ app/")`
2. MkDocs: `run_command("mkdocs build")`
