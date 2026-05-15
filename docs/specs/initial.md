# 公司研究网站架构设计

- 日期：2026-05-15
- 主题：用 GitHub Pages 托管公司研究报告，用 GitHub Actions 每日更新动态数据
- 状态：已通过 brainstorming，待用户审阅

## 1. 目标与约束

把 `company-reports/{ticker}-{name}/YYYY-MM-DD-reports.md` 里的分析内容沉淀为可访问、可分享的静态网站。

- 站点：GitHub Pages 静态托管
- 内容来源：markdown 是分析底稿（人写），HTML 是展示层（AI 维护）
- 通过一个 sync skill 把 markdown 的变更同步到 HTML，固化"分析 → 发布"流程
- 动态数据（股价、估值快照、10 年走势图、PER/PBR 走势）每日自动更新
- AI 操作的对象是直接的 HTML，所见即所得；不引入需要学习的模板引擎
- 公司数量当前 < 10，预期增长到 50 量级；架构按这个规模设计，不为更大规模做超前设计

## 2. 整体架构

```text
仓库内容
├── company-reports/{ticker}-{name}/YYYY-MM-DD-reports.md   ← markdown 底稿（人写）
├── site/                                                    ← 网站源 + 输出
│   ├── index.html                                           ← 首页（build.py 注入 COMPANIES_JSON）
│   ├── companies/{TICKER}/
│   │   ├── index.html                                       ← 公司详情页（AI 写）
│   │   ├── changelog.html                                   ← 变更日志（AI 追加）
│   │   └── data.json                                        ← 动态数据（Actions 写）
│   ├── partials/{head,header,footer}.html                   ← 公共片段
│   └── assets/{css,js,vendor}/
├── scripts/
│   ├── build.py                                             ← 注入 partials + 生成首页 JSON
│   └── update_market_data.py                                ← 拉股价 → data.json
├── .github/workflows/
│   ├── deploy.yml                                           ← push 触发：build + 部署
│   ├── daily-data-us.yml                                    ← cron：美股盘后更新
│   └── daily-data-jp.yml                                    ← cron：日股盘后更新
├── .agents/skills/sync-md-to-html/SKILL.md                  ← markdown → HTML 同步 skill（.claude/skills 是 symlink）
├── docs/template.md                                         ← 既有 markdown 模板
└── docs/template.html                                       ← 新增 HTML 详情页骨架
```

### 三方编辑边界（清晰隔离）

| 角色 | 编辑对象 | 触发时机 |
| --- | --- | --- |
| 用户 | `company-reports/*.md` | 写分析时 |
| sync skill（AI） | `site/companies/{TICKER}/index.html`、`changelog.html` | 用户说"同步 X 到 HTML"时 |
| build.py | `site/index.html` 注入、所有 HTML 的 partials 注入 | deploy workflow 中 |
| update_market_data.py | `site/companies/{TICKER}/data.json` | cron 触发 |

**互不冲突的保证**：每个文件由唯一角色负责写，靠 `data-region` 标记和 partials include 注释划清边界。

### 数据流

```text
分析 → markdown                       sync skill        → HTML 详情页 + changelog
                                                                ↓
cron (daily, 按市场)  →  update_market_data.py            → data.json
                                                                ↓
push → deploy.yml  →  build.py（注入 partials + 首页 JSON）→ GitHub Pages

浏览器：加载 HTML → JS fetch data.json + companies.json → Chart.js 画图 + 卡片网格
```

## 3. HTML 详情页结构

### 3.1 骨架（`docs/template.html`）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <!-- include: head.html -->
  <title data-region="title">TICKER — Company Name</title>
  <meta data-region="meta"
        data-ticker="TICKER"
        data-name="中文名"
        data-name-en="English Name"
        data-market="US"
        data-sector="行业"
        data-view="Watch"
        data-tags="tag-a,tag-b"
        data-last-updated="YYYY-MM-DD">
