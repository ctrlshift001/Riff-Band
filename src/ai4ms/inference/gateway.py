from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from base.engine.async_llm import AsyncLLM, LLMsConfig


class InferenceUnavailableError(RuntimeError):
    """Raised when the configured model cannot complete a request."""


@dataclass(frozen=True)
class InferenceResponse:
    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class InferenceGateway(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse: ...


def configured_model_name() -> str:
    explicit = os.getenv("AI4MS_MODEL", "").strip()
    if explicit:
        return explicit
    configured = os.getenv("AUTOENV_OPENAI_MODELS", "").split(",")
    return next((item.strip() for item in configured if item.strip()), "")


def _configured_number(name: str, explicit: float | int | None, default: str, cast: type[float] | type[int]):
    raw: float | int | str = explicit if explicit is not None else os.getenv(name, default)
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise InferenceUnavailableError(f"Invalid {name} value: {raw!r}") from exc


def inference_status() -> dict[str, Any]:
    model = configured_model_name()
    if not model:
        return {"configured": False, "model": "", "reason": "AI4MS_MODEL or AUTOENV_OPENAI_MODELS is not set"}
    try:
        config = LLMsConfig.default().get(model)
    except (FileNotFoundError, ValueError) as exc:
        return {"configured": False, "model": model, "reason": str(exc)}
    return {
        "configured": bool(config.key and config.base_url),
        "model": model,
        "reason": "" if config.key and config.base_url else "model API key or base URL is missing",
    }


class OpenAICompatibleGateway:
    """Small product-facing wrapper around the legacy AsyncLLM transport."""

    def __init__(
        self,
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.model = (model or configured_model_name()).strip()
        if not self.model:
            raise InferenceUnavailableError("No model is configured for AI4MS stage generation")
        try:
            self.config = LLMsConfig.default().get(self.model)
        except (FileNotFoundError, ValueError) as exc:
            raise InferenceUnavailableError(str(exc)) from exc
        if not self.config.key or not self.config.base_url:
            raise InferenceUnavailableError(f"Model '{self.model}' is missing its API key or base URL")
        self.config.temperature = 0.2
        self.config.top_p = 0.9
        self.timeout_seconds = max(
            1.0,
            _configured_number("AI4MS_INFERENCE_TIMEOUT_SECONDS", timeout_seconds, "90", float),
        )
        self.max_attempts = max(
            1,
            _configured_number("AI4MS_INFERENCE_MAX_ATTEMPTS", max_attempts, "2", int),
        )
        self.max_tokens = max(
            256,
            _configured_number("AI4MS_INFERENCE_MAX_TOKENS", max_tokens, "4000", int),
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            llm = AsyncLLM(self.config, system_msg=system_prompt, max_completion_tokens=self.max_tokens)
            try:
                text = await asyncio.wait_for(llm(user_prompt), timeout=self.timeout_seconds)
                if not isinstance(text, str) or not text.strip():
                    raise RuntimeError("model returned an empty response")
                summary = llm.usage_tracker.get_summary()
                usage = {
                    "input_tokens": summary.get("total_input_tokens", 0),
                    "output_tokens": summary.get("total_output_tokens", 0),
                    "total_tokens": summary.get("total_tokens", 0),
                    "call_count": summary.get("call_count", 0),
                }
                return InferenceResponse(text=text.strip(), model=self.model, usage=usage)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts:
                    await asyncio.sleep(min(2**attempt, 4))

        reason = str(last_error or "unknown inference error")
        if self.config.key:
            reason = reason.replace(self.config.key, "***")
        raise InferenceUnavailableError(f"Model '{self.model}' request failed: {reason[:500]}") from last_error
