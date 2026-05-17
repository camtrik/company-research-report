---
name: sync-md-to-html
description: Use when the user says "同步 TICKER 到 HTML", "sync TICKER", or similar—converting a company-reports markdown file into a site/companies/{TICKER}/index.html detail page and updating changelog.html. Handles new companies (copy from template) and updates (diff regions). Also use when reviewing HTML region content for accuracy.
---

# sync-md-to-html

将 `company-reports/{ticker}-{name}/YYYY-MM-DD-reports.md` 转换为 `site/companies/{TICKER}/index.html` 公司详情页，并维护 `changelog.html`。动手改 HTML 之前必须先读 `docs/rules/website.md`。

## 新公司初始化：数据脚本

新增公司时，除同步 HTML 外还需要准备两个 JSON 文件。脚本均有两份内容一致的副本：

```
.agents/skills/sync-md-to-html/scripts/  ← 权威副本
scripts/                                  ← 镜像副本（修改时两处同步）
```

### 1. 股价数据（data.json · price_10y）

```bash
python .agents/skills/sync-md-to-html/scripts/fetch_price_data.py \
  --ticker 6098 --market JP

# 美股（market 可省略，从 ticker 自动推断）
python .agents/skills/sync-md-to-html/scripts/fetch_price_data.py \
  --ticker AMZN
```

写入 `site/companies/{TICKER}/data.json`，包含 10 年周线收盘价。之后由 GitHub Actions（`update_market_data.py`）每周自动更新，无需手动再跑。

### 2. PER / PBR 历史数据（per_pbr.json）

```bash
# 日股（需 EDINETDB_API_KEY 环境变量）
python .agents/skills/sync-md-to-html/scripts/per_pbr_10y.py \
  --ticker 6098.T \
  --output site/companies/6098/per_pbr.json

# 美股（无需 API Key）
python .agents/skills/sync-md-to-html/scripts/per_pbr_10y.py \
  --ticker AMZN \
  --output site/companies/AMZN/per_pbr.json
```

写入 `site/companies/{TICKER}/per_pbr.json`，包含 10 年 PER / PBR 历史数据。之后需要手动重跑更新（无自动化）。

### 完成后重建

```bash
python scripts/build.py
```

## 输入参数

| 参数 | 必填 | 默认值 |
|------|------|--------|
| ticker | 是 | — |
| date | 否 | 该公司目录下最新的 `YYYY-MM-DD-reports.md` |

## 准备工作

1. 读 `docs/rules/website.md`——AI 编辑边界规则。
2. 如需添加新 CSS 组件，先读 `DESIGN.md`（视觉系统）和 `site/assets/css/company.css`（已有组件）。

## 工作流程

```
1. 解析路径
   - 源 MD：  company-reports/{ticker}-*/YYYY-MM-DD-reports.md（date 未指定则取最新）
   - 目标 HTML：site/companies/{TICKER}/index.html（TICKER 始终大写）

2. 若目标 HTML 不存在（新公司）：
   - 复制 site/_templates/template.html → 目标路径
   - 替换 <title> 和 <script>loadCompanyData('TICKER') 中的 TICKER 占位符
   - 主页 company-grid 卡片**无需手动添加**：build.py 扫描所有
     site/companies/*/index.html 中的 <meta data-region="meta"> 属性，
     自动生成 window.COMPANIES，由 filters.js 渲染成卡片。
     只要步骤 3 的 data-ticker、data-name、data-market 等属性填写正确，
     运行 python scripts/build.py 后主页即自动出现该公司的卡片。

3. 更新元数据（只改属性值，不改 <meta> 标签结构）：
   - <title data-region="title">  → "{TICKER} — {data-name 值}"
   - <meta data-region="meta">    → 从 frontmatter 同步各 data-* 属性：
       data-ticker、data-name、data-market、data-sector、
       data-view、data-tags（逗号分隔）、data-last-updated
   - data-name-en：从 markdown 内容推导公司英文名（通常出现在公司概要或标题中）；
     更新时如英文名未变，保留现有值

4. 填充 snapshot section 的 tiles 和末尾注释行：
   - tiles：10 个纯静态 `.market-data__tile`（见「HTML 组件模式 → snapshot」）
   - 末尾注释行：snapshot section 的 `</div></div></section>` 结构前，有
     `<p class="eyebrow eyebrow--muted" ...>数据截至 YYYY-MM-DD</p>`
     同步时将日期替换为 `## 关键数据` 表格第一行的股价日期（或 frontmatter `data-last-updated`）

