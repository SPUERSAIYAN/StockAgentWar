# 当前数据源整理

本文档按当前代码和 `config.yaml` 配置整理数据源。信息收集入口在 `collectors/digital_oracle_collector.py`，实际数据源按 `collectors/connectors/` 分组调用，统一汇总到 `raw_market_data` 和 `info_report`。

## 总览

| 分组 | 当前状态 | 数据源 | 所属市场 | 主要作用 |
| --- | --- | --- | --- | --- |
| `us_equity` | 启用 | Yahoo Finance Prices | 美股、ETF、全球指数、商品期货、外汇 | 候选标的日/周 K 线，宏观代理资产价格 |
| `us_equity` | 启用 | Yahoo Finance Options | 美股期权 | 期权链、ATM IV、隐含波动、Put/Call、Max Pain |
| `us_equity` | 启用 | SEC EDGAR | 美国上市公司公告市场 | Form 4 内部人交易、10-K/10-Q 等公告检索 |
| `us_equity` | 未启用 | Stooq 兼容层 | 全球价格兼容符号 | 旧 Stooq 符号到 Yahoo 符号的兼容转发 |
| `china_equity` | 启用 | Tencent Finance | A 股、A 股指数；接口也支持港股/美股快照 | 实时价格、估值、市值、换手率、量比、指数快照 |
| `china_equity` | 启用 | MooTDX | A 股、沪深指数、本地通达信数据 | K 线、实时行情、分时、盘口、分笔、财务摘要、股本/股东、F10 |
| `china_equity` | 启用 | 本地 Excel 概念板块表 `astockdate/全部A股20264.xlsx` | A 股概念板块成分股 | 指定板块/概念任务的候选发现和静态评分 |
| `macro` | 启用 | U.S. Treasury | 美国利率与财政汇率数据 | 国债收益率曲线、实际利率、短债、长期利率、财政部汇率 |
| `macro` | 启用 | CNN Fear & Greed | 美股情绪 | 风险偏好/恐慌情绪快照 |
| `macro` | 启用 | CME FedWatch | 美国利率期货 | FOMC 目标利率隐含概率 |
| `macro` | 启用 | CFTC COT | 商品、金融期货持仓 | 管理基金、商业、掉期商持仓和净头寸 |
| `macro` | 未启用 | BIS | 全球央行与信用周期 | 政策利率、信用/GDP 缺口 |
| `macro` | 未启用 | World Bank | 全球宏观经济 | GDP、CPI、实际利率等年度指标 |
| `prediction_markets` | 启用 | Kalshi | 美国监管预测市场 | 事件合约概率、成交量、流动性、盘口 |
| `prediction_markets` | 启用 | Polymarket | 全球/加密预测市场 | 事件市场、结果概率、成交量、流动性、盘口 |
| `crypto` | 启用 | CoinGecko | 加密现货市场 | 币价、市值、24h 成交量、全市场概览 |
| `crypto` | 启用 | Deribit | 加密衍生品市场 | BTC/ETH 期货期限结构、期权链、盘口 |
| `web_search` | 未启用 | DuckDuckGo + 页面抓取 | 泛网页信息 | 新闻/网页搜索摘要、指定网页正文抓取 |

## 当前默认采集范围

### 候选标的与价格

- 非 A 股候选标的走 `us_equity` 分组；A 股候选标的走 `china_equity` 分组。
- A 股板块、行业、概念、地域、通达信板块或板块轮动任务仍走 `china_equity` 分组；指定概念板块成分股优先从本地 Excel `astockdate/全部A股20264.xlsx` 的 `Sheet1.概念板块` 获取，后续实时行情和估值继续由 Tencent/MooTDX 等 A 股行情源补充。
- 问题规划 Agent 决定是否触发这个本地 Excel 的方式是：对 A 股板块/概念/行业/地域/通达信板块任务选择 `china_equity`，并把识别出的板块或概念写入 `question_understanding.sector_terms`。Python collector 会据此调用 `candidate_discovery.local_concept_board`，读取 `astockdate/全部A股20264.xlsx`；LLM 不直接打开文件。
- A 股任务没有显式候选股票时，会启用自动候选发现：`MooTDX.list_stocks()` 扫描沪深 A 股列表，再用 `TencentFinanceProvider.get_stock_metrics()` 批量拉取实时指标并排序。
- A 股指定板块任务没有显式候选股票时，前端 `sectors` 优先；若前端未传，问题规划 Agent 应把自然语言中识别出的板块/概念写入 `question_understanding.sector_terms`，供本地 Excel 概念板块源使用。
- 当前 A 股自动候选发现配置：最多输出 15 个候选，扫描上限 5000，批量大小 80，过滤 ST、停牌、低于 50 亿市值、PE 高于 80 的标的。
- 当前宏观代理价格由 Yahoo 拉取：`SPY`、`QQQ`、`^VIX`、`GC=F`、`USDCNY=X`。

