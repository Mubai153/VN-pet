from __future__ import annotations

import asyncio
import json
import re
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
    ReasoningTokenLimitExceeded,
    ToolCallStreamAggregator,
    ToolsNotSupportedError,
    is_tools_not_supported_error,
    parse_message_tool_calls,
    build_deepseek_user_text,
    ModelImagePayload,
    insert_current_user_message,
    is_context_window_error,
    require_real_api_key,
    require_text_config,
)


CONNECT_RETRY_DELAY_SECONDS = 0.5
UPSTREAM_ERROR_MESSAGE_LIMIT = 240
_API_KEY_PATTERN = re.compile(r"(?i)\b(?:bearer\s+)?sk-[a-z0-9_-]{8,}\b")
DEEPSEEK_REASONING_EFFORTS = {"low", "high", "max"}


def _apply_generation_parameters(payload: dict[str, Any], config: dict[str, Any]) -> None:
    thinking_enabled = config.get("thinking_enabled", True) is not False
    payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}
    if thinking_enabled:
        effort = str(config.get("reasoning_effort") or "high").strip().lower()
        payload["reasoning_effort"] = effort if effort in DEEPSEEK_REASONING_EFFORTS else "high"
        return
    payload["temperature"] = config.get("temperature", 0.9)
    if "top_p" in config:
        payload["top_p"] = config.get("top_p")


def _assistant_history_message(message: dict[str, Any], content: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "role": "assistant",
        "content": content or None,
        "tool_calls": message.get("tool_calls"),
    }
    if message.get("reasoning_content") is not None:
        entry["reasoning_content"] = str(message.get("reasoning_content") or "")
    return entry


def _safe_upstream_error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    cleaned = " ".join(message.split())
    cleaned = _API_KEY_PATTERN.sub("[已隐藏敏感信息]", cleaned)
    return cleaned[:UPSTREAM_ERROR_MESSAGE_LIMIT]


def _upstream_http_exception(status_code: int, body: str) -> HTTPException:
    upstream_message = _safe_upstream_error_message(body)
    if status_code in {400, 404}:
        local_status = 400
        detail = "DeepSeek 请求配置或模型不受支持"
    elif status_code in {401, 403}:
        local_status = status_code
        detail = "DeepSeek API 密钥无效或无权限"
    elif status_code == 429:
        local_status = 429
        detail = "DeepSeek 请求受限，请检查频率、余额或额度"
    elif status_code >= 500:
        local_status = 502
        detail = f"DeepSeek 服务暂时异常（HTTP {status_code}），请稍后再试"
    else:
        local_status = 502
        detail = f"DeepSeek 请求失败（HTTP {status_code}）"
    if upstream_message:
        detail = f"{detail}：{upstream_message}"
    return HTTPException(status_code=local_status, detail=detail)


async def _post_with_connect_retry(
    client: httpx.AsyncClient,
    api_url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> httpx.Response:
    for attempt in range(2):
        try:
            return await client.post(api_url, json=payload, headers=headers)
        except httpx.ConnectError:
            if attempt == 1:
                raise
            await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS)
    raise RuntimeError("unreachable")


