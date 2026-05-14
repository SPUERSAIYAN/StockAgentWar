# 本地 A 股概念板块数据接入

## Summary

把 `E:\IDEA\multi-Agent-Inv\astockdate\全部A股20264.xlsx` 作为 A 股“概念板块成分股”来源。Excel 只替代板块成员发现；现有 Tencent/MooTDX 行情和估值采集继续用于最终候选股。前端传入 `sectors` 时优先使用；未传时由 QuestionPlanningAgent 从自然语言问题中抽取板块。

## Key Changes

- 新增本地板块目录加载器：读取 `Sheet1`，只匹配 `概念板块` 列，不用 `行业` 列做板块匹配；股票代码规范化为 `.SH`、`.SZ`、`.BJ`。
- 更新 `discover_candidate_universe()`：当发现请求板块时，不再返回“板块数据源缺失”，改为从 Excel 匹配概念板块并生成 `candidates`。
- 板块匹配规则：先做概念名精确匹配；无精确匹配时做概念名包含匹配，例如“半导体”可匹配“半导体概念”。
- 候选排序规则：用 Excel 静态字段评分后取 `candidate_discovery.max_candidates`，当前默认 15；评分使用 ROE、营收增速、归母净利润增速、预测利润增速、市值、PE 合理性，并应用已有 `exclude_st`、`min_market_cap_yi`、`max_pe` 过滤项。
- QuestionPlanningAgent 的 `question_understanding` 增加可选 `sector_terms: list[str]`；collector 使用 `scan_scope.sectors` 优先，空时使用 `question_understanding.sector_terms`。
- `stock_pool` 中保留 Excel 静态字段作为候选 metadata：`sector` 用匹配到的概念板块，另带 `industry`、`concepts`、`roe`、`revenue_growth_yoy`、`net_profit_growth_yoy`、`pe`、`total_market_cap_cny_100m` 等；后续实时行情字段仍可覆盖同名字段。
- 更新文档和 prompt：删除“当前未接入板块成分股数据源”的旧表述，改为说明本地 Excel 概念板块源已接入。
- 增加 `openpyxl` 依赖，用于稳定读取 `.xlsx`。

## Public Interfaces

- `question_understanding.sector_terms`：新增可选字段，由问题 Agent 输出板块/概念词。
- `candidate_discovery.method`：成功时使用类似 `local_excel_concept_board` 的方法名。
- `candidate_discovery` 输出包含 `requested_sectors`、`matched_sectors`、`matched_count`、`source_labels`、`candidates`。
- 成功匹配时不再产生 `candidate_discovery.board_membership` 错误；仅在 Excel 缺失、列缺失或无匹配时记录明确数据缺口。

## Test Plan

- 新增本地 Excel loader 单元测试：用临时 workbook 验证只匹配 `概念板块`，不匹配 `行业`。
- 更新 `tests/test_sector_collection.py`：指定“半导体”时应返回本地候选，而不是空候选和“未接入”错误。
- 增加 Agent fallback 测试：`scan_scope.sectors` 为空但 `question_understanding.sector_terms` 有值时能发现候选。
- 增加无匹配/文件缺失测试：返回清晰 gap，不伪造成分股。
- 回归运行：`python -m pytest tests/test_sector_collection.py tests/test_question_planning.py tests/test_documented_chain.py`。

## Assumptions

- Excel 只作为概念板块成员和静态基本面数据源，不替代实时行情源。
- 前端“指定板块”输入保留；用户不填时由问题 Agent 抽取板块。
- 板块匹配只看 `概念板块`，不看 `行业`。
- 当前工作树已有大量未提交变更，实施时只做增量修改，不回退已有改动。
