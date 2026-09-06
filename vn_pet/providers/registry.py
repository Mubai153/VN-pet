from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMFieldSpec:
    key: str
    label: str
    kind: str = "text"
    placeholder: str = ""
    step: str = ""
    required: bool = False
    options: tuple[str, ...] = ()

    def to_public(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.kind,
            "placeholder": self.placeholder,
            "step": self.step,
            "required": self.required,
            "options": list(self.options),
        }


@dataclass(frozen=True)
class LLMProviderSpec:
    id: str
    label: str
    transport: str
    description: str
    fields: tuple[LLMFieldSpec, ...]
    vendor_id: str = ""
    billing_mode: str = "payg"
    credential_hint: str = ""
    usage_notice: str = ""
    default_config: dict[str, Any] = field(default_factory=dict)
    requires_api_key: bool = True
    supports_vision: bool = False
    supports_native_tools: bool = False
    recommended_models: tuple[str, ...] = ()
    can_fetch_models: bool = True
    request_timeout_s: float = 60.0

    def public_fields(self) -> list[dict[str, Any]]:
        return [item.to_public() for item in self.fields]


CHAT_COMMON_FIELDS = (
    LLMFieldSpec("base_url", "URL 地址", "text", "https://example.com/v1", required=True),
    LLMFieldSpec("models_url", "模型目录 URL（可选）", "text", "留空时根据 URL 地址推导"),
    LLMFieldSpec("api_key", "API Key", "password", "留空保持原密钥不变"),
    LLMFieldSpec("model", "模型名", "text", "model-name", required=True),
    LLMFieldSpec("context_length", "上下文窗口 Token（留空自动识别）", "number", "自动识别", required=False),
    LLMFieldSpec("max_tokens", "最大 Token", "number", "512", required=False),
    LLMFieldSpec("temperature", "Temperature", "number", "0.8", "0.1"),
    LLMFieldSpec("top_p", "Top P", "number", "1.0", "0.1"),
)


REASONING_CHAT_FIELDS = CHAT_COMMON_FIELDS[:5] + (
    LLMFieldSpec("reasoning_effort", "推理强度", "select", "high", options=("low", "medium", "high")),
) + CHAT_COMMON_FIELDS[5:]

CODEX_FIELDS = (
    LLMFieldSpec("model", "模型名", "text", "gpt-5.6-terra", required=True),
    LLMFieldSpec("reasoning_effort", "推理强度", "select", "medium", options=("low", "medium", "high", "xhigh", "max", "ultra")),
)


KIMI_CODEPLAN_FIELDS = (
    LLMFieldSpec("base_url", "URL 地址", "text", "https://api.kimi.com/coding/v1", required=True),
    LLMFieldSpec("models_url", "模型目录 URL（可选）", "text", "留空时根据 URL 地址推导"),
    LLMFieldSpec("api_key", "API Key", "password", "留空保持原密钥不变"),
    LLMFieldSpec("model", "模型名", "text", "k3-256k", required=True),
    LLMFieldSpec("context_length", "上下文窗口 Token（留空自动识别）", "number", "自动识别"),
    LLMFieldSpec("reasoning_effort", "推理强度", "text", "high"),
    LLMFieldSpec("max_tokens", "最大 Token", "number", "512"),
)


