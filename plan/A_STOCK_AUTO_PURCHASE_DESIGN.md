# A 股自动购买多 Agent 系统设计方案

> **项目**: multi-Agent-Inv
> **日期**: 2026-05-12
> **版本**: v1.0

---

## 一、系统概述

本系统通过多个 AI Agent 协作完成 A 股自动购买决策，模拟一个完整投研团队的工作流程：

```
信息分析 Agent ──→ 股票池 + 分析报告
                      │
              ┌────────┴────────┐
              ▼                  ▼
         多头 Agent          空头 Agent
        (看多论据)          (看空论据)
              │                  │
              └────────┬────────┘
                       ▼
                  裁判 Agent
              (辩论裁决报告)
                       │
                       ▼
              总经理 Agent
          (最终购买决策 + 策略)
                       │
                       ▼
          写入交易计划 JSON 文件
                       │
                       ▼
          TradeMonitorScheduler（定时任务程序）
          每 60 秒拉取实时价格，匹配触发条件自动下单
```

## 二、与现有架构的关系

项目已有一个美股/通用股票的 LangGraph 工作流，本设计在现有基础上**扩展**而非重构：

| 现有组件 | 状态 | 说明 |
|---------|------|------|
| `InformationCollectionAgent` | 保留复用 | 增加 A 股板块分析能力 |
| `BullAgent` | 保留复用 | 增加 A 股看多分析提示词 |
| `BearAgent` | 保留复用 | 增加 A 股看空分析提示词 |
| `JudgeAgent` | 保留复用 | 增加 A 股裁决维度 |
| `RiskAgent` | 保留复用 | 风控能力继续发挥作用 |
| 新增 `PortfolioManagerAgent` | 新建 | 总经理 Agent，最终决策 |
| 新增 `TradeMonitorScheduler` | 新建 | 定时任务程序，负责监控价格并自动下单 |

## 三、Agent 详细设计

### 3.1 信息分析 Agent（Information Analysis Agent）

**角色**: 投研分析师，负责全景扫描 A 股市场。

#### 职责

1. **板块扫描**: 扫描申万一级/二级行业板块，识别强势/弱势板块
2. **个股筛选**: 在强势板块中筛选候选个股
3. **基本面分析**: PE/PB/ROE/营收增速/净利润增速/现金流等
4. **技术面分析**: 均线系统/MACD/KDJ/成交量/支撑压力位
5. **资金面分析**: 北向资金/融资融券/主力资金流向
6. **事件/政策分析**: 行业政策/财报季/重大事件
7. **输出**: 股票池（候选列表）+ 信息分析报告

#### 输入

```python
{
    "task": str,                    # 用户指令，如 "筛选未来1个月可买入标的"
    "scan_scope": {
        "market": "A_SHARE",
        "sectors": list[str],       # 可选：指定板块，空则全量扫描
        "min_market_cap": float,    # 最小市值过滤（亿元）
        "max_pe": float,            # PE 上限
        "exclude_st": bool,         # 是否排除 ST 股
        "exclude_new_days": int,    # 排除上市不足 N 天的新股
    },
    "analysis_date": str,           # YYYY-MM-DD
}
```

#### 输出

```python
{
    "stock_pool": [
        {
            "symbol": str,           # 如 "600519"
            "name": str,             # 如 "贵州茅台"
            "sector": str,           # 所属板块，如 "白酒"
            "price": float,
            "pe_ratio": float,
            "pb_ratio": float,
            "roe": float,
            "revenue_growth_yoy": float,
            "net_profit_growth_yoy": float,
            "market_cap_yi": float,  # 市值（亿）
            "turnover_rate": float,  # 换手率
            "north_net_flow_5d": float,  # 北向资金 5 日净流入（万）
            "technical_signal": str,     # 技术信号，如 "MA5上穿MA20"
            "information_score": float,  # 信息评分 0-100
            "preliminary_reason": str,   # 入选理由
        }
    ],
    "sector_summary": [
        {
            "sector_name": str,
            "change_pct_5d": float,
            "change_pct_20d": float,
            "avg_pe": float,
            "money_flow_signal": str,
            "policy_catalyst": str,
        }
    ],
    "info_report": str,             # Markdown 格式分析报告
    "data_gaps": list[str],         # 数据缺口列表
    "confidence_level": float,      # 整体置信度 0-1
}
```

