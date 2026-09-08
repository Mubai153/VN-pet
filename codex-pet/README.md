# VN Codex Pet

这里维护供 Codex 播放的 VN 角色素材。它与仓库根目录的 **VN Windows 桌宠**是两个独立交付物：Windows 桌宠是可运行的陪伴程序，Codex Pet 是由 Codex 驱动的素材包。两者共用角色名称，代码与制作流程分别维护。

## 使用成品

当前成品为 [VN A3 v3](packages/vn-a3-v3/README.md)，含完整图集、配置、安装说明和[离线预览](packages/vn-a3-v3/preview.html)。直接复制 `packages/vn-a3-v3/` 即可使用，不需要制作工作区。

## 继续开发

Agent 工作规则见 [AGENTS.md](AGENTS.md)，仅适用于本目录。

先读[决策记录](docs/decisions.md)，再读[制作流程](docs/production.md)。A3 v3 的[规格](design/vn-a3-v3/spec.md)与[主形象](design/vn-a3-v3/master.png)共同约束后续制作；[发布记录](releases/vn-a3-v3.json)记录已批准成品的哈希与已接受的细节。

```text
codex-pet/
├── AGENTS.md                  Codex 素材开发规则与检查入口
├── CONTEXT.md                 术语：角色、程序、素材包和制作阶段
├── docs/                      重要决策与持续开发流程
├── design/<版本>/             已确认主形象与制作规格
├── packages/<包 ID>/          可独立安装、预览的最终产物
├── releases/<包 ID>.json       验收摘要及成品、主形象哈希
├── tools/                     可复用的成品检查工具
└── .work/                     本地制作区，不纳入 Git
    ├── references/            原始参考照片
    ├── prototypes/            视觉方向探索与对比
    ├── design-reviews/        主形象迭代、校准与审查
    ├── production/            动画制作、提示、中间图集与逐轮 QA
    ├── exports/               本地压缩包及旧交付副本
    ├── archive/               已结束的旧方案、脚本与文档原件
    ├── review/                本次 commit、PR 草稿
    └── migration/             本地迁移映射与完整性记录
```

Git 保留成品及继续开发需要的稳定依据；过程材料统一进入 `.work/`。只有本目录的 `.gitignore` 排除 `.work/`，不修改上游的忽略规则。新克隆没有 `.work/` 仍可使用、预览和核验成品；需要原始制作材料时从本地归档或备份恢复。原型和历史记录不会自动成为后续版本的设计依据。

从仓库根目录运行成品检查：

```powershell
.\.venv\Scripts\python.exe codex-pet/tools/verify_package.py
```

Python 环境与依赖安装见[仓库 README](../README.md)。检查只依赖 Python 与 Pillow；它验证素材结构及已批准哈希，不替代动作观感验收。
