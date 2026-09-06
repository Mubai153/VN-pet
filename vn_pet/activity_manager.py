"""Activity manager decision state machine shared by backend and legacy.

Holds the manager-mode speak/avoid decision logic that previously lived in
``legacy_server.py``: event classification, foreground focus tracking, min/max
speech intervals, avoid-reason gating and auto-prompt feedback bookkeeping.
Mutable state lives in the ``ActivityService.manager_state`` dict passed in as
``manager`` and is guarded by the service's lock.

The legacy ``fixed_interval`` interaction mode bypasses manager event gating
but still honors do-not-disturb; the modular service's historical
``should_speak`` path is subsumed by this decision while keeping the same
response fields.
"""

from __future__ import annotations

import time
from typing import Any


from vn_pet.activity_sources import (
    PAPER_KEYWORDS,
    collect_rule_text,
    is_night_time,
    update_foreground_state,
)

FOCUS_STABLE_SECONDS = 5 * 60
FOCUS_IDLE_SECONDS = 90
PENDING_PROMPT_HISTORY = 12
PROMPT_EXPIRY_SECONDS = 60 * 60
RECENTLY_IGNORED_THRESHOLD = 3

HARD_SILENCE_REASONS = ("fullscreen_focus", "media_audio", "recently_ignored")


def _foreground_key(foreground: dict[str, Any]) -> str:
    return f"{foreground.get('process_name') or ''}|{foreground.get('title') or ''}"


def update_focus_state(manager: dict[str, Any], state: dict[str, Any], now_monotonic: float) -> tuple[bool, float]:
    """Track foreground stability and whether the user is actively focused."""
    foreground = state.get("foreground") or {}
    key = _foreground_key(foreground)
    idle_seconds = state.get("idle_seconds")
    stable_since = update_foreground_state(
        manager,
        key,
        window_switch_enabled=False,
        now_monotonic=now_monotonic,
    )
    stable_seconds = max(0.0, now_monotonic - stable_since)
    is_active = isinstance(idle_seconds, (int, float)) and idle_seconds < FOCUS_IDLE_SECONDS
    return bool(is_active and stable_seconds >= FOCUS_STABLE_SECONDS), stable_seconds


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_event(state: dict[str, Any], now_epoch: float | None = None) -> tuple[str, str]:
    """Return (event_type, event_reason) for the current activity state."""
    signals = state.get("signals") or {}
    if signals.get("pressure_level") in {"medium", "high"}:
        return "error", "检测到疑似报错、失败或调试压力"
    health = signals.get("system_health") or {}
    if health.get("warnings"):
        return "system_health", "检测到系统状态需要注意"
    if signals.get("idle_returned"):
        return "idle_return", "检测到用户刚从空闲状态回来"
    if signals.get("is_night") and signals.get("has_recent_input"):
        return "late_night", "检测到深夜仍在使用电脑"
    if signals.get("session_seconds", 0) >= 90 * 60:
        return "long_session", "检测到本次连续使用电脑时间较长"
    if signals.get("paper_context"):
        return "paper", "检测到疑似论文或技术文档"

    text = collect_rule_text(state)
    idle_seconds = state.get("idle_seconds")
    local_time = time.localtime(now_epoch or time.time())
    is_night = bool(state.get("context_sources", {}).get("time_context")) and is_night_time(local_time)

    if _matches_any(text, (
        "traceback",
        "exception",
        "error",
        "failed",
        "failure",
        "fatal",
        "panic",
        "segmentation fault",
        "syntaxerror",
        "typeerror",
        "valueerror",
        "assertionerror",
        "build failed",
        "test failed",
        "报错",
        "错误",
        "异常",
        "失败",
    )):
        return "error", "检测到疑似代码或终端报错"

    if is_night and (
        _matches_any(text, (
            "code",
            "visual studio",
            "pycharm",
            "cursor",
            "terminal",
            "powershell",
            "cmd.exe",
            ".py",
            ".js",
            ".ts",
            ".cpp",
            "论文",
            "paper",
            "pdf",
        ))
        or isinstance(idle_seconds, (int, float))
    ):
        return "late_night", "检测到深夜仍在使用电脑"

    if _matches_any(text, PAPER_KEYWORDS):
        return "paper", "检测到疑似论文或技术文档"

    if isinstance(idle_seconds, (int, float)) and idle_seconds >= 10 * 60:
        return "idle", "检测到长时间没有操作"

    return "general", ""


