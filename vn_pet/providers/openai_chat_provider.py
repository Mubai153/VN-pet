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
    ToolCallStreamAggregator,
    ToolsNotSupportedError,
    build_vision_content_parts,
    is_tools_not_supported_error,
    parse_message_tool_calls,
    build_deepseek_user_text,
    extract_attachment_text,
    has_real_model_api_key,
    insert_current_user_message,
    is_image_attachment,
    is_context_window_error,
    require_text_config,
)
from .registry import is_vision_supported, require_provider_spec


class OpenAIChatCompletionsProvider(LLMProvider):
    provider_id = "openai_chat"

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        provider_id = str(config.get("provider_id") or cls.provider_id)
        spec = require_provider_spec(provider_id)
        if provider_id == "deepseek":
            require_text_config(config, "api_url", spec.label)
        else:
            require_text_config(config, "base_url", spec.label)
        require_text_config(config, "model", spec.label)
        if spec.requires_api_key and not has_real_model_api_key(config.get("api_key", "")):
            raise ValueError(f"missing {spec.label} api_key")

    def _api_url(self) -> str:
        if str(self.config.get("api_url", "") or "").strip():
            return str(self.config.get("api_url", "") or "").strip()
        base_url = str(self.config.get("base_url", "") or "").strip().rstrip("/")
        if not base_url:
            raise HTTPException(status_code=503, detail="尚未配置模型 API 地址，请在设置页填写并保存模型配置")
        return f"{base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = str(self.config.get("api_key", "") or "").strip()
        if has_real_model_api_key(api_key):
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _request_timeout(self) -> float:
        """Return the provider-specific request timeout, bounded for safety."""
        spec = require_provider_spec(str(self.config.get("provider_id") or self.provider_id))
        try:
            timeout = float(spec.request_timeout_s)
        except (TypeError, ValueError):
            timeout = 60.0
        return max(1.0, min(timeout, 3600.0))

    def _apply_generation_parameters(self, payload: dict[str, Any], provider_id: str) -> None:
        if provider_id == "kimi_codeplan":
            model = str(self.config.get("model") or "").lower()
            reasoning_effort = str(self.config.get("reasoning_effort") or "").strip()
            if model.startswith("k3") and reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
            return
        payload["temperature"] = self.config.get("temperature", 0.8)
        if "top_p" in self.config:
            payload["top_p"] = self.config.get("top_p")
        if provider_id in {"stepfun", "stepfun_tokenplan", "gemini", "grok"}:
            reasoning_effort = str(self.config.get("reasoning_effort") or "").strip()
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort

    async def chat_result(
        self,
        text: str,
        history: list[dict],
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: str = "",
        tools: list[dict] | None = None,
    ) -> LLMCallResult:
        provider_id = str(self.config.get("provider_id") or self.provider_id)
        spec = require_provider_spec(provider_id)
        api_key = str(self.config.get("api_key", "") or "").strip()
        if spec.requires_api_key and not has_real_model_api_key(api_key):
            raise HTTPException(
                status_code=503,
                detail=f"尚未配置 {spec.label} API Key，请在设置页填写并保存模型配置",
            )

        attachments = attachments or []
        has_image = any(is_image_attachment(item) for item in attachments)
        supports_vision = is_vision_supported(provider_id, self.config)
        if has_image and not supports_vision:
            raise HTTPException(status_code=400, detail="图片需要切换到支持视觉的模型才能读取")

        messages = [{"role": "system", "content": self.system_prompt()}]
        supports_vision = is_vision_supported(provider_id, self.config)
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "tool":
                # Trusted screenshot results may carry a host-internal image
                # payload. Vision models receive image_url parts; non-vision
                # models receive only the public attachment metadata text.
                messages.append({
                    "role": "tool",
                    "tool_call_id": str(msg.get("tool_call_id") or ""),
                    "content": build_vision_content_parts(content, supports_vision=supports_vision),
                })
                continue
            if role == "user":
                content = build_vision_content_parts(content, supports_vision=supports_vision)
            if role == "assistant" and msg.get("tool_calls"):
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": msg.get("tool_calls"),
                })
                continue
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        if has_image:
            text_sections = [
                f"{runtime_context.strip()}\n\n[当前用户消息]\n{text}"
                if runtime_context.strip() else text
            ]
            image_parts: list[dict[str, Any]] = []
            for attachment in attachments:
                if is_image_attachment(attachment):
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{attachment['mime_type']};base64,{attachment['data_base64']}",
                        },
                    })
                else:
                    content = extract_attachment_text(attachment) or "[未提取到可读文本]"
                    text_sections.append(f"\n\n[附件: {attachment['name']}]\n{content[:60000]}")
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": "".join(text_sections)}, *image_parts],
            })
        else:
            user_text = build_deepseek_user_text(text, attachments)
            if runtime_context.strip():
                user_text = f"{runtime_context.strip()}\n\n[当前用户消息]\n{user_text}"
            messages.append({"role": "user", "content": user_text})

        payload: dict[str, Any] = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 512),
        }
        self._apply_generation_parameters(payload, provider_id)
        native_tools = bool(tools and spec.supports_native_tools)
        if native_tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self._request_timeout()) as client:
                resp = await client.post(self._api_url(), json=payload, headers=self._headers())
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.exception("%s API request timed out", provider_id)
            raise HTTPException(status_code=502, detail="大语言模型连接超时，请检查网络或稍后再试") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.exception("%s API request failed", provider_id)
            raise HTTPException(status_code=502, detail="大语言模型连接失败，请检查网络或代理设置") from exc

        if resp.status_code != 200:
            if self.logger:
                self.logger.error("%s API returned %s: %s", provider_id, resp.status_code, resp.text[:300])
            if native_tools and is_tools_not_supported_error(resp.status_code, resp.text):
                raise ToolsNotSupportedError()
            if is_context_window_error(resp.status_code, resp.text):
                raise ContextWindowExceeded()
            raise HTTPException(status_code=502, detail="大语言模型服务异常，请稍后再试")

        try:
            data = resp.json()
            message = data["choices"][0]["message"]
            reply = str(message.get("content") or "").strip()
            tool_calls = parse_message_tool_calls(message)
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise HTTPException(status_code=502, detail="大语言模型没有返回有效文本") from exc
        if not reply and not tool_calls:
            raise EmptyModelResponse()
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        return LLMCallResult(
            text=reply,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
            model=str(data.get("model") or self.config.get("model") or ""),
            usage_estimated=not bool(prompt_tokens),
            tool_calls=tool_calls or None,
        )

    async def stream_result(
        self,
        text: str,
        history: list[dict],
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: str = "",
        tools: list[dict] | None = None,
        current_user_message_index: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        provider_id = str(self.config.get("provider_id") or self.provider_id)
        spec = require_provider_spec(provider_id)
        api_key = str(self.config.get("api_key", "") or "").strip()
        if spec.requires_api_key and not has_real_model_api_key(api_key):
            raise HTTPException(status_code=503, detail=f"\u5c1a\u672a\u914d\u7f6e {spec.label} API Key")

        attachments = attachments or []
        has_image = any(is_image_attachment(item) for item in attachments)
        if has_image and not is_vision_supported(provider_id, self.config):
            raise HTTPException(status_code=400, detail="\u5f53\u524d\u6a21\u578b\u4e0d\u652f\u6301\u56fe\u7247\u8f93\u5165")
        if has_image:
            text_sections = [
                f"{runtime_context.strip()}\n\n[\u5f53\u524d\u7528\u6237\u6d88\u606f]\n{text}"
                if runtime_context.strip() else text
            ]
            image_parts: list[dict[str, Any]] = []
            for attachment in attachments:
                if is_image_attachment(attachment):
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{attachment['mime_type']};base64,{attachment['data_base64']}"},
                    })
                else:
                    attachment_content = extract_attachment_text(attachment) or "[No readable text extracted]"
                    text_sections.append(f"\n\n[Attachment: {attachment['name']}]\n{attachment_content[:60000]}")
            current_user_message = {
                "role": "user",
                "content": [{"type": "text", "text": "".join(text_sections)}, *image_parts],
            }
        else:
            user_text = build_deepseek_user_text(text, attachments)
            if runtime_context.strip():
                user_text = f"{runtime_context.strip()}\n\n[\u5f53\u524d\u7528\u6237\u6d88\u606f]\n{user_text}"
            current_user_message = {"role": "user", "content": user_text}

        messages = [{"role": "system", "content": self.system_prompt()}]
        supports_vision = is_vision_supported(provider_id, self.config)
        for message in insert_current_user_message(
            history,
            current_user_message,
            current_user_message_index,
        ):
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": str(message.get("tool_call_id") or ""),
                    "content": build_vision_content_parts(content, supports_vision=supports_vision),
                })
                continue
            if role == "user":
                content = build_vision_content_parts(content, supports_vision=supports_vision)
            if role == "assistant" and message.get("tool_calls"):
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": message.get("tool_calls"),
                })
                continue
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        payload: dict[str, Any] = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 512),
            "stream": True,
        }
        self._apply_generation_parameters(payload, provider_id)
        native_tools = bool(tools and spec.supports_native_tools)
        if native_tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {**self._headers(), "Accept": "text/event-stream"}
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        model = str(self.config.get("model") or "")
        tool_aggregator = ToolCallStreamAggregator()
        try:
            timeout = httpx.Timeout(self._request_timeout(), read=None)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", self._api_url(), json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        if native_tools and is_tools_not_supported_error(response.status_code, body):
                            raise ToolsNotSupportedError()
                        if is_context_window_error(response.status_code, body):
                            raise ContextWindowExceeded()
                        if self.logger:
                            self.logger.error("%s stream returned %s: %s", provider_id, response.status_code, body[:300])
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
                        if isinstance(event.get("usage"), dict):
                            usage = event["usage"]
                        model = str(event.get("model") or model)
                        choices = event.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                        if isinstance(delta, dict):
                            tool_aggregator.feed(delta.get("tool_calls"))
                        content = delta.get("content") if isinstance(delta, dict) else ""
                        if isinstance(content, str) and content:
                            chunks.append(content)
                            yield LLMStreamChunk(delta=content)
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=502, detail="\u5927\u8bed\u8a00\u6a21\u578b\u8fde\u63a5\u8d85\u65f6") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="\u5927\u8bed\u8a00\u6a21\u578b\u8fde\u63a5\u5931\u8d25") from exc

        reply = "".join(chunks).strip()
        tool_calls = tool_aggregator.tool_calls()
        if not reply and not tool_calls:
            raise EmptyModelResponse()
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        yield LLMStreamChunk(result=LLMCallResult(
            text=reply,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
            model=model,
            usage_estimated=not bool(prompt_tokens),
            tool_calls=tool_calls or None,
        ))
