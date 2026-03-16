"""Unified LLM client abstraction over Claude, OpenAI, and local models."""

from __future__ import annotations

from dataclasses import dataclass

from research.config.settings import settings


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    """Unified interface for LLM providers."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ):
        self._provider = provider or settings.LLM_PROVIDER
        self._model = model or settings.LLM_MODEL

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a completion request to the configured LLM provider."""
        if self._provider == "anthropic":
            return self._call_anthropic(system, user, max_tokens, temperature)
        elif self._provider == "openai":
            return self._call_openai(system, user, max_tokens, temperature)
        elif self._provider == "local":
            return self._call_local(system, user, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {self._provider}")

    def _call_anthropic(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def _call_openai(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or self._model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def _call_local(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Call a local OpenAI-compatible API (Ollama, vLLM, etc.)."""
        import openai

        client = openai.OpenAI(
            base_url=settings.LLM_LOCAL_BASE_URL,
            api_key="local",
        )
        response = client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=self._model,
        )
