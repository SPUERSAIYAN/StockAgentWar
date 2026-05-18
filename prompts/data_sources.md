# 当前数据源整理

本文档是 QuestionPlanningAgent 选择数据源分组的依据。Planner 只输出业务分组：
`us_equity`、`china_equity`、`macro`、`prediction_markets`、`crypto`、`web_search`。

注意：`tushare` 是当前主要结构化数据实现，不是 planner 可输出的 provider group。Python collector 会把业务分组映射到 `providers.tushare` 的子接口。

## 总览

| 分组 | 当前状态 | 当前主要实现 | 所属市场 | 主要作用 |
| --- | --- | --- | --- | --- |
| `us_equity` | 启用 | Tushare Pro `us_basic`、`us_daily` | 美股、美股 ETF | 美股列表、日线行情、候选标的价格趋势 |
| `china_equity` | 启用 | Tushare Pro、Tencent Finance、MooTDX、本地 Excel | A 股、A 股指数、ETF、国内期货期权 | A 股行情、财务基本面、资金流、龙虎榜、指数/ETF、期货期权、候选发现 |
| `macro` | 启用 | Tushare Pro 美国利率、中国宏观、U.S. Treasury、Fear & Greed | 美国利率、中国宏观、风险偏好 | 美国国债收益率曲线、实际利率、短债/长期利率、Shibor、GDP/CPI/PMI、情绪 |
| `prediction_markets` | 关闭 | Kalshi、Polymarket | 预测市场 | 当前默认不采集；Tushare 无等价替代 |
| `crypto` | 关闭 | CoinGecko、Deribit；Tushare crypto 代理不可用 | 加密资产 | 当前默认不采集；Tushare crypto 接口在当前代理返回接口不存在 |
| `web_search` | 关闭 | DuckDuckGo + 页面抓取 | 泛网页结构化缺口 | 仅在明确需要结构化网页数据缺口时启用 |

## Tushare 当前覆盖

### 美股

- `us_basic`：美股基础列表。
- `us_daily`：美股日线行情。
- 当前没有启用 Yahoo 美股价格、Yahoo 期权、SEC EDGAR；因此美股问题应选 `us_equity`，后端会走 Tushare 美股接口。
- 美股财报类 Tushare 接口需要更高积分/权限，当前 5000 积分默认不启用。

### A 股

选择 `china_equity` 会启用 A 股相关接口：

- 行情：A 股日/周 K、`daily_basic`。
- 财务基本面：`income`、`balancesheet`、`cashflow`、`fina_indicator`、`dividend`、`disclosure_date`。
- 资金流/龙虎榜：`moneyflow`、`moneyflow_hsgt`、`margin`、`margin_detail`、`top_list`、`top_inst`。
- 指数/ETF：`index_basic`、`index_daily`、`index_weight`、`index_dailybasic`、`fund_basic`、`fund_daily`、`fund_nav`。
- 国内期货期权：`fut_basic`、`fut_daily`、`fut_mapping`、`opt_basic`。
- Tencent/MooTDX 仍用于 A 股实时行情、盘口、本地/通达信补充数据和候选发现。

### A 股候选发现

- A 股板块、行业、概念、地域、通达信板块、板块轮动任务，应选择 `china_equity`。
- 若没有显式股票代码，planner 应把板块/概念词写入 `question_understanding.sector_terms`。
- Python collector 会读取 `astockdate/全部A股20264.xlsx` 生成候选股票池；LLM 不直接打开 Excel，也不能自行编造股票代码。

### 宏观利率与经济

选择 `macro` 会启用宏观数据。若没有选择 `china_equity`，Tushare 中国宏观会被后端过滤，只保留美国利率相关接口。

- 美国国债收益率曲线：`us_tycr`。
- 美国国债实际收益率曲线：`us_trycr`。
- 美国短期国债利率：`us_tbr`。
- 美国长期国债利率：`us_tltr`。
- 美国实际长期利率均值：`us_trltr`。
- 中国宏观：`shibor`、`cn_gdp`、`cn_cpi`、`cn_pmi`，仅在中国/A 股相关问题中作为宏观上下文。
- U.S. Treasury 和 Fear & Greed 仍可作为补充宏观与风险偏好来源。

## 关闭与缺口

- Yahoo/CFTC/CME FedWatch/预测市场/旧 crypto 已在 `config.yaml` 默认关闭。
- `macro_symbols=[]`，不再通过 Yahoo 拉 SPY、QQQ、VIX、黄金、USDCNY 代理价格。
- Tushare 未提供 CFTC COT、CME FedWatch、Kalshi/Polymarket 等价接口；这些仍是数据缺口。
- Tushare crypto 接口 `coinlist`、`coincap`、`coin_bar` 当前代理返回接口不存在，默认关闭。
- `fund_portfolio` 当前代理超时，默认关闭。
- `moneyflow_ind_dc`、`report_rc` 等高积分接口当前 5000 积分不启用。

## Planner 选择规则

- 美股个股、ETF、美国上市资产问题：选择 `us_equity`；通常也选择 `macro`。
- A 股个股、A 股指数、A 股 ETF、A 股板块/概念/行业、国内期货期权问题：选择 `china_equity`；通常也选择 `macro`。
- A 股宏观、大盘、流动性、政策、指数风险、市场环境问题：选择 `china_equity` + `macro`，但不要输出 `sector_terms`，也不要触发本地 Excel 候选发现。
- 美国利率、收益率曲线、宏观经济、风险偏好问题：选择 `macro`。
- 事件概率、政策事件定价、预测市场问题：只有用户明确需要预测市场概率时才选择 `prediction_markets`；当前默认关闭且可能没有数据。
- 加密资产问题：只有用户明确问 crypto/BTC/ETH 或加密风险偏好时才选择 `crypto`；当前默认关闭且 Tushare crypto 不可用。
- Web 数据：只有明确存在结构化数据缺口时选择 `web_search`，不要为普通新闻、观点、传闻启用。

## 市场归属索引

| 用户问题 | 应选分组 | 说明 |
| --- | --- | --- |
| AAPL、MSFT、NVDA、SPY 等美股/ETF | `us_equity` + `macro` | 后端走 Tushare 美股日线和美国利率 |
| A 股个股，如 600519、000001.SZ | `china_equity` + `macro` | 后端走 Tushare A 股行情/财务/资金流与 A 股补充源 |
| A 股板块，如半导体、白酒、机器人 | `china_equity` + `macro` | 同时输出 `sector_terms`，触发本地 Excel 候选发现 |
| A 股宏观、大盘流动性、指数风险 | `china_equity` + `macro` | 不输出 `sector_terms`；后端走市场/指数/宏观轻量采集，不扫候选股票 |
| 美国利率、收益率曲线、实际利率、短债 | `macro` | 后端走 Tushare 美国国债利率接口 |
| 加息概率、CFTC 持仓、预测市场概率 | `macro` 或 `prediction_markets`，但标注缺口 | 当前 CME/CFTC/预测市场默认关闭，Tushare 无等价替代 |
| BTC/ETH、加密衍生品 | `crypto`，但标注缺口 | 当前旧 crypto 关闭，Tushare crypto 代理不可用 |