5. per-pbr-history div（它是 [data-region="charts"] 的兄弟节点，不在其内部）：
   - **`<tbody data-bind="per-pbr-table">` 由 JS 从 per_pbr.json 渲染，sync skill 不要填行数据**
   - sync skill 只维护该 div 末尾的 `<blockquote>`——把 markdown ## 图表区 的数据来源说明（"注：期末股价使用 yfinance ..."）抄进去
   - 格式见下方「HTML 组件模式 → per-pbr-history」
   - 注意：div **之后**（同一 `section__inner` 内）的
     `<p class="eyebrow eyebrow--muted" ...>图表 / 表格数据截至 <span data-bind="per-pbr-updated">YYYY-MM-DD</span></p>`
     由 JS 从 per_pbr.json 的 `updated_at` 覆盖，**不要修改**

6. 按 markdown 章节逐一填充各内容 data-region：
   - 只替换每个 region 可编辑容器的内部 HTML
   - 详见下方「章节 → Region 映射表」

6. 向用户预览改动：哪些 region 有变化、changelog 新增内容
7. 等待用户确认后写入文件
8. 更新 changelog.html（见下方「Changelog」）
```

## 章节 → Region 映射表

| Markdown 章节 | HTML region | 可编辑目标 |
|---|---|---|
| `## 关键数据` | `data-region="snapshot"` | 整个 `.market-data` 内所有 `.market-data__tile`；见下方「HTML 组件模式 → snapshot」 |
| `## 核心结论` | `data-region="thesis"` | 整个 `.section-plain__body`；无副标题 |
| `## 公司概要` | `data-region="company-overview"` | 整个 `.section-plain__body`；副标题固定为 `基本面 · 业务定位` |
| `## 图表区`（数据来源说明） | `<div class="per-pbr-history">` 内的 `<blockquote>` | 只更新数据来源说明文字；表格 `<tbody>` 由 JS 从 per_pbr.json 渲染，不要手填 |
| `## 业务模式` | `data-region="business-model"` | `.feature-card` 正文 + `.section-plain__body`；无副标题 |
| `## 财务表现` | `data-region="financials"` | 整个 `.section-plain__body`；副标题动态填写（如 `FY2021 – FY2026E · 单位：十亿日元`） |
| `## 竞争与护城河` | `data-region="moat"` | `.feature-card` 正文 + `.section-plain__body`；无副标题 |
| `## 催化剂 / 关注点` | `data-region="catalysts"` | 整个 `.section-plain__body`；无副标题 |
| `## 风险 / 反向论证` | `data-region="risks"` | 整个 `.section-plain__body`；副标题固定为 `按可能性 × 影响排序` |
| `## 管理层与资本配置`（可选） | 合并进 `data-region="valuation"` | 作为末尾 `<h3>` 块追加到 `.section-plain__body` |
| `## 估值分析` | `data-region="valuation"` | 整个 `.section-plain__body`；副标题动态填写（描述本次使用的估值方法） |
| `## 后续关键问题` + `## 来源` | `data-region="open-questions"` | 整个 `.section-plain__body`；无副标题 |

**副标题写法**：有副标题的区域，在 `section-plain__head` 的 `<h2>` 后插入 `<span class="section-plain__meta">文字</span>`。template 里该 div 没有预留 span，需要展开写：

```html
<div class="section-plain__head">
  <h2>公司概要</h2>
  <span class="section-plain__meta">基本面 · 业务定位</span>
</div>
```

**完全跳过：** `## 图表区` 中的股价链接（JS 驱动）。

## HTML 组件模式

所有模式以 `site/companies/6098/index.html` 为权威参考。

### 全局通用

```html
<span class="kpi">17.5x</span>          <!-- 内联高亮关键数字 -->
<p class="lede">导语句。</p>             <!-- 较大的引导段落 -->
<blockquote>脚注 / 数据说明。</blockquote>
<div class="table-wrap"><table>…</table></div>        <!-- 普通表格 -->
<div class="table-wrap table-wrap--dense"><table>…</table></div>  <!-- 紧凑表格 -->
```

表格单元格对齐类：`class="num"`（右对齐）、`class="pos"`（绿色）、`class="neg"`（红色）。
高亮行：`class="row--highlight"`；合计行：`class="row--total"`。

### snapshot（关键数据快照）

替换 `data-region="snapshot"` 内所有 tile 的**静态文本值**，最后一个 tile 保留 `data-bind="last-updated"`（由 JS 从 meta 标签填入分析截至日期）：