</head>
<body>
  <!-- include: header.html -->

  <main class="company-page">
    <!-- 数据区（JS 从 data.json 填充，AI 与 sync skill 勿动） -->
    <section class="market-data" data-region="market-data">
      <div data-bind="price"></div>
      <div data-bind="market-cap"></div>
      <div data-bind="pe-forward"></div>
      <div data-bind="pb"></div>
      <div data-bind="revenue-growth-ttm"></div>
      <div data-bind="operating-margin"></div>
      <div data-bind="net-margin"></div>
      <div data-bind="week52-range"></div>
      <div data-bind="analyst-target"></div>
      <div data-bind="updated-at"></div>
    </section>

    <section class="charts" data-region="charts">
      <canvas data-chart="price-10y"></canvas>
      <canvas data-chart="per-pbr-10y"></canvas>
    </section>

    <!-- 内容区（AI 通过 sync skill 维护） -->
    <section data-region="thesis"><h2>核心结论</h2></section>
    <section data-region="company-overview"><h2>公司概要</h2></section>
    <section data-region="business-model"><h2>业务模式</h2></section>
    <section data-region="financials"><h2>财务表现</h2></section>
    <section data-region="moat"><h2>竞争与护城河</h2></section>
    <section data-region="catalysts"><h2>催化剂 / 关注点</h2></section>
    <section data-region="valuation"><h2>估值</h2></section>
    <section data-region="risks"><h2>主要风险</h2></section>
    <section data-region="open-questions"><h2>待验证问题</h2></section>

    <!-- 变更日志入口（永远是最后一个 section） -->
    <section data-region="changelog-link">
      <a href="changelog.html">查看更新记录 →</a>
    </section>
  </main>

  <!-- include: footer.html -->
  <script src="/assets/vendor/chart.umd.min.js"></script>
  <script src="/assets/js/charts.js"></script>
  <script>loadCompanyData('TICKER');</script>
</body>
</html>
```

### 3.2 `data-region` 集合

| 类别 | regions | 谁写 | 写法 |
| --- | --- | --- | --- |
| 内容区 | `thesis`、`company-overview`、`business-model`、`financials`、`moat`、`catalysts`、`valuation`、`risks`、`open-questions` | sync skill | 自由生成 HTML 片段 |
| 元数据区 | `title`、`meta` | sync skill | 结构化更新属性 / 文本（不重写结构） |
| 运行时数据区 | `market-data`、`charts` | 前端 JS（数据来自 data.json） | 不写，仅 DOM 操作填充 |
| 固定结构区 | `changelog-link` | 一次写好，永不变 | 不写 |

内容区 region 与 `docs/template.md` 的章节一一对应（命名一致，便于 sync skill 映射）。

## 4. sync-md-to-html Skill

### 4.1 触发与输入

- 用户在对话中说"同步 BABA 到 HTML"（或类似措辞）
- 输入：ticker（必需）；可选指定 markdown 日期，未指定则取该公司目录下最新的 `YYYY-MM-DD-reports.md`

### 4.2 工作流程

1. 解析 ticker → 找到 `company-reports/{ticker}-*/最新.md`
2. 读现有 `site/companies/{TICKER}/index.html`；若不存在，从 `docs/template.html` 复制
3. 解析 markdown frontmatter，更新 HTML 的 `<meta data-region="meta">` 属性
4. 解析 markdown 各章节，按章节 → region 的映射生成 HTML 片段：
   - 段落 → `<p>`
   - 表格 → `<table>`（保留 markdown 的列对齐语义）
   - 引用块 → `<blockquote>`
   - 列表 → `<ul>` / `<ol>`
   - 关键数字 / 结论可包装为视觉强调块（如 `.callout`、`.kpi-card`）
5. 替换对应 `data-region` 的 innerHTML
6. 维护 changelog：
   - 若是新公司：创建 `changelog.html`，加入"YYYY-MM-DD — 初次研究"
   - 若是更新：在 `changelog.html` 顶部追加一行 `YYYY-MM-DD — 1-2 句关键变化摘要`（从新旧 markdown 的 diff 中提取要点）
7. 给用户预览改动（修改了哪些 region、新增 changelog 内容），确认后写入

### 4.3 护栏（skill 永远不修改）

- `data-region` 属性值为 `market-data`、`charts`、`changelog-link` 的 section（连同其内部所有 DOM）
- 任何 `<!-- include: ... -->` 注释行
- 任何 `<script>` 标签
- `data-region="meta"` 的 `<meta>` 标签本身（skill 只更新它的 `data-*` 属性值，不增删属性或重写整行）
- `data-region="title"` 的 `<title>` 标签本身（skill 只更新文本内容）

### 4.4 sync skill 的副产物

skill 在写完公司 HTML 后，还应该更新 `site/companies.json`（增量维护，不重新扫描全目录）：若该 ticker 是新加入，append 一条；若是更新，更新 `last_updated`、`view`、`tags` 等可能变化的字段。

这一步也可以延迟到 build.py 做（扫描全目录生成）。**采用 build.py 扫描方案**：sync skill 不操心首页索引，单一职责更清晰。

## 5. 动态数据更新

### 5.1 `data.json` 结构（每公司一份）

```json
{
  "ticker": "BABA",
  "updated_at": "2026-05-15T20:30:00Z",
  "snapshot": {
    "price": 132.45,
    "currency": "USD",
    "market_cap_b": 320.4,
    "ev_b": 285.1,
    "pe_forward": 11.2,
    "pb": 1.8,
    "pb_tbv": 2.1,
    "revenue_growth_ttm": 0.07,
    "operating_margin": 0.14,
    "net_margin": 0.10,
    "net_debt_to_ebitda": -0.5,
    "week52_low": 71.8,
    "week52_high": 143.2,
    "analyst_target_median": 155.0
  },
  "charts": {
    "price_10y": {
      "dates": ["2016-05-15", "...", "2026-05-15"],
      "values": [80.2, "...", 132.45]
    },
    "per_pbr_10y": {
      "years": [2016, "...", 2025],
      "per": [22.1, "...", 11.0],
      "pbr": [3.2, "...", 1.6],
      "year_end_price": [85.0, "...", 130.0],
      "eps": [3.8, "...", 11.8],
      "bps": [26.5, "...", 81.2]
    }
  }
}
```

### 5.2 `scripts/update_market_data.py`

```text
参数：--market US|JP|HK|CN