#### 数据源增强（在现有 collectors/connectors 基础上）

| 数据类别 | 现有 | 新增 |
|---------|------|------|
| A 股行情 | `TencentFinanceProvider` | 增加板块行情聚合 |
| A 股技术指标 | 无 | 新增 `TechnicalIndicatorsProvider`（MA/MACD/KDJ） |
| 北向资金 | 无 | 新增 `NorthboundFlowProvider` |
| 融资融券 | 无 | 新增 `MarginTradingProvider` |
| 行业板块 | 无 | 新增 `SectorIndexProvider` |
| 财务报表 | `TencentFinanceProvider` | 增强：季报利润表/现金流量表 |

#### 工作流程

```
START
  │
  ├── 1. 板块扫描 → sector_summary
  ├── 2. 板块排序 → 选 Top N 强势板块
  ├── 3. 板块内个股初筛 → 按市值/PE/ST 过滤
  ├── 4. 基本面打分 → PE/PB/ROE/增速等综合评分
  ├── 5. 技术面打分 → 均线/MACD/量价配合
  ├── 6. 资金面打分 → 北向/主力/融资
  ├── 7. 综合排名 → 取 Top K 入池
  ├── 8. 生成信息报告 → Markdown
  └── END → 输出 stock_pool + info_report
```

---

### 3.2 多头 Agent（Bull Agent）

**角色**: 看多方，为股票池中的每只股票构建买入论据。

#### 职责

1. 接收信息分析报告和股票池
2. 为每只股票撰写看多论据
3. 重点关注：估值修复空间、成长性、政策红利、资金流入趋势、技术突破
4. 给出看多信心等级（1-5 级）
5. 给出目标价和买入触发价

#### 输入

```python
{
    "stock_pool": list[StockCandidate],   # 来自信息分析 Agent
    "info_report": str,                    # 信息分析报告
    "sector_summary": list[dict],          # 板块摘要
    "task": str,                           # 用户原始任务
    "macro_context": dict,                 # 宏观环境摘要
}
```

#### 输出

```python
{
    "bull_cases": [
        {
            "symbol": str,
            "name": str,
            "bull_argument": str,          # 看多论据（Markdown）
            "key_catalysts": list[str],     # 核心催化因素
            "target_price": float,          # 目标价
            "buy_trigger_price": float,     # 建议买入触发价
            "upside_pct": float,            # 预期涨幅
            "confidence": int,              # 信心等级 1-5
            "time_horizon": str,            # 时间维度，如 "1-3个月"
            "risk_acknowledged": str,       # 主动承认的风险点
        }
    ],
    "bull_summary": str,                   # 多头总结（整体看好哪些标的）
    "bull_overall_confidence": float,      # 多头整体信心 0-1
}
```

---

### 3.3 空头 Agent（Bear Agent）

**角色**: 看空方，为股票池中的每只股票构建卖出/回避论据。

#### 职责

1. 接收信息分析报告和股票池
2. 为每只股票撰写看空论据
3. 重点关注：估值泡沫、盈利下滑、政策风险、资金流出、技术破位
4. 给出看空信心等级（1-5 级）
5. 给出卖出触发价和风险提示

#### 输入

与多头 Agent 相同。

#### 输出

```python
{
    "bear_cases": [
        {
            "symbol": str,
            "name": str,
            "bear_argument": str,          # 看空论据（Markdown）
            "key_risks": list[str],         # 核心风险因素
            "downside_price": float,        # 预期下行目标价
            "sell_trigger_price": float,    # 建议卖出触发价
            "downside_pct": float,          # 预期跌幅
            "confidence": int,              # 信心等级 1-5
            "time_horizon": str,            # 时间维度
        }
    ],
    "bear_summary": str,                   # 空头总结（建议回避哪些标的）
    "bear_overall_confidence": float,      # 空头整体信心 0-1
}
```

---

### 3.5 裁判 Agent（Judge Agent）

**角色**: 客观中立裁判，综合评估多空观点并给出裁决。

#### 职责

1. 接收信息分析报告、股票池、多头论据、空头论据
2. 评估双方论据质量（数据支撑、逻辑严谨性）
3. 对每只股票给出裁决结论
4. 标注可信度等级

#### 输入

```python
{
    "stock_pool": list[StockCandidate],
    "info_report": str,
    "bull_cases": list[dict],
    "bear_cases": list[dict],
    "macro_context": dict,
}
```

