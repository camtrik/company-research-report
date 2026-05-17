# Company Research

公司研究与投资分析笔记。线上版本：**https://camtrik.github.io/company-research-report/**

---

## 内容

- **公司详情页** — 每家公司一页，包含关键数据快照、10 年股价走势、PER/PBR 历史图表，以及公司概要、核心结论、业务模式、财务表现、护城河、估值、风险等分析章节。
- **主页** — 所有已收录公司的卡片列表，含实时股价，支持按市场/行业筛选。
- **更新记录** — 每家公司的 `changelog.html`，追踪历次分析更新。

股价数据由 GitHub Actions 每周自动更新；PER/PBR 历史数据手动维护。

---

## How to Use

本项目配合 [Claude Code](https://claude.ai/code) 的 skill 系统使用。核心 skill：

### 1. 写研究报告

在 `company-reports/{ticker}-{name}/` 下新建或更新 `YYYY-MM-DD-reports.md`，格式参考已有报告。frontmatter 示例：

```yaml
---
ticker: 6098
name: リクルートホールディングス
market: JP
sector: HR Technology
view: Buy
tags: HR, SaaS, Japan
date: 2026-05-15
---
```

### 2. 同步到 HTML 页面

在 Claude Code 中输入：

```
同步 6098 到 HTML
```

skill `sync-md-to-html`（位于 `.agents/skills/sync-md-to-html/`）会自动：
- 新公司：从 `site/_templates/template.html` 创建页面
- 更新各内容区块（公司概要、核心结论、财务表现等）
- 维护 `changelog.html`
- **主页卡片无需手动添加**，`build.py` 从 meta 标签自动生成

### 3. 新公司初始化数据

同步 HTML 后，还需要跑两个脚本准备图表数据：

```bash
# 股价数据（10 年周线）
python .agents/skills/sync-md-to-html/scripts/fetch_price_data.py \
  --ticker 6098 --market JP

# PER/PBR 历史数据
python .agents/skills/sync-md-to-html/scripts/per_pbr_10y.py \
  --ticker 6098.T \
  --output site/companies/6098/per_pbr.json
```

### 4. 构建 & 预览

```bash
python scripts/build.py
```

构建产物输出到 `site/_dist/`，推送后由 GitHub Actions 自动部署到 GitHub Pages。
