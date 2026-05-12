# 股票 Agent 相关开源项目调研

> 调研日期：2026-05-06  
> 两个方向：① 实时股价接口  ② 投资知识/技能辅助

---

## 零、himself65/finance-skills 深度评估

> **GitHub**: https://github.com/himself65/finance-skills  
> **Stars**: ⭐ 1,439 | **语言**: TypeScript | **定位**: Claude Code agent skills 合集

这是一个专为 Claude Code / Agent Skills 标准设计的金融技能包，可用 `npx plugins add himself65/finance-skills` 一键安装。包含 6 个插件，与我们的两个需求直接相关的是：

### 插件一：`yfinance-data` skill（市场分析插件）

**是否满足实时价格需求：✅ 满足，完全免费**

该 skill 通过 yfinance Python 库获取数据，agent 在运行时自动安装（`pip install yfinance`），无需任何 API Key。

支持的数据类型：

| 数据类型 | 方法 |
|---------|------|
| 实时/当前价格 | `ticker.info` / `ticker.fast_info` |
| 历史 OHLCV（1m 到 3mo 周期） | `ticker.history()` / `yf.download()` |
| 财务三张报表 | `ticker.income_stmt` / `balance_sheet` / `cashflow` |
| 期权链 | `ticker.option_chain()` |
| 分析师目标价 / 评级 | `ticker.analyst_price_targets` / `recommendations` |
| 股息 / 拆股 | `ticker.dividends` / `splits` |
| 机构持仓 / 内部交易 | `ticker.institutional_holders` / `insider_transactions` |
| 新闻 | `ticker.news` |
| 多股票对比 / 筛选 | `yf.download()` / `yf.Screener` |

**局限**：Yahoo Finance 偶尔限流；A 股数据质量有限；最短 1 分钟 K 线只能回溯 7 天。

---

### 插件二：`funda-data` skill（数据提供商插件）

**是否需要付费 API：⚠️ 是，需要 `FUNDA_API_KEY`**

