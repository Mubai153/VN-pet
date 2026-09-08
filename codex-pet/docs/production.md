# Codex Pet 持续开发流程

## 两个产品的边界

**VN Windows 桌宠**由根目录的 `codex_desktop_pet.py` 启动，`vn_pet/` 是它的 Python 实现，`web_src/`、`static/`、`tests/` 服务于该程序。保留这些上游路径和现有导入关系。

**VN Codex Pet**仅在 `codex-pet/` 中维护，交付配置和角色图集，不复用 `vn_pet/` 作为素材目录。包 ID `vn-a3-v3` 是 Codex 的角色标识，与 Python 模块名无关。术语见 [CONTEXT.md](../CONTEXT.md)。

## 资料归属

| 内容 | 位置 | 生命周期与 Git 范围 |
| --- | --- | --- |
| 用户已确认的范围、撤回和替代关系 | `docs/decisions.md` | 纳入 Git；就地更新当前状态，保留重要历史编号。 |
| 已选主形象与当前规格 | `design/<版本>/` | 纳入 Git；候选确认后提升到此处，不能用未选候选覆盖。 |
| 可安装图集、配置与离线预览 | `packages/<包 ID>/` | 纳入 Git；所有运行资源在包内，不能引用 `.work/` 或机器绝对路径。 |
| 验收摘要、来源与哈希 | `releases/<包 ID>.json` | 纳入 Git；内容与成品对应，保留已接受的限制。 |
| 多轮提示、生成素材、草稿、服务日志、原始 QA | `.work/` 对应子目录 | 仅本地；需要备份时单独备份，不通过 Git 保存。 |
| 压缩包与历史交付副本 | `.work/exports/` | 仅本地；正式源文件以 `packages/` 为准，避免 ZIP 与解压副本重复进入仓库。 |

`.work/production/vn-b3-paused/` 保留 B3 的暂停现场；`.work/archive/a3-v2-production/` 保存旧 A3，`.work/archive/initial-single-pet/` 保存早期单套探索。它们不代表当前授权或当前主形象。历史 JSON 保持原样，其中的旧绝对路径可通过本地 `.work/migration/manifest.json` 查找新位置。

## 从设计到成品

1. **确定版本与范围。** 阅读决策和已有发布记录。新版本在 `.work/production/<版本>/` 制作，原始参考放 `.work/references/`，对比方案放 `.work/prototypes/`，主形象审查放 `.work/design-reviews/`。
2. **固定设计基准。** 确认主形象后，将唯一采用图及规格整理到 `design/<版本>/`；被撤回或未选的图继续留在 `.work/`。记录与上一版本的关系，避免旧脸、新动作和新脸、旧动作混用。
3. **完成动作及审查。** 生成、提取、注册、组装和逐轮 QA 均在制作目录内进行。对照规格检查 9 组动作、16 个方向、主形象一致性和循环；保留来源及验收证据。不能从成品图集恢复已清理的生成条带，也不把历史脚本描述为完整可复现流水线。
4. **提升最终产物。** 将确认的 `pet.json`、`spritesheet.webp`、安装说明及可独立打开的预览整理到 `packages/<包 ID>/`。本项目保留旧包时使用不同 ID；预览只引用包内资源。
5. **记录与核验。** 在 `releases/` 写入包 ID、设计版本、图集契约、批准日期、成品及主形象 SHA-256、已接受的细微差异。运行检查工具，并用浏览器从包目录直接打开预览，检查播放、逐帧与鼠标注视。文件变化应来自新的制作结果；不能仅更新哈希来掩盖未确认的素材变化。
6. **归档与交付。** 更新决策中的当前版本与状态，将结束的旧制作目录移入 `.work/archive/`；需下载 ZIP 时从对应包目录导出到 `.work/exports/`。提交稳定依据和成品。安装到个人 Codex 是独立操作，不由整理或打包隐含执行。

## 检查命令

从仓库根目录执行；使用 Codex Pet 的独立校验环境，默认检查全部已登记成品，也可指定一个包：

```powershell
.\codex-pet\.venv\Scripts\python.exe codex-pet/tools/verify_package.py
.\codex-pet\.venv\Scripts\python.exe codex-pet/tools/verify_package.py vn-a3-v3
```

检查包括发布记录与包对应关系、配置和主形象哈希、图集尺寸与透明度、有效及空白槽位、包内链接和预览图集引用。它不启动浏览器，也不代替视觉判断。

## 本地目录迁移

2026-09-08 将散落的 `pets/`、`docs/codex-pet/`、根 `CONTEXT.md`、照片目录和 `output/` 中的 Codex Pet 制作材料集中到本目录。没有移动 Windows 桌宠的上游文件。

原始路径、迁移前哈希与新位置存于本地 `.work/migration/manifest.json`；迁移过程只修复需要继续使用的文档及预览引用，原始 QA JSON 和图片保持原字节。归档里已有缺失的生成条带、机器相关辅助脚本和旧端口说明属于历史现场，不是正式交付依赖。后续维护以本页、决策、设计及发布记录为入口。
