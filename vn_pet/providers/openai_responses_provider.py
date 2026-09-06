from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException

from .base import (
    ContextWindowExceeded,
    EmptyModelResponse,
    LLMCallResult,
    LLMProvider,
    LLMStreamChunk,
    build_responses_input,
    extract_responses_text,
    is_context_window_error,
    require_real_api_key,
    require_text_config,
)


class OpenAIResponsesProvider(LLMProvider):
    provider_id = "gpt"

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        require_real_api_key(config, "gpt")
        require_text_config(config, "base_url", "gpt")
        require_text_config(config, "model", "gpt")

    async def chat_result(
        self,
        text: str,
        history: list[dict],
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: str = "",
    ) -> LLMCallResult:
        api_key = str(self.config.get("api_key", "") or "").strip()
        if not api_key or api_key.startswith("YOUR_"):
            raise HTTPException(
                status_code=503,
                detail="尚未配置 gpt API 密钥，请在设置页填写并保存模型配置",
            )

        base_url = str(self.config.get("base_url", "") or "").strip().rstrip("/")
        if not base_url:
            raise HTTPException(
                status_code=503,
                detail="尚未配置 gpt API 地址，请在设置页填写并保存模型配置",
            )

        payload = {
            "model": self.config["model"],
            "instructions": self.system_prompt(),
            "input": build_responses_input(
                text,
                history,
                attachments or [],
                runtime_context,
                supports_vision=self.config.get("supports_vision") is not False,
            ),
            "reasoning": {"effort": self.config.get("reasoning_effort", "high")},
            "max_output_tokens": self.config.get("max_output_tokens", 512),
            "store": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{base_url}/responses", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.exception("%s API request timed out", self.provider_id)
            raise HTTPException(status_code=502, detail="大语言模型连接超时，请检查网络或稍后再试") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.exception("%s API request failed", self.provider_id)
            raise HTTPException(status_code=502, detail="大语言模型连接失败，请检查网络或代理设置") from exc

        if resp.status_code != 200:
            if self.logger:
                self.logger.error("%s API returned %s: %s", self.provider_id, resp.status_code, resp.text[:300])
            if is_context_window_error(resp.status_code, resp.text):
                raise ContextWindowExceeded()
            raise HTTPException(status_code=502, detail="大语言模型服务异常，请稍后再试")

        data = resp.json()
        reply = extract_responses_text(data)
        if not reply:
            raise EmptyModelResponse()
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        return LLMCallResult(
            text=reply,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
            model=str(data.get("model") or self.config.get("model") or ""),
            usage_estimated=not bool(prompt_tokens),
        )

    async def stream_result(
        self,
        text: str,
        history: list[dict],
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: str = "",
        *,
        current_user_message_index: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        api_key = str(self.config.get("api_key", "") or "").strip()
        if not api_key or api_key.startswith("YOUR_"):
            raise HTTPException(status_code=503, detail="\u5c1a\u672a\u914d\u7f6e GPT API \u5bc6\u94a5")
        base_url = str(self.config.get("base_url", "") or "").strip().rstrip("/")
        if not base_url:
            raise HTTPException(status_code=503, detail="\u5c1a\u672a\u914d\u7f6e GPT API \u5730\u5740")

        payload = {
            "model": self.config["model"],
            "instructions": self.system_prompt(),
            "input": build_responses_input(
                text,
                history,
                attachments or [],
                runtime_context,
                current_user_message_index,
                supports_vision=self.config.get("supports_vision") is not False,
            ),
            "reasoning": {"effort": self.config.get("reasoning_effort", "high")},
            "max_output_tokens": self.config.get("max_output_tokens", 512),
            "store": False,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        model = str(self.config.get("model") or "")
        try:
            timeout = httpx.Timeout(60.0, read=None)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{base_url}/responses", json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        if is_context_window_error(response.status_code, body):
                            raise ContextWindowExceeded()
                        if self.logger:
                            self.logger.error("GPT stream returned %s: %s", response.status_code, body[:300])
                        raise HTTPException(status_code=502, detail="\u5927\u8bed\u8a00\u6a21\u578b\u6d41\u5f0f\u670d\u52a1\u5f02\u5e38")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            if raw == "[DONE]":
                                break
                            continue
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        event_type = str(event.get("type") or "")
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta")
                            if isinstance(delta, str) and delta:
                                chunks.append(delta)
                                yield LLMStreamChunk(delta=delta)
                        elif event_type in {"response.completed", "response.incomplete"}:
                            completed = event.get("response") if isinstance(event.get("response"), dict) else {}
                            if isinstance(completed.get("usage"), dict):
                                usage = completed["usage"]
                            model = str(completed.get("model") or model)
                        elif event_type in {"error", "response.failed"}:
                            error = event.get("error") if isinstance(event.get("error"), dict) else event
                            detail = str(error.get("message") or "\u5927\u8bed\u8a00\u6a21\u578b\u6d41\u5f0f\u54cd\u5e94\u5931\u8d25")
                            raise HTTPException(status_code=502, detail=detail)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=502, detail="\u5927\u8bed\u8a00\u6a21\u578b\u8fde\u63a5\u8d85\u65f6") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="\u5927\u8bed\u8a00\u6a21\u578b\u8fde\u63a5\u5931\u8d25") from exc

        reply = "".join(chunks).strip()
        if not reply:
            raise EmptyModelResponse()
        prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        yield LLMStreamChunk(result=LLMCallResult(
            text=reply,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
            model=model,
            usage_estimated=not bool(prompt_tokens),
        ))
