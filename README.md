# VN 桌宠

Windows 像素桌宠，支持摇头动画、拖动、文字气泡、主动陪伴以及独立的 Vue 设置窗口。

另提供供 Codex 播放的 [VN A3 v3 素材包](codex-pet/packages/vn-a3-v3/README.md)，含完整图集、安装说明及离线预览，可独立于 Windows 桌宠程序使用。

## 启动与首次使用

双击 `启动Codex桌宠.bat`。左键拖动桌宠，右键只有 **设置** 和 **退出**；按 Esc 也可以退出桌宠。

1. 右键 → **设置** → **AI 模型**，选择服务商后点「＋」。
2. 填写服务地址、模型名和需要的 API Key，点击 **保存配置**、**测试连接**，再点 **设为当前模型**。
3. 在 **VN 角色** 中修改人设并保存。
4. 在 **主动陪伴** 中点击 **立即触发一次**，检查桌宠旁的文字气泡；确认后开启自动陪伴。

设置窗口可以关闭和重新打开；关闭设置不会退出桌宠。重复启动程序不会创建第二只桌宠。模型与角色需要明确保存；陪伴及气泡选项在修改后延迟约 500 毫秒保存，失败会提示并恢复上次已保存的值。

## 设置内容

- **AI 模型**：迁移 Lin-pian-pian 的 27 个服务商模板、配置新增/复制/删除、连接测试、模型列表与生成参数。当前启用的配置用于文字生成和可选的截图视觉。服务商的实际模型、套餐和能力以对应服务为准。
- **VN 角色**：名称、身份、性格、说话风格、示例对话、补充系统提示和最终提示词预览。仅编辑 VN，不包含人物工坊或多角色切换。
- **主动陪伴**：固定间隔、智能判断、检查间隔、最短/最长发言间隔、勿扰和手动触发。默认自动关闭，5 分钟检查，最短 10 分钟、最长 45 分钟；最长间隔用于智能判断，勿扰、全屏/媒体抑制和模型静默优先。
- **感知来源**：按开关读取窗口、空闲、节奏、应用类型、窗口切换、报错信号、时间、媒体/全屏和系统状态。OCR 与截图视觉默认关闭，截图默认不落盘。关闭自动陪伴后不再自动采集，手动触发会采集所选来源。
- **发言气泡**：默认 14 像素、最大宽度 340 像素、每页显示 10 秒。长文本分页，可点左右箭头翻页，也会按时自动翻至下一页。支持颜色、位置、字号、时长和桌面预览；点击气泡右上角 × 关闭。

本版本为文字陪伴，不含 TTS、聊天窗口、工具调用、长期记忆或原项目用户数据导入。只有实际显示的陪伴发言进入近期记录，预览和静默回复不计入记录。完整历史最多保留 100 条，生成参考最近 12 条。

## 数据与连接

数据保存在 `%LOCALAPPDATA%\VNDesktopPet`：

- `settings.json`：VN 的独立配置，包含本地保存的 API Key；请勿分享该文件。
- `history.json`：实际显示过的陪伴发言。
- `app.log`：启动及桌面错误。
- `latest-screenshot.png`：只有打开“保存最近截图”且启用 OCR/视觉时才创建或更新。

界面中的 API Key 使用掩码；留空保存会保留已有密钥，开启“清空此配置的 API 密钥”才删除。屏幕 OCR 在本地处理，但识别文字会作为上下文发送给你配置的模型；截图视觉会发送截图。所有来源都可单独关闭。

设置服务仅监听随机的本机回环端口，并校验地址、来源和会话令牌。正常使用应从桌宠右键打开设置；直接在普通浏览器访问该地址不会获得设置会话。

## 开发与重新安装

Windows 10/11，Python 3.13（需 Tkinter）、Edge WebView2 Runtime。以下两种方式任选一种，均在仓库根目录创建 `.venv`，依赖统一维护在 `requirements*.txt`；无需启动原 Lin-pian-pian 项目。

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

`.python-version` 指定 Python 3.13，uv 会在缺少该版本时自动下载：

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

## 模块

`codex_desktop_pet.py` 持有 Tkinter 主线程。`vn_pet` 包含统一配置、模型适配、情境采集、主动陪伴、气泡及回环设置服务；WebView2 设置窗口运行于独立子进程。后台请求通过队列交付气泡，显示前复查任务版本，退出时统一取消任务并关闭服务及窗口。

迁移来源与适配范围见 `MIGRATION_NOTES.md`。