## 数据源明细

### Yahoo Finance Prices

- 代码入口：`YahooPriceProvider`
- 调用位置：`collectors/connectors/equity.py`、`collectors/connectors/macro.py`
- 当前状态：启用
- 所属市场：美股、ETF、全球指数、商品期货、外汇；也可覆盖 Yahoo Finance 支持的欧洲股票等全球资产。
- 主要作用：拉取 OHLCV 历史价格，候选标的默认拉日 K 与周 K，宏观代理资产拉日 K。
- 典型输出：开高低收、成交量、总收益率、20 bar 收益率、20 bar 高低点、20 bar 平均成交量、20 bar 年化实现波动率。
- 注意：外汇类 Yahoo 符号成交量通常为 0，这是 OTC 外汇市场数据特征，不代表采集失败。

### Yahoo Finance Options

- 代码入口：`YFinanceProvider`
- 调用位置：`collectors/connectors/equity.py`
- 当前状态：启用，仅对纯美股 ticker 生效，例如 `AAPL`、`MSFT`、`SPY`。
- 所属市场：美国股票期权市场。
- 主要作用：拉取最近到期期权链，并计算 Black-Scholes Greeks。
- 典型输出：标的价格、到期日、ATM strike、ATM IV、隐含波动区间、Put/Call 成交量比、Put/Call 持仓比、总成交量、总持仓量、Max Pain。

### SEC EDGAR

- 代码入口：`EdgarProvider`
- 调用位置：`collectors/connectors/equity.py`
- 当前状态：启用，仅对纯美股 ticker 生效。
- 所属市场：美国上市公司监管披露市场。
- 主要作用：拉取内部人交易与公告检索结果。
- 典型输出：Form 4 数量、最近 Form 4、10-K/10-Q 检索命中、公告日期、表格类型、描述。
- 当前配置：`edgar_form4_limit=8`，`edgar_filing_forms=10-K,10-Q`，`edgar_filing_limit=8`。

### Stooq 兼容层

- 代码入口：`StooqProvider`
- 调用位置：`collectors/connectors/equity.py`
- 当前状态：未启用，`stooq_compat=false`。
- 所属市场：全球价格数据兼容层。
- 主要作用：兼容旧 Stooq 风格符号，并映射到 Yahoo Finance，例如 `xauusd` 到 `GC=F`、`cl.c` 到 `CL=F`。
- 注意：当前实现实际委托给 `YahooPriceProvider`，不是独立 Stooq 网络数据源。

### Tencent Finance

- 代码入口：`TencentFinanceProvider`
- 调用位置：`collectors/connectors/china.py`、候选发现、交易监控 `trade_monitor.price_source=tencent`
- 当前状态：启用。
- 所属市场：A 股、沪深主要指数；Provider 能力也支持港股和美股快照，但当前默认采集主要用于 A 股。
- 主要作用：拉取实时交易和估值指标，用于 A 股候选排序、个股分析、指数快照和模拟交易价格监控。
- 典型输出：价格、涨跌幅、成交量、成交额、换手率、PE、PB、流通市值、总市值、振幅、量比、涨停价、跌停价、时间戳。
- 当前指数：`sh000001`、`sz399001`、`sz399006`、`sh000300`。

### MooTDX

- 代码入口：`MootdxProvider`
- 调用位置：`collectors/connectors/china.py`、A 股自动候选发现。
- 当前状态：启用。
- 所属市场：中国 A 股、沪深指数、本地通达信数据。
- 主要作用：提供 A 股深度行情和基础资料。
- 当前个股 K 线频率：`day`、`week`、`month`、`1m`、`5m`、`15m`、`30m`、`1h`。
- 当前指数 K 线频率：`day`、`week`、`month`、`1m`、`5m`、`15m`、`30m`、`1h`。
- 典型输出：K 线、实时行情、分时点、五档盘口、财务摘要、股东/股本快照、F10 公司资料、分笔交易。
- 当前启用项：实时行情、分时、盘口、财务摘要、股东、F10 公司资料、分笔交易。
- 未启用项：`mootdx_local_tdxdir` 为空，因此本地通达信文件读取不会主动执行。

