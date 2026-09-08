# VN 桌宠项目

本仓库维护两种使用 VN 角色的桌宠：

| 产品 | 用途 | 入口与目录 |
| --- | --- | --- |
| **VN Windows 桌宠** | 独立运行的 Windows 程序，支持拖动、文字气泡、主动陪伴和 Vue 设置窗口。 | 下文的启动说明；`codex_desktop_pet.py`、`vn_pet/`、`web_src/` 等现有目录。 |
| **VN Codex Pet** | 安装到 Codex 的角色素材，由 Codex 播放任务动作和注视方向。 | [Codex Pet 项目入口](codex-pet/README.md)；[A3 v3 成品与安装说明](codex-pet/packages/vn-a3-v3/README.md)。 |

两套产品的边界固定如下：

- Windows 桌宠只使用根目录的 `codex_desktop_pet.py`、`vn_pet/`、`web_src/`、`static/` 和根目录资源；它不读取 `codex-pet/`。
- Codex Pet 只使用 `codex-pet/` 内的配置、图集、预览、校验工具和开发文档；它不导入 `vn_pet/`，也不参与 Windows 桌宠启动。
- 修改或验证其中一套时，不需要重建、安装或启动另一套。Codex Pet 的预览本身是离线 HTML；校验工具仅是可选的开发检查。

因此，下面的安装与运行步骤只针对 Windows 桌宠。Codex Pet 的安装、预览和独立校验见 [Codex Pet 入口](codex-pet/README.md)。

## Windows 桌宠：启动与首次使用

双击 `启动Codex桌宠.bat`。左键拖动桌宠，右键只有 **设置** 和 **退出**；按 Esc 也可以退出桌宠。

生蛋动画：连续点击人物三次即可触发。

1. 右键 → **设置** → **AI 模型**，选择服务商后点「＋」。
2. 填写服务地址、模型名和需要的 API Key，点击 **保存配置**、**测试连接**，再点 **设为当前模型**。
3. 在 **VN 角色** 中修改人设并保存。
4. 在 **主动陪伴** 中点击 **立即触发一次**，检查桌宠旁的文字气泡；确认后开启自动陪伴。

如果希望使用 Codex 原生通道，在 **AI 模型** 中选择 **Codex 原生连接**，拉取并选择模型后保存、测试并启用即可。它通过本机 `codex app-server` 使用 Codex 的登录态，不需要单独填写 API Key；首次使用前请先在 Codex CLI 或桌面应用中登录。

设置窗口可以关闭和重新打开；关闭设置不会退出桌宠。重复启动程序不会创建第二只桌宠。模型与角色需要明确保存；陪伴及气泡选项在修改后延迟约 500 毫秒保存，失败会提示并恢复上次已保存的值。

## Windows 桌宠：设置内容

- **AI 模型**：迁移 Lin-pian-pian 的 27 个服务商模板，并增加 Codex 原生连接、配置新增/复制/删除、连接测试、模型列表与生成参数。当前启用的配置用于文字生成和可选的截图视觉。服务商的实际模型、套餐和能力以对应服务为准。
- **VN 角色**：名称、身份、性格、说话风格、示例对话、补充系统提示和最终提示词预览。仅编辑 VN，不包含人物工坊或多角色切换。
- **主动陪伴**：固定间隔、智能判断、检查间隔、最短/最长发言间隔、勿扰和手动触发。默认自动关闭，5 分钟检查，最短 10 分钟、最长 45 分钟；最长间隔用于智能判断，勿扰、全屏/媒体抑制和模型静默优先。
- **感知来源**：按开关读取窗口、空闲、节奏、应用类型、窗口切换、报错信号、时间、媒体/全屏和系统状态。OCR 与截图视觉默认关闭，截图默认不落盘。关闭自动陪伴后不再自动采集，手动触发会采集所选来源。
- **发言气泡**：默认 14 像素、最大宽度 340 像素、每页显示 10 秒。长文本分页，可点左右箭头翻页，也会按时自动翻至下一页。支持颜色、位置、字号、时长和桌面预览；点击气泡右上角 × 关闭。

本版本为文字陪伴，不含 TTS、聊天窗口、长期记忆或原项目用户数据导入。Codex 原生连接使用独立线程和只读沙箱，主动陪伴不会自动修改文件或执行需要审批的操作。只有实际显示的陪伴发言进入近期记录，预览和静默回复不计入记录。完整历史最多保留 100 条，独立模型模式生成参考最近 12 条。

## Windows 桌宠：数据与连接

数据保存在 `%LOCALAPPDATA%\VNDesktopPet`：

