from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .base import EmptyModelResponse, LLMCallResult, LLMProvider


class CodexAppServerError(RuntimeError):
    pass


def _item_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        str(part.get("text") or part.get("value") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") in {"output_text", "text"}
    )


class CodexAppServerClient:
    """Small JSONL client for the local Codex app-server process."""

    def __init__(self, data_dir: Path, logger: Any = None):
        self.data_dir = Path(data_dir)
        self.session_file = self.data_dir / "codex-thread.json"
        self.logger = logger
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task | None = None
        self.stderr_task: asyncio.Task | None = None
        self.notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.pending: dict[int, asyncio.Future] = {}
        self.next_id = 1
        self.thread_id = self._read_thread_id()
        self.write_lock = asyncio.Lock()
        self.turn_lock = asyncio.Lock()

    def _read_thread_id(self) -> str:
        try:
            value = json.loads(self.session_file.read_text(encoding="utf-8"))
            return str(value.get("thread_id") or "")
        except (OSError, ValueError, TypeError, AttributeError):
            return ""

    def _save_thread_id(self, thread_id: str) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.session_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"thread_id": thread_id}), encoding="utf-8")
        temporary.replace(self.session_file)

    async def _write(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise CodexAppServerError("Codex app-server 未启动")
        async with self.write_lock:
            self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode())
            await self.process.stdin.drain()

    async def _read_loop(self) -> None:
        assert self.process and self.process.stdout
        try:
            while line := await self.process.stdout.readline():
                try:
                    message = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if "method" in message:
                    await self.notifications.put(message)
                    continue
                request_id = message.get("id")
                future = self.pending.pop(request_id, None)
                if future and not future.done():
                    error = message.get("error")
                    if error:
                        future.set_exception(CodexAppServerError(str(error.get("message") or error)))
                    else:
                        future.set_result(message.get("result") or {})
        except asyncio.CancelledError:
            pass
        finally:
            error = CodexAppServerError("Codex app-server 连接已关闭")
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(error)
            self.pending.clear()

    async def _drain_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        try:
            while line := await self.process.stderr.readline():
                if self.logger:
                    self.logger.debug("codex app-server: %s", line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            pass

    async def _request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            await self._write({"method": method, "id": request_id, "params": params or {}})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(request_id, None)

    async def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._write({"method": method, "params": params or {}})

    async def start(self) -> None:
        if self.process and self.process.returncode is None:
            return
        command = shutil.which("codex") or "codex"
        process_options = {}
        if os.name == "nt":
            process_options["creationflags"] = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
        try:
            self.process = await asyncio.create_subprocess_exec(
                command,
                "app-server",
                "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **process_options,
            )
        except (OSError, FileNotFoundError) as exc:
            raise CodexAppServerError("找不到 Codex CLI，请先安装并登录 Codex。") from exc
        self.reader_task = asyncio.create_task(self._read_loop())
        self.stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            await self._request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "vn_desktop_pet",
                        "title": "VN 桌宠",
                        "version": "1.0.0",
                    }
                },
            )
            await self._notify("initialized")
        except Exception:
            await self.close()
            raise

    async def _thread(self, config: dict[str, Any]) -> str:
        await self.start()
        model = str(config.get("model") or "").strip()
        if self.thread_id:
            try:
                await self._request("thread/resume", {"threadId": self.thread_id})
                return self.thread_id
            except CodexAppServerError:
                self.thread_id = ""
        result = await self._request(
            "thread/start",
            {
                "model": model,
                "cwd": str(self.data_dir.resolve()),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "personality": "friendly",
                "serviceName": "vn_desktop_pet",
            },
        )
        self.thread_id = str(result.get("thread", {}).get("id") or "")
        if not self.thread_id:
            raise CodexAppServerError("Codex 没有返回有效线程")
        self._save_thread_id(self.thread_id)
        return self.thread_id

    async def complete(self, config: dict[str, Any], text: str, attachments: list[dict[str, Any]]) -> LLMCallResult:
        async with self.turn_lock:
            thread_id = await self._thread(config)
            temporary_files: list[str] = []
            try:
                input_items: list[dict[str, Any]] = [{"type": "text", "text": text}]
                for attachment in attachments:
                    if attachment.get("kind") != "image":
                        continue
                    raw = attachment.get("data_base64")
                    if not raw:
                        continue
                    suffix = "." + str(attachment.get("mime_type") or "image/png").split("/")[-1]
                    with tempfile.NamedTemporaryFile(dir=self.data_dir, suffix=suffix, delete=False) as handle:
                        import base64
                        handle.write(base64.b64decode(raw))
                        temporary_files.append(handle.name)
                    input_items.append({"type": "localImage", "path": temporary_files[-1]})

                result = await self._request(
                    "turn/start",
                    {
                        "threadId": thread_id,
                        "input": input_items,
                        "model": str(config.get("model") or "").strip(),
                        "effort": str(config.get("reasoning_effort") or "medium"),
                        "summary": "concise",
                    },
                    timeout=30,
                )
                turn_id = str(result.get("turn", {}).get("id") or "")
                if not turn_id:
                    raise CodexAppServerError("Codex 没有返回有效回合")
                chunks: list[str] = []
                fallback_text = ""
                while True:
                    message = await asyncio.wait_for(self.notifications.get(), 120)
                    params = message.get("params") or {}
                    if params.get("threadId") not in {None, thread_id}:
                        continue
                    if params.get("turnId") not in {None, turn_id}:
                        continue
                    method = message.get("method")
                    if method == "item/agentMessage/delta":
                        delta = params.get("delta")
                        if isinstance(delta, str):
                            chunks.append(delta)
                    elif method == "item/completed":
                        item = params.get("item")
                        if isinstance(item, dict) and item.get("type") == "agentMessage":
                            fallback_text = _item_text(item)
                    elif method == "turn/completed":
                        turn = params.get("turn") or {}
                        if turn.get("status") not in {None, "completed"}:
                            raise CodexAppServerError("Codex 回合未完成")
                        reply = "".join(chunks).strip() or fallback_text.strip()
                        if not reply:
                            raise EmptyModelResponse()
                        return LLMCallResult(text=reply, model=str(config.get("model") or ""))
            finally:
                for name in temporary_files:
                    try:
                        Path(name).unlink()
                    except OSError:
                        pass

    async def catalog(self) -> dict[str, Any]:
        await self.start()
        result = await self._request("model/list", {"limit": 100, "includeHidden": False})
        entries = []
        for row in result.get("data", []):
            if not isinstance(row, dict):
                continue
            model = str(row.get("model") or row.get("id") or "").strip()
            if not model:
                continue
            entries.append({
                "id": model,
                "name": row.get("displayName") or model,
                "owned_by": "Codex",
                "source": "live",
                "recommended": bool(row.get("isDefault")),
                "input_modalities": row.get("inputModalities") or ["text", "image"],
            })
        return {"entries": entries, "models": [item["id"] for item in entries], "cache_state": "fresh", "refreshing": False}

    async def check(self) -> None:
        await self.start()
        result = await self._request("account/read", {"refreshToken": False})
        if result.get("requiresOpenaiAuth") and not result.get("account"):
            raise CodexAppServerError("Codex 尚未登录，请先在 Codex CLI 或桌面应用中登录。")
        await self._request("model/list", {"limit": 1, "includeHidden": False})

    async def close(self) -> None:
        process, self.process = self.process, None
        for task, attr in [(self.reader_task, "reader_task"), (self.stderr_task, "stderr_task")]:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                setattr(self, attr, None)
        for future in self.pending.values():
            if not future.done():
                future.cancel()
        self.pending.clear()
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


class CodexAppServerProvider(LLMProvider):
    provider_id = "codex_app_server"

    def __init__(self, config: dict[str, Any], *, client: CodexAppServerClient | None = None, **kwargs: Any):
        super().__init__(config, **kwargs)
        self.client = client or CodexAppServerClient(Path.cwd(), logger=kwargs.get("logger"))

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> None:
        if not str(config.get("model") or "").strip():
            raise ValueError("missing Codex model")

    async def chat_result(self, text: str, history: list[dict], attachments: list[dict[str, Any]] | None = None, runtime_context: str = "") -> LLMCallResult:
        prompt = self.system_prompt()
        if runtime_context:
            prompt += f"\n\n[当前桌面感知数据]\n{runtime_context}"
        return await self.client.complete(self.config, f"{prompt}\n\n{text}".strip(), attachments or [])

    async def check(self) -> None:
        await self.client.check()

    async def catalog(self) -> dict[str, Any]:
        return await self.client.catalog()