流程：
1. 扫描 site/companies/*/index.html，提取 <meta data-region="meta"> 中
   data-market 等于 --market 的 ticker 列表
2. 对每个 ticker：
   - yfinance 拉 snapshot（fast_info + info）
   - yfinance 拉 10 年日线 → charts.price_10y
   - yfinance 拉年度财报 → 取可得年份的 EPS / BPS / 年末股价 → charts.per_pbr_10y
     - 注意：yfinance 的 `.income_stmt` / `.balance_sheet` 通常只覆盖最近 ~4 年；如需更长历史，需额外抓 `.history(period='10y')` 取年末价后与可得财务数据按年份对齐。缺失年份字段写 null，前端图表跳过 null 点
   - 单个 ticker 失败 → 记日志，跳过，不阻断其他 ticker；保留原 data.json
3. 仅当字段有实质变化时写 data.json（避免 git churn）
4. 输出日志摘要：成功 N，失败 M（含 ticker 列表）
```

### 5.3 GitHub Actions

```yaml
# .github/workflows/daily-data-us.yml
on:
  schedule:
    - cron: '0 21 * * 1-5'   # UTC 21:00 = 美东盘后半小时（夏令时 EDT 17:00）
  workflow_dispatch:
jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install yfinance pandas
      - run: python scripts/update_market_data.py --market US
      - name: Commit if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add site/companies/*/data.json
          git diff --cached --quiet || git commit -m "data: daily US update"
          git push