#### 输出

```python
{
    "judge_rulings": [
        {
            "symbol": str,
            "name": str,
            "ruling": Literal["STRONG_BUY", "BUY", "WATCH", "AVOID", "STRONG_AVOID"],
            "reasoning": str,              # 裁决理由
            "bull_score": float,           # 多头论据质量分 0-100
            "bear_score": float,           # 空头论据质量分 0-100
            "data_quality": float,         # 双方引用的数据质量分 0-100
            "credibility_level": Literal["HIGH", "MEDIUM", "LOW"],
            "final_recommendation": str,   # 一句话建议
        }
    ],
    "judge_report": str,                  # 完整裁决报告（Markdown）
    "overall_market_view": str,           # 对当前市场整体看法
}
```

---

### 3.6 总经理 Agent（Portfolio Manager Agent）

**角色**: 投资决策最终制定者，综合所有信息做出购买决定。

#### 职责

1. 综合阅读：信息报告、股票池、多头论据、空头论据、裁判裁决
2. 决定最终购买标的（可能全买/部分买/全不买）
3. 制定购买策略：仓位分配、止损止盈**价格触发条件**
4. 输出可执行的交易计划，交由**定时任务程序**监控并执行

#### 输入

```python
{
    "stock_pool": list[StockCandidate],
    "info_report": str,
    "sector_summary": list[dict],
    "bull_cases": list[dict],
    "bear_cases": list[dict],
    "judge_rulings": list[dict],
    "judge_report": str,
    "risk_report": str,                   # 来自风控 Agent
    "portfolio_context": {
        "current_positions": list[dict],  # 当前持仓
        "available_capital": float,       # 可用资金
        "max_position_pct": float,        # 单只股票最大仓位比例
        "max_drawdown_limit": float,      # 最大回撤限制
        "risk_tolerance": str,            # 风险偏好: "conservative"/"moderate"/"aggressive"
    },
    "task": str,
}
```

#### 输出

```python
{
    "final_decision": {
        "action": Literal["BUY", "HOLD", "WAIT", "NO_TRADE"],
        "reasoning": str,                  # 决策理由摘要
    },
    "trade_plan": {
        "monitored_stocks": [
            {
                "symbol": str,
                "name": str,
                "allocation_pct": float,           # 占总资金比例
                "allocation_amount": float,        # 分配金额
                "quantity": int,                    # 买入股数（100股整数倍）
                "buy_trigger_price": float,         # 买入触发价，如 500
                "sell_trigger_price": float,        # 卖出触发价，如 550
                "stop_loss_price": float,           # 止损价
                "take_profit_price": float,         # 止盈价
                "valid_from": str,                  # 生效日期 YYYY-MM-DD
                "valid_until": str,                 # 失效日期 YYYY-MM-DD
                "expiry_action": Literal["SELL", "HOLD", "REVIEW"],  # 到期处理
                "conditions": [
                    {
                        "type": Literal["PRICE_ABOVE", "PRICE_BELOW", "PRICE_RANGE"],
                        "price": float,
                        "action": Literal["BUY", "SELL"],
                        "quantity": int,
                    }
                ],
            }
        ],
        "position_sizing_rationale": str,           # 仓位分配逻辑
    },
    "alternative_scenarios": [
        {
            "scenario": str,               # 如 "大盘突发利空"
            "action": str,                 # 应对措施
        }
    ],
    "confidence": float,                   # 总经理信心 0-1
    "manager_report": str,                 # 完整总经理报告（Markdown）
}
```

---

## 四、LangGraph 工作流设计

### 4.1 节点拓扑

