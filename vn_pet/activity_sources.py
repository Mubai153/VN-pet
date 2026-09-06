"""Advanced activity context sources shared by the modular backend and legacy.

This module holds the platform collectors and pure signal builders that were
migrated out of ``legacy_server.py``: foreground/browser window enumeration,
app categorization, rhythm/typing state, window-switch statistics, task-pressure
keywords, time buckets, fullscreen detection, optional media audio state
(pycaw), the schedule placeholder and system health. Every function must
degrade independently — a missing optional dependency, a non-Windows platform or
an access failure may never raise into the proactive flow.

Stateful collectors (rhythm, window switches, foreground stability) keep their
mutable state in the ``ActivityService.manager_state`` dict passed in as
``manager``, which is guarded by the service's lock.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

BROWSER_PROCESS_NAMES = {
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
}

APP_CATEGORY_RULES = {
    "coding": (
        "code", "cursor", "pycharm", "devenv", "terminal", "powershell",
        "cmd.exe", "wt.exe", "python", "node", "git", "visual studio",
    ),
    "document": (
        "winword", "excel", "powerpnt", "acrobat", "onenote", "notepad",
        "obsidian", "wps", "pdf", "word",
    ),
    "browser": tuple(BROWSER_PROCESS_NAMES.keys()) + ("chrome", "edge", "firefox", "browser"),
    "media": ("vlc", "potplayer", "spotify", "cloudmusic", "music", "video", "bilibili"),
    "communication": ("wechat", "qq", "teams", "zoom", "discord", "telegram", "dingtalk"),
    "game": ("steam", "unity", "unreal", "game", "launcher", "epicgames"),
}

PRESSURE_KEYWORDS = (
    "traceback", "exception", "error", "failed", "failure", "fatal", "panic",
    "segmentation fault", "syntaxerror", "typeerror", "valueerror", "assertionerror",
    "build failed", "test failed", "cannot", "denied", "timeout", "refused",
    "报错", "错误", "异常", "失败", "无法", "超时", "拒绝",
)

PAPER_KEYWORDS = (
    "论文", "paper", "arxiv", "ieee", "abstract", "references", "introduction",
    "pdf", "robot", "robotics", "control", "控制", "机器人",
)

TIME_BUCKETS = ("morning", "lunch", "daytime", "evening", "late_night")

FULLSCREEN_TOLERANCE_PX = 8

WINDOW_SWITCH_WINDOW_SECONDS = 5 * 60
IDLE_RETURN_THRESHOLD_SECONDS = 5 * 60
IDLE_RECENT_INPUT_SECONDS = 90
TYPING_IDLE_SECONDS = 8
TYPING_STABLE_SECONDS = 30

# 系统健康阈值（保持 legacy 语义）
BATTERY_LOW_PERCENT = 20
DISK_LOW_FREE_GB = 5
CPU_HIGH_PERCENT = 90
MEMORY_HIGH_PERCENT = 90


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def collect_browser_windows(limit: int = 8) -> list[dict[str, str]]:
    """枚举可见浏览器窗口标题，供主动陪伴上下文使用。

    返回 `[{"browser": "Microsoft Edge", "title": "..."}]`；非 Windows 或依赖
    缺失时返回空列表，不抛异常。
    """
    if sys.platform != "win32":
        return []
    try:
        import psutil
        import win32gui
        import win32process
    except Exception:
        return []

    windows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def collect(hwnd, _data):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process_name = psutil.Process(pid).name().lower()
            except (psutil.Error, OSError):
                return True
            browser_name = BROWSER_PROCESS_NAMES.get(process_name)
            if not browser_name:
                return True
            key = (browser_name, title)
            if key in seen:
                return True
            seen.add(key)
            windows.append({"browser": browser_name, "title": title})
            return len(windows) < limit
        except Exception:
            return True

    try:
        win32gui.EnumWindows(collect, None)
    except Exception:
        pass
    return windows[:limit]


def classify_app_category(foreground: dict[str, Any], text: str = "") -> str:
    """按前台窗口的进程名、标题与附加文本粗略分类应用类型。

    分类见 `APP_CATEGORY_RULES`；无匹配时返回 ``"unknown"``。
    """
    haystack = (
        f"{foreground.get('process_name') or ''}\n"
        f"{foreground.get('title') or ''}\n"
        f"{text}"
    ).lower()
    for category, keywords in APP_CATEGORY_RULES.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "unknown"


def get_idle_seconds() -> float | None:
    if sys.platform != "win32":
        return None
    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            elapsed_ms = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
            return max(0.0, elapsed_ms / 1000.0)
    except Exception:
        return None
    return None


def get_foreground_window_info() -> dict[str, Any]:
    info = {"title": "", "process_name": ""}
    if sys.platform != "win32":
        return info
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return info
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        info["title"] = win32gui.GetWindowText(hwnd) or ""
        try:
            info["process_name"] = psutil.Process(pid).name()
        except (psutil.Error, OSError):
            pass
    except Exception:
        pass
    return info


def is_night_time(local_time: "time.struct_time") -> bool:
    return local_time.tm_hour >= 23 or local_time.tm_hour < 6


def time_bucket_for(hour: int, night: bool) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 14:
        return "lunch"
    if 18 <= hour < 23:
        return "evening"
    if night:
        return "late_night"
    return "daytime"


def match_keywords(text: str, keywords: tuple[str, ...], limit: int | None = None) -> list[str]:
    """Return keyword hits in the same relative order as the keyword table."""
    hits = [keyword for keyword in keywords if keyword in text]
    if limit is not None:
        hits = hits[:limit]
    return hits


def collect_rule_text(state: dict[str, Any]) -> str:
    """Lowercased concatenation of foreground, browser windows and OCR texts."""
    parts: list[str] = []
    foreground = state.get("foreground") or {}
    parts.append(str(foreground.get("process_name") or ""))
    parts.append(str(foreground.get("title") or ""))
    for item in state.get("browser_windows") or []:
        parts.append(str(item.get("browser") or ""))
        parts.append(str(item.get("title") or ""))
    for text in (state.get("screen_ocr") or {}).get("texts") or []:
        parts.append(str(text))
    return "\n".join(part for part in parts if part).lower()


def get_foreground_window_rect() -> dict[str, Any]:
    result = {"available": False, "left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}
    if sys.platform != "win32":
        return result
    try:
        import win32gui

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return result
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return {
            "available": True,
            "left": int(left),
            "top": int(top),
            "right": int(right),
            "bottom": int(bottom),
            "width": max(0, int(right - left)),
            "height": max(0, int(bottom - top)),
        }
    except Exception:
        return result


def get_virtual_screen_rect() -> dict[str, Any]:
    result = {"available": False, "left": 0, "top": 0, "width": 0, "height": 0}
    if sys.platform != "win32":
        return result
    try:
        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(76))
        top = int(user32.GetSystemMetrics(77))
        width = int(user32.GetSystemMetrics(78))
        height = int(user32.GetSystemMetrics(79))
        return {"available": True, "left": left, "top": top, "width": width, "height": height}
    except Exception:
        return result


def detect_fullscreen_state(foreground: dict[str, Any]) -> dict[str, Any]:
    rect = get_foreground_window_rect()
    screen = get_virtual_screen_rect()
    try:
        import win32api
        import win32gui
        handle = win32gui.GetForegroundWindow()
        monitor = win32api.GetMonitorInfo(win32api.MonitorFromWindow(handle, 2))["Monitor"]
        screen = {"available": True, "width": monitor[2]-monitor[0], "height": monitor[3]-monitor[1]}
    except Exception:
        pass
    category = classify_app_category(foreground)
    is_fullscreen = False
    if rect.get("available") and screen.get("available"):
        is_fullscreen = (
            rect.get("width", 0) >= max(1, int(screen.get("width", 0)) - FULLSCREEN_TOLERANCE_PX)
            and rect.get("height", 0) >= max(1, int(screen.get("height", 0)) - FULLSCREEN_TOLERANCE_PX)
        )
    protected = bool(is_fullscreen and category in {"game", "media", "communication"})
    return {
        "available": bool(rect.get("available") and screen.get("available")),
        "is_fullscreen": is_fullscreen,
        "protected_fullscreen": protected,
        "rect": rect,
        "screen": screen,
    }


def detect_media_audio_state() -> dict[str, Any]:
    """Optional pycaw audio-session probe.

    Missing dependency, non-Windows and access failures all return an
    unavailable state instead of raising.
    """
    result = {"available": False, "is_playing": False, "reason": "unavailable"}
    if sys.platform != "win32":
        return result
    try:
        import pycaw.pycaw as pycaw  # type: ignore

        sessions = pycaw.AudioUtilities.GetAllSessions()
        active = []
        for session in sessions:
            try:
                process = getattr(session, "Process", None)
                name = process.name() if process else ""
                volume = getattr(session, "SimpleAudioVolume", None)
                if volume and not volume.GetMute() and int(session.State) == 1:
                    active.append(name)
            except Exception:
                continue
        return {
            "available": True,
            "is_playing": bool(active),
            "active_sessions": active[:8],
            "reason": "",
        }
    except Exception as exc:
        return {"available": False, "is_playing": False, "reason": type(exc).__name__}


def collect_system_health() -> dict[str, Any]:
    result = {"available": True, "warnings": []}
    try:
        import psutil

        battery = psutil.sensors_battery()
        if battery:
            percent = float(battery.percent)
            result["battery_percent"] = percent
            result["power_plugged"] = bool(battery.power_plugged)
            if percent <= BATTERY_LOW_PERCENT and not battery.power_plugged:
                result["warnings"].append("battery_low")
    except Exception:
        result["battery_error"] = True
    try:
        import psutil

        disk = psutil.disk_usage("/")
        free_gb = disk.free / (1024 ** 3)
        result["disk_free_gb"] = round(free_gb, 1)
        if free_gb <= DISK_LOW_FREE_GB:
            result["warnings"].append("disk_low")
    except Exception:
        result["disk_error"] = True
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.0)
        result["cpu_percent"] = cpu_percent
        if cpu_percent >= CPU_HIGH_PERCENT:
            result["warnings"].append("cpu_high")
    except Exception:
        result["cpu_error"] = True
    try:
        import psutil

        memory = psutil.virtual_memory()
        result["memory_percent"] = float(memory.percent)
        if memory.percent >= MEMORY_HIGH_PERCENT:
            result["warnings"].append("memory_high")
    except Exception:
        result["memory_error"] = True
    try:
        import psutil

        result["network_available"] = any(psutil.net_if_stats().values())
    except Exception:
        result["network_error"] = True
    return result


def collect_schedule_context() -> dict[str, Any]:
    return {
        "available": False,
        "configured": False,
        "reason": "未配置本地日历/待办来源",
        "upcoming": [],
    }


# ── 前台稳定性、节律与窗口切换（状态在 service.manager_state） ──

def foreground_key(foreground: dict[str, Any]) -> str:
    return f"{foreground.get('process_name') or ''}|{foreground.get('title') or ''}"


def update_foreground_state(
    manager: dict[str, Any],
    current_key: str,
    *,
    window_switch_enabled: bool,
    now_monotonic: float,
) -> float:
    """Track foreground stability and the 5-minute switch window.

    Returns the monotonic time the current foreground became stable.
    """
    if current_key and current_key == manager.get("last_foreground_key"):
        return float(manager.get("foreground_stable_since") or now_monotonic)
    previous_key = str(manager.get("last_foreground_key") or "")
    manager["last_foreground_key"] = current_key
    manager["foreground_stable_since"] = now_monotonic
    if window_switch_enabled and previous_key:
        switches = list(manager.get("window_switches") or [])
        switches.append(now_monotonic)
        cutoff = now_monotonic - WINDOW_SWITCH_WINDOW_SECONDS
        manager["window_switches"] = [
            value for value in switches if isinstance(value, (int, float)) and value >= cutoff
        ]
    return now_monotonic


def count_window_switches_5m(manager: dict[str, Any], now_monotonic: float) -> int:
    cutoff = now_monotonic - WINDOW_SWITCH_WINDOW_SECONDS
    return len([
        value for value in (manager.get("window_switches") or [])
        if isinstance(value, (int, float)) and value >= cutoff
    ])


def update_activity_rhythm(manager: dict[str, Any], idle_seconds: Any, now_monotonic: float) -> None:
    if isinstance(idle_seconds, (int, float)):
        if idle_seconds < 15:
            manager["last_input_active_at"] = now_monotonic
        manager["last_idle_seconds"] = float(idle_seconds)


def collect_rhythm_signals(
    manager: dict[str, Any],
    idle_seconds: Any,
    *,
    prior_last_idle: Any = None,
    prior_last_input_at: float = 0.0,
    stable_seconds: float,
    now_monotonic: float,
) -> dict[str, Any]:
    session_started_at = float(manager.get("session_started_at") or now_monotonic)
    last_idle = prior_last_idle
    last_input_active_at = prior_last_input_at
    return {
        "session_seconds": max(0.0, now_monotonic - session_started_at),
        "has_recent_input": isinstance(idle_seconds, (int, float)) and idle_seconds < IDLE_RECENT_INPUT_SECONDS,
        "continuous_typing": (
            isinstance(idle_seconds, (int, float))
            and idle_seconds < TYPING_IDLE_SECONDS
            and stable_seconds >= TYPING_STABLE_SECONDS
        ),
        "idle_returned": (
            isinstance(last_idle, (int, float))
            and last_idle >= IDLE_RETURN_THRESHOLD_SECONDS
            and isinstance(idle_seconds, (int, float))
            and idle_seconds < 45
        ),
        "seconds_since_input": (
            max(0.0, now_monotonic - last_input_active_at)
            if last_input_active_at > 0
            else None
        ),
    }
