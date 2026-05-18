# Digital Oracle 数据源状态

当前配置已把 Yahoo、CFTC、CME FedWatch、预测市场和原 crypto 数据源关闭，并新增 Tushare Pro 作为统一结构化行情入口。旧 provider 代码保留，但默认不再参与采集。

| 数据源 / Provider | 当前配置 | 覆盖市场 / 类型 | 获取的数据 | 主要用途 | 依赖 | API Key |
| --- | --- | --- | --- | --- | --- | --- |
| `TushareProvider` | 启用 | A 股、美股、指数/ETF、期货期权、宏观利率 | A 股 K 线、财务报表、财务指标、资金流、龙虎榜、指数/ETF、国内期货期权、Shibor、中国宏观、美国国债利率、美股列表和日线 | 替代 Yahoo 美股/指数价格路径，补充 A 股基本面、资金面和宏观利率数据 | `tushare` | `config.yaml` |
| `TencentFinanceProvider` | 启用 | 腾讯财经 / A 股、指数、港股、美股快照 | PE、PB、市值、换手率、涨跌幅、成交量、成交额 | A 股估值、实时交易指标、指数快照 | 无额外依赖 | 无 |
| `MootdxProvider` | 启用 | 中国 A 股 / 通达信 | 日/周/月/分钟 K、实时行情、分时、分笔、五档盘口、指数 K、本地通达信文件、财务摘要、F10 公司概况 | A 股行情、盘口、财务摘要、本地数据读取 | `mootdx` | 无 |
| `USTreasuryProvider` | 启用 | 美国财政部 | 国债收益率曲线、实际利率、票据利率、长期利率、财政部汇率 | 利率曲线、通胀预期、美元流动性 | 无额外依赖 | 无 |
| `FearGreedProvider` | 启用 | CNN Fear & Greed Index | 恐惧贪婪指数、评级、历史对比值 | 美股市场情绪、风险偏好判断 | 无额外依赖 | 无 |
| `EdgarProvider` | 关闭 | SEC EDGAR | 公司公告检索、Form 4 内部人交易 | 10-K/10-Q 检索、风险披露、内部人交易 | 无额外依赖 | 无 |
| `YahooPriceProvider` | 关闭 | 全球股票、ETF、外汇、商品、指数 | OHLCV 历史价格 | 已由 Tushare 美股/指数日线替代可用部分 | `yfinance` | 无 |
| `YFinanceProvider` | 关闭 | 美股期权 | 到期日、期权链、IV、Greeks、put/call、max pain | 期权情绪、隐含波动率、事件预期 | `yfinance` | 无 |
| `CftcCotProvider` | 关闭 | CFTC COT 持仓报告 | 管理基金、商业交易商、掉期商持仓，open interest | 商品、股指、外汇期货仓位分析 | 无额外依赖 | 无 |
| `CMEFedWatchProvider` | 关闭 | CME FedWatch | FOMC 会议目标利率概率 | 市场隐含加息/降息概率 | 无额外依赖 | 无 |
| `PolymarketProvider` | 关闭 | 事件合约 / 预测市场 | 事件、市场、概率、orderbook | 事件概率定价、市场预期 | 无额外依赖 | 无 |
| `KalshiProvider` | 关闭 | 美国事件合约市场 | 市场、事件、概率、orderbook | 利率、宏观、事件类概率定价 | 无额外依赖 | 无 |
| `DeribitProvider` | 关闭 | 加密衍生品 | BTC/ETH 期货期限结构、期权链、orderbook | 加密市场期限结构、IV、风险偏好 | 无额外依赖 | 无 |
| `CoinGeckoProvider` | 关闭 | 加密现货市场 | 币价、市值、成交量、涨跌幅、BTC/ETH dominance、排名 | 加密资产行情、市场总览 | 无额外依赖 | 无 |
| `BisProvider` | 关闭 | BIS 国际清算银行 | 央行政策利率、Credit-to-GDP gap | 政策利率比较、信用周期、金融过热指标 | 无额外依赖 | 无 |
| `WorldBankProvider` | 关闭 | 世界银行 | GDP、人口、通胀、贸易、经常账户等宏观指标 | 国家宏观基本面、长期经济趋势 | 无额外依赖 | 无 |
| `WebSearchProvider` | 关闭 | DuckDuckGo / 网页 | 搜索摘要、网页正文抓取 | 补充非结构化公开信息 | 无额外依赖 | 无 |

## Tushare 接入说明

- 统一初始化位于 `collectors/tushare/client.py`，所有调用都执行 `ts.pro_api(token)` 后设置 `pro._DataApi__http_url = "http://118.89.66.41:8010/"`。
- 当前已验证可用：`index_basic(limit=5)`、`ts.pro_bar(api=pro, ts_code="000001.SZ", limit=3)`、`us_daily(ts_code="AAPL")`。
- 已扩展默认接入：A 股 `income`、`balancesheet`、`cashflow`、`fina_indicator`、`dividend`、`disclosure_date`，资金流 `moneyflow`、`moneyflow_hsgt`、两融 `margin`/`margin_detail`、龙虎榜 `top_list`/`top_inst`，指数 `index_weight`/`index_dailybasic`，ETF/基金 `fund_basic`/`fund_daily`/`fund_nav`，国内期货期权 `fut_basic`/`fut_daily`/`fut_mapping`/`opt_basic`，宏观 `shibor`、`cn_gdp`、`cn_cpi`、`cn_pmi`。
- 美国利率接口已通过代理 smoke 并默认启用：`us_tycr` 国债收益率曲线、`us_trycr` 实际收益率曲线、`us_tbr` 短期国债利率、`us_tltr` 长期国债利率、`us_trltr` 实际长期利率平均值。
- 当前专用代理返回“接口名不存在”：`coincap`、`coinlist`、`coin_bar`。因此 Tushare crypto 代码保留，但 `config.yaml` 默认关闭 `providers.tushare.crypto`。

## 配置要点

- `providers.us_equity.enabled=false`，且 `price`、`weekly_price`、`options`、`edgar`、`edgar_filings` 均关闭。
- `macro_symbols=[]`，避免 Yahoo 宏观代理价格任务生成。
- `providers.macro.cme_fedwatch=false`、`providers.macro.cftc=false`。
- `providers.prediction_markets.enabled=false`，Kalshi 和 Polymarket 子开关关闭。
- `providers.crypto.enabled=false`，CoinGecko 和 Deribit 子开关关闭。
- `providers.tushare.enabled=true`，A 股、美股、指数/ETF、资金流/龙虎榜、国内期货期权和宏观利率任务启用；crypto 子任务默认关闭。
- `fund_portfolio`、美股财报接口、`moneyflow_ind_dc`、`report_rc` 等超权限或代理不稳定接口不启用。