```

```yaml
# .github/workflows/daily-data-jp.yml — 同上，cron 改为 '30 6 * * 1-5'（JST 15:30），参数改 --market JP
```

冬令时 / 夏令时偏移：US 在冬令时（EST）盘后是 UTC 22:00；选 UTC 21:00 在冬令时仍在收盘时间但与 yfinance 最后一根 K 线写入之间可能有 ~30 分钟延迟，可接受。如果发现数据滞后明显，把 cron 调到 UTC 22:00。

### 5.4 前端渲染（`site/assets/js/charts.js`）

```javascript
async function loadCompanyData(ticker) {
  const data = await fetch('./data.json').then(r => r.json());
  fillMarketData(data.snapshot, data.updated_at);
  renderChart('price-10y', buildPriceChart(data.charts.price_10y));
  renderChart('per-pbr-10y', buildPerPbrChart(data.charts.per_pbr_10y));
}
```

`fillMarketData` 把字段写入 `[data-bind="..."]` 元素，并把 `data-bind="updated-at"` 设为友好格式（`2026-05-15 16:30 EDT`）。

## 6. 首页与 build.py

### 6.1 首页布局

```text
┌────────────────────────────────────────────────────────────┐
│ Header（partial）                                            │
│ 投资研究                                                     │
├────────────────────────────────────────────────────────────┤
│ 搜索栏 + 筛选器 [市场 ▾] [观点 ▾] [行业 ▾]                   │
├────────────────────────────────────────────────────────────┤
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ │ BABA 阿里巴巴 │  │ SOFI         │  │ ...          │       │
│ │ 美股·互联网   │  │ 美股·金融科技 │  │              │       │
│ │ [Watch]      │  │ [Long]       │  │              │       │
│ │ $132.45      │  │ $14.20       │  │              │       │
│ │ 52w:71.8-143 │  │ ...          │  │              │       │
│ │ Fwd P/E 11.2x│  │              │  │              │       │
│ │ 报告:5-14    │  │              │  │              │       │
│ │ 数据:5-15 16 │  │              │  │              │       │
│ └──────────────┘  └──────────────┘  └──────────────┘       │
├────────────────────────────────────────────────────────────┤
│ Footer（partial）                                            │
└────────────────────────────────────────────────────────────┘
```

卡片内容来源：

- 静态字段（ticker、name、market、sector、view、tags、last_updated）来自 `COMPANIES_JSON`
- 动态字段（price、52w 区间、Fwd P/E、数据更新时间）来自每家公司的 `data.json`（JS 并行 fetch）

### 6.2 `scripts/build.py` 的两个职责

#### 职责 A：扫描公司 HTML → 注入 COMPANIES_JSON

```text
1. 扫描 site/companies/*/index.html
2. 解析每个文件的 <meta data-region="meta">，抽出：
   {ticker, name, name_en, market, sector, view, tags, last_updated}
3. 拼成 JSON 数组
4. 替换 site/index.html 中的 {{COMPANIES_JSON}} 占位
```

为什么不让 sync skill 维护索引：浏览器无法列目录，必须有"某一刻"完整知道所有公司。把这件事交给 build 时扫描，sync skill 单一职责（只管单家公司的 HTML），不易出错。

#### 职责 B：注入 partials

`partials/head.html`：

```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/assets/css/base.css">
<link rel="stylesheet" href="/assets/css/company.css">
<link rel="icon" href="/assets/favicon.svg">
```

`partials/header.html`：

```html
<nav class="site-nav">
  <a href="/" class="logo">投资研究</a>
  <a href="/" class="back-link">← 全部公司</a>
</nav>
```

`partials/footer.html`：

```html
<footer class="site-footer">
  <p>个人投资研究笔记 · 仅供参考，不构成投资建议</p>
  <p>最后部署：<span>{{BUILD_TIME}}</span></p>
  <p><a href="https://github.com/{user}/investment" target="_blank">GitHub 仓库</a></p>
</footer>
```

HTML 文件里的标记：

```html
<!-- include: head.html -->
<!-- include: header.html -->
<!-- include: footer.html -->
```

build.py 用简单的字符串替换（不需要模板引擎），把 `<!-- include: xxx.html -->` 替换为 `partials/xxx.html` 的内容；同时把 `{{COMPANIES_JSON}}`、`{{BUILD_TIME}}` 等占位替换为实际值。

### 6.3 build.py 的输出

build.py 输出到 `site/_dist/`，GitHub Pages 服务 `site/_dist/`。源始终是 `site/`，输出始终是 `site/_dist/`。`_dist/` 加入 `.gitignore`（CI 中临时生成，不入库）。

build.py 的行为：

1. 把 `site/` 的所有内容**原样镜像**到 `site/_dist/`（保留目录结构）
2. 对镜像中的 `.html` 文件做两件事：替换 `<!-- include: xxx.html -->` 注释为对应 partial 内容；替换 `{{COMPANIES_JSON}}`、`{{BUILD_TIME}}` 等占位
3. **非 HTML 文件原样保留**（关键：`data.json`、CSS、JS、字体、图片等都直接落到 `_dist/`，不做任何处理）
4. `partials/` 目录本身不复制到 `_dist/`（它只是构建期的素材）

这样保证：

- daily-data workflow 写入的 `site/companies/*/data.json` 经 build 后落到 `_dist/companies/*/data.json`，前端可正常 fetch
- 源 HTML 始终含 `<!-- include: ... -->`，可重复构建无状态污染

本地预览：

```bash
python scripts/build.py
python -m http.server 8000 --directory site/_dist
```

### 6.4 deploy.yml

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
    paths:
      - 'site/**'
      - 'scripts/build.py'
  workflow_dispatch:
permissions:
  pages: write
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python scripts/build.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/_dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

注意 daily-data workflow commit data.json 也会触发 deploy（因为 path 匹配 `site/**`），保证数据变更后首页/详情页拿到新数据。

## 7. 开发与部署流程

### 7.1 情景 A — 写新公司

1. 创建 `company-reports/NVDA-nvidia/2026-05-15-reports.md`，按 `docs/template.md` 写
2. 跟 AI 说"同步 NVDA 到 HTML"
3. sync skill：
   - 复制 `docs/template.html` 到 `site/companies/NVDA/index.html`
   - 填入元数据 meta + 各 region 内容
   - 创建 `changelog.html`，写"2026-05-15 — 初次研究"
4. `git add site/companies/NVDA/ && git commit && git push`
5. deploy workflow 触发：build.py 扫描到 NVDA → 注入首页 → Pages 部署
6. daily-data workflow 下次运行时自动拉 NVDA 的数据

### 7.2 情景 B — 更新已有公司

1. 创建 `company-reports/BABA-alibaba/2026-08-01-reports.md`
2. 跟 AI 说"同步 BABA"
3. sync skill：
   - diff 与上次 markdown 的变化
   - 更新对应 region 的 HTML
   - 在 `changelog.html` 顶部追加一行（如"2026-08-01 — Q2 财报后下调云业务增长预期至 12%"）
4. push → 自动部署

### 7.3 情景 C — 仅数据更新（无人参与）

1. cron 触发 daily-data-us.yml / daily-data-jp.yml
2. update_market_data.py 拉 yfinance → 写 data.json（仅当有变化）
3. workflow 自动 commit + push
4. 触发 deploy → Pages 部署

### 7.4 本地预览

```bash
python scripts/build.py
python -m http.server 8000 --directory site/_dist
# 浏览器打开 http://localhost:8000
```

### 7.5 手动触发

GitHub Actions 页面，每个 workflow 都有 "Run workflow" 按钮（`workflow_dispatch:`）。需要紧急刷新某市场数据时手动触发。

## 8. 风险与未来留白

**风险：**

- yfinance 偶发数据缺失或异常值 → update_market_data.py 必须对单个 ticker 失败容错，保留上次成功数据
- HTML 详情页结构演化（新增 region）→ 用 git 管理 `docs/template.html`；老公司页面手动补 region 或由 sync skill 检测并补齐
- 港股 / A 股加入时 → 复制一个 daily-data-{hk,cn}.yml，调整 cron 时间和 `--market` 参数

**留白（YAGNI）：**

- 公司数量超过 50 后，首页 N 个并行 fetch 可能慢 → 改为 build.py 生成聚合 `companies-snapshot.json`
- 想要历史报告独立可访问 → 增加 `site/companies/{TICKER}/history/{date}.html`，由 sync skill 在写新版前先归档旧版
- 想要全文搜索 → 引入 pagefind 或 lunr.js，构建期生成索引
- 想要订阅 / RSS → build.py 同时生成 `site/feed.xml`

## 9. 待做事项一览

实现阶段需要做的事（不在本设计内展开，留给 writing-plans）：

1. 写 `docs/template.html`
2. 写 `site/partials/{head,header,footer}.html`
3. 写 `site/index.html`（带 `{{COMPANIES_JSON}}` 占位）和 `site/assets/css/base.css`、`site/assets/js/filters.js`
4. 写 `site/assets/js/charts.js`（Chart.js 初始化、`loadCompanyData`、`fillMarketData`）
5. 写 `scripts/build.py`
6. 写 `scripts/update_market_data.py`
7. 写 `.github/workflows/{deploy,daily-data-us,daily-data-jp}.yml`
8. 写 `.agents/skills/sync-md-to-html/SKILL.md`（默认路径，`.claude/skills` 是它的 symlink）
9. 把现有 6 家公司的 markdown 用 sync skill 转成 HTML，验证全流程
10. 启用 GitHub Pages（Settings → Pages → Source: GitHub Actions）
