from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .providers.factory import LLMProviderFactory
from .providers.codex_app_server_provider import CodexAppServerClient, CodexAppServerError
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
    if isinstance(exc, CodexAppServerError):
        return str(exc)
    return "模型请求失败，请检查模型配置与服务状态。"


def public_spec(spec):
    return {"id": spec.id, "label": spec.label, "transport": spec.transport,
            "fields": spec.public_fields(), "description": spec.description,
            "billing_mode": spec.billing_mode, "credential_hint": spec.credential_hint,
            "usage_notice": spec.usage_notice, "recommended_models": list(spec.recommended_models),
            "can_fetch_models": spec.can_fetch_models, "supports_vision": spec.supports_vision,
            "requires_api_key": spec.requires_api_key, "supports_native_tools": spec.supports_native_tools}


class Models:
    def __init__(self, store):
        self.store = store
        self.codex_client = CodexAppServerClient(store.directory)

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
        provider = self._provider(p, prompt)
        result = await provider.chat_result(text, [], attachments or [])
        # Reasoning lives in a separate result field. Strip embedded reasoning as well.
        reply = re.sub(r"<(think|thinking|reasoning)\b[^>]*>.*?(?:</\1>|$)", "", result.text or "", flags=re.S | re.I).strip()
        return reply

    def _provider(self, p, prompt=""):
        return LLMProviderFactory.create(
            p["provider"],
            p["config"],
            system_prompt_provider=lambda: prompt,
            client=self.codex_client if p["provider"] == "codex_app_server" else None,
        )

    async def test(self, p):
        provider = self._provider(p, "只回复简短中文。")
        if hasattr(provider, "check"):
            await provider.check()
            return
        text = await self.generate(p, "只回复简短中文。", "请回复：连接成功")
        if not text:
            raise ValueError()

    async def catalog(self, p):
        if p["provider"] == "codex_app_server":
            return await self._provider(p).catalog()
        spec = LLM_PROVIDER_SPECS[p["provider"]]
        cfg = p["config"]
        explicit_url = str(cfg.get("models_url") or "").strip()
        base = str(cfg.get("base_url") or cfg.get("api_url") or "").rstrip("/")
        base = re.sub(r"/(chat/completions|responses)$", "", base)
        if explicit_url:
            urls = [explicit_url]
        elif spec.id == "local":
            # LM Studio's native catalog includes downloaded (not only loaded) models.
            root = re.sub(r"/(?:api/)?v1$", "", base)
            urls = [root + "/api/v1/models", root + "/v1/models"]
        else:
            urls = [base + "/models"]
        if not all(url.startswith(("http://", "https://")) for url in urls):
            raise HTTPException(422, "请先填写模型服务地址")
        headers = {"Authorization": f"Bearer {cfg.get('api_key', '')}"} if has_real_model_api_key(cfg.get("api_key")) else {}
        local_entries = []
        host = (urlsplit(base).hostname or "").lower()
        if spec.id == "local" and host in {"localhost", "127.0.0.1", "::1"}:
            try:
                index = json.loads((Path.home() / ".lmstudio" / ".internal" / "model-index-cache.json").read_text(encoding="utf-8"))
                for row in index.get("models", []):
                    if not isinstance(row, dict) or row.get("domain") != "llm":
                        continue
                    model_id = str(row.get("indexedModelIdentifier") or row.get("defaultIdentifier") or "").strip()
                    if not model_id:
                        continue
                    entry = {"id": model_id, "name": row.get("displayName") or model_id, "source": "configured"}
                    if row.get("contextLength"):
                        entry["context_length"] = row["contextLength"]
                        entry["max_context_length"] = row["contextLength"]
                        entry["context_source"] = "detected"
                    local_entries.append(entry)
            except (OSError, ValueError):
                pass
        async with httpx.AsyncClient(timeout=20) as client:
            last_error = None
            for url in urls:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    rows = data.get("data", data.get("models", [])) if isinstance(data, dict) else []
                    entries = []
                    seen = set()
                    for row in rows:
                        if not isinstance(row, dict) or row.get("type") == "embedding":
                            continue
                        model_id = str(row.get("id") or row.get("key") or row.get("name") or "").strip()
                        if not model_id or model_id in seen:
                            continue
                        seen.add(model_id)
                        entry = {"id": model_id, "name": row.get("display_name") or model_id, "source": "live"}
                        if row.get("owned_by") or row.get("publisher"):
                            entry["owned_by"] = row.get("owned_by") or row.get("publisher")
                        if row.get("max_context_length"):
                            entry["max_context_length"] = row["max_context_length"]
                            entry["context_length"] = row["max_context_length"]
                            entry["context_source"] = "detected"
                        entries.append(entry)
                    seen = {entry["id"] for entry in entries}
                    merged = entries + [item for item in local_entries if item["id"] not in seen]
                    ids = [entry["id"] for entry in merged]
                    return {"entries": merged, "models": ids, "cache_state": "fresh"}
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
            if last_error:
                if local_entries:
                    ids = [entry["id"] for entry in local_entries]
                    return {"entries": local_entries, "models": ids, "cache_state": "fresh"}
                raise last_error
        return {"entries": [], "models": [], "cache_state": "fresh"}

    async def close(self):
        await self.codex_client.close()
