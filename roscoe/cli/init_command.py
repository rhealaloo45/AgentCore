"""``roscoe init`` — scaffold a new agent project.

Blank scaffold (default) copies ``cli/scaffold/`` and substitutes the project name.
``--template`` copies a pre-built template from ``roscoe.templates`` and adds the
project-level files a template doesn't carry (``main.py``, ``.env.example``,
``evals/test_cases.json``). No Jinja2 — a single ``__PROJECT_NAME__`` placeholder is
enough, keeping the dependency surface small.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from roscoe.templates import available_templates, template_path

SCAFFOLD_DIR = Path(__file__).parent / "scaffold"
PLACEHOLDER = "__PROJECT_NAME__"
_RENDER_SUFFIXES = {".yaml", ".yml", ".txt", ".py", ".md", ".json"}

# Per-template entry point: how to build that template's tools.
_TEMPLATE_MAIN = {
    "hr_agent": '''"""Entry point for the HR agent. Run: python main.py"""

from roscoe import AgentRunner
from roscoe.connectors import RESTConnector

from tools.hr_tools import build_tools

rest = RESTConnector(
    {"base_url": __import__("os").environ["HR_API_BASE_URL"], "auth": "bearer",
     "token": __import__("os").environ["HR_API_TOKEN"]}
)
agent = AgentRunner.from_config("agent_config.yaml", tools=build_tools(rest))

if __name__ == "__main__":
    print(agent.run("How many leave days does employee E1 have left?").output)
''',
    "it_support_agent": '''"""Entry point for the IT support agent. Run: python main.py"""

import os

from roscoe import AgentRunner
from roscoe.connectors import ServiceNowConnector

from tools.it_tools import build_tools

snow = ServiceNowConnector(
    {"instance_url": os.environ["SERVICENOW_INSTANCE_URL"],
     "username": os.environ["SERVICENOW_USERNAME"],
     "password": os.environ["SERVICENOW_PASSWORD"]}
)
agent = AgentRunner.from_config("agent_config.yaml", tools=build_tools(snow))

if __name__ == "__main__":
    print(agent.run("My laptop won't connect to wifi, please open a ticket.").output)
''',
    "legal_agent": '''"""Entry point for the legal agent. Run: python main.py"""

from roscoe import AgentRunner
from roscoe.memory.knowledge import KnowledgeMemory

from tools.legal_tools import build_tools

# Replace with your real contract texts (and embeddings for semantic search).
contracts = ["Limitation of liability: ... ", "Term and termination: ..."]
knowledge = KnowledgeMemory.from_texts(
    contracts, metadatas=[{"source": "contract.pdf"}, {"source": "contract.pdf"}]
)
agent = AgentRunner.from_config("agent_config.yaml", tools=build_tools(knowledge))

if __name__ == "__main__":
    print(agent.run("What does the liability clause say?").output)
''',
}

_TEMPLATE_ENV = {
    "hr_agent": "OPENAI_API_KEY=\nHR_API_BASE_URL=\nHR_API_TOKEN=\n",
    "it_support_agent": (
        "OPENAI_API_KEY=\nSERVICENOW_INSTANCE_URL=\n"
        "SERVICENOW_USERNAME=\nSERVICENOW_PASSWORD=\n"
    ),
    "legal_agent": "OPENAI_API_KEY=\n",
}

_EXAMPLE_CASES = {
    "cases": [
        {"id": "example-1", "input": "Replace with a real test input.", "expected_output": "..."}
    ]
}


def scaffold_project(name: str, *, template: str | None = None, dest_dir: str | Path = ".") -> Path:
    """Create a new project directory. Returns the path created."""
    dest = Path(dest_dir) / name
    if dest.exists():
        raise FileExistsError(f"Destination already exists: {dest}")

    if template:
        shutil.copytree(
            template_path(template), dest, ignore=shutil.ignore_patterns("__pycache__")
        )
        _add_template_extras(dest, template)
    else:
        shutil.copytree(SCAFFOLD_DIR, dest)

    _render_placeholders(dest, name)
    return dest


def _add_template_extras(dest: Path, template: str) -> None:
    (dest / "main.py").write_text(_TEMPLATE_MAIN[template])
    (dest / ".env.example").write_text(_TEMPLATE_ENV[template])
    evals_dir = dest / "evals"
    evals_dir.mkdir(exist_ok=True)
    (evals_dir / "test_cases.json").write_text(json.dumps(_EXAMPLE_CASES, indent=2))


def _render_placeholders(dest: Path, name: str) -> None:
    for p in dest.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in _RENDER_SUFFIXES and p.name != ".env.example":
            continue
        text = p.read_text()
        if PLACEHOLDER in text:
            p.write_text(text.replace(PLACEHOLDER, name))


@click.command("init")
@click.argument("project_name")
@click.option(
    "--template",
    type=click.Choice(available_templates()),
    default=None,
    help="Scaffold from a pre-built template instead of a blank project.",
)
def init_command(project_name: str, template: str | None) -> None:
    """Create a new roscoe agent project."""
    try:
        dest = scaffold_project(project_name, template=template)
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    kind = f"template '{template}'" if template else "blank project"
    click.echo(f"Created {kind} at {dest}/")
    click.echo("Next:")
    click.echo(f"  cd {dest}")
    click.echo("  cp .env.example .env   # fill in your keys")
    click.echo("  python main.py")
