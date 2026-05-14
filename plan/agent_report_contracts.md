# Agent 报告内容与 Prompt 可见字段

## 核心原则

Agent 能读到什么，取决于最终塞进 prompt 的字段，而不是 `state` 里有什么。

也就是说，只有 prompt 模板里出现了 `{xxx}`，或者代码动态拼接进 user prompt 的内容，大模型才真正能看到。没有 prompt 的节点不做 LLM 判断，只用 Python 读 `state` 并生成结构化结果或前端展示文本。

## 当前链路总览

| 阶段 | 是否 LLM | 使用的 prompt | 大模型实际可见输入 | 主要产出 | 报告/结果用途 |
| --- | --- | --- | --- | --- | --- |
| 问题规划 Agent | 是 | `prompts/question_planning_agent.md` + `prompts/data_sources.md` | `task`、`candidates`、`metadata`、`data_sources`、已有 `stock_pool`、`sector_summary`、`macro_context` | `question_understanding`、`provider_selection`、`question_plan_report` | 根据数据源文档理解问题并选择数据源 |
| 信息分析 Agent | 是 | `prompts/information_agent.md` + 代码动态拼接 | `task`、`candidates`、`workflow_plan`、`provider_selection`、`signal_reasoning`、`raw_market_data` | `info_report`、`information_workflow`、`provider_selection`、`signal_reasoning`、`raw_market_data`、`stock_pool`、`sector_summary`、`confidence_level`、`data_gaps`、`macro_context` | 把采集数据整理成市场信息分析报告，并在节点内部生成后续 Agent 使用的结构化市场上下文 |
| 多头 Agent | 是 | `prompts/bull_agent.md` | `task`、`candidates`、`info_report`、`stock_pool`、`sector_summary`、`macro_context` | `bull_case` | 从看多角度写上涨逻辑、触发条件和失效条件 |
| 多头结构化 | 否 | 无 | 不读 prompt；Python 读 `stock_pool`、`bull_case` | `bull_cases`、`bull_summary`、`bull_overall_confidence` | 把多头文本转换为逐股票结构化多头观点 |
| 空头 Agent | 是 | `prompts/bear_agent.md` | `task`、`candidates`、`info_report`、`stock_pool`、`sector_summary`、`macro_context` | `bear_case` | 从看空角度写风险、下跌逻辑和回避条件 |
| 空头结构化 | 否 | 无 | 不读 prompt；Python 读 `stock_pool`、`bear_case` | `bear_cases`、`bear_summary`、`bear_overall_confidence` | 把空头文本转换为逐股票结构化风险观点 |
| 裁判 Agent | 是 | `prompts/judge_agent.md` | `task`、`info_report`、`bull_case`、`bear_case`、`bull_cases`、`bear_cases`、`stock_pool`、`data_gaps` | `judge_decision` | 综合信息报告和多空观点，给出裁判结论 |
| 裁判结构化 | 否 | 无 | 不读 prompt；Python 读 `stock_pool`、`confidence_level`、`judge_decision` | `judge_rulings`、`judge_report`、`overall_market_view` | 把裁判结论转换为逐股票评级 |
| 风控 Agent | 是 | `prompts/risk_agent.md` | `task`、`candidates`、`judge_decision` | `risk_report` | 对裁判结论做仓位、止损、风险和暂停条件复核 |
| 风控结构化字段透传 | 否 | 无 | 不读 prompt；LangGraph state 保留结构化字段 | `stock_pool`、`sector_summary`、`data_gaps`、`judge_rulings` 等 | 让后续总经理还能拿到结构化字段 |
| 总经理 Agent | 是 | `prompts/portfolio_manager_agent.md` | `task`、`candidates`、`stock_pool`、`info_report`、`bull_cases`、`bear_cases`、`judge_decision`、`judge_rulings`、`risk_report`、`portfolio_context`、`data_gaps` | `manager_report` | 从组合视角给出最终配置、暂停和执行建议 |
| 总经理结构化决策 | 否 | 无 | 不读 prompt；`portfolio_decision` 节点调用 Python 读 `stock_pool`、`judge_rulings`、`bull_cases`、`bear_cases`、`portfolio_context`、`data_gaps` | `final_decision`、`trade_plan`、`alternative_scenarios`、`manager_confidence` | 生成可被调度器读取的交易计划结构 |
| 交易计划保存 | 否 | 无 | 不读 prompt；Python 读 `final_decision`、`trade_plan` | 写入 `data/trade_plan.json` 或标记跳过 | 只有 `final_decision.action == BUY` 且存在可监控标的时才保存计划 |
| 最终输出 | 否 | 无 | 不读 prompt；Python 读 `final_decision`、`manager_report`、`trade_plan`、metadata | `final_output`；前端展示 `trade_plan_report` | 生成最终股票自动购买决策展示 |

