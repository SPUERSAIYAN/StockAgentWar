# 研究发现

## 现有架构发现

### 已存在的 Agent

| Agent | 文件 | 状态 |
|-------|------|------|
| InformationCollectionAgent | `agents/information_agent.py` | 已实现，支持多数据源采集 |
| BullAgent | `agents/bull_agent.py` | 已实现 |
| BearAgent | `agents/bear_agent.py` | 已实现 |
| JudgeAgent | `agents/judge_agent.py` | 已实现 |
| RiskAgent | `agents/risk_agent.py` | 已实现 |
| PortfolioManagerAgent | 提示词存在 `prompts/portfolio_manager_agent.md` | Agent 代码未实现 |

### 数据源现状

- A 股价格数据：通过 `TencentFinanceProvider` 采集
- Mootdx：可选的 A 股数据源，config 中已配置
- 北向资金、融资融券、板块指数：**均未实现**，需新增 Provider

### LangGraph 工作流

当前流程：`信息分析 → 多头 → 空头 → 裁判 → 风控 → 输出`
- 缺少多空多轮辩论环节
- 缺少总经理最终决策环节
- 缺少交易执行环节

### 前端

- 已有基础页面 `web/index.html` 支持输入股票代码和决策任务
- 需要新增 A 股专属页面展示完整工作流
