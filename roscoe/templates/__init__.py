"""Agent templates — pre-built configs + tools + prompts for common use cases.

Each template is a directory under this package containing ``agent_config.yaml``, a
``prompts/system.txt``, and a ``tools/`` module exposing ``build_tools(...)``. The Phase
10 CLI (``roscoe init <name> --template <t>``) copies a template directory into a new
project. ``available_templates`` / ``template_path`` are the lookup helpers it uses.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent

#: Templates shipped with roscoe v0.1.0.
AVAILABLE = [
    "hr_agent",
    "it_support_agent",
    "legal_agent",
    "knowledge_base_agent",
    "exec_assistant_agent",
]


def available_templates() -> list[str]:
    """Names of the templates that can be scaffolded."""
    return list(AVAILABLE)


def template_path(name: str) -> Path:
    """Filesystem path to a template directory. Raises ValueError if unknown."""
    if name not in AVAILABLE:
        raise ValueError(f"Unknown template '{name}'. Available: {', '.join(AVAILABLE)}.")
    return TEMPLATES_DIR / name
