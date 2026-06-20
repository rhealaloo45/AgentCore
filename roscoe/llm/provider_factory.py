"""ProviderFactory — turns a config ``model:`` block into a LangChain chat model.

Phase 1 ships **Azure OpenAI only**. Phase 2 generalizes this into the full
provider abstraction (OpenAI, Gemini, Anthropic, Ollama, custom ``register()``).
The public surface — ``ProviderFactory.get_llm(config)`` — stays stable across that
change, so nothing downstream needs to move.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

_BUILTINS = ("azure_openai",)


class ProviderFactory:
    """Resolves a ``model:`` config block to a ``BaseChatModel``."""

    @classmethod
    def get_llm(cls, config: dict[str, Any]) -> BaseChatModel:
        """Build a chat model from the config's ``model`` block.

        Args:
            config: The ``model:`` mapping from agent_config.yaml. Must contain a
                ``provider`` key.

        Raises:
            ValueError: If ``provider`` is missing or not supported in this phase.
        """
        provider = config.get("provider")
        if not provider:
            raise ValueError("model config is missing required key 'provider'.")

        if provider == "azure_openai":
            return cls._azure_openai(config)

        raise ValueError(
            f"Unknown provider '{provider}'. Built-in providers: {', '.join(_BUILTINS)}. "
            f"(More providers + ProviderFactory.register() arrive in Phase 2.)"
        )

    @staticmethod
    def _azure_openai(config: dict[str, Any]) -> BaseChatModel:
        from langchain_openai import AzureChatOpenAI

        missing = [k for k in ("deployment", "endpoint", "api_key") if not config.get(k)]
        if missing:
            raise ValueError(
                f"azure_openai config missing required keys: {', '.join(missing)}."
            )

        return AzureChatOpenAI(
            azure_deployment=config["deployment"],
            azure_endpoint=config["endpoint"],
            api_key=config["api_key"],
            api_version=config.get("api_version", "2024-06-01"),
            temperature=config.get("temperature", 0.1),
            max_tokens=config.get("max_tokens"),
        )