## 字段作用说明

| 字段 | 作用 |
| --- | --- |
| `task`（用户任务） | 用户输入的原始问题或决策目标，是所有 Agent 判断“要解决什么问题”的核心输入。 |
| `candidates`（候选标的） | 用户指定或系统发现的股票/资产候选列表，通常包含 `symbol`、`name`、`sector` 等基础字段。 |
| `metadata`（运行元信息） | 本次运行的附加上下文，例如 UI 模式、运行模式、交易计划文件路径等，不直接代表市场判断。 |
| `data_sources`（数据源说明） | `prompts/data_sources.md` 的数据源目录内容，供问题规划 Agent 判断应该启用哪些 provider group。 |
| `question_understanding`（问题理解结构） | 问题规划 Agent 对任务的结构化理解，包括改写问题、核心意图、市场范围、时间窗口和候选范围。 |
| `provider_selection`（数据源选择结果） | 问题规划 Agent 产出的 provider group 启用/拒绝结果，信息采集必须按这个字段执行，不再自行重选。 |
| `question_plan_report`（问题规划报告） | 面向用户的规划报告，说明系统如何理解问题、选择数据源和拒绝数据源。 |
| `workflow_plan`（信息工作流计划） | 信息分析阶段传给 LLM 的采集与分析计划，用来说明本次信息分析如何组织数据。 |
| `information_workflow`（信息工作流记录） | 信息节点生成的结构化执行记录，描述问题拆解、候选发现、provider 覆盖和采集步骤。 |
| `signal_reasoning`（信号解释） | 对原始 provider 数据的程序化整理，提炼价格、估值、成交、期权、宏观、预测市场等信号含义。 |
| `raw_market_data`（原始市场数据） | provider 返回的原始采集结果和错误信息，是信息分析报告和结构化市场上下文的证据来源。 |
| `info_report`（信息分析报告） | 信息分析 Agent 产出的用户可读市场报告，给后续多头、空头、裁判和总经理提供基础事实背景。 |
| `stock_pool`（结构化股票池） | 信息节点内部生成的候选股票结构化数据，包含价格、板块、评分、技术信号、风险提示等后续节点需要的字段。 |
| `sector_summary`（板块摘要） | 信息节点内部由 `stock_pool` 聚合生成的板块摘要，用于辅助多空分析理解候选分布；指定概念板块候选可来自本地 Excel 概念板块表。 |
| `confidence_level`（信息置信度） | 信息节点对本次数据完整度和质量的总体置信判断，后续结构化裁判和交易决策会参考。 |
| `data_gaps`（数据缺口） | 采集失败、字段缺失或证据不足的列表，用于提示后续 Agent 哪些结论需要保守处理。 |
| `macro_context`（宏观上下文） | 信息节点整理出的宏观背景，例如利率、市场情绪、指数、流动性或风险偏好环境。 |
| `bull_case`（多头报告） | 多头 Agent 的用户可读报告，描述上涨逻辑、关键证据、触发条件和失效条件。 |
| `bull_cases`（逐股票多头结构） | 内部结构化字段，把 `bull_case` 转换为每只股票的催化、目标价、买入触发价、上行空间和多头置信度。 |
| `bull_summary`（多头摘要） | 内部结构化字段，总结多头观点的整体方向和主要支撑。 |
| `bull_overall_confidence`（多头总体置信度） | 内部结构化字段，表示多头观点整体可信度。 |
| `bear_case`（空头报告） | 空头 Agent 的用户可读报告，描述下跌/跑输逻辑、核心风险、回避条件和看空观点失效条件。 |
| `bear_cases`（逐股票空头结构） | 内部结构化字段，把 `bear_case` 转换为每只股票的风险点、下行价格、卖出/回避触发和空头置信度。 |
| `bear_summary`（空头摘要） | 内部结构化字段，总结空头观点的整体方向和主要风险。 |
| `bear_overall_confidence`（空头总体置信度） | 内部结构化字段，表示空头观点整体可信度。 |
| `judge_decision`（裁判报告） | 裁判 Agent 的用户可读综合结论，比较信息报告、多头和空头观点，给出最终裁判意见。 |
| `judge_rulings`（逐股票裁判结构） | 内部结构化字段，把裁判结论转成每只股票的评级、分数、数据质量和最终建议。 |
| `judge_report`（裁判文本承接） | 内部结构化字段，通常直接承接 `judge_decision` 文本，方便后续节点统一读取。 |
| `overall_market_view`（整体市场观点） | 内部结构化字段，总结裁判节点对当前市场环境或候选池的整体看法。 |
| `risk_report`（风控报告） | 风控 Agent 的用户可读报告，对裁判结论做仓位、止损、暂停条件和风险暴露复核。 |
| `portfolio_context`（组合上下文） | 组合层输入，通常包含当前持仓、可用资金、最大仓位、最大回撤限制和风险偏好。 |
| `manager_report`（总经理报告） | 总经理 Agent 的用户可读最终建议，从组合视角整合信息、多空、裁判和风控结果。 |
| `final_decision`（最终动作结构） | 内部结构化字段，表示系统最终动作，例如 `BUY`、`WAIT`、`NO_TRADE` 以及动作理由。 |
| `trade_plan`（交易计划结构） | 内部结构化字段，包含可被调度器读取的监控标的、仓位、数量、买卖触发、止损止盈和有效期。 |
| `alternative_scenarios`（备选情景） | 内部结构化字段，描述突发利空、数据源不可用等情景下应采取的替代动作。 |
| `manager_confidence`（总经理置信度） | 总经理结构化决策对最终动作的置信度，前端可作为用户可读的非原始结构字段展示。 |
| `trade_plan_report`（交易计划报告） | 面向用户的交易计划展示文本，由服务端根据 `save_trade_plan` 阶段状态生成，不暴露 `trade_plan` 原始 JSON。 |
| `final_output`（最终输出） | 面向用户的最终总结，包含最终动作、理由、总经理报告、交易计划文件状态和免责声明。 |