```
START
  │
  ▼
┌─────────────────────┐
│  information_node   │  信息分析 Agent
│  (scan + pool)      │
└────────┬────────────┘
         │
    stock_pool
    info_report
         │
         ▼
┌──────────────────────┐     ┌──────────────────────┐
│  bull_node           │     │  bear_node           │
│  (看多论据)          │     │  (看空论据)          │
└────────┬─────────────┘     └────────┬─────────────┘
         │                            │
         └────────────┬───────────────┘
                      ▼
           ┌─────────────────────┐
           │  judge_node         │  裁判 Agent
           │  (裁决 + 报告)       │
           └────────┬────────────┘
                    │
                    ▼
           ┌─────────────────────┐
           │  risk_node          │  风控 Agent（现有）
           │  (风控审查)          │
           └────────┬────────────┘
                    │
                    ▼
           ┌─────────────────────┐
           │  portfolio_manager  │  总经理 Agent
           │  (最终决策 + 策略)   │
           └────────┬────────────┘
                    │ trade_plan (写入 JSON)
                    ▼
                  END

═══════════════════════════════════════════
  LangGraph 工作流到此结束，以下是独立运行：
═══════════════════════════════════════════

┌─────────────────────┐
│  TradeMonitor       │  定时任务程序（非 AI）
│  Scheduler          │  每 60 秒拉取实时行情
│                     │  匹配触发条件 → 自动下单
│                     │  买入：股价 ≤ buy_trigger_price
│                     │  卖出：股价 ≥ sell_trigger_price
│                     │  止损/止盈同理
└─────────────────────┘
```

### 4.2 State 扩展

在现有 `MarketDecisionState` 基础上新增字段：

```python
class AShareAutoPurchaseState(MarketDecisionState, total=False):
    # 信息分析阶段新增
    stock_pool: list[dict]           # 股票池
    sector_summary: list[dict]       # 板块摘要
    confidence_level: float          # 整体置信度

    # 多空论据细化
    bull_cases: list[dict]           # 多头论据列表
    bear_cases: list[dict]           # 空头论据列表
    bull_summary: str
    bear_summary: str

    # 裁判
    judge_rulings: list[dict]        # 逐只股票裁决
    judge_report: str
    overall_market_view: str

    # 总经理
    final_decision: dict
    trade_plan: dict
    alternative_scenarios: list[dict]
    manager_report: str

    # 执行
    execution_results: list[dict]    # 定时任务成交记录（来自 order_log.json）
    portfolio_context: dict          # 投资组合上下文

    # 宏观
    macro_context: dict              # 宏观环境摘要
```

### 4.3 条件边（Conditional Edges）

```python
def final_action(state) -> Literal["save_plan", "no_plan"]:
    """总经理决策后的路由"""
    action = state.get("final_decision", {}).get("action", "WAIT")
    if action == "BUY":
        return "save_plan"
    return "no_plan"

def save_trade_plan(state):
    """将总经理的交易计划写入 data/trade_plan.json"""
    trade_plan = state.get("trade_plan", {})
    with open("data/trade_plan.json", "w") as f:
        json.dump(trade_plan, f, ensure_ascii=False, indent=2)
    return state
```

---

## 五、配置文件扩展

在 `config.yaml` 中新增以下配置项：

```yaml
agents:
  information:
    collector:
      candidate_discovery:
        enabled: true
        max_candidates: 15          # A 股候选池上限
        scan_limit: 5000            # 扫描股票数量上限
        batch_size: 80              # 每批扫描数量
        # A 股专属
        a_share_filters:
          exclude_st: true          # 排除 ST
          exclude_new_days: 60      # 排除上市不足 60 天
          min_market_cap_yi: 50     # 最小市值 50 亿
          max_pe: 80                # PE 上限
          exclude_suspended: true   # 排除停牌股票

  portfolio_manager:
    model:
      provider: openrouter
      model: openai/gpt-5.5
      temperature: 0.1
    position_sizing:
      max_single_position_pct: 20   # 单只最大仓位 20%
      max_total_exposure_pct: 80    # 总仓位上限 80%
      cash_reserve_min_pct: 20      # 最低现金保留 20%
    risk_control:
      max_drawdown_pct: 10          # 最大回撤 10%
      stop_loss_pct: 8              # 止损比例 8%
      take_profit_pct: 20           # 止盈比例 20%

trade_monitor:
  enabled: true                     # 是否启用定时监控
  interval_seconds: 60              # 轮询间隔（秒）
  mode: "SIMULATED"                 # SIMULATED | PAPER | LIVE
  plan_file: "data/trade_plan.json" # 总经理输出的交易计划路径
  commission_rate: 0.0003           # 佣金率 万分之三
  stamp_tax_rate: 0.0005            # 印花税 千分之零.五
  a_share_market_hours:
    morning_start: "09:30"
    morning_end: "11:30"
    afternoon_start: "13:00"
    afternoon_end: "15:00"
  price_source: "tencent"           # 实时行情数据源
  order_log_file: "data/order_log.json"  # 成交记录
```

