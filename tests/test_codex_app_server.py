import pytest

from vn_pet.providers.codex_app_server_provider import CodexAppServerProvider


class FakeCodexClient:
    async def complete(self, config, text, attachments):
        self.config = config
        self.text = text
        self.attachments = attachments
        from vn_pet.providers.base import LLMCallResult
        return LLMCallResult(text="Codex 回复", model=config["model"])


@pytest.mark.asyncio
async def test_codex_provider_uses_client_without_api_key():
    client = FakeCodexClient()
    provider = CodexAppServerProvider(
        {"model": "gpt-5.6-terra", "reasoning_effort": "medium"},
        client=client,
        system_prompt_provider=lambda: "你是 VN。",
    )
    result = await provider.chat_result("请问候用户", [], [], "当前窗口：桌面")
    assert result.text == "Codex 回复"
    assert "你是 VN。" in client.text
    assert "当前窗口：桌面" in client.text
    assert client.attachments == []
    CodexAppServerProvider.validate_config({"model": "gpt-5.6-terra"})