Funda AI（[funda.ai](https://funda.ai)）是付费服务，但数据极为全面，覆盖 60+ 端点：

| 能力 | 说明 |
|-----|------|
| 实时报价 / 批量报价 | `/v1/quotes?type=realtime` 和 `type=batch` |
| 盘后报价 | `/v1/quotes?type=aftermarket-quote` |
| 分钟级 K 线 + 技术指标 | `/v1/charts?type=5min` / `sma` / `ema` / `rsi` |
| 基本面全套 | 财务报表、P/E、DCF、分析师预期 |
| 期权流（机构大单）+ Greeks + GEX | 完整期权生态 |
| 供应链知识图谱 | 上游供应商 / 下游客户 / 竞争对手 |
| 社交情绪 | Twitter、Reddit、Polymarket |
| AI 增强新闻 | 情感标注 + 事件时间线 |
| SEC 文件 / 财报电话会议记录 | 10-K / 10-Q / 8-K + 转录文本 |
| 国会交易 / 内部人交易 / 13F | 另类数据 |
| 宏观经济 / FRED | 利率、GDP、CPI |
| AI 公司招聘信号 | OpenAI / Anthropic / Google 职位分析 |

**API Key 获取方式**：`export FUNDA_API_KEY="sk_..."` 或写入 `.env`

---

### 插件三：`finance-sentiment` skill（数据提供商插件）

**是否需要付费 API：⚠️ 是，需要 `ADANOS_API_KEY`**

通过 Adanos Finance API 获取跨平台股票情绪数据（Reddit、X.com、新闻、Polymarket），适合判断市场热度和多空分歧。

---

### 插件四：社交阅读器（`finance-social-readers`）

**是否需要付费 API：✅ 基本免费，但需本地工具**

通过 [opencli](https://github.com/jackwener/opencli) 开源工具读取 Twitter/X、LinkedIn、Discord、Telegram 等平台，覆盖 Yahoo Finance、Bloomberg、雪球、东方财富、Reddit 等 90+ 数据源，只读，无需付费。需要本地安装 opencli（和 tdl for Telegram）。

---

### 综合评估

| 问题 | 结论 |
|------|------|
| 能满足实时获取价格需求吗？ | ✅ **`yfinance-data` skill 完全满足**，免费，美股/港股/ETF/加密货币均支持 |
| 是否需要付费 API？ | **取决于使用的 skill**：yfinance-data 完全免费；funda-data 和 finance-sentiment 需要付费 API Key |
| 建议的免费方案？ | `yfinance-data`（价格/基本面）+ `opencli-reader`（新闻/社交舆论）|
| 建议的完整方案？ | `funda-data`（付费，60+ 端点全覆盖）—— 一个 key 解决实时价格 + 期权 + 情绪 + 新闻 |
| 安装方式 | `npx plugins add himself65/finance-skills --plugin finance-market-analysis` |

---

## 一、实时股价接口

### 🥇 yfinance
- **GitHub**: https://github.com/ranaroussi/yfinance  
- **Stars**: ⭐ 23,422  
- **语言**: Python  
- **简介**: Yahoo Finance 数据接口，支持实时/历史价格、财务报表、期权链、股息等。使用最广泛的免费股票数据库，无需 API Key。  
- **适合场景**: 快速集成，美股/港股/ETF 均支持，适合 agent 直接调用获取实时行情。  
- **局限**: Yahoo Finance 本身偶尔限流，不适合高频量化；A 股数据质量一般。

---

### 🥇 AKShare
- **GitHub**: https://github.com/akfamily/akshare  
- **Stars**: ⭐ 18,913  
- **语言**: Python  
- **简介**: 国内最成熟的开源财经数据接口库，覆盖 A 股、港股、美股、期货、基金、宏观经济数据，数据来源包括东方财富、新浪、同花顺等。  
- **适合场景**: 需要 A 股实时行情或中文财经数据的 agent，与国内数据源对接首选。  
- **配套**: AKTools 提供 HTTP API 封装，可直接作为 MCP tool endpoint。

---

### 🥈 OpenBB
- **GitHub**: https://github.com/OpenBB-finance/OpenBB  
- **Stars**: ⭐ 67,099  
- **语言**: Python  
- **简介**: 面向分析师、量化和 AI agent 的金融数据平台，聚合 100+ 数据提供商（Polygon、Alpha Vantage、FRED 等），统一接口调用。官方已有 agent/MCP 集成支持。  
- **适合场景**: 需要多数据源聚合（不只是股价，还有宏观、债券、加密货币）的企业级 agent。  
- **局限**: 配置较复杂，部分高质量数据源需付费 API Key。

---

### 🥈 financial-datasets/mcp-server
- **GitHub**: https://github.com/financial-datasets/mcp-server  
- **Stars**: ⭐ 2,062  
- **语言**: Python  
- **简介**: 专为 MCP 协议设计的股票数据服务器，对接 Financial Datasets API，支持股价、财务数据、新闻等工具调用。  
- **适合场景**: 直接接入 Claude Desktop / 任何支持 MCP 的 agent 框架，零代码获取股票数据。  
- **局限**: 依赖 Financial Datasets 付费 API，免费额度有限。

---

### 🥈 yahoo-finance-mcp
- **GitHub**: https://github.com/Alex2Yang97/yahoo-finance-mcp  
- **Stars**: ⭐ 282  
- **语言**: Python  
- **简介**: 基于 Yahoo Finance 的 MCP server，提供历史价格、公司信息、财务报表、期权数据、市场新闻等 MCP tool 接口，免费无需 Key。  
- **适合场景**: 轻量接入，Claude agent 直接调用 yfinance 数据，无需自建服务。

---

### 🥉 MCP_Stock_Analysis（A股/港股/美股）
- **GitHub**: https://github.com/ZMX946/MCP_Stock_Analysis  
- **Stars**: ⭐ 7  
- **语言**: Python  
- **简介**: 基于 FastAPI + MCP 构建的股票分析服务，覆盖 A 股、港股、美股及基金，集成技术指标计算（MACD、RSI、BOLL 等）、评分模型，并通过 FastApiMCP 自动注册为 MCP tool，可被 LLM 直接调用。  
- **适合场景**: 需要中文市场覆盖且有 AI 分析能力的 MCP server，适合本地部署。

---

### 🥉 mcp-stockflow / mcp-stockscreen
- **GitHub**: https://github.com/twolven/mcp-stockflow  
- **Stars**: ⭐ 25 / 39  
- **语言**: Python  
- **简介**: 两个轻量 MCP server，分别提供股票行情数据（stockflow）和股票筛选（stockscreen），专为 Claude Desktop 设计。  
- **适合场景**: Claude Desktop 快速试验，开箱即用。

---

## 二、投资知识 / Agent 技能

### 🥇 FinGPT
- **GitHub**: https://github.com/AI4Finance-Foundation/FinGPT  
- **Stars**: ⭐ 19,951  
- **语言**: Python / Jupyter  
- **简介**: AI4Finance 基金会出品，开源金融大语言模型。提供情感分析、股票走势预测、金融新闻摘要、财报解读等能力。模型已发布在 HuggingFace，可本地微调部署。  
- **适合场景**: 给 agent 注入金融领域语言理解能力，尤其是新闻情感 → 股价关联分析。

---

### 🥇 FinRL
- **GitHub**: https://github.com/AI4Finance-Foundation/FinRL  
- **Stars**: ⭐ 15,078  
- **语言**: Python / Jupyter  
- **简介**: 金融强化学习框架，训练 agent 在股票/加密货币市场做交易决策。支持多种 RL 算法（PPO、A2C、DDPG 等），内置回测环境。  
- **适合场景**: 需要 agent 自主学习交易策略，而非依赖规则或 LLM 推理的场景。

---

### 🥇 FinRobot
- **GitHub**: https://github.com/AI4Finance-Foundation/FinRobot  
- **Stars**: ⭐ 6,875  
- **语言**: Python / Jupyter  
- **简介**: 基于 LLM 的金融分析 AI agent 平台，内置多个专业 agent（市场预测、文件分析、财报解读），支持与 AutoGen 等框架集成。  
- **适合场景**: 构建多 agent 投资分析流水线，各 agent 分工：数据获取 → 分析 → 建议生成。

---

### 🥈 FinanceToolkit
- **GitHub**: https://github.com/JerBouma/FinanceToolkit  
- **Stars**: ⭐ 4,728  
- **语言**: Python  
- **简介**: 透明、高效的金融分析工具库，涵盖 100+ 金融指标（P/E、DCF、夏普比率、β 值等），一行代码获取任意股票的完整基本面分析。  
- **适合场景**: 给 agent 提供量化的基本面分析能力，作为 tool function 直接集成。

---

### 🥈 FinanceDatabase
- **GitHub**: https://github.com/JerBouma/FinanceDatabase  
- **Stars**: ⭐ 7,565  
- **语言**: Python  
- **简介**: 包含 30 万+ 金融标的（股票、ETF、基金、指数、外汇、加密货币）的结构化数据库，支持按行业、国家、市值等筛选。  
- **适合场景**: 给 agent 提供标的发现能力，辅助回答"哪些股票属于新能源行业"之类的问题。

---

### 🥈 shashankvemuri/Finance
- **GitHub**: https://github.com/shashankvemuri/Finance  
- **Stars**: ⭐ 3,830  
- **语言**: Python  
- **简介**: 150+ 量化金融 Python 程序集合，覆盖数据获取、技术分析、投资组合优化、期权定价、风险管理等主题，每个程序独立可运行。  
- **适合场景**: 作为 agent skill 的参考实现库，快速找到某类金融计算的代码原型。

---

### 🥉 MCP_StockAssistant
- **GitHub**: https://github.com/AdvaitDarbare/MCP_StockAssistant  
- **Stars**: ⭐ 6  
- **语言**: Python  
- **简介**: 基于 Claude AI + LangGraph + FastAPI 的多 agent 股票助手，通过 Schwab & Finviz API 提供实时报价、基本面、新闻、期权链和历史图表，符合 MCP 协议。  
- **适合场景**: 完整的投资助手 agent 参考实现，可直接 fork 改造。

---

## 三、综合对比与选型建议

| 需求 | 推荐方案 |
|------|---------|
| 快速获取美股实时价格（免费） | yfinance + yahoo-finance-mcp |
| A 股实时行情 | AKShare（+ AKTools HTTP 封装） |
| 多数据源聚合（专业级） | OpenBB |
| 直接插入 Claude Desktop | financial-datasets/mcp-server 或 yahoo-finance-mcp |
| 金融语言理解 / 新闻分析 | FinGPT |
| 基本面量化分析技能 | FinanceToolkit |
| 多 agent 投资分析流水线 | FinRobot |
| 完整 agent 参考实现 | MCP_StockAssistant |

**推荐组合（MVP）**：  
`yfinance / AKShare`（数据层）+ `yahoo-finance-mcp`（MCP 接口层）+ `FinGPT 情感分析`（知识层）+ `FinanceToolkit`（基本面分析技能）