- `settings.json`：VN 的独立配置，包含本地保存的 API Key；请勿分享该文件。
- `history.json`：实际显示过的陪伴发言。
- `codex-thread.json`：Codex 原生连接使用的独立线程 ID。
- `app.log`：启动及桌面错误。
- `latest-screenshot.png`：只有打开“保存最近截图”且启用 OCR/视觉时才创建或更新。

界面中的 API Key 使用掩码；留空保存会保留已有密钥，开启“清空此配置的 API 密钥”才删除。屏幕 OCR 在本地处理，但识别文字会作为上下文发送给你配置的模型；截图视觉会发送截图。所有来源都可单独关闭。

设置服务仅监听随机的本机回环端口，并校验地址、来源和会话令牌。正常使用应从桌宠右键打开设置；直接在普通浏览器访问该地址不会获得设置会话。

## Windows 桌宠：开发与重新安装

Windows 10/11，Python 3.13（需 Tkinter）、Edge WebView2 Runtime。以下两种方式任选一种，在仓库根目录创建 Windows 桌宠专用 `.venv`；不会安装或修改 Codex Pet 的校验环境。

### 方式一：Python venv + pip

先安装包含 Tkinter 的 Python 3.13，在 PowerShell 中执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 可选 OCR
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
# 开发时安装，已包含运行依赖
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### 方式二：uv

如果尚未安装 uv，执行[官方安装命令](https://docs.astral.sh/uv/getting-started/installation/)，完成后重新打开终端：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

`.python-version` 指定 Python 3.13，uv 会在缺少该版本时自动下载。以下命令仍只创建和维护 Windows 桌宠的根 `.venv`：

```powershell
uv venv
uv pip install --python .venv -r requirements.txt
# 可选 OCR
uv pip install --python .venv -r requirements-ocr.txt
# 开发时安装，已包含运行依赖
uv pip install --python .venv -r requirements-dev.txt
```

uv 使用 pip 接口读取 requirements，尚未采用 `pyproject.toml` 和 `uv.lock`，因此不使用 `uv sync`；依赖仍按 requirements 中的版本约束解析。

### 启动与检查

已有 Python 3.13 的 `.venv` 时，跳过创建步骤，按所选方式安装依赖即可。两种方式都明确使用项目环境，无需激活；启动命令相同：

```powershell
.\.venv\Scripts\python.exe codex_desktop_pet.py
```

也可双击 `启动Codex桌宠.bat`，它会优先使用项目虚拟环境。

OCR 小模型随当前 RapidOCR wheel 提供；不会安装 PyTorch 或语音模型。RapidOCR 的安装及输出接口见[官方快速开始](https://rapidai.github.io/RapidOCRDocs/main/quickstart/)。

网页源码位于 `web_src`，构建产物位于 `static`。产物已随项目交付，日常运行不需要 Node；修改前端时执行：

```powershell
cd web_src
npm ci
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

按上述任一方式安装 `requirements-dev.txt` 后，在仓库根目录执行 Python 与 Windows 实机检查：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m tests.native_smoke
```

E2E 使用隔离临时目录和模拟模型，不读取真实密钥，不调用付费服务；实机检查会临时打开桌宠、气泡和设置窗口，并验证关闭及重新打开。真实模型连接需要在设置页填写有效的服务信息后测试。

## Codex Pet：独立使用

Codex Pet 不需要启动 Windows 桌宠，也不依赖 `vn_pet/`、WebView2 或根目录的设置服务。直接复制 `codex-pet/packages/vn-a3-v3/` 可安装成品；打开包内 `preview.html` 可离线预览。

如需验证成品文件，可使用 Codex Pet 自己的可选环境，不影响 Windows 桌宠：

```powershell
py -3.13 -m venv codex-pet/.venv
.\codex-pet\.venv\Scripts\python.exe -m pip install -r codex-pet/requirements-dev.txt
.\codex-pet\.venv\Scripts\python.exe codex-pet/tools/verify_package.py
```

验证工具只检查 Codex Pet 的图集、配置、批准哈希和包内资源引用；修改 Codex Pet 不需要运行 `pytest tests`、前端构建或 `tests.native_smoke`。

## Windows 桌宠：模块

`codex_desktop_pet.py` 持有 Tkinter 主线程。`vn_pet` 包含统一配置、模型适配、情境采集、主动陪伴、气泡及回环设置服务；WebView2 设置窗口运行于独立子进程。后台请求通过队列交付气泡，显示前复查任务版本，退出时统一取消任务并关闭服务及窗口。

迁移来源与适配范围见 `MIGRATION_NOTES.md`。