### 本地 Excel 概念板块表

- 文件路径：`astockdate/全部A股20264.xlsx`
- 代码入口：`collectors/local_a_share_concepts.py`
- 调用位置：`collectors/digital_oracle_collector.py` 的 A 股候选发现流程。
- 当前状态：启用，配置项为 `candidate_discovery.local_concept_board_path`。
- 所属市场：中国 A 股概念板块成分股与静态基本面表。
- 主要作用：当任务要求分析指定 A 股板块、行业、概念、地域、通达信板块或板块轮动，且没有显式股票代码时，用本地 Excel 生成候选股票池。
- 触发条件：`provider_selection.selected_groups` 包含 `china_equity`，并且前端 `scan_scope.sectors` 或 `question_understanding.sector_terms` 提供了板块/概念词。
- 问题规划动作：如果任务中出现“半导体板块”“白酒概念”“机器人行业”等 A 股板块/概念表达，输出 `sector_terms`，并在 `china_equity.reason` 中说明需要使用本地 Excel 概念板块表。
- 典型输出：`candidate_discovery.local_concept_board` source label、匹配板块、候选股票、Excel 静态评分、行业/概念、ROE、营收增速、归母净利润增速、PE、总市值等 metadata。
- 限制：只匹配 `Sheet1` 的 `概念板块` 列，不把 `行业` 列当作板块匹配源；Excel 只做候选发现和静态评分，不替代 Tencent/MooTDX 的实时行情与估值补充。

### U.S. Treasury

- 代码入口：`USTreasuryProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：启用。
- 所属市场：美国国债利率市场、美国财政部汇率数据。
- 主要作用：提供利率曲线和财政部汇率，作为宏观流动性、期限利差、美元相关风险判断依据。
- 当前采集：名义收益率曲线、实际收益率曲线、短债曲线、长期利率、财政部汇率。
- 当前汇率国家：China、Japan。
- 典型输出：各期限收益率、10Y-2Y 利差、10Y-3M 利差、国家/币种汇率记录。

### CNN Fear & Greed

- 代码入口：`FearGreedProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：启用。
- 所属市场：美股市场情绪。
- 主要作用：补充风险偏好和恐慌程度。
- 典型输出：0-100 分数、评级、前收、一周前、一月前、一年前数值。

### CME FedWatch

- 代码入口：`CMEFedWatchProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：启用。
- 所属市场：美国联邦基金利率期货/利率预期。
- 主要作用：读取市场对后续 FOMC 目标利率区间的隐含概率。
- 典型输出：会议日期、当前目标区间、各目标区间概率。

### CFTC COT

- 代码入口：`CftcCotProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：启用。
- 所属市场：美国期货市场。
- 主要作用：识别商品和指数期货中不同参与者的持仓方向。
- 当前品种：`GOLD`、`CRUDE OIL`、`S&P 500`。
- 典型输出：报告日期、市场名称、未平仓量、Managed Money 多空与净头寸、Producer/Merchant 多空与净头寸、Swap Dealer 持仓。

### BIS

