import queue

import pytest
from fastapi.testclient import TestClient

from vn_pet.activity import Companion
from vn_pet.models import Models
from vn_pet.server import create_app
from vn_pet.settings import Store


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    events = queue.Queue()
    companion = Companion(store, events)
    app = create_app(companion, "test-secret", "http://testserver", events)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test-secret"
        yield store, companion, client


def test_defaults_and_persistence(setup):
    store, _, client = setup
    assert client.get("/settings/llm").json()["profiles"] == []
    a = client.get("/activity/settings").json()["settings"]
    assert not a["enabled"] and not a["context_sources"]["screen_ocr"]
    a["interval_minutes"] = 7
    assert client.put("/activity/settings", json=a).status_code == 200
    assert Store(store.directory).snapshot("activity")["interval_minutes"] == 7


def test_key_mask_preserve_clear_and_independent_models(setup):
    store, _, client = setup
    data = client.post("/settings/llm/profiles", json={"provider": "custom"}).json()
    ident = data["selected_id"]
    body = {"name": "测试", "config": {"base_url": "https://example.invalid/v1", "model": "demo", "api_key": "secret-do-not-return"}}
    response = client.put(f"/settings/llm/profiles/{ident}", json=body)
    assert response.status_code == 200
    assert "secret-do-not-return" not in response.text
    assert response.json()["profiles"][0]["has_api_key"]
    for blank in ["", "********"]:
        body["config"]["api_key"] = blank
        assert client.put(f"/settings/llm/profiles/{ident}", json=body).status_code == 200
        assert Models(store).profile(ident)["config"]["api_key"] == "secret-do-not-return"
    assert client.put("/settings/llm", json={"profile_id": ident}).status_code == 200
    assert client.delete(f"/settings/llm/profiles/{ident}").status_code == 409
    duplicate = client.post("/settings/llm/profiles", json={"provider": "custom", "duplicate": ident}).json()["selected_id"]
    body["clear_api_key"] = True
    client.put(f"/settings/llm/profiles/{duplicate}", json=body)
    assert Models(store).profile(duplicate)["config"]["api_key"] == ""
    assert Models(store).profile(ident)["config"]["api_key"] == "secret-do-not-return"


@pytest.mark.parametrize("headers,status", [({"Authorization": ""}, 401), ({"Origin": "https://attacker.invalid"}, 403), ({"Host": "attacker.invalid"}, 403)])
def test_api_host_origin_and_session(setup, headers, status):
    _, _, client = setup
    assert client.get("/settings/character", headers=headers).status_code == status


def test_validation_omits_secret_input_and_keeps_saved_state(setup):
    store, _, client = setup
    original = store.snapshot("activity")
    body = dict(original, min_speech_interval_minutes=100, max_speech_interval_minutes=5)
    response = client.put("/activity/settings", json=body)
    assert response.status_code == 422
    assert store.snapshot("activity") == original
    response = client.post("/settings/llm/profiles", json={"provider": {"api_key": "secret-leak"}})
    assert response.status_code == 422 and "secret-leak" not in response.text


def test_write_failure_rolls_back_live_state(setup, monkeypatch):
    store, _, client = setup
    original = store.snapshot("character")
    def fail(*args):
        raise OSError("private-path-or-secret")
    monkeypatch.setattr(store, "atomic_write", fail)
    response = client.put("/settings/character", json={**original, "name": "Changed"})
    assert response.status_code == 500
    assert "private-path-or-secret" not in response.text
    assert store.snapshot("character") == original


def test_character_prompt_preview_and_no_other_app_features(setup):
    _, _, client = setup
    response = client.put("/settings/character", json={"name": "VN", "personality": "安静", "system_prompt": "不重复提醒"})
    assert response.status_code == 200
    assert "性格：安静" in response.json()["prompt_preview"]
    assert "不重复提醒" in response.json()["prompt_preview"]
    assert client.get("/settings/tts").status_code == 404


def test_bubble_preview_is_an_event_not_history(setup):
    store, companion, client = setup
    response = client.post("/pet/preview", json={"settings": store.snapshot("pet"), "text": "你好"})
    assert response.status_code == 200
    event = companion.events.get_nowait()
    assert event[0] == "preview" and event[1]["text"] == "你好"
    assert store.history == []


def test_bad_file_falls_back(tmp_path):
    (tmp_path / "settings.json").write_text("{ broken", encoding="utf-8")
    store = Store(tmp_path)
    assert store.warning and store.snapshot("character")["name"] == "VN"


def test_malformed_model_rows_do_not_break_startup(tmp_path):
    (tmp_path / "settings.json").write_text('{"llm":{"profiles":[null,{},42],"active_id":"missing"}}', encoding="utf-8")
    store = Store(tmp_path)
    assert Models(store).public()["profiles"] == []


def test_cleared_optional_generation_parameters_use_provider_defaults(setup):
    store, _, _ = setup
    models = Models(store)
    ident = models.create("local")
    p = models.resolve_draft(ident, {"base_url": "http://localhost:11434/v1", "model": "test", "temperature": "", "top_p": "", "max_tokens": ""})
    assert "temperature" not in p["config"] and "top_p" not in p["config"]
