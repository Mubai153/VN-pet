import asyncio
import queue
import time

import pytest

from vn_pet.activity import Companion
from vn_pet.activity_manager import should_activity_manager_speak
from vn_pet.settings import ActivitySettings, Store


def companion(tmp_path, monkeypatch, reply="今天也辛苦啦。"):
    app = Companion(Store(tmp_path), queue.Queue())
    monkeypatch.setattr(app.models, "active", lambda: {"provider": "local", "config": {}})
    monkeypatch.setattr(app.models, "vision_available", lambda: False)
    monkeypatch.setattr(app.collector, "collect", lambda *a, **k: ({"signals": {}}, []))
    async def generate(*args):
        return reply
    monkeypatch.setattr(app.models, "generate", generate)
    return app


async def wait_for_event(app):
    for _ in range(100):
        if not app.events.empty():
            return app.events.get_nowait()
        await asyncio.sleep(.01)
    raise AssertionError(f"Missing bubble event: {app.status}")


@pytest.mark.asyncio
async def test_manual_bypasses_disabled_and_records_only_on_display(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    await app.start()
    assert app.trigger(True)["accepted"]
    event = await wait_for_event(app)
    assert app.store.history == []
    _, payload, ack = event
    assert app.display(payload, lambda *a: True)
    ack.set_result(True)
    await app.task
    assert app.store.history[0]["text"] == "今天也辛苦啦。"
    assert app.status["last_spoken"] and app.last_speech
    await app.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", ["", "  [SILENT]。", "```\n[SILENT]\n```"])
async def test_silent_does_not_display_record_or_advance_clock(tmp_path, monkeypatch, reply):
    app = companion(tmp_path, monkeypatch, reply)
    await app.run(True)
    assert app.events.empty() and app.store.history == [] and app.last_speech == 0
    assert app.status["skip_reason"] == "silent"


@pytest.mark.asyncio
async def test_busy_and_model_change_discard_late_response(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    entered = asyncio.Event()
    resume = asyncio.Event()
    async def stubborn(*args):
        entered.set()
        try:
            await resume.wait()
        except asyncio.CancelledError:
            await resume.wait()
        return "旧角色回复"
    monkeypatch.setattr(app.models, "generate", stubborn)
    await app.start()
    assert app.trigger()["accepted"]
    await entered.wait()
    assert not app.trigger()["accepted"]
    app.settings_changed("character")
    resume.set()
    await app.task
    assert app.events.empty() and not app.store.history
    await app.shutdown()


@pytest.mark.asyncio
async def test_pending_bubble_rejected_after_config_change(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    await app.start()
    app.trigger()
    _, payload, ack = await wait_for_event(app)
    app.settings_changed("llm")
    called = []
    assert not app.display(payload, lambda *a: called.append(True))
    assert not called and not app.store.history
    await app.shutdown()


@pytest.mark.asyncio
async def test_disabled_bubble_not_recorded(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    await app.start()
    app.trigger()
    _, payload, ack = await wait_for_event(app)
    assert not app.display(payload, lambda *a: False)
    ack.set_result(False)
    await app.task
    assert app.last_speech == 0 and not app.store.history
    await app.shutdown()


@pytest.mark.asyncio
async def test_min_interval_and_do_not_disturb_skip_before_capture(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    settings = app.store.snapshot("activity")
    settings["enabled"] = True
    app.store.replace("activity", settings)
    app.last_speech = time.monotonic()
    def forbidden(*a, **k):
        raise AssertionError("must not collect")
    monkeypatch.setattr(app.collector, "collect", forbidden)
    await app.run(False)
    assert app.status["skip_reason"] == "min_interval"
    settings["do_not_disturb"] = True
    app.store.replace("activity", settings)
    assert not app.valid(app.generation, False)


@pytest.mark.asyncio
async def test_failure_is_sanitized_and_shutdown_cleans_tasks(tmp_path, monkeypatch):
    app = companion(tmp_path, monkeypatch)
    async def fail(*args):
        raise RuntimeError("secret api-key and captured screen content")
    monkeypatch.setattr(app.models, "generate", fail)
    await app.start()
    app.trigger()
    await app.task
    assert app.status["state"] == "error" and "secret" not in str(app.status)
    await app.shutdown()
    assert app.scheduler_task.done() and not app.trigger()["accepted"]


@pytest.mark.parametrize("reason", ["fullscreen_focus", "media_audio", "continuous_typing"])
def test_manager_honors_focus_suppression(reason):
    settings = ActivitySettings(interaction_mode="manager").model_dump()
    result = should_activity_manager_speak(settings, {"signals": {"avoid_reasons": [reason]}}, False, {})
    assert not result["should_speak"] and result["skip_reason"] == reason


@pytest.mark.parametrize("reason", ["fullscreen_focus", "media_audio"])
def test_fixed_interval_also_respects_explicit_no_interruption_signals(reason):
    result = should_activity_manager_speak(ActivitySettings().model_dump(), {"signals": {"avoid_reasons": [reason]}}, False, {})
    assert not result["should_speak"] and result["skip_reason"] == reason