- 代码入口：`BisProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：未启用，`bis=false`。
- 所属市场：全球央行政策利率、信用周期宏观数据。
- 主要作用：提供跨国政策利率和信用/GDP 缺口，用于判断信用过热、宏观周期和系统性风险。
- 配置准备值：国家 `US`、`CN`，政策利率起始年 2020，信用缺口起始年 2018。

### World Bank

- 代码入口：`WorldBankProvider`
- 调用位置：`collectors/connectors/macro.py`
- 当前状态：未启用，`worldbank=false`。
- 所属市场：全球宏观经济基本面。
- 主要作用：提供年度宏观指标，适合中长期国家/地区基本面背景，不适合高频交易信号。
- 配置准备值：国家 `US`、`CN`，日期范围 `2018:2026`，指标包括 GDP、CPI、实际利率。

### Kalshi

- 代码入口：`KalshiProvider`
- 调用位置：`collectors/connectors/prediction.py`
- 当前状态：启用。
- 所属市场：美国监管预测市场。
- 主要作用：读取事件合约价格，把真实交易价格转成概率信号。
- 当前采集：开放市场列表，limit 10；未指定 series/event/ticker 过滤。
- 典型输出：市场 ticker、事件 ticker、标题、yes/no bid/ask、last price、成交量、24h 成交量、未平仓、流动性、规则。
- 未启用项：`kalshi_event_tickers` 和 `kalshi_orderbook_tickers` 为空，因此不会主动拉指定事件详情或盘口。

### Polymarket

- 代码入口：`PolymarketProvider`
- 调用位置：`collectors/connectors/prediction.py`
- 当前状态：启用。
- 所属市场：全球/加密预测市场。
- 主要作用：读取主题事件市场概率，补充宏观、加密、利率相关事件的市场定价。
- 当前标签：`economy`、`crypto`、`fed`，每个标签 limit 10。
- 典型输出：事件标题、slug、市场问题、yes 概率、成交量、24h 成交量、流动性、open interest、结果 token。
- 未启用项：`polymarket_event_slugs` 和 `polymarket_orderbook_token_ids` 为空，因此不会主动拉指定事件详情或盘口。

### CoinGecko

- 代码入口：`CoinGeckoProvider`
- 调用位置：`collectors/connectors/crypto.py`
- 当前状态：启用。
- 所属市场：加密现货市场。
- 主要作用：提供主流币价格、市值、成交量和全市场概览。
- 当前币种：`bitcoin`、`ethereum`。
- 当前市场列表：按市值拉前 20。
- 典型输出：美元价格、市值、24h 成交量、24h 涨跌幅、BTC/ETH dominance、总市值、活跃币种数。

### Deribit

- 代码入口：`DeribitProvider`
- 调用位置：`collectors/connectors/crypto.py`
- 当前状态：启用。
- 所属市场：加密衍生品市场。
- 主要作用：读取 BTC/ETH 衍生品期限结构和期权隐含波动。
- 当前币种：`BTC`、`ETH`。
- 当前采集：期货期限结构、期权链。
- 典型输出：永续/交割合约价格、相对永续 basis、年化 basis、open interest、期权到期、标的价格、ATM strike。
- 未启用项：`deribit_orderbook_instruments` 为空，因此不会主动拉指定合约盘口。

### Web Search

- 代码入口：`WebSearchProvider`
- 调用位置：`collectors/connectors/web_search.py`
- 当前状态：未启用，`web_search.enabled=false`。
- 所属市场：泛网页信息，不绑定单一市场。
- 主要作用：补足结构化 Provider 无法覆盖的新闻、网页、另类数据和临时查询。
- 典型输出：DuckDuckGo 搜索标题、链接、摘要；指定网页标题和正文截断内容。
- 注意：启用后如果未配置 queries，会按任务和候选 symbols 自动生成市场新闻/业绩展望查询。

## 市场归属索引

| 市场/数据域 | 当前主要数据源 |
| --- | --- |
| A 股个股与指数 | Tencent Finance、MooTDX |
| A 股板块与成分股 | 本地 Excel 概念板块表 `astockdate/全部A股20264.xlsx` |
| A 股候选发现 | 全市场：MooTDX 股票列表 + Tencent Finance 实时指标；指定概念板块：本地 Excel 成分股 + Excel 静态评分 |
| 美股价格与 ETF | Yahoo Finance Prices |
| 美股期权 | Yahoo Finance Options |
| 美国上市公司公告 | SEC EDGAR |
| 全球指数/商品/外汇价格代理 | Yahoo Finance Prices |
| 美国利率与收益率曲线 | U.S. Treasury、CME FedWatch |
| 美国/全球期货持仓 | CFTC COT |
| 美股情绪 | CNN Fear & Greed、Yahoo 宏观代理资产 |
| 全球宏观慢变量 | BIS、World Bank（当前未启用） |
| 预测市场 | Kalshi、Polymarket |
| 加密现货 | CoinGecko |
| 加密衍生品 | Deribit |
| 临时新闻/网页 | Web Search（当前未启用） |

## 当前未主动采集但已有代码支持

- Stooq 兼容价格：需要打开 `providers.us_equity.stooq_compat`。
- MooTDX 本地通达信文件：需要配置 `providers.china_equity.mootdx_local_tdxdir`。
- Kalshi 指定事件和盘口：需要配置 `kalshi_event_tickers` 或 `kalshi_orderbook_tickers`。
- Polymarket 指定事件和盘口：需要配置 `polymarket_event_slugs` 或 `polymarket_orderbook_token_ids`。
- Deribit 指定合约盘口：需要配置 `deribit_orderbook_instruments`。
- BIS 与 World Bank：需要把 `providers.macro.bis`、`providers.macro.worldbank` 改为 `true`。
- Web Search：需要把 `providers.web_search.enabled` 改为 `true`，并可配置 `queries` 或 `pages`。
