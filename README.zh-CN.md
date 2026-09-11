# UltraSplitter

[English](README.md) | [简体中文](README.zh-CN.md)

**把 AIGC 生成的整张方案图，变成生产流程真正能用的独立资产。**

图片模型很擅长在一张图里展示一组创意：UI 图标、武器合集、角色多视图、建筑立面、家具方案、产品变体。整图看起来已经完成，但里面的素材仍被锁在一个位图文件中。间距不均、尺寸混杂、文字边框、轮廓相接和主体截断，都会让均匀切图失效。

> 当前状态：v0.1.0 已提供可用的确定性拆图工具，以及与供应商无关的生成式修复契约。工具本身尚未直接调用图片生成 API。

## 为什么需要 UltraSplitter

UltraSplitter 面向已经在生成视觉资产、下一步需要获得干净独立文件的用户：

- **UI 与产品设计**——拆出图标家族、界面状态、插画、徽章和组件变体。
- **游戏资产生产**——提取角色、多视图、武器、道具、服装、背包图标和概念设定元素。
- **建筑与室内设计**——拆出立面方案、外观变体、材料样本、家具概念和汇报板素材。
- **通用视觉生产**——把情绪板和变体合集变成可命名、可检查、可继续加工的独立文件。

UltraSplitter 不让视觉模型猜最终裁剪坐标。多模态宿主负责判断“这是什么、哪些部分属于同一主体”，确定性代码负责处理“原图像素具体在哪里”。

## UltraSplitter 提供什么

- **按内容拆分，不依赖均匀宫格**——主体位置、宽度、比例和间距不规则时，仍按真实内容边界处理。
- **优先保留原图像素**——完整素材直接裁切；检测框重叠但轮廓可分时，通过前景掩码清理和重排解决，不重新生成。
- **需要 AIGC 补全时先审批**——可识别但被截断、遮挡的主体会合并成一次高效宫格任务；调用生成模型前，先向用户展示范围与成本。
- **有界质量循环**——检查数量、重复、背景、分辨率、触边、留白和可见身份特征；每个冲突组最多尝试两次，不无限生成。
- **直接交付生产资产**——在 `output/` 和 `manifest.json` 中提供命名图片、紧凑联系表、来源、状态、评估证据和绝对访问路径。
- **AI 原生调用**——可为 Codex、Claude Code 等兼容 Agent 安装 Skill，也可直接使用 Python CLI。

## Showcases

以下均为当前工作流处理的真实输入。结果图使用自适应卡片布局，并按主体最长边统一视觉尺度；高密度案例也能清楚预览，但不会改变实际交付文件。点击输入或结果可查看大图。

<table>
  <thead>
    <tr>
      <th width="20%">案例</th>
      <th width="40%">输入</th>
      <th width="40%">结果</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>分布不均</strong><br><code>success</code> · 4 个主体<br><sub>4 个原图裁切，按语义重新排序；未生成像素。</sub></td>
      <td align="center"><a href="docs/assets/case-uneven-input.png"><img src="docs/assets/case-uneven-input-preview.png" alt="分布不均的角色多视图输入" width="470"></a></td>
      <td align="center"><a href="docs/assets/case-uneven-output.png"><img src="docs/assets/case-uneven-output-preview.png" alt="统一尺度排版的 4 张角色视图" width="470"></a></td>
    </tr>
    <tr>
      <td><strong>数量多、排布杂</strong><br><code>success</code> · 11 个主体<br><sub>6 个原图裁切、5 个原像素重排；排除 1 条边界线伪候选。</sub></td>
      <td align="center"><a href="docs/assets/case-dense-input.png"><img src="docs/assets/case-dense-input-preview.png" alt="高密度武器素材输入" width="470"></a></td>
      <td align="center"><a href="docs/assets/case-dense-output.png"><img src="docs/assets/case-dense-output-preview.png" alt="紧凑排版的 11 件武器结果" width="470"></a></td>
    </tr>
    <tr>
      <td><strong>边缘截断</strong><br><code>success</code> · 5 个主体<br><sub>2 个原像素重排、3 个审批后重建；忽略 3 个身份信息不足的碎片。</sub></td>
      <td align="center"><a href="docs/assets/case-clipped-input.png"><img src="docs/assets/case-clipped-input-preview.png" alt="主体被画面边缘截断的输入" width="470"></a></td>
      <td align="center"><a href="docs/assets/case-clipped-output.png"><img src="docs/assets/case-clipped-output-preview.png" alt="审批补全后紧凑排版的 5 个主体" width="470"></a></td>
    </tr>
  </tbody>
</table>

## Quickstart

### 1. AI 原生：安装 Skill

直接从仓库中的单个 Skill 路径安装：

```bash
npx skills@latest add https://github.com/PlevanTem/UltraSplitter/tree/main/skills/splitting-image-grids-by-content
```

之后用自然语言告诉 Agent：

```text
使用 splitting-image-grids-by-content 拆分 @generated-sheet.png。
交付所有可用主体；遇到需要生成式补全的截断主体，先向我确认。
```

Skill 会优先复用已有的 `ultrasplit` 运行时；若缺少运行时，会从本仓库安装 Python 包。

### 2. 安装并运行 CLI

```bash
git clone https://github.com/PlevanTem/UltraSplitter.git
cd UltraSplitter
python -m pip install -e .
ultrasplit run input.png --name character-views
```

<details>
<summary>显式执行扫描、规划、修复与评估</summary>

多模态 Agent 也可以逐个驱动状态：

```bash
ultrasplit scan input.png --output-dir work/scan
ultrasplit apply input.png --scan work/scan/scan.json --plan work/plan.json --output-dir output/task
ultrasplit inspect output/task/manifest.json
ultrasplit repair prepare output/task/manifest.json
# 宿主 Agent 向用户展示修复请求，并等待批准。
ultrasplit repair approve output/task/manifest.json --group conflict-001
# 宿主根据修复包生成一张宫格图，再将结果交回工具：
ultrasplit repair ingest output/task/manifest.json --group conflict-001 --grid generated-grid.png
ultrasplit evaluate output/task/manifest.json --visual-verdict pass
```

</details>

## 架构

<img src="docs/assets/architecture.svg" alt="UltraSplitter AI 原生处理架构" width="100%">

每次运行都会写入 schema v3 的 `manifest.json`，记录准确的源图坐标、路由依据、来源追踪、批准状态、有界修复次数、评估结果和绝对访问路径。完整设计见 [ARCHITECTURE.md](ARCHITECTURE.md)。

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