## 实现备注

`question_planning_agent.md` 的职责是生成 `provider_selection`，并且当前 prompt 会额外注入 `prompts/data_sources.md` 的全文，要求问题规划 Agent 根据这份数据源文档选择 provider group。

当前 `InformationCollectionAgent` 会调用 `information_workflow.select_information_providers()`，但该函数只校验并规范化 `QuestionPlanningAgent` 已写入 `state["provider_selection"]` 的结果，不再根据任务重新选择 provider。实际采集严格使用问题规划节点产出的 provider group。

`a_share_context` 不再是独立节点。股票池、板块摘要、数据缺口、宏观上下文等结构化字段由 `InformationCollectionAgent` 在信息报告生成后内部构建，并随 `information_analysis` 节点输出传递给后续 Agent。

当前指定概念板块成分股来自本地 Excel `astockdate/全部A股20264.xlsx` 的 `Sheet1.概念板块`；腾讯财经和 MooTDX 继续用于个股/指数行情、估值、市值、换手率、K 线和基础资料等用途。前端传入 `scan_scope.sectors` 优先，未传时可使用 `question_understanding.sector_terms` 作为本地板块匹配词。

前端可见阶段只包含：`question_planning`、`information_analysis`、`bull_debate`、`bear_debate`、`judge_decision`、`risk_review`、`portfolio_manager`、`save_trade_plan`。`bull_cases`、`bear_cases`、`judge_rulings`、`portfolio_decision` 是内部 graph 节点，只给后续 Agent、总经理结构化决策和交易计划保存逻辑使用，不作为 `/api/health` 阶段、不产生前端 `stage` 展示事件，也不在 `complete.state` 暴露原始结构。

`complete.state` 只返回用户可读报告字段和必要 metadata：`question_plan_report`、`info_report`、`bull_case`、`bear_case`、`judge_decision`、`risk_report`、`manager_report`、`manager_confidence`、`final_output`，以及 `metadata.trade_plan_file`。`bull_cases`、`bear_cases`、`judge_rulings`、`final_decision`、`trade_plan`、`alternative_scenarios` 等结构化原始字段保留在服务端 state 内部，不直接发给前端。

## 各报告内容

### `question_plan_report`

来源：`QuestionPlanningAgent.render_question_plan_report()`。

Prompt 参考文档：

- `prompts/question_planning_agent.md`
- `prompts/data_sources.md`

报告内容：

- 问题理解：改写问题、核心意图、市场范围、时间窗口、候选范围。
- 数据源选择：根据 `prompts/data_sources.md` 启用的数据源分组。
- Provider 表格：`us_equity`、`china_equity`、`macro`、`prediction_markets`、`crypto`、`web_search` 的 enabled/disabled 状态和原因。

