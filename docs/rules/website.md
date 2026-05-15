# 前端页面构建规则

公司 markdown 报告通过 GitHub Pages 静态站点对外展示。markdown 是分析底稿，HTML 是展示层；两者由 `sync-md-to-html` skill 同步。

详细设计见 [`docs/superpowers/specs/2026-05-15-website-architecture-design.md`](../superpowers/specs/2026-05-15-website-architecture-design.md)。

## UI 设计参考

视觉系统的单一真实来源是 [`DESIGN.md`](../../DESIGN.md)（Airtable 风格的编辑型设计系统）。写任何 HTML 片段、CSS、组件样式前，先读 DESIGN.md 中对应章节。

关键约定（细节看 DESIGN.md）：

- **基调**：白色画布 + 深墨色字体 + 大量留白；不要 hero 渐变、aurora、mesh 背景。品牌力量来自满版签名色卡（coral / forest / cream / dark navy），不是装饰底纹。
- **颜色**：用 DESIGN.md 中的 token，不要自创色值。primary（CTA 背景）是近黑 `#181d26`，**不是**链接蓝 `#1b61c9`——这是最常踩的坑。
- **字体**：Haas Grotesk 在显示尺寸只用 weight 400/500，绝不用 700。强调靠尺寸和颜色，不靠加粗。系统不可用时降级到 Inter Display。
- **圆角**：分层使用——主 CTA 与签名卡 `12px`、内容卡 `10px`、输入 `6px`、图标按钮圆形、定价 pill `9999px`（**仅限定价页**）。
- **间距**：所有段落垂直节奏统一为 `96px`（`{spacing.section}`）。
- **按钮**：primary（近黑实心）+ secondary（白底细线）成对出现，每屏只用一个 primary。
- **节奏**：白底 → 签名卡 → 白底 → cream → 深底 → 白底，避免连续两段白底。
- **公司详情页**：内容区（`data-region`）的视觉表达可以使用签名色卡 / cream callout / demo-grid card 等 DESIGN.md 中定义的容器，但运行时数据区（market-data / charts）保持中性骨架，让 JS 渲染的数据成为视觉焦点。
- **不做悬停态**：DESIGN.md 全局策略——只定义 Default 和 Active/Pressed。

任何与 DESIGN.md 冲突的视觉决定都要先在该文件中确认或更新。不要在 HTML 里硬编码与 DESIGN.md 不一致的颜色 / 字号 / 圆角。

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

- 动态数据（股价、估值快照、10 年走势）写入 `site/companies/{TICKER}/data.json`，由 `update_market_data.py` 通过 yfinance 每日抓取，GitHub Actions 按市场分时触发（US 盘后、JP 盘后等）。
- 前端 JS（`assets/js/charts.js`）加载页面时 fetch `data.json`，把字段绑定到 `[data-bind="..."]` 元素，并用 Chart.js 在 `<canvas data-chart="...">` 上画图。
- AI 不写 `data.json`，也不修改图表 canvas 区域。

## 本地预览

```bash
python scripts/build.py
python -m http.server 8000 --directory site/_dist
```
