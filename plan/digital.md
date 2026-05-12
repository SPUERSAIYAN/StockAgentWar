| 数据源 / Provider          | 覆盖市场 / 类型                       | 获取的数据                                                                                      | 主要用途                               | 依赖         | API Key |
| -------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------- | ------------ | ------- |
| `PolymarketProvider`     | 事件合约 / 预测市场                   | 事件、市场、概率、orderbook                                                                     | 事件概率定价、市场预期                 | 无额外依赖   | 无      |
| `KalshiProvider`         | 美国事件合约市场                      | 市场、事件、概率、orderbook                                                                     | 利率、宏观、事件类概率定价             | 无额外依赖   | 无      |
| `YahooPriceProvider`     | 全球股票、ETF、外汇、商品、指数       | OHLCV 历史价格                                                                                  | 价格走势、资产对比、技术分析           | `yfinance` | 无      |
| `YFinanceProvider`       | 美股期权                              | 到期日、期权链、IV、Greeks、put/call、max pain                                                  | 期权情绪、隐含波动率、事件预期         | `yfinance` | 无      |
| `DeribitProvider`        | 加密衍生品                            | BTC/ETH 期货期限结构、期权链、orderbook                                                         | 加密市场期限结构、IV、风险偏好         | 无额外依赖   | 无      |
| `CoinGeckoProvider`      | 加密现货市场                          | 币价、市值、成交量、涨跌幅、BTC/ETH dominance、排名                                             | 加密资产行情、市场总览                 | 无额外依赖   | 无      |
| `USTreasuryProvider`     | 美国财政部                            | 国债收益率曲线、实际利率、票据利率、长期利率、财政部汇率                                        | 利率曲线、通胀预期、美元流动性         | 无额外依赖   | 无      |
| `CftcCotProvider`        | CFTC COT 持仓报告                     | 管理基金、商业交易商、掉期商持仓，open interest                                                 | 商品、股指、外汇期货仓位分析           | 无额外依赖   | 无      |
| `EdgarProvider`          | SEC EDGAR                             | 公司公告检索、Form 4 内部人交易                                                                 | 10-K/10-Q 检索、风险披露、内部人交易   | 无额外依赖   | 无      |
| `BisProvider`            | BIS 国际清算银行                      | 央行政策利率、Credit-to-GDP gap                                                                 | 政策利率比较、信用周期、金融过热指标   | 无额外依赖   | 无      |
| `WorldBankProvider`      | 世界银行                              | GDP、人口、通胀、贸易、经常账户等宏观指标                                                       | 国家宏观基本面、长期经济趋势           | 无额外依赖   | 无      |
| `MootdxProvider`         | 中国 A 股 / 通达信                    | 日/周/月/分钟 K、实时行情、分时、分笔、五档盘口、指数 K、本地通达信文件、财务摘要、F10 公司概况 | A 股行情、盘口、财务摘要、本地数据读取 | `mootdx`   | 无      |
| `TencentFinanceProvider` | 腾讯财经 / A 股、指数、港股、美股快照 | PE、PB、市值、换手率、涨跌幅、成交量、成交额、板块原始数据                                      | A 股估值、实时交易指标、板块监控       | 无额外依赖   | 无      |
| `FearGreedProvider`      | CNN Fear & Greed Index                | 恐惧贪婪指数、评级、历史对比值                                                                  | 美股市场情绪、风险偏好判断             | 无额外依赖   | 无      |
| `CMEFedWatchProvider`    | CME FedWatch                          | FOMC 会议目标利率概率                                                                           | 市场隐含加息/降息概率                  | 无额外依赖   | 无      |
| `WebSearchProvider`      | DuckDuckGo / 网页                     | 搜索摘要、网页正文抓取                                                                          | 补充非结构化公开信息                   | 无额外依赖   | 无      |