class DeepSeekProvider(LLMProvider):
    provider_id = "deepseek"

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        require_real_api_key(config, "deepseek")
        require_text_config(config, "api_url", "deepseek")
        require_text_config(config, "model", "deepseek")

    async def chat_result(
        self,
        text: str,
        history: list[dict],
        attachments: list[dict[str, Any]] | None = None,
        runtime_context: str = "",
        tools: list[dict] | None = None,
    ) -> LLMCallResult:
        api_key = str(self.config.get("api_key", "") or "").strip()
        if not api_key or api_key.startswith("YOUR_"):
            raise HTTPException(
                status_code=503,
                detail="尚未配置 DeepSeek API 密钥，请在设置页填写并保存模型配置",
            )

        api_url = str(self.config.get("api_url", "") or "").strip()
        if not api_url:
            raise HTTPException(
                status_code=503,
                detail="尚未配置 DeepSeek API 地址，请在设置页填写并保存模型配置",
            )

        messages = [{"role": "system", "content": self.system_prompt()}]
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "tool":
                # DeepSeek has no vision; keep the tool result as text metadata.
                messages.append({
                    "role": "tool",
                    "tool_call_id": str(msg.get("tool_call_id") or ""),
                    "content": content.public_text if isinstance(content, ModelImagePayload) else str(content or ""),
                })
                continue
            if role == "assistant" and msg.get("tool_calls"):
                messages.append(_assistant_history_message(msg, content))
                continue
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        user_text = build_deepseek_user_text(text, attachments or [])
        if runtime_context.strip():
            user_text = f"{runtime_context.strip()}\n\n[当前用户消息]\n{user_text}"
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 8192),
        }
        _apply_generation_parameters(payload, self.config)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await _post_with_connect_retry(
                    client,
                    api_url,
                    payload=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.exception("DeepSeek API request timed out")
            raise HTTPException(status_code=502, detail="DeepSeek 连接超时，请检查网络或稍后再试") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.exception("DeepSeek API request failed")
            raise HTTPException(status_code=502, detail="DeepSeek 连接失败，请检查网络或代理设置") from exc

        if resp.status_code != 200:
            safe_message = _safe_upstream_error_message(resp.text)
            if self.logger:
                self.logger.error(
                    "DeepSeek API returned %s: %s",
                    resp.status_code,
                    safe_message or "no safe upstream detail",
                )
            if is_context_window_error(resp.status_code, resp.text):
                raise ContextWindowExceeded()
            if tools and is_tools_not_supported_error(resp.status_code, resp.text):
                raise ToolsNotSupportedError()
            raise _upstream_http_exception(resp.status_code, resp.text)

        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]
        reply = str(message.get("content") or "").strip()
        reasoning_content = message.get("reasoning_content")
        reasoning_content = str(reasoning_content) if reasoning_content is not None else None
        finish_reason = str(choice.get("finish_reason") or "") or None
        tool_calls = parse_message_tool_calls(message)
        if not reply and not tool_calls:
            if reasoning_content and finish_reason == "length":
                raise ReasoningTokenLimitExceeded()
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
            reasoning_content=reasoning_content,
            finish_reason=finish_reason,
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
        api_key = str(self.config.get("api_key", "") or "").strip()
        if not api_key or api_key.startswith("YOUR_"):
            raise HTTPException(status_code=503, detail="\u5c1a\u672a\u914d\u7f6e DeepSeek API \u5bc6\u94a5")
        api_url = str(self.config.get("api_url", "") or "").strip()
        if not api_url:
            raise HTTPException(status_code=503, detail="\u5c1a\u672a\u914d\u7f6e DeepSeek API \u5730\u5740")

        user_text = build_deepseek_user_text(text, attachments or [])
        if runtime_context.strip():
            user_text = f"{runtime_context.strip()}\n\n[\u5f53\u524d\u7528\u6237\u6d88\u606f]\n{user_text}"
        current_user_message = {"role": "user", "content": user_text}

        messages = [{"role": "system", "content": self.system_prompt()}]
        for message in insert_current_user_message(
            history,
            current_user_message,
            current_user_message_index,
        ):
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool":
                # DeepSeek has no vision; keep the tool result as text metadata.
                messages.append({
                    "role": "tool",
                    "tool_call_id": str(message.get("tool_call_id") or ""),
                    "content": content.public_text if isinstance(content, ModelImagePayload) else str(content or ""),
                })
                continue
            if role == "user" and isinstance(content, ModelImagePayload):
                content = content.public_text
            if role == "assistant" and message.get("tool_calls"):
                messages.append(_assistant_history_message(message, content))
                continue
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        payload = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config.get("max_tokens", 8192),
            "stream": True,
        }
        _apply_generation_parameters(payload, self.config)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        chunks: list[str] = []
        reasoning_chunks: list[str] = []
        usage: dict[str, Any] = {}
        model = str(self.config.get("model") or "")
        finish_reason: str | None = None
        tool_aggregator = ToolCallStreamAggregator()
        try:
            timeout = httpx.Timeout(60.0, read=None)
            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(2):
                    response_started = False
                    try:
                        async with client.stream("POST", api_url, json=payload, headers=headers) as response:
                            response_started = True
                            if response.status_code != 200:
                                body = (await response.aread()).decode("utf-8", errors="replace")
                                if is_context_window_error(response.status_code, body):
                                    raise ContextWindowExceeded()
                                safe_message = _safe_upstream_error_message(body)
                                if self.logger:
                                    self.logger.error(
                                        "DeepSeek stream returned %s: %s",
                                        response.status_code,
                                        safe_message or "no safe upstream detail",
                                    )
                                if tools and is_tools_not_supported_error(response.status_code, body):
                                    raise ToolsNotSupportedError()
                                raise _upstream_http_exception(response.status_code, body)
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
                                choice = choices[0] if isinstance(choices[0], dict) else {}
                                if choice.get("finish_reason") is not None:
                                    finish_reason = str(choice.get("finish_reason") or "") or None
                                delta = choice.get("delta")
                                if isinstance(delta, dict):
                                    tool_aggregator.feed(delta.get("tool_calls"))
                                reasoning_delta = delta.get("reasoning_content") if isinstance(delta, dict) else ""
                                if isinstance(reasoning_delta, str) and reasoning_delta:
                                    reasoning_chunks.append(reasoning_delta)
                                    yield LLMStreamChunk(reasoning_delta=reasoning_delta)
                                content = delta.get("content") if isinstance(delta, dict) else ""
                                if isinstance(content, str) and content:
                                    chunks.append(content)
                                    yield LLMStreamChunk(delta=content)
                        break
                    except httpx.ConnectError:
                        if response_started or attempt == 1:
                            raise
                        await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS)
        except httpx.TimeoutException as exc:
            if self.logger:
                self.logger.exception("DeepSeek stream timed out")
            raise HTTPException(status_code=502, detail="DeepSeek \u8fde\u63a5\u8d85\u65f6") from exc
        except httpx.RequestError as exc:
            if self.logger:
                self.logger.exception("DeepSeek stream request failed")
            raise HTTPException(status_code=502, detail="DeepSeek \u8fde\u63a5\u5931\u8d25") from exc

        reply = "".join(chunks).strip()
        reasoning_content = "".join(reasoning_chunks)
        tool_calls = tool_aggregator.tool_calls()
        if not reply and not tool_calls:
            if reasoning_content and finish_reason == "length":
                raise ReasoningTokenLimitExceeded()
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
            reasoning_content=reasoning_content or None,
            finish_reason=finish_reason,
        ))