```html
<div class="market-data" data-region="snapshot">
  <div class="market-data__tile">
    <span class="market-data__label">股价</span>
    <span class="market-data__value">¥X,XXX</span>
  </div>
  <!-- …其余 8 个指标 tile，均为静态文本值… -->
  <div class="market-data__tile market-data__tile--sm">
    <span class="market-data__label">分析截至</span>
    <span class="market-data__value">YYYY-MM-DD</span>
  </div>
</div>
```

- 所有 10 个 tile 均为**纯静态文本**，不含 `data-bind`（包括"分析截至"，直接硬编码分析日期）。
- 第 8 个 tile 加 `market-data__tile--sm`，第 9 个（分析师目标价）加 `market-data__tile--accent`，第 10 个加 `market-data__tile--sm`。

### thesis（核心结论）

```html
<div class="callout callout--ink">
  <div class="callout__label">观点 · {view} · 基准合理价值 ¥X,XXX</div>
  <p>来自 ## 核心结论 的 3-5 句话。</p>
</div>
<p class="lede">核心看多点一句话概括。</p>
<p>补充段落…</p>
```

### company-overview（公司概要）

```html
<div class="kv-grid">
  <div class="kv-grid__item">
    <div class="kv-grid__label">上市地 / 代码</div>
    <div class="kv-grid__value">TSE Prime · 6098</div>
  </div>
  <!-- 每条基本信息对应一个 item，来自 ## 公司概要 ## 基本信息 -->
</div>
<p>业务描述段落。</p>
<h3>护城河来源（速览）</h3>
<ul><li>…</li></ul>
<blockquote>可选补充说明。</blockquote>
```

### per-pbr-history

`<tbody>` 留空 + 加 `data-bind="per-pbr-table"`，由 `charts.js` 从 `per_pbr.json` 渲染。sync skill 只动 `<blockquote>` 的文字。

```html
<div class="per-pbr-history">
  <div class="per-pbr-history__head">
    <span class="eyebrow eyebrow--muted">10 年 PER / PBR 历史数据</span>
    <span class="per-pbr-history__hint">期末股价 · EPS · BPS</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>年度</th><th class="num">期末股价</th><th class="num">EPS</th><th class="num">BPS</th><th class="num">PER</th><th class="num">PBR</th></tr>
      </thead>
      <tbody data-bind="per-pbr-table"></tbody>
    </table>
  </div>
  <blockquote>来自 markdown 的数据来源说明。</blockquote>
</div>
```

### business-model（业务模式）

`data-region="business-model"` 有两个容器，都需要填充：

```html
<!-- .feature-card 内（<h2>业务模式</h2> 之后） -->
<p class="lede">一句话框架。</p>
<ul class="numbered-list">
  <li>
    <span class="numbered-list__index">01</span>
    <div class="numbered-list__body"><strong>板块名</strong> — 描述。</div>
  </li>
  <!-- 02、03… -->
</ul>

<!-- .section-plain__body 内（表格、补充细节） -->
<h3>Business Segments</h3>
<div class="table-wrap">…</div>
<blockquote>…</blockquote>
```

### financials（财务表现）

更新区段副标题：`<span class="section-plain__meta">FY20XX – FY20XXE · 单位：…</span>`

```html
<div class="table-wrap"><table>…多年期损益表…</table></div>
<blockquote>单位 / 数据来源说明。</blockquote>
<p>2-3 句财务质量与驱动因素点评。</p>
```

### moat（护城河）

与 business-model 相同的双容器模式：

```html
<!-- .feature-card 内 -->
<p class="lede">护城河评级：<strong>Wide and Expanding</strong>。</p>
<div class="moat-block"><h4>护城河名称</h4><p>说明。</p></div>
<!-- 每条护城河来源一个 moat-block -->

<!-- .section-plain__body 内 -->
<h3>同业对比</h3>
<div class="table-wrap table-wrap--dense"><table>…同业表…</table></div>
<blockquote>…</blockquote>
<p>定位分析。</p>
```

### catalysts（催化剂 / 关注点）

```html
<div class="catalyst-grid">
  <div class="catalyst-card">
    <h3>短期（&lt; 6 月）</h3>
    <ul>
      <li><span class="material-symbols-outlined">bolt</span><span>…</span></li>
    </ul>
  </div>
  <div class="catalyst-card catalyst-card--medium">
    <h3>中期（6 – 18 月）</h3>
    <ul>
      <li><span class="material-symbols-outlined">trending_up</span><span>…</span></li>
    </ul>
  </div>
</div>
```

### valuation（估值分析）

更新副标题：`<span class="section-plain__meta">EV/EBITDA · EPS DCF · SOTP · 情景三档</span>`

每个子方法用 `<h3>` 标题。估值结论放在末尾：