---

## 六、目录结构规划

```
multi-Agent-Inv/
├── agents/
│   ├── information_agent.py        # 现有，增强
│   ├── bull_agent.py               # 现有，增强
│   ├── bear_agent.py               # 现有，增强
│   ├── judge_agent.py              # 现有，增强
│   ├── risk_agent.py               # 现有
│   ├── prompt_loader.py            # 现有
│   ├── trace_logger.py             # 现有
│   └── portfolio_manager_agent.py  # 新建：总经理 Agent
│
├── collectors/
│   ├── digital_oracle_collector.py # 现有
│   ├── connectors/
│   │   ├── china.py                # 现有，增强
│   │   ├── sector_index.py         # 新建：板块指数
│   │   ├── technical_indicators.py # 新建：技术指标
│   │   ├── northbound_flow.py      # 新建：北向资金
│   │   └── margin_trading.py       # 新建：融资融券
│
├── graph/
│   ├── stock_graph.py              # 现有
│   └── a_share_auto_trade_graph.py # 新建：A 股自动交易图
│
├── prompts/
│   ├── information_agent.md        # 现有
│   ├── bull_agent.md               # 现有
│   ├── bear_agent.md               # 现有
│   ├── judge_agent.md              # 现有
│   ├── risk_agent.md               # 现有
│   ├── portfolio_manager_agent.md  # 现有
│   └── references/
│       └── a_share_knowledge.md    # 新建：A 股领域知识参考
│
├── schemas/
│   ├── state.py                    # 现有，扩展
│   └── a_share_state.py            # 新建：A 股专属 State
│
├── services/
│   ├── sector_service.py           # 新建：板块行情服务
│   └── order_service.py            # 新建：订单服务（模拟/实盘）
│
├── schedulers/
│   └── trade_monitor_scheduler.py  # 新建：定时监控交易程序（非 AI）
│
├── data/
│   ├── trade_plan.json             # 总经理输出的交易计划（自动生成）
│   └── order_log.json              # 成交记录（自动生成）
│
├── config.yaml                     # 现有，扩展
├── main.py                         # 现有，新增 A 股入口
├── server.py                       # 现有，新增 A 股前端页面
└── web/
    ├── index.html                  # 现有
    ├── a_share.html                # 新建：A 股自动购买前端
    └── ...
```

---

## 七、关键流程时序

### 7.1 完整自动购买流程

```
T+0  08:00  系统启动，信息分析 Agent 扫描全市场
T+0  08:05  生成板块排行 → 强势板块 Top 5
T+0  08:10  强势板块内筛选 → 候选股票池 Top 15
T+0  08:15  生成信息分析报告
T+0  08:20  多头 Agent 收到报告，撰写看多论据
T+0  08:20  空头 Agent 收到报告，撰写看空论据（并行）
T+0  08:30  多头/空头论据完成
T+0  08:35  裁判 Agent 综合多空观点 → 生成裁决报告
T+0  08:45  风控 Agent 审查 → 生成风控意见
T+0  08:50  总经理 Agent 综合所有报告 → 生成最终决策
T+0  08:55  输出交易计划 → 写入 data/trade_plan.json
T+0  08:55  交易计划文件生成后，TradeMonitorScheduler 自动接管
T+1  09:30  开盘 → TradeMonitorScheduler 每隔 60 秒拉取实时价格
              → 股价 ≤ 买入触发价 → 立即买入
              → 股价 ≥ 卖出触发价 → 立即卖出
```

### 7.2 定时触发

```
每日盘前:   信息分析 → 多头/空头并行分析 → 裁判裁决 → 总经理决策 → 写入交易计划 JSON
交易时段:   TradeMonitorScheduler 定时任务监控价格，自动触发买卖（非 AI）
每日盘后:   复盘 Agent（可选）→ 评估当日决策质量 → 更新记忆
```

---

## 八、交易监控定时任务（Trade Monitor Scheduler）

> **重要：这不是 AI Agent，是一个纯程序化的定时任务。**

### 8.1 职责

1. 读取总经理 Agent 输出的交易计划（`data/trade_plan.json`）
2. 每隔 N 秒（默认 60 秒）拉取监控列表中股票的实时价格
3. 逐一对比当前价格与触发条件：
   - 股价 ≤ `buy_trigger_price` → 立即买入
   - 股价 ≥ `sell_trigger_price` → 立即卖出
   - 股价 ≤ `stop_loss_price` → 止损卖出
   - 股价 ≥ `take_profit_price` → 止盈卖出
