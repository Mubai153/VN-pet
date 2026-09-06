from __future__ import annotations

import asyncio
import secrets
import socket
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import safe_error
from .settings import ActivitySettings, Character, PetSettings, character_prompt

STATIC = Path(__file__).resolve().parent.parent / "static"


class ProfileCreate(BaseModel):
    provider: str
    duplicate: str | None = None


class ProfileEdit(BaseModel):
    name: str = Field(default="", max_length=80)
    config: dict = Field(default_factory=dict)
    clear_api_key: bool = False


class Activate(BaseModel):
    profile_id: str


class Trigger(BaseModel):
    manual: bool = True


class Preview(BaseModel):
    settings: PetSettings
    text: str = Field(default="忙了一会儿，也记得让眼睛歇一歇。我在这里陪着你。", max_length=12000)


def create_app(companion, token, origin, events):
    store, models = companion.store, companion.models

    @asynccontextmanager
    async def lifespan(app):
        await companion.start()
        yield
        await companion.shutdown()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request, call_next):
        if request.headers.get("host") != origin.split("//", 1)[1]:
            return JSONResponse({"detail": "无效的本机地址"}, 403)
        supplied_origin = request.headers.get("origin")
        if supplied_origin and supplied_origin != origin:
            return JSONResponse({"detail": "无效的请求来源"}, 403)
        if request.url.path not in {"/", "/index.html"} and not request.url.path.startswith("/assets/"):
            expected = "Bearer " + token
            if not secrets.compare_digest(request.headers.get("authorization", ""), expected):
                return JSONResponse({"detail": "设置窗口会话已失效，请重新打开。"}, 401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "字段格式无效，请检查：" + ", ".join(".".join(str(x) for x in e["loc"][1:]) for e in exc.errors())}, 422)

    @app.exception_handler(OSError)
    async def write_failed(request, exc):
        return JSONResponse({"detail": "无法保存本地设置，请检查磁盘空间和目录权限。"}, 500)

    @app.get("/settings/llm")
    async def get_models():
        return models.public()

    @app.post("/settings/llm/profiles")
    async def create_profile(body: ProfileCreate):
        ident = models.create(body.provider, body.duplicate)
        return {**models.public(), "selected_id": ident}

    @app.put("/settings/llm/profiles/{ident}")
    async def save_profile(ident: str, body: ProfileEdit):
        models.save(ident, body.name, body.config, body.clear_api_key)
        companion.settings_changed("llm")
        return models.public()

    @app.delete("/settings/llm/profiles/{ident}")
    async def delete_profile(ident: str):
        models.delete(ident)
        return models.public()

    @app.put("/settings/llm")
    async def activate_profile(body: Activate):
        models.activate(body.profile_id)
        companion.settings_changed("llm")
        return models.public()

    @app.post("/settings/llm/profiles/{ident}/test")
    async def test_profile(ident: str, body: ProfileEdit):
        p = models.resolve_draft(ident, body.config, body.clear_api_key)
        try:
            await asyncio.wait_for(models.test(p), 40)
            return {"ok": True}
        except Exception as exc:
            raise HTTPException(502, safe_error(exc)) from None

    @app.post("/settings/llm/profiles/{ident}/models/refresh")
    async def refresh_models(ident: str, body: ProfileEdit):
        p = models.resolve_draft(ident, body.config, body.clear_api_key)
        try:
            return await models.catalog(p)
        except Exception as exc:
            raise HTTPException(502, safe_error(exc)) from None

    @app.get("/settings/character")
    async def get_character():
        c = store.snapshot("character")
        return {"settings": c, "prompt_preview": character_prompt(c)}

    @app.put("/settings/character")
    async def save_character(body: Character):
        store.replace("character", body.model_dump())
        companion.settings_changed("character")
        return await get_character()

    @app.post("/settings/character/preview")
    async def preview_character(body: Character):
        return {"prompt_preview": character_prompt(body.model_dump())}

    @app.get("/activity/settings")
    async def get_activity():
        return {"settings": store.snapshot("activity")}

    @app.put("/activity/settings")
    async def save_activity(body: ActivitySettings):
        store.replace("activity", body.model_dump())
        companion.settings_changed("activity")
        return await get_activity()

    @app.post("/activity/proactive")
    async def trigger(body: Trigger):
        return companion.trigger(body.manual)

    @app.get("/activity/status")
    async def get_status():
        return companion.snapshot()

    @app.get("/settings/pet")
    async def get_pet():
        return {"settings": store.snapshot("pet")}

    @app.put("/settings/pet")
    async def save_pet(body: PetSettings):
        store.replace("pet", body.model_dump())
        events.put(("pet_settings", body.model_dump(), None))
        return await get_pet()

    @app.post("/pet/preview")
    async def preview_pet(body: Preview):
        events.put(("preview", {"text": body.text, "settings": body.settings.model_dump()}, None))
        return {"ok": True}

    @app.post("/pet/clear")
    async def clear_pet():
        events.put(("clear", {}, None))
        return {"ok": True}

    @app.get("/")
    async def index():
        if not (STATIC / "index.html").exists():
            raise HTTPException(503, "设置页面尚未构建，请在 web_src 中运行 npm run build。")
        return FileResponse(STATIC / "index.html")

    if (STATIC / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")
    return app


class LocalServer:
    def __init__(self, companion, events):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(128)
        self.origin = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.token = secrets.token_urlsafe(32)
        app = create_app(companion, self.token, self.origin, events)
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_config=None, log_level="critical", access_log=False, timeout_graceful_shutdown=2))
        self.thread = threading.Thread(target=lambda: self.server.run(sockets=[self.socket]), daemon=True, name="VN-settings-service")

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=4)
        self.socket.close()
