from __future__ import annotations

import copy
import re
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .providers.factory import LLMProviderFactory
from .providers.registry import LLM_PROVIDER_SPECS, is_vision_supported
from .secrets import MASK, has_real_model_api_key


def safe_error(exc):
    """Never return provider response bodies, request URLs, prompts or credentials."""
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "模型请求超时，请检查网络或稍后重试。"
    if isinstance(exc, httpx.RequestError):
        return "无法连接模型服务，请检查地址、网络和代理。"
    if isinstance(exc, HTTPException):
        return f"模型服务未完成请求（HTTP {exc.status_code}），请检查密钥、模型和额度。"
    return "模型请求失败，请检查模型配置与服务状态。"


def public_spec(spec):
    return {"id": spec.id, "label": spec.label, "transport": spec.transport,
            "fields": spec.public_fields(), "description": spec.description,
            "billing_mode": spec.billing_mode, "credential_hint": spec.credential_hint,
            "usage_notice": spec.usage_notice, "recommended_models": list(spec.recommended_models),
            "can_fetch_models": spec.can_fetch_models, "supports_vision": spec.supports_vision}


class Models:
    def __init__(self, store):
        self.store = store

    def profile(self, ident):
        value = next((p for p in self.store.snapshot("llm")["profiles"] if p.get("id") == ident), None)
        if not value:
            raise HTTPException(404, "模型配置不存在")
        return value

    def active(self):
        ident = self.store.snapshot("llm").get("active_id")
        if not ident:
            raise HTTPException(400, "请先在 AI 模型页面保存并启用一个模型配置。")
        p = self.profile(ident)
        try:
            LLMProviderFactory.validate_config(p["provider"], p["config"])
        except ValueError:
            raise HTTPException(400, "当前模型配置不完整，请检查地址、密钥和模型名称。") from None
        return p

    def public(self):
        state = self.store.snapshot("llm")
        profiles = []
        for p in state["profiles"]:
            spec = LLM_PROVIDER_SPECS.get(p.get("provider"))
            if not spec:
                continue
            config = copy.deepcopy(p["config"])
            has_key = has_real_model_api_key(config.get("api_key"))
            config["api_key"] = MASK if has_key else ""
            try:
                LLMProviderFactory.validate_config(spec.id, p["config"])
                configured = True
            except ValueError:
                configured = False
            profiles.append({**public_spec(spec), **{k: p[k] for k in ["id", "name", "provider"]},
                             "provider_label": spec.label, "config": config, "has_api_key": has_key,
                             "configured": configured, "active": state.get("active_id") == p["id"],
                             "model": config.get("model", "")})
        return {"providers": [public_spec(s) for s in LLM_PROVIDER_SPECS.values()],
                "profiles": profiles, "active_id": state.get("active_id", "")}

    def create(self, provider, duplicate=None):
        if provider not in LLM_PROVIDER_SPECS:
            raise HTTPException(400, "未知服务商")
        spec = LLM_PROVIDER_SPECS[provider]
        p = {"id": uuid.uuid4().hex, "name": spec.label, "provider": provider,
             "config": copy.deepcopy(spec.default_config)}
        if duplicate:
            old = self.profile(duplicate)
            p.update(name=old["name"] + " 副本", provider=old["provider"], config=old["config"])
        state = self.store.snapshot("llm")
        state["profiles"].append(p)
        self.store.replace("llm", state)
        return p["id"]

    def resolve_draft(self, ident, draft=None, clear=False):
        p = self.profile(ident)
        if draft is None:
            return p
        config = dict(draft)
        # UI fields are strings until normalized; adapters expect numeric parameters.
        for key in ["max_tokens", "context_length", "timeout", "request_timeout_s"]:
            if key in config and config[key] not in (None, ""):
                try:
                    config[key] = int(config[key])
                    if config[key] <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(422, f"{key} 必须是正整数") from None
            elif key in config:
                del config[key]
        for key in ["temperature", "top_p"]:
            if key in config and config[key] not in (None, ""):
                try:
                    config[key] = float(config[key])
                    limit = 2 if key == "temperature" else 1
                    if not 0 <= config[key] <= limit:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(422, f"{key} 超出有效范围") from None
            elif key in config:
                del config[key]
        if clear:
            config["api_key"] = ""
        elif not has_real_model_api_key(config.get("api_key")):
            config["api_key"] = p["config"].get("api_key", "")
        for key in ["base_url", "api_url", "models_url"]:
            if config.get(key):
                try:
                    url = urlsplit(str(config[key]))
                    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                        raise ValueError()
                except ValueError:
                    raise HTTPException(422, "模型服务地址必须是有效的 HTTP(S) 地址，不能包含登录信息。") from None
        p["config"] = config
        return p

    def save(self, ident, name, config, clear=False):
        p = self.resolve_draft(ident, config, clear)
        p["name"] = name.strip()[:80] or LLM_PROVIDER_SPECS[p["provider"]].label
        state = self.store.snapshot("llm")
        state["profiles"] = [p if old["id"] == ident else old for old in state["profiles"]]
        self.store.replace("llm", state)

    def activate(self, ident):
        p = self.profile(ident)
        try:
            LLMProviderFactory.validate_config(p["provider"], p["config"])
        except ValueError:
            raise HTTPException(422, "请先补齐并保存服务地址、模型名称及所需密钥。") from None
        state = self.store.snapshot("llm")
        state["active_id"] = ident
        self.store.replace("llm", state)

    def delete(self, ident):
        state = self.store.snapshot("llm")
        self.profile(ident)
        if state.get("active_id") == ident:
            raise HTTPException(409, "请先启用其他模型，再删除当前模型。")
        state["profiles"] = [p for p in state["profiles"] if p["id"] != ident]
        self.store.replace("llm", state)

    def vision_available(self):
        try:
            p = self.active()
            return is_vision_supported(p["provider"], p["config"])
        except (HTTPException, ValueError):
            return False

    async def generate(self, p, prompt, text, attachments=None):
        provider = LLMProviderFactory.create(p["provider"], p["config"], system_prompt_provider=lambda: prompt)
        result = await provider.chat_result(text, [], attachments or [])
        # Reasoning lives in a separate result field. Strip embedded reasoning as well.
        reply = re.sub(r"<(think|thinking|reasoning)\b[^>]*>.*?(?:</\1>|$)", "", result.text or "", flags=re.S | re.I).strip()
        return reply

    async def catalog(self, p):
        spec = LLM_PROVIDER_SPECS[p["provider"]]
        cfg = p["config"]
        url = str(cfg.get("models_url") or "").strip()
        if not url:
            base = str(cfg.get("base_url") or cfg.get("api_url") or "").rstrip("/")
            base = re.sub(r"/(chat/completions|responses)$", "", base)
            url = base + "/models"
        if not url.startswith(("http://", "https://")):
            raise HTTPException(422, "请先填写模型服务地址")
        headers = {"Authorization": f"Bearer {cfg['api_key']}"} if has_real_model_api_key(cfg.get("api_key")) else {}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        rows = data.get("data", data.get("models", []))
        ids = [str(row.get("id") or row.get("name") or "") for row in rows if isinstance(row, dict)]
        return {"entries": [{"id": m, "name": m, "source": "live"} for m in ids if m],
                "models": [m for m in ids if m], "cache_state": "fresh"}