```html
<div class="scenario-grid">
  <div class="scenario-card">
    <div class="scenario-card__label">保守</div>
    <div class="scenario-card__value">¥X,XXX</div>
    <div class="scenario-card__trigger">触发条件。</div>
  </div>
  <div class="scenario-card scenario-card--base">…基准…</div>
  <div class="scenario-card">…乐观…</div>
</div>
<p><strong>当前 vs 合理价值：</strong>…</p>
```

`## 管理层与资本配置` 映射为末尾一个 `<h3>管理层与资本配置</h3>` + `<ul>` 块。

### risks（主要风险）

```html
<div class="risk-grid">
  <div class="risk-item">
    <h4>01. 风险名称</h4>
    <p>触发情况 · 影响 · 监控信号。</p>
  </div>
  <!-- 按序编号；第 5 条通常跨列：-->
  <div class="risk-item risk-item--wide">…</div>
</div>

<!-- 来自"什么情况下我会撤回结论" -->
<div class="callout">
  <div class="callout__label">撤回条件</div>
  <p>…</p>
</div>
```

### open-questions（后续关键问题）

```html
<div class="open-questions-card">
  <ul class="open-questions-list">
    <li>
      <span class="q-badge">Q</span>
      <p>问题内容。</p>
    </li>
  </ul>
</div>

<h3>参考来源</h3>
<ul>
  <li>作者/来源，<a class="link-blue" href="…" rel="noopener" target="_blank">标题</a>，YYYY-MM-DD。</li>
</ul>
```

## 护栏——绝对不改

| 内容 | 原因 |
|------|------|
| `[data-region="charts"]` 及其所有子节点 | 运行时 JS + Chart.js canvas |
| `[data-region="changelog-link"]` | 固定结构 |
| 所有 `<!-- include: ... -->` 注释行 | build.py 在构建时替换 |
| 所有 `<script>` 标签 | 构建管道，不属于 sync skill 管辖 |
| `<tbody data-bind="per-pbr-table">` | JS 从 per_pbr.json 渲染整张 PER/PBR 表格；保持 `<tbody>` 为空 |
| `data-bind="per-pbr-updated"` 元素（图表区下方小字） | JS 从 per_pbr.json 覆盖；HTML 内有硬编码日期作兜底，不改该元素 |
| 所有其他 `data-bind="..."` 元素 | 由 JS 在运行时填充 |
| 所有 `<canvas data-chart="...">` 元素 | Chart.js 渲染目标 |
| `<meta data-region="meta">` 标签结构 | 只更新 `data-*` 属性值，不改标签本身 |
| `<title data-region="title">` 标签结构 | 只更新文本内容 |

**`.per-pbr-history` div 是 `[data-region="charts"]` 的兄弟节点，不是其子节点——sync skill 负责填充它。** 不要把外层 `<section>`（同时包含 charts）误认为是 `data-region="charts"` 元素本身。

## Changelog

### 新公司

创建 `site/companies/{TICKER}/changelog.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <!-- include: head.html -->
  <title>{TICKER} — 更新记录</title>
  <link rel="stylesheet" href="{{SITE_BASE_PATH}}/assets/css/company.css">
</head>
<body>
  <!-- include: header.html -->
  <main class="changelog-page">
    <header style="padding: var(--s-5) 0 var(--s-3);">
      <div class="eyebrow eyebrow--muted" style="margin-bottom: var(--s-2); color: var(--slate);">{TICKER} · {公司名}</div>
      <h1>更新记录</h1>
      <p class="muted">每次同步报告时新增一行，记录关键变化。</p>
      <p><a href="./" class="link-blue">← 返回 {TICKER} 详情页</a></p>
    </header>
    <section>
      <article class="changelog-entry">
        <div class="changelog-entry__date">{YYYY-MM-DD} · 初次研究</div>
        <p class="changelog-entry__summary">
          1-2 句：观点、基准合理价值、核心看多 / 看空点。
        </p>
      </article>
    </section>
  </main>
  <!-- include: footer.html -->
</body>
</html>
```

### 更新已有公司

在 `<section>` 内现有第一个 `<article>` **之前**插入新条目：

```html
<article class="changelog-entry">
  <div class="changelog-entry__date">{YYYY-MM-DD} · {2-3 字摘要}</div>
  <p class="changelog-entry__summary">
    1-2 句关键变化（对比前一版 markdown diff 提炼）。
  </p>
</article>
```

摘要从新旧 markdown 的差异中提炼——例如合理价值调整、观点变化、重大 thesis 更新。
---

> **每次写入任何 HTML / JSON 文件后，都必须运行 `python scripts/build.py` 才能在本地预览中看到改动。**
