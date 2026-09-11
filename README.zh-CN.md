# UltraSplitter

[English](README.md) | [简体中文](README.zh-CN.md)

UltraSplitter 将分栏图、角色多视图、联系表和简单背景的主体拼图，拆分成可独立访问的图片资产。它结合多模态判断与确定性像素处理，不假设输入图片一定是均匀排列的宫格。

> 当前状态：v0.1.0 已提供可用的确定性拆图工具，以及与供应商无关的生成式修复契约。工具本身尚未直接调用图片生成 API。

## 为什么需要 UltraSplitter

当分栏宽度不一致、标题文字位于边框外、主体散落分布，或多个检测框互相重叠时，均匀裁切会产生错误。UltraSplitter 将处理策略分为三类：

1. **原图裁切（Source crop）**——主体完整时，直接保留原图像素。
2. **原像素重排（Source composite）**——检测框重叠但前景轮廓可分离时，提取原始前景并放置到干净画布。
3. **生成式重建（Generated reconstruction）**——像素缺失或主体无法分离时，生成可审计的修复包；执行生成前必须由 Agent 获得用户批准。

## 实测案例

以下结果均由当前工作流实际运行产生。每个案例只展示一张输出联系表，所有预览统一使用 8:5 画布；点击输入或输出可打开完整图片。

| 案例与实测结果 | 输入 | 输出 |
| --- | --- | --- |
| **分布不均**<br>`success` · 4 个主体<br>4 个原图裁切，由多模态规划调整输出顺序；未生成任何像素。 | [<img src="docs/assets/case-uneven-input-preview.png" alt="分布不均的角色多视图输入" width="320">](docs/assets/case-uneven-input.png) | [<img src="docs/assets/case-uneven-output-preview.png" alt="4 张角色视图拆分结果" width="320">](docs/assets/case-uneven-output.png) |
| **数量多、排布杂**<br>视觉复核后 `success` · 11 个主体<br>6 个原图裁切 + 5 个原像素重排；规划阶段排除了 1 条边界线伪候选。 | [<img src="docs/assets/case-dense-input-preview.png" alt="高密度武器素材输入" width="320">](docs/assets/case-dense-input.png) | [<img src="docs/assets/case-dense-output-preview.png" alt="11 件武器拆分结果" width="320">](docs/assets/case-dense-output.png) |
| **边缘截断**<br>`awaiting_user_approval` · 8 个候选<br>识别到 6 个边缘截断候选并归入 2 个修复请求；未执行图片生成。 | [<img src="docs/assets/case-clipped-input-preview.png" alt="主体被画面边缘截断的输入" width="320">](docs/assets/case-clipped-input.png) | [<img src="docs/assets/case-clipped-output-preview.png" alt="等待修复批准的暂存拆分联系表" width="320">](docs/assets/case-clipped-output.png) |

## 能力优势

- **不依赖均匀宫格**——主体的位置、宽度、大小和间距不一致时，仍按内容边界定位。
- **适用于高密度素材图**——矩形框互相重叠但前景像素可分时，组合使用原图裁切与原像素重排。
- **让多模态模型只做关键判断**——宿主模型负责排除噪声、组合断开部件、命名排序和判断语义完整性，不让模型凭空填写像素坐标。
- **缺失内容不会静默放行**——遇到截断、遮挡或不可分离主体时，停在明确的用户批准关口，不把残缺素材当成成功结果交付。
- **保真且可追溯**——确定性路径保留原始像素；`manifest.json` 记录每张图的路由、源图坐标、评估、来源和绝对访问路径。
- **面向 Agent 集成**——CLI 与 Skill 契约可被 Codex、Claude Code 和其他多模态编码 Agent 调用，核心包不绑定单一图片生成供应商。

## 安装与运行

```bash
git clone https://github.com/PlevanTem/UltraSplitter.git
cd UltraSplitter
python -m pip install -e .
ultrasplit run input.png --name character-views
```

也可以显式执行 Agent 规划流程：

```bash
ultrasplit scan input.png --output-dir work/scan
ultrasplit apply input.png --scan work/scan/scan.json --plan work/plan.json --output-dir output/task
ultrasplit inspect output/task/manifest.json
```

对于需要生成式修复的结果：

```bash
ultrasplit repair prepare output/task/manifest.json
# 宿主 Agent 向用户展示修复请求，并等待批准。
ultrasplit repair approve output/task/manifest.json --group conflict-001
# 宿主根据修复包生成一张宫格图，再将结果交回工具：
ultrasplit repair ingest output/task/manifest.json --group conflict-001 --grid generated-grid.png
ultrasplit evaluate output/task/manifest.json --visual-verdict pass
```

## 架构

```text
图片 → 确定性扫描 → 多模态规划 → 路由
                                ├─ 原图裁切
                                ├─ 原像素重排
                                └─ 修复包 → 用户批准
                                                ↓
                                         外部图片生成
                                                ↓
                                  回流 → 拆图 → 评估 → 退出
```

每次运行都会写入 schema v3 的 `manifest.json`，记录准确的源图坐标、路由依据、来源追踪、批准状态、有界修复次数、评估结果和绝对访问路径。完整设计见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## AI 原生调用

仓库在 `skills/splitting-image-grids-by-content` 中提供兼容 Codex 的 Skill。Claude Code 和其他多模态编码 Agent 也可以调用相同的 CLI 契约。核心包不绑定具体模型供应商。

## 当前能力边界

- 支持带边框的分栏图，以及透明或近似纯色背景中空间分离的主体。
- 不执行复杂的语义实例分割。
- 生成式补全属于重建内容，不是对缺失原始像素的恢复。
- 对密集、透明、相互接触或被画面截断的情况，返回明确的复核或批准状态，不静默宣称成功。

## 路线图

- 在更大规模、授权清晰的基准集上校准前景冲突阈值。
- 增加供应商适配器，同时保持核心包不接触用户凭据。
- 增加独立的多模态身份一致性评分，并改进透明边缘处理。
- 仅在完成可复现评估后发布性能数据。

## 许可证

MIT
