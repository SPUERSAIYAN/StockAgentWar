# 任务计划：AI 自动 A 股购买多 Agent 系统设计

## 目标

设计一个完整的 AI 自动购买 A 股的多 Agent 系统方案，输出为一份 Markdown 设计文档，涵盖信息分析、股票池构建、多空辩论、裁判裁决、总经理决策五大阶段。

## 阶段

| # | 阶段名称 | 状态 | 说明 |
|---|---------|------|------|
| 1 | 现有架构梳理 | complete | 分析现有 multi-Agent-Inv 项目结构、数据流、Agent 职责 |
| 2 | 设计文档编写 | complete | 撰写完整方案设计文档 `A_STOCK_AUTO_PURCHASE_DESIGN.md` |
| 3 | 更新任务进度 | complete | 更新 progress.md 记录成果 |
| 4 | 前端技术方案设计 | complete | 撰写 `frontend_technical_plan.md`，涵盖布局、流水线、三视图、API 扩展 |

## 决策日志

- 前端保持单文件结构（`index.html` + `styles.css` + `app.js`），当前代码量可控，暂不拆分
- 推荐扩展现有 `/api/decide/stream` 端点，通过 `mode` 字段路由到 A 股/美股流程
- 摘要生成采用 fallback 策略：后端优先返回 `summary`，前端截取前 200 字符兜底

## 遇到的错误

无