注意：这是规划报告，不包含真实采集结果。

### `info_report`

来源：`InformationCollectionAgent` 调用 `information_agent.md` 生成；如果 LLM 失败或使用 mock，则走确定性 fallback。

报告内容：

- Workflow 执行摘要：问题拆解、时间窗口、候选来源、候选发现状态。
- Provider 覆盖情况：启用/拒绝的数据源、采集状态、成功来源数、失败来源数。
- Provider Signals：价格、估值、成交、期权、利率、CFTC、预测市场、加密等信号解释。
- Candidate Comparison：候选股票的证据、得分、优劣势。
- Resonance Signals：多源共振信号。
- Key Divergences：跨市场、跨周期或跨信号分歧。
- Time Stratification：短期、中期、长期信号分层。
- Probability Estimates：情景概率和依据。
- Conclusion：信息分析结论、风险因素、需要监控的信号、数据来源和采集时间。

注意：信息分析 LLM 能看到的是代码动态拼进去的 `workflow_plan`、`provider_selection`、`signal_reasoning`、`raw_market_data`，不是普通 prompt 模板里的 `{raw_market_data}` 占位。`stock_pool`、`sector_summary`、`data_gaps`、`macro_context` 是信息节点内的 Python 后处理输出，不是信息分析 LLM 的输入。

### `bull_case`

来源：`BullAgent` + `prompts/bull_agent.md`。

报告内容要求：

- 最强看多候选股票。
- 上行逻辑和触发条件。
- 关键证据。
- 看多观点失效条件。
- A 股流程下，对每个候选给出目标价、买入触发价、预期上行空间、1-5 置信度、已承认风险。

可见输入：`task`、`candidates`、`info_report`、`stock_pool`、`sector_summary`、`macro_context`。

### `bull_cases`

来源：无 LLM，由 `structure_bull_cases()` 生成。

结构化内容：

- `symbol`、`name`
- `bull_argument`：完整 `bull_case`
- `key_catalysts`：由股票池字段推导的多头催化
- `target_price`：默认当前价 * 1.12
- `buy_trigger_price`：默认当前价 * 0.99
- `upside_pct`：默认 12%
- `confidence`：由 `information_score` 映射为 1-5
- `time_horizon`：默认 1-3 个月
- `risk_acknowledged`：数据缺口和 A 股波动风险

### `bear_case`

来源：`BearAgent` + `prompts/bear_agent.md`。

报告内容要求：

- 风险最高候选股票。
- 下跌或跑输逻辑。
- 关键证据。
- 看空观点失效条件。
- A 股流程下，对每个候选给出下行价格、卖出/回避触发、预期下行空间、1-5 置信度、核心风险。

可见输入：`task`、`candidates`、`info_report`、`stock_pool`、`sector_summary`、`macro_context`。

### `bear_cases`

来源：无 LLM，由 `structure_bear_cases()` 生成。

结构化内容：

- `symbol`、`name`
- `bear_argument`：完整 `bear_case`
- `key_risks`：由股票池字段推导的空头风险
- `downside_price`：默认当前价 * 0.92
- `sell_trigger_price`：默认当前价 * 0.95
- `downside_pct`：默认 8%
- `confidence`：与信息评分反向映射
- `time_horizon`：默认 1-3 个月

### `judge_decision`

来源：`JudgeAgent` + `prompts/judge_agent.md`。

报告内容要求：

- 候选股票表：股票、方向、优先级、核心理由、主要风险、监控信号。
- 最终裁判结论。
- 风控 Agent 应重点检查的问题。
- 下一步需要补充的数据。
- A 股流程下，每只股票的 ruling、bull score、bear score、data quality、credibility level、一句话最终建议。

可见输入：`task`、`info_report`、`bull_case`、`bear_case`、`bull_cases`、`bear_cases`、`stock_pool`、`data_gaps`。

### `judge_rulings` 与 `judge_report`

来源：无 LLM，由 `structure_judge_rulings()` 生成。

结构化内容：

- `judge_report`：直接承接 `judge_decision` 文本。
- `judge_rulings`：逐股票结构化裁决。
- `ruling`：`STRONG_BUY`、`BUY`、`WATCH`、`AVOID`、`STRONG_AVOID`。
- `reasoning`：信息评分与数据质量的简述。
- `bull_score`、`bear_score`。
- `data_quality`：由 `confidence_level` 转成百分制。
- `credibility_level`：由数据质量映射。
- `final_recommendation`：按 ruling 生成的一句话建议。
- `overall_market_view`：A 股链路整体观点。

