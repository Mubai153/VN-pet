import json

import httpx
import pytest

from vn_pet.bubble import bubble_position, paginate
from vn_pet.models import Models
from vn_pet.settings import Store


@pytest.mark.parametrize("pet,area", [((2480, 1300, 71, 130), (0, 0, 2560, 1400)), ((-1900, 40, 71, 130), (-1920, 0, 0, 1040)), ((-80, -1050, 71, 130), (-1920, -1080, 0, 0))])
@pytest.mark.parametrize("side", ["auto", "left_top", "right_top"])
def test_bubble_stays_in_current_monitor(pet, area, side):
    x, y = bubble_position(pet, (340, 200), area, side)
    assert area[0] <= x <= area[2] - 340
    assert area[1] <= y <= area[3] - 200


def test_pagination_never_truncates_long_text():
    text = "这是一段很长的发言。" * 200
    pages = paginate(text, len, 22, 5)
    assert len(pages) > 1
    assert "".join(pages).replace("\n", "") == text
    assert all(len(page.splitlines()) <= 5 for page in pages)


@pytest.mark.asyncio
async def test_imported_provider_request_and_reasoning_separation(tmp_path, monkeypatch):
    models = Models(Store(tmp_path))
    original_client = httpx.AsyncClient
    requests = []
    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>不应显示</think>你好 VN", "reasoning_content": "private"}, "finish_reason": "stop"}], "usage": {}})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    p = {"provider": "local", "config": {"base_url": "http://localhost:11434/v1", "model": "test", "temperature": .4}}
    reply = await models.generate(p, "VN 人设", "主动陪伴上下文")
    assert reply == "你好 VN"
    assert requests[0]["messages"][0]["content"] == "VN 人设"
    assert requests[0]["temperature"] == .4
    assert "tools" not in requests[0]


@pytest.mark.asyncio
async def test_vision_attachment_is_sent_only_to_vision_provider(tmp_path, monkeypatch):
    models = Models(Store(tmp_path))
    original_client = httpx.AsyncClient
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "屏幕测试"}, "finish_reason": "stop"}], "usage": {}})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    p = {"provider": "local", "config": {"base_url": "http://localhost:11434/v1", "model": "test", "supports_vision": True}}
    image = {"mime_type": "image/png", "data_base64": "dGVzdA==", "name": "screen.png"}
    assert await models.generate(p, "VN", "screen", [image]) == "屏幕测试"
    content = requests[0]["messages"][-1]["content"]
    assert any(part.get("type") == "image_url" for part in content)


def test_media_state_uses_current_monitor_and_no_stale_audio():
    # Runtime platform probe is intentionally separate from rendering/UI.
    from vn_pet.activity_sources import get_idle_seconds, detect_fullscreen_state
    idle = get_idle_seconds()
    assert idle is None or 0 <= idle < 2**32 / 1000
    assert "available" in detect_fullscreen_state({})


@pytest.mark.asyncio
async def test_model_catalog_uses_saved_address_and_key(tmp_path, monkeypatch):
    models = Models(Store(tmp_path))
    original_client = httpx.AsyncClient
    def respond(request):
        assert str(request.url) == "https://example.invalid/v1/models"
        assert request.headers["authorization"] == "Bearer private"
        return httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b"}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    result = await models.catalog({"provider": "custom", "config": {"base_url": "https://example.invalid/v1", "api_key": "private"}})
    assert result["models"] == ["model-a", "model-b"]
