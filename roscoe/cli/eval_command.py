"""``roscoe eval`` — run an eval suite from the terminal.

Builds an agent from a config, runs a dataset through it, and prints a scored report.
The deterministic tool-usage scorer always runs; add ``--judge`` to also run the
LLM-as-judge output-quality scorer (uses the config's model as the judge).

Custom tools live in Python, so point ``--tools`` at a ``module:attribute`` that resolves
to a list of tools (e.g. ``tools.my_tools:TOOLS``).
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import click

from roscoe.core.agent_runner import AgentRunner
from roscoe.evals import EvalRunner, load_dataset, render_report
from roscoe.evals.scorers import OutputQualityScorer, ToolUsageScorer
from roscoe.llm.provider_factory import ProviderFactory


def _load_tools(tools_ref: str | None) -> list[Any]:
    """Resolve a ``module:attribute`` reference to a list of tools."""
    if not tools_ref:
        return []
    if ":" not in tools_ref:
        raise ValueError("--tools must be 'module:attribute', e.g. tools.my_tools:TOOLS")
    import sys
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    module_name, attr = tools_ref.split(":", 1)
    module = importlib.import_module(module_name)
    tools = getattr(module, attr)
    if callable(tools):  # a build_tools-style factory taking no args
        tools = tools()
    return list(tools)


def run_eval(
    dataset_path: str | Path,
    config_path: str | Path,
    *,
    tools_ref: str | None = None,
    use_judge: bool = False,
    pass_threshold: float = 0.7,
):
    """Run the eval suite and return an EvalReport."""
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
    cases = load_dataset(dataset_path)
    tools = _load_tools(tools_ref)
    agent = AgentRunner.from_config(config_path, tools=tools)

    scorers: list[Any] = [ToolUsageScorer()]
    if use_judge:
        from roscoe.config.loader import load_config

        judge = ProviderFactory.get_llm(load_config(config_path)["model"])
        scorers.append(OutputQualityScorer(judge))

    return EvalRunner(agent, scorers, pass_threshold=pass_threshold).run(cases)


@click.command("eval")
@click.option("--dataset", required=True, help="Path to the test_cases.json dataset.")
@click.option("--config", required=True, help="Path to the agent config YAML.")
@click.option("--tools", "tools_ref", default=None, help="module:attribute resolving to a tool list.")
@click.option("--judge/--no-judge", default=False, help="Also run the LLM output-quality scorer.")
@click.option("--threshold", default=0.7, show_default=True, help="Pass threshold for the overall score.")
def eval_command(dataset: str, config: str, tools_ref: str | None, judge: bool, threshold: float) -> None:
    """Run an eval suite against an agent config and print a scored report."""
    try:
        report = run_eval(
            dataset, config, tools_ref=tools_ref, use_judge=judge, pass_threshold=threshold
        )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(render_report(report))
    if not report.passed:
        raise SystemExit(1)
