from __future__ import annotations

from typing import Any

from .base import LLMProvider, SystemPromptProvider
from .deepseek_provider import DeepSeekProvider
from .openai_chat_provider import OpenAIChatCompletionsProvider
from .openai_responses_provider import OpenAIResponsesProvider
from .registry import require_provider_spec


class LLMProviderFactory:
    _providers: dict[str, type[LLMProvider]] = {
        DeepSeekProvider.provider_id: DeepSeekProvider,
        OpenAIResponsesProvider.provider_id: OpenAIResponsesProvider,
        "openai_responses": OpenAIResponsesProvider,
        "openrouter": OpenAIChatCompletionsProvider,
        "claude": OpenAIChatCompletionsProvider,
        "stepfun": OpenAIChatCompletionsProvider,
        "stepfun_tokenplan": OpenAIChatCompletionsProvider,
        "longcat": OpenAIChatCompletionsProvider,
        "longcat_tokenplan": OpenAIChatCompletionsProvider,
        "hunyuan": OpenAIChatCompletionsProvider,
        "hunyuan_tokenplan": OpenAIChatCompletionsProvider,
        "gemini": OpenAIChatCompletionsProvider,
        "grok": OpenAIChatCompletionsProvider,
        "qwen": OpenAIChatCompletionsProvider,
        "qwen_codingplan": OpenAIChatCompletionsProvider,
        "qwen_tokenplan": OpenAIChatCompletionsProvider,
        "kimi": OpenAIChatCompletionsProvider,
        "kimi_codeplan": OpenAIChatCompletionsProvider,
        "glm": OpenAIChatCompletionsProvider,
        "glm_codingplan": OpenAIChatCompletionsProvider,
        "mimo": OpenAIChatCompletionsProvider,
        "mimo_tokenplan": OpenAIChatCompletionsProvider,
        "doubao": OpenAIChatCompletionsProvider,
        "doubao_codingplan": OpenAIChatCompletionsProvider,
        "minimax": OpenAIChatCompletionsProvider,
        "minimax_tokenplan": OpenAIChatCompletionsProvider,
        "custom": OpenAIChatCompletionsProvider,
        "local": OpenAIChatCompletionsProvider,
    }

    @classmethod
    def create(
        cls,
        provider_id: str,
        config: dict[str, Any],
        *,
        system_prompt_provider: SystemPromptProvider | None = None,
        logger: Any = None,
    ) -> LLMProvider:
        provider_cls = cls._providers.get(provider_id)
        if provider_cls is None:
            raise ValueError(f"Unsupported LLM provider: {provider_id}")
        config = dict(config or {})
        config.setdefault("provider_id", provider_id)
        return provider_cls(
            config,
            system_prompt_provider=system_prompt_provider,
            logger=logger,
        )

    @classmethod
    def validate_config(cls, provider_id: str, config: dict[str, Any]) -> None:
        provider_cls = cls._providers.get(provider_id)
        if provider_cls is None:
            raise ValueError(f"Unsupported LLM provider: {provider_id}")
        normalized = dict(config or {})
        normalized.setdefault("provider_id", provider_id)
        if provider_id in {
            "openrouter", "claude", "stepfun", "stepfun_tokenplan", "longcat",
            "longcat_tokenplan", "hunyuan", "hunyuan_tokenplan", "gemini", "grok",
            "qwen", "qwen_codingplan", "qwen_tokenplan",
            "kimi", "kimi_codeplan", "glm", "glm_codingplan", "mimo",
            "mimo_tokenplan", "doubao", "doubao_codingplan", "minimax",
            "minimax_tokenplan", "custom", "local",
        }:
            require_provider_spec(provider_id)
        provider_cls.validate_config(normalized)
