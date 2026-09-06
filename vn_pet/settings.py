from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Character(SettingsModel):
    name: str = Field(default="VN", min_length=1, max_length=80)
    identity: str = Field(default="陪在用户身边的桌面伙伴。", max_length=4000)
    personality: str = Field(default="友善、自然、体贴，尊重用户的节奏。", max_length=4000)
    speaking_style: str = Field(default="使用简体中文，简短自然，不频繁追问。", max_length=4000)
    example_dialogues: str = Field(default="", max_length=8000)
    system_prompt: str = Field(default="", max_length=16000)


def character_prompt(character: dict) -> str:
    c = Character.model_validate(character)
    fields = [("名称", c.name), ("身份", c.identity), ("性格", c.personality),
              ("说话风格", c.speaking_style), ("示例对话", c.example_dialogues),
              ("补充系统提示", c.system_prompt)]
    return "\n\n".join(f"{label}：{text.strip()}" for label, text in fields if text.strip())


class ContextSources(SettingsModel):
    foreground_window: bool = True
    browser_windows: bool = False
    idle_time: bool = True
    activity_rhythm: bool = False
    app_category: bool = False
    window_switch_activity: bool = False
    task_pressure_signals: bool = False
    time_context: bool = True
    media_audio_state: bool = False
    fullscreen_focus_state: bool = False
    system_health: bool = False
    screen_ocr: bool = False
    screen_vision: bool = False


class ActivitySettings(SettingsModel):
    enabled: bool = False
    interaction_mode: Literal["fixed_interval", "manager"] = "fixed_interval"
    interval_minutes: int = Field(default=5, ge=1, le=180)
    min_speech_interval_minutes: int = Field(default=10, ge=1, le=180)
    max_speech_interval_minutes: int = Field(default=45, ge=1, le=240)
    do_not_disturb: bool = False
    save_latest_screenshot: bool = False
    context_sources: ContextSources = Field(default_factory=ContextSources)

    @model_validator(mode="after")
    def validate_intervals(self):
        if self.max_speech_interval_minutes < self.min_speech_interval_minutes:
            raise ValueError("最长发言间隔不能小于最短发言间隔")
        return self


class PetSettings(SettingsModel):
    enabled: bool = True
    font_size: int = Field(default=14, ge=12, le=32)
    position: Literal["auto", "left_top", "right_top"] = "auto"
    duration_seconds: int = Field(default=10, ge=4, le=120)
    background: str = Field(default="#fff8ed", pattern=r"^#[0-9a-fA-F]{6}$")
    border: str = Field(default="#b99666", pattern=r"^#[0-9a-fA-F]{6}$")
    text_color: str = Field(default="#40382d", pattern=r"^#[0-9a-fA-F]{6}$")


class Store:
    """One owner for local data; failed writes never change the live snapshot."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VNDesktopPet"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "settings.json"
        self.lock = threading.RLock()
        self.warning = ""
        self.data = {"version": 1, "llm": {"profiles": [], "active_id": ""},
                     "character": Character().model_dump(), "activity": ActivitySettings().model_dump(),
                     "pet": PetSettings().model_dump()}
        self.history = []
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                for name, cls in [("character", Character), ("activity", ActivitySettings), ("pet", PetSettings)]:
                    try:
                        self.data[name] = cls.model_validate(saved.get(name, {})).model_dump()
                    except (ValueError, TypeError):
                        self.warning = "部分旧设置无效，已使用默认值；原文件将在下次保存时更新。"
                llm = saved.get("llm", {})
                if isinstance(llm, dict) and isinstance(llm.get("profiles"), list):
                    from .providers.registry import LLM_PROVIDER_SPECS
                    profiles = [p for p in llm["profiles"] if isinstance(p, dict)
                                and isinstance(p.get("id"), str) and p["id"]
                                and isinstance(p.get("name"), str)
                                and p.get("provider") in LLM_PROVIDER_SPECS
                                and isinstance(p.get("config"), dict)]
                    active = llm.get("active_id", "")
                    self.data["llm"] = {"profiles": profiles, "active_id": active if active in [p["id"] for p in profiles] else ""}
            except (OSError, ValueError, TypeError, AttributeError):
                self.warning = "设置文件无法读取，已使用默认设置。"
        try:
            records = json.loads((self.directory / "history.json").read_text(encoding="utf-8"))
            self.history = [r for r in records if isinstance(r, dict) and isinstance(r.get("text"), str)][-100:]
        except (OSError, ValueError, TypeError):
            pass

    def snapshot(self, key=None):
        with self.lock:
            return copy.deepcopy(self.data[key] if key else self.data)

    def atomic_write(self, path: Path, value):
        fd, name = tempfile.mkstemp(prefix=".vn-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def replace(self, key, value):
        with self.lock:
            updated = copy.deepcopy(self.data)
            updated[key] = copy.deepcopy(value)
            self.atomic_write(self.path, updated)
            self.data = updated

    def remember(self, record):
        with self.lock:
            if any(r.get("id") == record["id"] for r in self.history):
                return
            history = (self.history + [record])[-100:]
            self.atomic_write(self.directory / "history.json", history)
            self.history = history