4. 记录成交日志到 `data/order_log.json`
5. 只在交易时段运行（A 股 09:30-11:30, 13:00-15:00）

### 8.2 交易计划格式（trade_plan.json）

```json
{
  "generated_at": "2026-05-12 09:15:00",
  "monitored_stocks": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "allocation_amount": 200000,
      "quantity": 100,
      "buy_trigger_price": 500.0,
      "sell_trigger_price": 550.0,
      "stop_loss_price": 480.0,
      "take_profit_price": 580.0,
      "valid_from": "2026-05-13",
      "valid_until": "2026-06-13",
      "expiry_action": "REVIEW",
      "conditions": [
        {
          "type": "PRICE_BELOW",
          "price": 500.0,
          "action": "BUY",
          "quantity": 100
        },
        {
          "type": "PRICE_ABOVE",
          "price": 550.0,
          "action": "SELL",
          "quantity": 100
        }
      ]
    }
  ]
}
```

### 8.3 运行逻辑

```python
class TradeMonitorScheduler:
    def __init__(self, plan_file, interval_seconds=60, mode="SIMULATED"):
        self.plan = load_json(plan_file)
        self.interval = interval_seconds
        self.mode = mode  # SIMULATED | PAPER | LIVE
        self.executed_orders = set()  # 已执行的订单去重

    def run(self):
        while True:
            if not is_trading_time():
                sleep_until_next_trading_time()
                continue

            for stock in self.plan["monitored_stocks"]:
                if not is_valid_date(stock):
                    continue
                if already_executed(stock):
                    continue

                current_price = fetch_realtime_price(stock["symbol"])

                # 止损优先
                if current_price <= stock["stop_loss_price"]:
                    self.execute_sell(stock, current_price, reason="止损")
                    continue

                # 止盈
                if current_price >= stock["take_profit_price"]:
                    self.execute_sell(stock, current_price, reason="止盈")
                    continue

                # 买入触发
                if current_price <= stock["buy_trigger_price"]:
                    if not self.has_bought(stock["symbol"]):
                        self.execute_buy(stock, current_price)

                # 卖出触发
                if current_price >= stock["sell_trigger_price"]:
                    if self.has_bought(stock["symbol"]):
                        self.execute_sell(stock, current_price, reason="达到目标价")

            sleep(self.interval)
```

### 8.4 订单执行方式

| 模式 | 说明 |
|------|------|
| SIMULATED | 模拟盘，按实时价格记录虚拟成交，计算盈亏 |
| PAPER | 纸面交易，调用券商测试接口，不真实下单 |
| LIVE | 实盘，调用券商真实接口下单（需手动开启） |

### 8.5 成交记录（order_log.json）

```json
{
  "orders": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "action": "BUY",
      "price": 498.50,
      "quantity": 100,
      "amount": 49850.00,
      "commission": 14.96,
      "timestamp": "2026-05-13 10:23:00",
      "trigger_reason": "股价低于买入触发价 500.00",
      "mode": "SIMULATED"
    }
  ]
}
```

### 8.6 启动方式

```bash
# 独立启动定时监控程序
python -m schedulers.trade_monitor_scheduler \
  --config config.yaml \
  --plan-file data/trade_plan.json \
  --interval 60 \
  --mode SIMULATED
```

---

## 九、风控集成

现有的 `RiskAgent` 继续发挥作用，在总经理决策前提供风控审查：

```
裁判裁决报告
      │
      ▼
┌─────────────────────┐
│  risk_node          │
│  • 评估组合风险       │
│  • 检查集中度         │
│  • 评估市场系统性风险  │
│  • 建议仓位上限       │
└────────┬────────────┘
         │ risk_report
         ▼
┌─────────────────────┐
│  portfolio_manager  │  总经理参考风控意见做决策
└─────────────────────┘
```

风控 Agent 输出:

```python
{
    "risk_report": str,
    "risk_level": Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    "max_recommended_exposure_pct": float,
    "concentration_warnings": list[str],
    "systemic_risk_factors": list[str],
    "position_limits": dict[str, float],  # symbol -> max_pct
}
```

---

## 十、A 股特色适配

### 10.1 交易规则

