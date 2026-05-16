# 前端页面构建规则

公司 markdown 报告通过 GitHub Pages 静态站点对外展示。markdown 是分析底稿，HTML 是展示层；两者由 `sync-md-to-html` skill 同步。

详细设计见 [`docs/superpowers/specs/2026-05-15-website-architecture-design.md`](../superpowers/specs/2026-05-15-website-architecture-design.md)。

## UI 设计参考

视觉系统的单一真实来源是 [`DESIGN.md`](../../DESIGN.md)（Mastercard 风格的编辑型设计系统）。写任何 HTML 片段、CSS、组件样式前，先读 DESIGN.md 中对应章节。

关键约定（细节看 DESIGN.md）：

- **基调**：暖奶油画布（`#F3F0EE`）+ 暖近黑字体（`#141413`）+ 大量留白。**不用纯白**做页面底色；不要 hero 渐变 / aurora / mesh 背景；视觉力量来自卡片形状（pill / stadium / circle）与节制的橙色点缀。
- **颜色**：用 DESIGN.md 的 token，写进 `site/assets/css/base.css` 的 CSS custom properties。primary（CTA 背景）是 Ink Black `#141413`，文字使用 Canvas Cream `#F3F0EE`（不是纯白）。Signal Orange `#CF4500` 仅用于合规 / 信号语境，**不要**作为营销 CTA。装饰性的 Light Signal Orange `#F37338` 仅用于 eyebrow 圆点和分隔弧线。
- **字体**：主字体 MarkForMC 是商业字体，开源替代是 **Sofia Sans**（DESIGN.md 备用栈中列出）。已在 `site/partials/head.html` 通过 Google Fonts 加载 Sofia Sans 400/500/700。显示文字使用 weight 500 + 字距 -2%；正文使用 weight 450（变量字重，比 400 软、比 500 紧）；eyebrow 使用 14px / weight 700 / +4% tracking / 全大写。不混用第二款字体。
- **圆角**：Mastercard 阶梯——`6px`（cookie 微元素）/ `20px`（按钮）/ `24px`（橙色合规 pill）/ `40px`（卡片、媒体框、签名容器）/ `999px`（导航 pill、价格 pill、tag）/ `50%`（头像、卫星 CTA）。**避免** 8–12px 的中间地带——会显得通用模板。
- **间距**：基础单元 8px，常用阶梯 `8 / 16 / 24 / 32 / 48 / 64 / 96 / 128`。桌面 section 垂直内距 96–128px；移动 48–64px。
- **按钮**：primary 为 Ink Pill（近黑实心 + 奶油字 + 20px 圆角）；secondary 为 Outlined Pill（白底 + 黑边）。每屏仅一个 primary。
- **节奏**：白底（cream）→ lifted cream → 深底（ink footer）三档；不连续堆叠两段奶油底。
- **公司详情页**：内容区（`data-region`）可以使用 `.callout` / `.callout--ink` / `.kv-grid` / `.scenario-grid` 这些已经在 `assets/css/company.css` 中定义的容器；运行时数据区（market-data / charts）保持中性骨架，让 JS 渲染的数字成为视觉焦点。
- **阴影**：氛围式而非定向。Level 1 `0 4px 24px rgba(0,0,0,0.04)` 用于导航 pill；Level 2 `0 24px 48px rgba(0,0,0,0.08)` 用于卡片。**不要**硬阴影。
- **hover 处理**：DESIGN.md 默认无 hover，只定义 default 与 active（按下时 `translateY(1px)`）。

任何与 DESIGN.md 冲突的视觉决定都要先在该文件中确认或更新。不要在 HTML 里硬编码与 DESIGN.md 不一致的颜色 / 字号 / 圆角；优先复用 `assets/css/base.css` 中已经声明好的 CSS custom properties（`--canvas`、`--ink`、`--signal-light`、`--r-md`、`--s-3` 等）。

## 站点目录

```text
site/
├── index.html                          ← 首页（含 {{COMPANIES_JSON}} 占位）
├── companies/{TICKER}/
│   ├── index.html                      ← 公司详情页（AI 维护）
│   ├── changelog.html                  ← 变更日志（AI 追加）
│   └── data.json                       ← 动态数据（GitHub Actions 写）
├── partials/{head,header,footer}.html  ← 公共片段
├── _templates/template.html            ← HTML 详情页骨架（构建期素材，不部署）
└── assets/{css,js,vendor}/

scripts/build.py                        ← 构建：注入 partials + COMPANIES_JSON
scripts/update_market_data.py           ← 每日数据更新
site/_dist/                             ← 构建输出（GitHub Pages 服务此目录；不入库）
```

## HTML 详情页编辑边界

详情页用 `data-region="..."` 标记区域，分四类，AI 编辑权限不同：

- **内容区**（AI 可自由生成 HTML 片段）：`thesis`、`company-overview`、`business-model`、`financials`、`moat`、`catalysts`、`valuation`、`risks`、`open-questions`。这些 region 与 `docs/template.md` 的章节一一对应。
- **元数据区**（AI 结构化更新属性 / 文本，不重写整行）：`title`、`meta`。
- **运行时数据区**（AI 永远不动）：`market-data`、`charts`。由前端 JS 从 `data.json` 渲染。
- **固定结构区**（AI 永远不动）：`changelog-link`。

**AI 永远不修改：**

- `data-region` 值为 `market-data`、`charts`、`changelog-link` 的 section（及其内部所有 DOM）
- 任何 `<!-- include: ... -->` 注释行
- 任何 `<script>` 标签
- 任何 `data-bind=` 元素、`<canvas data-chart=...>` 元素

## 同步 markdown 到 HTML

不要直接没有参照的改 `site/companies/{TICKER}/index.html`。流程：

1. 先把分析写进 `company-reports/{ticker}-{name}/YYYY-MM-DD-reports.md`。
2. 调用 `sync-md-to-html` skill（或让用户触发）把变更同步到 HTML。
3. Skill 会：对应 `data-region` 更新内容；在 `changelog.html` 顶部追加一行 `YYYY-MM-DD — 1-2 句关键变化摘要`。

新公司：skill 会用 `site/_templates/template.html` 作为详情页骨架，并初始化 `changelog.html`。

## 公共片段

`partials/head.html`、`partials/header.html`、`partials/footer.html` 是全站共享内容。HTML 文件里通过 `<!-- include: xxx.html -->` 引用，由 `build.py` 在构建时替换。需要改导航、页脚、CSS 引入时，只改 `partials/`，不要复制粘贴到每个公司页。

## 动态数据与图表

- 动态数据（股价周线、估值快照、10 年走势）写入 `site/companies/{TICKER}/data.json`，由 `update_market_data.py` 通过 yfinance 每周抓取周线股价 + 年度 PER/PBR，GitHub Actions 每周五盘后触发。snapshot 日更为后续功能。
- 前端 JS（`assets/js/charts.js`）加载页面时 fetch `data.json`，把字段绑定到 `[data-bind="..."]` 元素，并用 Chart.js 在 `<canvas data-chart="...">` 上画图。
- AI 不写 `data.json`，也不修改图表 canvas 区域。

## 本地预览

```bash
python scripts/build.py
python -m http.server 8000 --directory site/_dist
```
