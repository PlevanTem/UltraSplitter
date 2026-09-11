# UltraSplitter

[English](README.md) | [简体中文](README.zh-CN.md)

UltraSplitter 将分栏图、角色多视图、联系表和简单背景的主体拼图，拆分成可独立访问的图片资产。它结合多模态判断与确定性像素处理，不假设输入图片一定是均匀排列的宫格。

> 当前状态：v0.1.0 已提供可用的确定性拆图工具，以及与供应商无关的生成式修复契约。工具本身尚未直接调用图片生成 API。

## 为什么需要 UltraSplitter

当分栏宽度不一致、标题文字位于边框外、主体散落分布，或多个检测框互相重叠时，均匀裁切会产生错误。UltraSplitter 将处理策略分为三类：

1. **原图裁切（Source crop）**——主体完整时，直接保留原图像素。
2. **原像素重排（Source composite）**——检测框重叠但前景轮廓可分离时，提取原始前景并放置到干净画布。
3. **生成式重建（Generated reconstruction）**——像素缺失或主体无法分离时，生成可审计的修复包；执行生成前必须由 Agent 获得用户批准。

## 真实测试案例

下面的四人物参考图由 UltraSplitter 实际处理。运行终态为 `success`：检测到 4 个分栏，4 张输出均采用 `source_crop`，保留原图像素，未使用生成式重建。

| 真实测试输入 | 实际拆分结果联系表 |
| --- | --- |
| <img src="docs/assets/real-gothic-input.png" alt="真实四人物分栏输入图" width="560"> | <img src="docs/assets/real-gothic-output-grid.png" alt="四张实际拆分结果的联系表" width="560"> |

| 输出 01 | 输出 02 | 输出 03 | 输出 04 |
| --- | --- | --- | --- |
| [<img src="docs/assets/real-gothic-output-01.png" alt="拆分结果 01" width="220">](docs/assets/real-gothic-output-01.png) | [<img src="docs/assets/real-gothic-output-02.png" alt="拆分结果 02" width="220">](docs/assets/real-gothic-output-02.png) | [<img src="docs/assets/real-gothic-output-03.png" alt="拆分结果 03" width="220">](docs/assets/real-gothic-output-03.png) | [<img src="docs/assets/real-gothic-output-04.png" alt="拆分结果 04" width="220">](docs/assets/real-gothic-output-04.png) |

点击任意输出图可查看原始分辨率版本。

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