| 规则 | 说明 | 系统适配 |
|------|------|---------|
| T+1 交易 | 当日买入次日才能卖出 | `TradeMonitorScheduler` 持仓冻结 |
| 涨跌停板 | 主板 ±10%，科创/创业板 ±20% | 下单前价格校验 |
| 最小交易单位 | 100 股（1 手） | 数量自动取整 |
| 印花税 | 卖出方千分之 0.5 | 成本计算纳入 |
| 佣金 | 万分之 1~3（双向） | 成本计算纳入 |

### 10.2 A 股特色指标

| 指标 | 说明 | 采集方式 |
|------|------|---------|
| 北向资金 | 外资流入/流出信号 | `NorthboundFlowProvider` |
| 融资融券 | 杠杆资金情绪 | `MarginTradingProvider` |
| 龙虎榜 | 机构/游资动向 | 交易所数据 |
| 大宗交易 | 折价/溢价信号 | 交易所数据 |
| 限售解禁 | 供给冲击 | 公告数据 |
| 股东增减持 | 内部人信号 | 公告数据 |

### 10.3 板块体系

采用申万行业分类（2021 版）：

- **一级行业（31 个）**: 农林牧渔、基础化工、钢铁、有色金属、电子、汽车、食品饮料、医药生物等
- **二级行业（134 个）**: 白酒、半导体、新能源、医疗器械等

信息分析 Agent 扫描板块时，使用板块指数涨幅、资金流入等指标排序。

---

## 十一、前端交互设计

### 10.1 A 股专属页面 (`web/a_share.html`)

页面功能模块：

1. **任务输入区**:
   - 选择任务类型：每日扫描 / 指定板块扫描 / 指定个股分析
   - 风险偏好：保守 / 稳健 / 激进
   - 可用资金量
   - 自定义任务描述

2. **实时流程展示**:
   - 信息分析进度条 + 股票池实时更新
   - 板块排行可视化
   - 多头看多论据 + 空头看空论据
   - 裁判裁决展示
   - 总经理最终决策卡片

3. **交易计划展示**:
   - 购买标的列表
   - 仓位分配饼图
   - 止损止盈价格表
   - 分批买入计划

4. **历史决策记录**:
   - 日期 / 决策 / 结果对比
   - 胜率统计

5. **实时监控状态**:
   - 当前监控中的股票及触发价格
   - 最新拉取的价格（每 60 秒刷新）
   - 成交记录实时滚动
   - 盈亏统计

---

## 十二、命令行入口

```bash
# 每日自动扫描（盘前）
python main.py \
  --config config.yaml \
  --mode a_share_daily \
  --task "扫描全市场，找出未来1个月最具投资价值的标的" \
  --risk-tolerance moderate \
  --capital 1000000

# 指定板块扫描
python main.py \
  --config config.yaml \
  --mode a_share_sector \
  --sectors "白酒,半导体,新能源" \
  --task "分析指定板块并给出买入建议"

# 指定个股深度分析
python main.py \
  --config config.yaml \
  --mode a_share_deep \
  --symbols "600519,000858,300750" \
  --task "深度分析指定个股并给出交易策略"
```

---

## 十三、开发里程碑

| 阶段 | 内容 | 预估优先级 |
|------|------|-----------|
| Phase 1 | 增强信息分析 Agent 的 A 股板块扫描能力 | P0 |
| Phase 2 | 新建 A 股专属 State 和 Graph | P0 |
| Phase 3 | 增强多头/空头/裁判的 A 股提示词 | P0 |
| Phase 4 | 新建 PortfolioManagerAgent | P0 |
| Phase 5 | 新建 TradeMonitorScheduler（定时监控程序） | P1 |
| Phase 6 | 新增 A 股数据源 Providers | P1 |
| Phase 7 | 前端 A 股页面 | P2 |
| Phase 8 | 定时任务/自动化 | P2 |
| Phase 9 | 复盘 Agent（事后评估） | P3 |

---

## 十四、风险提示

> **本系统为实验性项目，不构成任何投资建议。**

1. AI 模型的判断不具备投资顾问资质
2. 历史表现不代表未来收益
3. 自动交易存在技术风险（网络、延迟、异常）
4. A 股市场波动大，需严格设置止损
5. 模拟盘与实盘存在显著差异（滑点、流动性）
6. 建议在充分测试和风险评估后再考虑实盘接入
