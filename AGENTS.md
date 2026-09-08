# Repository Guidelines

## 项目结构与模块职责

本仓库包含 VN Windows 桌宠程序与 VN Codex Pet 素材，两者共用角色名称，分别维护。Windows 桌宠保留现有上游目录；Codex 素材工作集中在 `codex-pet/`。

Windows 桌宠的 `codex_desktop_pet.py` 管理 Tkinter 主线程。`vn_pet/` 是其 Python 模块，包含配置、情境采集、陪伴调度、气泡及 FastAPI 本机回环服务；`vn_pet/providers/` 存放模型适配器。WebView2 设置窗口运行于独立进程。

`web_src/src/` 存放 Vue/TypeScript 设置页源码，`web_src/e2e/` 存放浏览器测试，`tests/` 存放 Python 测试。`codex_pet_v2.png` 为桌宠精灵图。`static/` 是纳入版本控制的前端构建产物；修改前端源码后需重新构建并提交产物。修改迁移而来的集成功能前，先阅读 `MIGRATION_NOTES.md`。

处理 Codex 素材、设计文档或制作目录时，先阅读 [Codex Pet 开发规则](codex-pet/AGENTS.md)；目录入口为 `codex-pet/README.md`。这些工作的规则与检查在子目录内维护。

## 构建、测试与本地开发

根目录的环境和命令只服务于 Windows 桌宠；Codex Pet 的可选校验依赖和环境只放在 `codex-pet/`。

Agent 日常使用 uv 管理项目 `.venv`，安装与环境创建步骤见 `README.md`。更新开发依赖使用 `uv pip install --python .venv -r requirements-dev.txt`，运行与测试使用 `.\.venv\Scripts\python.exe`。依赖维护在 `requirements*.txt`，使用 uv 的 pip 接口，无需激活环境。

Windows 桌宠的前端命令在 `web_src/` 中执行：

- `npm ci`：按锁文件安装依赖。
- `npm run dev`：启动 Vite；设置页的身份验证依赖桌面桥接。
- `npm run typecheck`：检查 Vue 和 TypeScript 类型。
- `npm run test`：运行 Vitest 单元测试。
- `npm run build`：重新生成 `../static/`。
- `npm run test:e2e`：使用 Edge 和隔离的 Python 服务运行 Playwright；执行前先构建前端。

## 代码风格与命名

Python 使用四空格缩进，函数和模块使用 `snake_case`，类使用 `PascalCase`。Vue/TypeScript 使用两空格缩进，函数使用 `camelCase`，组件使用 `PascalCase`；修改时保持周边格式一致。项目尚未配置格式化或 lint 工具，TypeScript 启用严格检查。后台结果通过队列传递，Tkinter 界面更新必须在主线程执行。

## 测试规范

Windows 桌宠修改按影响范围运行 `.\.venv\Scripts\python.exe -m pytest tests -q`，测试文件命名为 `test_*.py`。Vitest 测试使用 `src/**/*.spec.ts`，Playwright 测试使用 `e2e/*.spec.ts`。目前没有覆盖率门槛；测试应使用临时存储并模拟模型调用。修改桌面窗口生命周期后，在 Windows 上运行 `.\.venv\Scripts\python.exe -m tests.native_smoke`；该检查会打开真实窗口。

## 提交与 Pull Request 规范

沿用近期功能与修复提交的格式：`<type>(<scope>): <中文祈使句描述>`，例如 `fix(launcher): 优先使用项目虚拟环境启动桌宠`。`type` 和 `scope` 使用小写英文术语。PR 应说明行为变化、关联相关 issue，并列出验证结果；涉及可见界面变化时附截图。

## 配置与本地数据

`%LOCALAPPDATA%\VNDesktopPet` 中的运行数据不应提交，其中 `settings.json` 含 API Key。修改设置服务时，保留本机回环监听和设置会话身份验证。
