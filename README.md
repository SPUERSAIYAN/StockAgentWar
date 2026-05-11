# Stock Decision System

基于 LangGraph 的股票市场多 Agent 决策系统。

## 目录

```text
main.py
requirements.txt
config.yaml
server.py
external/
  Market-Information-Skill/
schemas/
  state.py
agents/
  skill_agent.py
  bull_agent.py
  bear_agent.py
  judge_agent.py
  risk_agent.py
graph/
  stock_graph.py
web/
  index.html
  styles.css
  app.js
```

## 前端页面

```powershell
pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

页面支持输入股票代码和决策任务，并实时展示信息分析、多头、空头、裁判、风控的输出。

## 命令行运行

```powershell
python main.py --config .\config.yaml --symbols AAPL,MSFT,NVDA --task "筛选未来 1-3 个月的候选股票"
```

## OpenRouter

`config.yaml` 默认使用 OpenRouter：

```yaml
provider: openrouter
model: openai/gpt-5.2
api_key_env: OPENROUTER_API_KEY
```

如果没有 `.env`，可以手动设置：

```powershell
$env:OPENROUTER_API_KEY="你的 OpenRouter API Key"
```

## 流程

```mermaid
flowchart TD
    START([START]) --> INFO[信息收集 Agent]
    INFO --> BULL[多头 Agent]
    INFO --> BEAR[空头 Agent]
    BULL --> JUDGE[裁判 Agent]
    BEAR --> JUDGE
    JUDGE --> RISK[风控 Agent]
    RISK --> OUTPUT[输出候选股票]
    OUTPUT --> END([END])
```

## 信息收集 Agent

信息收集默认使用：

```text
external/Market-Information-Skill/digital_oracle
```

不需要配置 `skill_import_path`。系统会直接调用 `digital_oracle` 中的 provider 方法采集数据，并把结果整理为：

- `raw_market_data`：结构化原始数据摘要
- `info_report`：给多头、空头、裁判 Agent 使用的 Markdown 信息报告

配置入口在 `config.yaml`：

```yaml
agents:
  information:
    collector:
      enabled: true
      timeout_seconds: 35
      price_history_limit: 90
      include_macro: true
      include_options: true
      include_edgar: true
      include_a_share_metrics: true
```

默认采集能力：

- 美股/ETF：日 K、周 K、收益率、20 日波动率、成交量
- 美股期权：ATM IV、隐含波动区间、Put/Call、Max Pain
- SEC EDGAR：近期 Form 4 内部人交易申报
- 宏观：美债收益率曲线、Fear & Greed、SPY、QQQ、VIX、黄金、USDCNY
- A 股：通过 TencentFinanceProvider 采集价格、PE、PB、市值、换手率等指标

如果某些数据源失败，信息收集 Agent 会保留成功来源，并把失败来源写入“数据缺口”。后续 Agent 必须把这些缺口当成不确定性处理。
# StockAgentWar