### `risk_report`

来源：`RiskAgent` + `prompts/risk_agent.md`。

报告内容要求：

- 风控后的候选股票表：股票、方向、优先级、建议仓位、止损/失效条件、主要风险。
- 风控复核结论。
- 不应进入候选池的证券及原因。
- 因数据不足而必须暂停交易的条件。

可见输入只有：`task`、`candidates`、`judge_decision`。

重要限制：虽然运行到风控时 `state` 中通常已经有 `stock_pool`、`data_gaps`、`macro_context`、`judge_rulings` 等字段，但当前 `risk_agent.md` 没有把这些字段写进 prompt，所以风控 LLM 不能直接看到它们，只能通过 `judge_decision` 间接获知。

### `manager_report`

来源：`PortfolioManagerAgent` + `prompts/portfolio_manager_agent.md`。

报告内容要求：

- 推荐组合权重。
- 行业和因子暴露。
- 相关性和集中度风险。
- 再平衡条件。
- 组合层面的暂停或降风险条件。
- 最终动作：`BUY`、`HOLD`、`WAIT`、`NO_TRADE`。
- A 股执行计划：买入触发价、100 股整数倍数量等。

可见输入：`task`、`candidates`、`stock_pool`、`info_report`、`bull_cases`、`bear_cases`、`judge_decision`、`judge_rulings`、`risk_report`、`portfolio_context`、`data_gaps`。

### `final_decision`、`trade_plan`、`manager_confidence`

来源：无 LLM，由 `portfolio_decision` 节点调用 `build_portfolio_decision()` 生成。

结构化内容：

- `final_decision.action`：若存在可执行监控股票则 `BUY`，否则有股票池时 `WAIT`，没有股票池时 `NO_TRADE`。
- `final_decision.reasoning`：最终动作理由。
- `trade_plan.generated_at`：计划生成时间。
- `trade_plan.monitored_stocks`：可执行标的列表。
- 每个可执行标的包含：symbol、name、allocation_pct、allocation_amount、quantity、buy_trigger_price、sell_trigger_price、stop_loss_price、take_profit_price、valid_from、valid_until、expiry_action、conditions。
- `alternative_scenarios`：突发利空、关键数据源不可用等场景下动作。
- `manager_confidence`：有可执行标的默认 0.72，否则 0.35；存在数据缺口会下调。

注意：这一层不解析 `manager_report` 文本，而是用结构化字段和配置生成交易计划。

### `trade_plan_report`

来源：无 LLM，由 `server.render_trade_plan_report()` 根据保存交易计划阶段的状态生成前端展示文本。

报告内容：

- 没有可执行标的时：最终动作、原因、未写入交易计划文件。
- 有可执行标的时：最终动作、计划文件、标的、数量、仓位、买入触发、卖出触发、止损、止盈、有效期。

### `final_output`

来源：无 LLM，由 `format_final_output()` 生成。

报告内容：

- 标题：股票自动购买决策。
- 最终动作。
- 决策理由。
- 总经理置信度。
- 总经理报告全文。
- 交易计划文件路径，或未生成交易计划文件。
- 研究用途免责声明。

## 未接入当前主链路的 prompt

`prompts/trader_agent.md` 存在，输入字段为 `task`、`candidates`、`info_report`、`judge_decision`、`risk_report`，目标是生成可执行交易计划。

但当前统一自动购买主链路没有挂载 LLM Trader Agent；交易计划由 `portfolio_decision` 节点的结构化 Python 逻辑生成，并由 `save_trade_plan` 节点按最终动作保存或跳过。

## 简化理解

```text
问题规划 prompt：看任务、已有上下文和 data_sources.md，生成数据源规划报告。
信息分析 prompt：看 workflow、provider 选择、信号推理和采集数据，写信息报告。
多头 prompt：看信息报告 + 股票池，写看多逻辑。
空头 prompt：看信息报告 + 股票池，写风险逻辑。
裁判 prompt：看信息报告 + 多空报告 + 结构化多空，做综合判断。
风控 prompt：只直接看裁判结论，做风险复核。
总经理 prompt：看关键报告和结构化字段，做组合层最终建议。
总经理结构化决策：Python 根据结构化字段生成 final_decision 和 trade_plan。
交易计划：Python 根据 final_decision 保存或跳过，展示层不再问 LLM。
```