LLM_PROVIDER_SPECS: dict[str, LLMProviderSpec] = {
    "deepseek": LLMProviderSpec(
        id="deepseek",
        label="DeepSeek",
        transport="chat_completions",
        description="DeepSeek 官方或兼容 Chat Completions 接口。",
        fields=(
            LLMFieldSpec("api_url", "URL 地址", "text", "https://api.deepseek.com/v1/chat/completions", required=True),
            LLMFieldSpec("models_url", "模型目录 URL（可选）", "text", "留空时根据 URL 地址推导"),
            LLMFieldSpec("api_key", "API Key", "password", "留空保持原密钥不变"),
            LLMFieldSpec("model", "模型名", "text", "deepseek-v4-flash", required=True),
            LLMFieldSpec("context_length", "上下文窗口 Token（留空自动识别）", "number", "自动识别"),
            LLMFieldSpec("thinking_enabled", "开启思考模式", "checkbox"),
            LLMFieldSpec("reasoning_effort", "思考强度", "select", "high", options=("low", "high", "max")),
            LLMFieldSpec("max_tokens", "最大 Token（含思考与最终回答）", "number", "8192"),
            LLMFieldSpec("temperature", "Temperature", "number", "0.9", "0.1"),
            LLMFieldSpec("top_p", "Top P", "number", "1.0", "0.1"),
        ),
        default_config={
            "api_url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-v4-flash",
            "thinking_enabled": True,
            "reasoning_effort": "high",
            "max_tokens": 8192,
            "temperature": 0.9,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("deepseek-v4-flash", "deepseek-v4-pro"),
    ),
    "gpt": LLMProviderSpec(
        id="gpt",
        label="GPT / OpenAI",
        transport="responses",
        description="OpenAI Responses API，支持截图视觉和文件输入。",
        fields=(
            LLMFieldSpec("base_url", "URL 地址", "text", "https://api.openai.com/v1", required=True),
            LLMFieldSpec("models_url", "模型目录 URL（可选）", "text", "留空时根据 URL 地址推导"),
            LLMFieldSpec("api_key", "API Key", "password", "留空保持原密钥不变"),
            LLMFieldSpec("model", "模型名", "text", "gpt-5.5", required=True),
            LLMFieldSpec("context_length", "上下文窗口 Token（留空自动识别）", "number", "自动识别"),
            LLMFieldSpec("reasoning_effort", "推理强度", "text", "high"),
            LLMFieldSpec("max_output_tokens", "最大输出 Token", "number", "512"),
        ),
        default_config={
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.5",
            "wire_api": "responses",
            "reasoning_effort": "high",
            "max_output_tokens": 512,
        },
        requires_api_key=True,
        supports_vision=True,
        recommended_models=("gpt-5.5", "gpt-5.1", "gpt-4.1"),
    ),
    "codex_app_server": LLMProviderSpec(
        id="codex_app_server",
        label="Codex 原生连接",
        transport="app_server",
        description="通过本机 Codex App Server 使用 Codex 登录态、线程和模型。",
        fields=CODEX_FIELDS,
        vendor_id="openai",
        credential_hint="使用本机 Codex 登录态，无需单独 API Key",
        usage_notice="桌宠使用独立 Codex 线程和只读沙箱；请先在 Codex CLI 或桌面应用中登录。",
        default_config={"model": "gpt-5.6-terra", "reasoning_effort": "medium"},
        requires_api_key=False,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"),
    ),
    "openrouter": LLMProviderSpec(
        id="openrouter",
        label="OpenRouter",
        transport="chat_completions",
        description="OpenRouter 聚合模型，使用 OpenAI 兼容接口。",
        fields=CHAT_COMMON_FIELDS,
        default_config={
            "base_url": "https://openrouter.ai/api/v1",
            "model": "openai/gpt-4.1",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=(
            "openai/gpt-4.1",
            "anthropic/claude-sonnet-4",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-chat",
            "qwen/qwen3-235b-a22b",
        ),
    ),
    "claude": LLMProviderSpec(
        id="claude",
        label="Claude-compatible",
        transport="chat_completions",
        description="支持 Claude 模型的 OpenAI-compatible Chat Completions 接口。",
        fields=CHAT_COMMON_FIELDS,
        default_config={
            "base_url": "https://example.com/v1",
            "model": "claude-sonnet-4-6",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        recommended_models=(
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "claude-fable-5",
            "claude-haiku-4-5",
        ),
    ),
    "stepfun": LLMProviderSpec(
        id="stepfun",
        label="阶跃星辰（按量）",
        transport="chat_completions",
        description="阶跃星辰 StepFun 官方 OpenAI 兼容接口，支持视觉、工具和推理参数。",
        fields=REASONING_CHAT_FIELDS,
        vendor_id="stepfun",
        billing_mode="payg",
        credential_hint="阶跃星辰开放平台 API Key",
        usage_notice="按量 API 根据实际输入输出 Token 计费；Step Plan 订阅请使用独立的 Step Plan 配置。",
        default_config={
            "base_url": "https://api.stepfun.com/v1",
            "model": "step-3.7-flash",
            "reasoning_effort": "high",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("step-3.7-flash", "step-3.7", "step-2-mini"),
    ),
    "stepfun_tokenplan": LLMProviderSpec(
        id="stepfun_tokenplan",
        label="阶跃星辰 Step Plan",
        transport="chat_completions",
        description="阶跃星辰 Step Plan 专用 OpenAI 兼容接口，使用独立的订阅额度配置。",
        fields=REASONING_CHAT_FIELDS,
        vendor_id="stepfun",
        billing_mode="token_plan",
        credential_hint="阶跃星辰 Step Plan API Key",
        usage_notice="Step Plan 使用订阅 Credit 配额，与普通按量 API profile 分开；请确认使用 Step Plan 专用地址。",
        default_config={
            "base_url": "https://api.stepfun.com/step_plan/v1",
            "model": "step-3.7-flash",
            "reasoning_effort": "high",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("step-3.7-flash",),
        can_fetch_models=False,
        request_timeout_s=600.0,
    ),
    "longcat": LLMProviderSpec(
        id="longcat",
        label="美团龙猫（按量）",
        transport="chat_completions",
        description="美团龙猫 LongCat 官方 OpenAI 兼容接口，当前提供 LongCat-2.0 文本模型。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="longcat",
        billing_mode="payg",
        credential_hint="美团龙猫 API Key",
        usage_notice="按量 API 按实际 Token 计费；Token Pack 采用独立套餐配置，官方允许两种模式共用物理 Key。",
        default_config={
            "base_url": "https://api.longcat.chat/openai/v1",
            "model": "LongCat-2.0",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=False,
        supports_native_tools=False,
        recommended_models=("LongCat-2.0",),
    ),
    "longcat_tokenplan": LLMProviderSpec(
        id="longcat_tokenplan",
        label="美团龙猫 Token Pack",
        transport="chat_completions",
        description="美团龙猫 Token Pack 套餐的 OpenAI 兼容接口，与按量 API 独立建模。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="longcat",
        billing_mode="token_plan",
        credential_hint="美团龙猫 Token Pack API Key",
        usage_notice="Token Pack 为固定 Token 套餐（有效期以官方规则为准），与按量 API 额度分开；可手动填入同一物理 Key。",
        default_config={
            "base_url": "https://api.longcat.chat/openai/v1",
            "model": "LongCat-2.0",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=False,
        supports_native_tools=False,
        recommended_models=("LongCat-2.0",),
    ),
    "hunyuan": LLMProviderSpec(
        id="hunyuan",
        label="腾讯混元（按量）",
        transport="chat_completions",
        description="腾讯混元官方 OpenAI 兼容接口，支持视觉和函数调用。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="hunyuan",
        billing_mode="payg",
        credential_hint="腾讯混元 API Key",
        usage_notice="普通混元 API 按量计费；Hy Token Plan 使用独立套餐地址和 profile。",
        default_config={
            "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
            "model": "hunyuan-turbos-latest",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("hunyuan-turbos-latest", "hunyuan-vision", "hunyuan-functioncall"),
        can_fetch_models=False,
    ),
    "hunyuan_tokenplan": LLMProviderSpec(
        id="hunyuan_tokenplan",
        label="腾讯混元 Hy Token Plan",
        transport="chat_completions",
        description="腾讯混元 Hy Token Plan 的 OpenAI 兼容接口，使用 sk-tp-* 套餐 Key。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="hunyuan",
        billing_mode="token_plan",
        credential_hint="腾讯混元 Hy Token Plan Key（sk-tp-*）",
        usage_notice="Hy Token Plan 与通用混元 API 共用 sk-tp-* 物理 Key，但地址、套餐额度和 profile 独立。该模式不提供多模态输入。",
        default_config={
            "base_url": "https://api.lkeap.cloud.tencent.com/plan/v3",
            "model": "hy3-preview",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("hy3-preview",),
        can_fetch_models=False,
    ),
    "gemini": LLMProviderSpec(
        id="gemini",
        label="Gemini",
        transport="chat_completions",
        description="Google Gemini API 的 OpenAI 兼容 Chat Completions 接口。",
        fields=REASONING_CHAT_FIELDS,
        vendor_id="gemini",
        billing_mode="payg",
        credential_hint="Google AI Studio API Key",
        usage_notice="Gemini API 独立按量计费；Google AI Pro/Ultra 产品订阅不提供本应用可直接使用的自定义 API Token Plan。",
        default_config={
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-3.5-flash",
            "reasoning_effort": "high",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("gemini-3.5-flash", "gemini-3.5-pro", "gemini-2.5-flash"),
    ),
    "grok": LLMProviderSpec(
        id="grok",
        label="Grok / xAI",
        transport="chat_completions",
        description="xAI Grok 官方 Chat Completions 接口，支持视觉、工具和推理参数。",
        fields=REASONING_CHAT_FIELDS,
        vendor_id="xai",
        billing_mode="payg",
        credential_hint="xAI API Key",
        usage_notice="xAI API 独立按量计费；SuperGrok 等产品订阅不提供可供自定义应用使用的 API Token Plan。推理请求可能需要更长等待时间。",
        default_config={
            "base_url": "https://api.x.ai/v1",
            "model": "grok-4.6",
            "reasoning_effort": "high",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("grok-4.6", "grok-4", "grok-3-mini"),
        request_timeout_s=3600.0,
    ),
    "qwen": LLMProviderSpec(
        id="qwen",
        label="阿里百炼（按量）",
        transport="chat_completions",
        description="阿里云百炼 DashScope OpenAI 兼容接口。截图/图片能力需选择 Qwen-VL 系列等视觉模型。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="qwen",
        billing_mode="payg",
        credential_hint="百炼按量 API Key（通常以 sk- 或 sk-ws- 开头）",
        default_config={
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("qwen-plus", "qwen-max", "qwen-turbo", "qwen-vl-plus"),
    ),
    "qwen_codingplan": LLMProviderSpec(
        id="qwen_codingplan",
        label="阿里百炼 Coding Plan",
        transport="chat_completions",
        description="阿里云百炼 Coding Plan 的 OpenAI 兼容接口，与按量和 Token Plan 凭据不互通。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="qwen",
        billing_mode="coding_plan",
        credential_hint="Coding Plan 专属 API Key（sk-sp-...）",
        usage_notice="官方仅允许在支持的交互式编程工具中使用，禁止用于自定义应用后端、自动化脚本或批量调用。",
        default_config={
            "base_url": "https://coding.dashscope.aliyuncs.com/v1",
            "model": "qwen3.7-plus",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=(
            "qwen3.7-plus",
            "qwen3.6-plus",
            "kimi-k2.5",
            "glm-5",
            "MiniMax-M2.5",
            "qwen3.5-plus",
            "qwen3-max-2026-01-23",
            "qwen3-coder-next",
            "qwen3-coder-plus",
            "glm-4.7",
        ),
        can_fetch_models=False,
    ),
    "qwen_tokenplan": LLMProviderSpec(
        id="qwen_tokenplan",
        label="阿里百炼 Token Plan",
        transport="chat_completions",
        description="阿里云百炼 Token Plan 的 OpenAI 兼容接口，与按量和 Coding Plan 凭据不互通。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="qwen",
        billing_mode="token_plan",
        credential_hint="Token Plan 专属 API Key（sk-sp-...）",
        usage_notice="官方仅允许在支持的交互式编程或智能体工具中使用，禁止用于自定义应用后端、自动化脚本或批量调用。",
        default_config={
            "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.8-max",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=(
            "qwen3.8-max",
            "qwen3.7-max",
            "qwen3.7-plus",
            "qwen3.6-flash",
            "deepseek-v4-pro",
            "deepseek-v4-pro-0813",
            "deepseek-v4-flash-0731",
            "glm-5.2",
        ),
        can_fetch_models=False,
    ),
    "kimi": LLMProviderSpec(
        id="kimi",
        label="Kimi / Moonshot（按量）",
        transport="chat_completions",
        description="Moonshot / Kimi 中国区 OpenAI 兼容接口。国际区账号可将 URL 改为 https://api.moonshot.ai/v1。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="kimi",
        billing_mode="payg",
        credential_hint="Moonshot 开放平台按量 API Key",
        default_config={
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k2-0711-preview",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=(
            "kimi-k2-0711-preview",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ),
    ),
    "kimi_codeplan": LLMProviderSpec(
        id="kimi_codeplan",
        label="Kimi Code（会员）",
        transport="chat_completions",
        description="Kimi Code 会员订阅的 OpenAI 兼容接口，与 Moonshot 按量平台的 API Key 不通用。",
        fields=KIMI_CODEPLAN_FIELDS,
        vendor_id="kimi",
        billing_mode="coding_plan",
        credential_hint="Kimi Code 会员专属 API Key",
        usage_notice="Kimi Code 会员权益面向编程工具；普通产品或服务集成应使用 Kimi 开放平台按量接口。",
        default_config={
            "base_url": "https://api.kimi.com/coding/v1",
            "model": "k3-256k",
            "reasoning_effort": "high",
            "max_tokens": 512,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=(
            "k3-256k",
            "k3",
            "kimi-for-coding",
            "kimi-for-coding-highspeed",
        ),
    ),
    "glm": LLMProviderSpec(
        id="glm",
        label="GLM / 智谱（按量）",
        transport="chat_completions",
        description="智谱 AI OpenAI 兼容接口。截图/图片能力需选择 GLM-4V 系列等视觉模型。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="glm",
        billing_mode="payg",
        credential_hint="智谱开放平台按量 API Key",
        default_config={
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4-plus",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("glm-4-plus", "glm-4.5", "glm-4.5-air", "glm-4v-plus"),
    ),
    "glm_codingplan": LLMProviderSpec(
        id="glm_codingplan",
        label="GLM Coding Plan",
        transport="chat_completions",
        description="GLM Coding Plan 的 OpenAI Chat Completions 接口，与按量平台凭据分开配置。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="glm",
        billing_mode="coding_plan",
        credential_hint="GLM Coding Plan 专属 API Key",
        usage_notice="官方仅允许在支持的指定编程工具与产品环境中使用。",
        default_config={
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "model": "glm-5.3",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("glm-5.3", "glm-5.3[1m]", "glm-4.7"),
        can_fetch_models=False,
    ),
    "mimo": LLMProviderSpec(
        id="mimo",
        label="MiMo / 小米（按量）",
        transport="chat_completions",
        description="小米 MiMo OpenAI 兼容 Chat Completions 接口。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="mimo",
        billing_mode="payg",
        credential_hint="小米 MiMo 按量 API Key（sk-...）",
        default_config={
            "base_url": "https://api.xiaomimimo.com/v1",
            "model": "mimo-v2.5-pro",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("mimo-v2.5-pro",),
    ),
    "mimo_tokenplan": LLMProviderSpec(
        id="mimo_tokenplan",
        label="MiMo Token Plan",
        transport="chat_completions",
        description="小米 MiMo Token Plan 的 OpenAI 兼容接口，使用独立的订阅凭据。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="mimo",
        billing_mode="token_plan",
        credential_hint="MiMo Token Plan 专属 API Key（tp-...）",
        default_config={
            "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
            "model": "mimo-v2.5-pro",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("mimo-v2.5-pro",),
        can_fetch_models=False,
    ),
    "doubao": LLMProviderSpec(
        id="doubao",
        label="豆包 / 火山方舟（按量）",
        transport="chat_completions",
        description="火山方舟按量付费 OpenAI 兼容接口。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="doubao",
        billing_mode="payg",
        credential_hint="火山方舟按量 API Key",
        default_config={
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "model": "doubao-seed-2.1-turbo",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("doubao-seed-2.1-turbo", "doubao-seed-2.0-lite"),
        can_fetch_models=False,
    ),
    "doubao_codingplan": LLMProviderSpec(
        id="doubao_codingplan",
        label="火山方舟 Coding Plan",
        transport="chat_completions",
        description="火山方舟 Coding Plan 的 OpenAI 兼容接口；误用按量地址会产生额外费用。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="doubao",
        billing_mode="coding_plan",
        credential_hint="火山方舟 Coding Plan 使用的 API Key",
        usage_notice="官方套餐面向支持的编程工具；请确认 Base URL 含 /api/coding/v3，使用 /api/v3 会按量计费。",
        default_config={
            "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "model": "ark-code-latest",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
        },
        requires_api_key=True,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=(
            "ark-code-latest",
            "doubao-seed-2.1-turbo",
            "doubao-seed-2.0-lite",
            "minimax-m3",
            "glm-5.3",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "kimi-k2.7-code",
        ),
        can_fetch_models=False,
    ),
    "minimax": LLMProviderSpec(
        id="minimax",
        label="MiniMax（按量）",
        transport="chat_completions",
        description="MiniMax 中国区按量 OpenAI 兼容 Chat Completions 接口。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="minimax",
        billing_mode="payg",
        credential_hint="MiniMax 开放平台按量 API Key",
        default_config={
            "base_url": "https://api.minimaxi.com/v1",
            "model": "MiniMax-M3",
            "max_tokens": 512,
            "temperature": 1.0,
            "top_p": 0.95,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=(
            "MiniMax-M3",
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5",
            "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1",
            "MiniMax-M2.1-highspeed",
            "MiniMax-M2",
        ),
    ),
    "minimax_tokenplan": LLMProviderSpec(
        id="minimax_tokenplan",
        label="MiniMax Token Plan",
        transport="chat_completions",
        description="MiniMax Token Plan 的 OpenAI 兼容接口，与普通按量 API Key 不互通。",
        fields=CHAT_COMMON_FIELDS,
        vendor_id="minimax",
        billing_mode="token_plan",
        credential_hint="MiniMax Token Plan 订阅 Key（sk-cp-...）",
        default_config={
            "base_url": "https://api.minimaxi.com/v1",
            "model": "MiniMax-M3",
            "max_tokens": 512,
            "temperature": 1.0,
            "top_p": 0.95,
        },
        requires_api_key=True,
        supports_vision=True,
        supports_native_tools=True,
        recommended_models=("MiniMax-M3",),
    ),
    "custom": LLMProviderSpec(
        id="custom",
        label="自定义接口",
        transport="chat_completions",
        description="任意 OpenAI-compatible Chat Completions 接口。",
        fields=CHAT_COMMON_FIELDS + (
            LLMFieldSpec("supports_vision", "支持视觉", "checkbox"),
        ),
        default_config={
            "base_url": "https://example.com/v1",
            "model": "",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
            "supports_vision": False,
        },
        requires_api_key=False,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=(),
    ),
    "local": LLMProviderSpec(
        id="local",
        label="本地模型",
        transport="chat_completions",
        description="LM Studio、Ollama、llama.cpp 等本地 OpenAI-compatible 服务。",
        fields=CHAT_COMMON_FIELDS + (
            LLMFieldSpec("supports_vision", "支持视觉", "checkbox"),
        ),
        default_config={
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "",
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 1.0,
            "supports_vision": False,
        },
        requires_api_key=False,
        supports_vision=False,
        supports_native_tools=True,
        recommended_models=("qwen3:14b", "llama3.1:8b", "gemma3:12b"),
    ),
}


def provider_ids() -> tuple[str, ...]:
    return tuple(LLM_PROVIDER_SPECS.keys())


def require_provider_spec(provider_id: str) -> LLMProviderSpec:
    provider = str(provider_id or "").strip().lower()
    spec = LLM_PROVIDER_SPECS.get(provider)
    if spec is None:
        raise ValueError(f"Unsupported LLM provider: {provider_id}")
    return spec


def provider_default_config(provider_id: str) -> dict[str, Any]:
    return dict(require_provider_spec(provider_id).default_config)


def merged_provider_config(provider_id: str, config: dict[str, Any] | None) -> dict[str, Any]:
    merged = provider_default_config(provider_id)
    if isinstance(config, dict):
        merged.update(config)
    return merged


def is_native_tools_supported(provider_id: str) -> bool:
    return bool(require_provider_spec(provider_id).supports_native_tools)


def is_vision_supported(provider_id: str, config: dict[str, Any] | None = None) -> bool:
    spec = require_provider_spec(provider_id)
    if isinstance(config, dict) and "supports_vision" in config:
        return bool(config.get("supports_vision"))
    return bool(spec.supports_vision)