def collect_avoid_reasons(signals: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if signals.get("protected_fullscreen"):
        reasons.append("fullscreen_focus")
    if signals.get("media_is_playing") and signals.get("app_category") in {"media", "communication"}:
        reasons.append("media_audio")
    if signals.get("continuous_typing"):
        reasons.append("continuous_typing")
    if (signals.get("feedback") or {}).get("ignored_auto_count", 0) >= RECENTLY_IGNORED_THRESHOLD:
        reasons.append("recently_ignored")
    return reasons


def should_activity_manager_speak(
    settings: dict[str, Any],
    state: dict[str, Any],
    manual: bool,
    manager: dict[str, Any],
) -> dict[str, Any]:
    if manual:
        return {
            "should_speak": True,
            "skip_reason": "",
            "event_type": "manual",
            "manager_state": {},
        }
    # Fullscreen/media are explicit no-interruption signals in either automatic mode.
    for reason in (state.get("signals") or {}).get("avoid_reasons", []):
        if reason in HARD_SILENCE_REASONS:
            return _skip(reason, "suppressed", {})
    if settings.get("interaction_mode") != "manager":
        if settings.get("do_not_disturb"):
            return _skip(
                "do_not_disturb",
                "fixed_interval",
                {"do_not_disturb": True},
            )
        return {
            "should_speak": True,
            "skip_reason": "",
            "event_type": "fixed_interval",
            "manager_state": {},
        }

    now_monotonic = time.monotonic()
    now_epoch = time.time()
    signals = state.get("signals") or {}
    event_type, event_reason = classify_event(state, now_epoch)
    is_focused, foreground_stable_seconds = update_focus_state(manager, state, now_monotonic)
    min_seconds = max(1, int(settings.get("min_speech_interval_minutes", 10))) * 60
    max_seconds = max(1, int(settings.get("max_speech_interval_minutes", 45))) * 60

    last_auto_speech_at = float(manager.get("last_auto_speech_at") or 0.0)
    seconds_since_last = (
        max(0.0, now_monotonic - last_auto_speech_at)
        if last_auto_speech_at > 0
        else None
    )
    recently_spoke = seconds_since_last is not None and seconds_since_last < min_seconds
    exceeded_max_interval = seconds_since_last is None or seconds_since_last >= max_seconds
    local_time = time.localtime(now_epoch)
    is_night = bool(state.get("context_sources", {}).get("time_context")) and is_night_time(local_time)

    manager_state = {
        "recently_spoke": recently_spoke,
        "seconds_since_last_speech": seconds_since_last,
        "is_focused": bool(signals.get("is_focused") or is_focused),
        "foreground_stable_seconds": foreground_stable_seconds,
        "has_obvious_event": bool(event_reason),
        "is_night": bool(signals.get("is_night") or is_night),
        "do_not_disturb": bool(settings.get("do_not_disturb")),
        "exceeded_max_interval": exceeded_max_interval,
        "event_reason": event_reason,
        "signals": signals,
    }

    if settings.get("do_not_disturb"):
        return _skip("do_not_disturb", event_type, manager_state)
    if recently_spoke:
        return _skip("min_interval", event_type, manager_state)

    avoid_reasons = list(signals.get("avoid_reasons") or [])
    hard_silence_reasons = [
        reason for reason in avoid_reasons if reason in HARD_SILENCE_REASONS
    ]
    if hard_silence_reasons:
        return _skip(hard_silence_reasons[0], event_type, manager_state)
    if "continuous_typing" in avoid_reasons and event_type not in {"error", "system_health"}:
        return _skip("continuous_typing", event_type, manager_state)
    if event_reason:
        if manager_state["is_focused"] and event_type not in {"error", "late_night", "system_health"} and not exceeded_max_interval:
            return _skip("focused", event_type, manager_state)
        return {
            "should_speak": True,
            "skip_reason": "",
            "event_type": event_type,
            "manager_state": manager_state,
        }
    if exceeded_max_interval:
        return {
            "should_speak": True,
            "skip_reason": "",
            "event_type": "max_interval",
            "manager_state": manager_state,
        }
    return _skip("no_event", event_type, manager_state)


def _skip(skip_reason: str, event_type: str, manager_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "should_speak": False,
        "skip_reason": skip_reason,
        "event_type": event_type,
        "manager_state": manager_state,
    }


def build_activity_prompt_context(
    state_summary: str,
    state: dict[str, Any],
    event_type: str,
    manager_state: dict[str, Any],
) -> str:
    if event_type in {"manual", "fixed_interval"}:
        return state_summary
    event_labels = {
        "error": "疑似代码/终端报错，适合关心地询问要不要帮忙看。",
        "idle": "用户较久没有操作，适合轻轻打趣或确认是在思考。",
        "late_night": "现在是深夜，适合温柔提醒休息。",
        "paper": "疑似正在看论文或技术文档，适合询问要不要抓核心贡献。",
        "max_interval": "已经较久没有主动说话，适合一句很轻的陪伴或状态确认。",
        "general": "没有强事件，只做自然陪伴。",
    }
    event_labels.update({
        "idle_return": "用户刚从空闲状态回来，适合轻轻问候，不要追问太多。",
        "long_session": "用户已经连续使用电脑较久，适合温柔提醒休息。",
        "system_health": "系统状态出现低电量、高负载或磁盘空间不足等信号，适合简短提醒。",
    })
    reason = manager_state.get("event_reason") or event_labels.get(event_type, "")
    return (
        f"主动发言管理器判断: {event_labels.get(event_type, event_type)}\n"
        f"触发原因: {reason or '达到最大发言间隔'}\n"
        f"用户可能正在专注: {'是' if manager_state.get('is_focused') else '否'}\n\n"
        f"{state_summary}"
    )
