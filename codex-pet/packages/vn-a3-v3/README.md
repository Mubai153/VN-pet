# VN · 圆润版（A3 v3）

供 Codex 使用的 VN 像素桌宠，穿红色连帽衫，包含空闲、左右小跑、招手、跳跃、受阻、等待、工作、查看结果等 9 组动作，以及 16 个注视方向。

本目录是完整的正式交付内容，可独立复制使用。角色 ID 为 `vn-a3-v3`，设计修订号为 v3，图集契约为 `spriteVersionNumber: 2`。它与仓库中的独立 Windows 桌宠程序分别运行。

## 预览

用浏览器直接打开 [preview.html](preview.html)，保持它与图集同目录即可，无需安装 Python 或 Node。可切换动作、暂停、逐帧查看、调整大小与背景；选择“注视方向”后移动鼠标体验方向变化。

## 安装

1. 下载或克隆仓库，找到 `codex-pet/packages/vn-a3-v3/`。
2. 将整个 `vn-a3-v3` 文件夹复制到 `$CODEX_HOME/pets/`。未设置 `CODEX_HOME` 时，Windows 默认目录为 `%USERPROFILE%\.codex\pets\vn-a3-v3\`。
3. 保持 `pet.json` 与 `spritesheet.webp` 同目录，在 Codex 的桌宠选择界面选择“VN · 圆润版”。

此目录不包含自动安装脚本。ID `vn-a3-v3` 与旧 A3 的 `vn-a3` 不同，可与旧版同时保留。

## 文件与验证

| 文件 | 用途 |
| --- | --- |
| [pet.json](pet.json) | 角色 ID、名称及图集版本配置。 |
| [spritesheet.webp](spritesheet.webp) | 1536×2288 透明图集，8 列×11 行，单格 192×208。 |
| [preview.html](preview.html) | 无外部依赖的动作播放器。 |

图集包含 57 个标准动作帧、16 个方向和 1 个中立参考，其余槽位为空。2026-09-08 的本地验收记录已确认此图集；本目录的图集与批准文件逐字节一致，SHA-256 为：

```text
07d0476b962facaf882c8edf3ddc9dfa12aa1d68f3c7d77f8992575ac883ef44
```

预览用于展示素材，实际播放节奏及状态触发由 Codex 控制。空闲呼吸较轻，部分相邻斜向注视差异较小，这些细节已在制作验收时接受。源照片、生成过程、历史方案及逐轮检查记录保留在本地制作归档，不是安装或预览所需文件。
