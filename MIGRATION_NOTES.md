# 迁移来源

VN 外观与原始 Tkinter 窗口来自 [Mubai153/codex-desktop-pet](https://github.com/Mubai153/codex-desktop-pet)，原始提交 `289a265`。

以下功能按用户要求从本机 [AiNaer/Lin-pian-pian](https://github.com/AiNaer/Lin-pian-pian) 工作区提取；读取时 HEAD 为 `bb51b0dd`：

- `providers/llm` 的服务商注册表、工厂、Chat Completions / Responses / DeepSeek 适配器 → `vn_pet/providers`。仅替换项目内部配置与错误标记依赖，VN 不提供工具执行入口。
- `backend/services/activity_sources.py` → `vn_pet/activity_sources.py`。修正 Windows 空闲计时回绕、按当前显示器判断全屏和仅检测活跃音频会话。
- `backend/services/activity_manager.py` 的时机判断部分 → `vn_pet/activity_manager.py`。移除没有聊天反馈入口的反馈逻辑，并遵守时间感知开关。
- Vue `LlmSettingsSection`、模型类型及公共 settings 样式 → `web_src/src`。保留模型管理交互，移除聊天上下文设置，适配独立 VN 页面。

新增的配置存储、FastAPI 服务、Tkinter 气泡、窗口进程管理和五页设置容器在 VN 仓库内独立实现。原项目的用户配置、密钥、角色文件、数据库、历史、语音模型和运行状态均未复制。

截图文字识别使用支持本机 Python 3.13 的 `rapidocr==3.9.2` 与 ONNX Runtime；原 `rapidocr-onnxruntime==1.4.4` 限制 Python < 3.13，故采用兼容接口适配。
