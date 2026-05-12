# 前端技术方案：流水线式工作台

## 1. 目标

在当前 LangGraph 多 Agent 架构之上，设计并实现一个「流水线式工作台」前端，使用户能实时看到每个 Agent 的执行状态、输出结果、数据来源，并支持交互控制。

**核心诉求**：
- 最贴合 LangGraph 流程，用户能看到每个 Agent 在干什么
- 信息量虽大但设计克制，不造成认知负担
- 支持摘要 / 原文 / 数据源 三种视图切换

## 2. 现状分析

### 2.1 已有前端能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 三栏布局 | 已有 | 左侧输入 → 中间流程 → 右侧输出 |
| 5 阶段展示 | 已有 | 信息分析、多头、空头、裁判、风控 |
| NDJSON 流式响应 | 已有 | `server.py` 的 `/api/decide/stream` |
| Markdown 渲染 | 已有 | marked + DOMPurify |
| 数据来源追踪 | 已有 | 信息分析阶段可展开来源 |
| 深色主题 | 已有 | 完整设计令牌系统 |

### 2.2 需要新增的能力

| 能力 | 优先级 | 说明 |
|------|--------|------|
| A 股模式支持 | P0 | 新增板块/个股/资金/风险偏好等输入 |
| 总经理 Agent 阶段 | P0 | 流水线第 6 阶段 |
| 交易计划阶段 | P0 | 流水线第 7 阶段 |
| 三视图切换 | P0 | 摘要 / 原文 / 数据源 |
| 自动展开机制 | P1 | Agent 完成后自动展开结果卡片 |
| 阶段间依赖可视化 | P1 | 并行节点（多头/空头）的连线 |
| 历史记录 | P2 | 保存并回看历史分析 |

## 3. 页面布局设计

### 3.1 整体结构

```
┌──────────────────────────────────────────────────────────────────┐
│  Topbar: 标题 + 健康状态 + 运行模式切换                            │
├────────────┬──────────────────────────┬──────────────────────────┤
│            │                          │                          │
│  左侧      │  中间：Agent 流程进度      │  右侧：当前阶段输出         │
│  任务输入   │  ┌────────────────────┐  │  ┌────────────────────┐  │
│            │  │ 流水线指示条(顶部)  │  │  │ 三视图 Tab 切换     │  │
│  • 模式     │  │ 信息 → A股上下文    │  │  │ [摘要][原文][数据]  │  │
│  • 板块     │  │ 多头 ↘              │  │  ├────────────────────┤  │
│  • 个股     │  │        → 裁判 → ... │  │  │                     │  │
│  • 风险偏好 │  │ 空头 ↗              │  │  │  Agent 输出内容      │  │
│  • 资金     │  │                      │  │  │  (Markdown)        │  │
│            │  ├────────────────────┤  │  │                     │  │
│  [开始分析] │  │ 阶段卡片列表       │  │  ├────────────────────┤  │
│            │  │  • 信息分析 ✓       │  │  │  最终汇总报告        │  │
│  耗时/状态  │  │  • 多头 ⏳ 运行中   │  │  │  (完整 Markdown)     │  │
│            │  │  • 空头 ✓          │  │  │                     │  │
│            │  │  • 裁判 ◯ 等待     │  │  └────────────────────┘  │
│            │  │  ...               │  │                          │
├────────────┴──────────────────────────┴──────────────────────────┤
│  底部：交易计划详情（仅在生成时展开）                               │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 三栏比例

| 区域 | 宽度 | 行为 |
|------|------|------|
| 左侧输入 | 300px (固定) | sticky 定位，滚动时保持可见 |
| 中间流程 | 自适应 (min 400px) | 阶段卡片可滚动 |
| 右侧输出 | 自适应 (min 380px) | 内容区可滚动 |

### 3.3 响应式断点

| 断点 | 行为 |
|------|------|
| > 1200px | 三栏布局 |
| 900–1200px | 三栏但压缩间距 |
| < 900px | 单栏堆叠：输入 → 流程 → 输出 |

## 4. Agent 流水线设计

### 4.1 完整阶段列表

| # | 阶段 ID | Agent 名称 | 图标 | 品牌色 | 并行? |
|---|---------|-----------|------|--------|-------|
| 1 | `information_analysis` | 信息分析 | 📊 雷达 | `#3B82F6` 蓝 | 否 |
| 2 | `a_share_context` | A 股上下文 | 🏛️ 建筑 | `#06B6D4` 青 | 否 |
| 3 | `bull_debate` | 多头 | 📈 上升线 | `#22C55E` 绿 | 是 |
| 4 | `bear_debate` | 空头 | 📉 下降线 | `#EF4444` 红 | 是 |
| 5 | `judge_decision` | 裁判 | ⚖️ 天平 | `#A78BFA` 紫 | 否 |
| 6 | `risk_review` | 风控 | 🛡️ 盾牌 | `#F59E0B` 橙 | 否 |
| 7 | `portfolio_manager` | 总经理 | 👔 公文包 | `#EC4899` 粉 | 否 |
| 8 | `save_trade_plan` | 交易计划 | 📋 剪贴板 | `#14B8A6` 青绿 | 条件 |

### 4.2 流水线指示条

顶部一行小卡片展示所有阶段，用箭头连接：

```
[信息] → [A股] → [多头] ↘
                    [裁判] → [风控] → [总经理] → [计划]
         [空头] ↗
```

**状态指示**：
- `等待`：灰色边框，半透明图标
- `运行中`：品牌色边框 + 发光效果，图标旋转动画
- `完成`：品牌色半透明背景 + 实心图标
- `失败`：红色边框 + 红色背景

### 4.3 阶段卡片

每个 Agent 一个卡片，包含：

```
┌─────────────────────────────────────┐
│ [图标] 多头 Agent    上涨逻辑  [完成] │  ← 头部：Agent名 + 描述 + 状态徽章
├─────────────────────────────────────┤
│                                     │  ← 主体：Markdown 输出（固定高度可滚动）
│  多头分析结果...                     │
│                                     │
├─────────────────────────────────────┤
│ ▶ 浏览来源与数据    8成功 / 0失败    │  ← 底部：可展开的数据源追踪（仅信息分析）
└─────────────────────────────────────┘
```

**自动展开机制**：
- Agent 完成时，如果当前没有运行中的卡片，自动将该卡片 body 展开
- 用户可手动点击收起/展开
- 运行中的卡片始终展开并显示 loading 指示器

## 5. 三视图切换设计

右侧输出区域顶部增加 Tab 切换：

### 5.1 Tab 结构

| Tab | 内容 | 触发时机 |
|-----|------|---------|
| **摘要** | AI 生成的结构化摘要（如多空核心论点、裁决结果） | Agent 完成后自动生成 |
| **原文** | 完整的 Agent Markdown 输出 | Agent 完成后立即可用 |
| **数据源** | 数据来源明细表（网站、接通状态、数据摘要） | 信息分析阶段专有 |

### 5.2 实现方案

```
┌──────────────────────────────────┐
│ [● 摘要] [  原文  ] [  数据源  ] │  ← Tab 栏
├──────────────────────────────────┤
│                                  │
│  当前 Tab 对应的内容区域          │
│  (Markdown 渲染 / 表格 / 列表)    │
│                                  │
└──────────────────────────────────┘
```

**交互逻辑**：
- 每个 Agent 完成后，其 Tab 上出现绿色圆点表示「有内容」
- 默认自动切换到第一个有内容的 Tab
- 用户可自由切换，切换时保持选中状态
- 「数据源」Tab 仅信息分析阶段有内容，其他阶段显示"此阶段无独立数据源"

### 5.3 摘要生成

在 `server.py` 中为每个 Agent 输出增加 `summary` 字段：

```python
# 在 handle_event 中解析
{
  "type": "stage",
  "node": "bull_debate",
  "content": "...",       # 完整原文
  "summary": "...",       # 前 3 行或 AI 生成的摘要
  "source_trace": [...]   # 数据源（仅信息分析阶段）
}
```

前端 fallback：如果后端暂未返回 `summary`，取原文前 200 字符 + "..." 作为临时摘要。

## 6. 左侧输入面板设计

### 6.1 A 股模式字段

```
┌─────────────────────────────┐
│ 决策参数                      │
├─────────────────────────────┤
│                             │
│ 模式                         │
│ [每日扫描] [指定板块] [个股]  │  ← 三段式切换
│                             │
│ 板块名称（指定板块模式）       │
│ [白酒,半导体,新能源     ]     │
│                             │
│ 股票代码（个股模式）          │
│ [600519.SH,000858.SZ   ]    │
│                             │
│ 风险偏好                     │
│ [● 保守] [  稳健] [  激进]   │
│                             │
│ 可用资金 (元)                │
│ [1,000,000            ]     │
│                             │
│ 任务描述                     │
│ [筛选未来 1-3 个月...   ]    │
│                             │
│ ┌─────────────────────────┐ │
│ │ ▶ 运行决策              │ │
│ └─────────────────────────┘ │
│                             │
│ 耗时: 0.0s   状态: 待运行     │
└─────────────────────────────┘
```

### 6.2 模式切换逻辑

| 模式 | 发送的 API 字段 | 说明 |
|------|----------------|------|
| 每日扫描 | `mode: "a_share_daily"` | 不传 symbols/sectors，后端自动扫描 |
| 指定板块 | `mode: "a_share_sector"`, `sectors: "白酒,半导体"` | 按板块筛选 |
| 指定个股 | `mode: "a_share_deep"`, `symbols: "600519.SH"` | 深度分析指定股票 |
| OpenRouter | `mode: "openrouter"`, `symbols: "AAPL,MSFT"` | 美股模式（现有） |
| Mock | `mode: "mock"`, `symbols: "AAPL"` | 测试模式（现有） |

## 7. 后端 API 扩展

### 7.1 现有 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/decide/stream` | POST | NDJSON 流式决策 |

### 7.2 需要扩展的部分

**`/api/decide/stream` 请求体**：

```typescript
interface DecisionRequest {
  task: string;
  symbols: string;         // 逗号分隔
  sectors: string;         // 逗号分隔（A 股模式）
  mode: "openrouter" | "mock" | "a_share_daily" | "a_share_sector" | "a_share_deep";
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  capital: number;
  config_path: string;
}
```

**NDJSON 事件类型扩展**：

```typescript
// 已有事件
type Event =
  | { type: "start"; stages: StageMeta[] }
  | { type: "stage_status"; node: string; status: "running" | "done" | "error" }
  | { type: "stage"; node: string; content: string; source_trace?: SourceItem[] }
  | { type: "complete"; final_output: string; state: object }
  | { type: "error"; message: string; hint: string };

// 新增字段（向后兼容）
interface StageEvent extends Event {
  type: "stage";
  summary?: string;         // 新增：AI 摘要
  source_trace?: SourceItem[];  // 已有
  node_meta?: {             // 新增：阶段元信息
    agent: string;
    title: string;
    color: string;
    icon_svg: string;
  };
}
```

### 7.3 新增 A 股流式端点（备选方案）

如果不想改动现有 `server.py`，可新增独立端点：

```python
@app.post("/api/a_share/stream")
def a_share_stream(request: AShareDecisionRequest) -> StreamingResponse:
    """A 股专用流式决策端点"""
    return StreamingResponse(
        stream_a_share_decision(request),
        media_type="application/x-ndjson; charset=utf-8",
    )
```

**推荐方案**：扩展现有 `/api/decide/stream`，通过 `mode` 字段路由到不同的 LangGraph。

## 8. 前端文件组织

### 8.1 当前文件结构

```
web/
├── index.html      # 单页面 HTML
├── styles.css      # 全部样式
└── app.js          # 全部逻辑
```

### 8.2 建议拆分（P2，当前保持单文件）

```
web/
├── index.html
├── css/
│   ├── base.css         # 重置、变量、通用
│   ├── layout.css       # 三栏布局
│   ├── components.css   # 卡片、按钮、标签
│   └── pipeline.css     # 流水线专用样式
└── js/
    ├── app.js           # 入口
    ├── state.js         # 状态管理
    ├── api.js           # 网络请求
    ├── renderer.js      # DOM 渲染
    └── markdown.js      # Markdown 处理
```

**当前阶段保持单文件**，代码量可控（~700 行 JS + ~1300 行 CSS），暂不拆分。

## 9. 前端状态管理

### 9.1 状态结构

```javascript
const state = {
  // 输入
  mode: "a_share_daily",          // 运行模式
  sectors: "",                     // 板块
  symbols: "",                     // 股票
  riskTolerance: "moderate",       // 风险偏好
  capital: 1_000_000,              // 资金

  // 运行状态
  running: false,
  startedAt: 0,
  timer: null,

  // Agent 输出
  stageContent: {},                // { nodeId: markdownString }
  stageSummary: {},                // { nodeId: summaryString }
  sourceTrace: {},                 // { nodeId: [SourceItem] }

  // UI 状态
  activeStageTab: null,            // 右侧当前选中的 Agent Tab
  activeStageView: "summary",      // 摘要 | 原文 | 数据源
  expandedCards: new Set(),        // 手动展开的卡片 ID
};
```

## 10. 交易计划展示

### 10.1 展示时机

当 `portfolio_manager` Agent 完成后，如果决策为 `BUY`，底部自动展开交易计划面板。

### 10.2 面板内容

```
┌─────────────────────────────────────────────────┐
│ 📋 交易计划                        [收起]         │
├─────────────────────────────────────────────────┤
│ 决策: BUY | 置信度: 72%                          │
│                                                 │
│ 标的: 贵州茅台 (600519.SH)                       │
│  • 买入价格区间: ¥1,680 - ¥1,720                 │
│  • 目标仓位: 15%                                 │
│  • 止损价: ¥1,545 (-8%)                          │
│  • 止盈价: ¥2,016 (+20%)                         │
│  • 持仓周期: 1-3 个月                            │
│  • 风险理由: 估值合理，北向资金持续流入...         │
└─────────────────────────────────────────────────┘
```

### 10.3 数据来源

从 `state.trade_plan` 或 `final_decision` 中提取结构化数据：

```json
{
  "final_decision": {
    "action": "BUY",
    "reasoning": "...",
    "target_stock": "600519.SH",
    "entry_price_min": 1680,
    "entry_price_max": 1720,
    "position_pct": 15,
    "stop_loss_pct": 8,
    "take_profit_pct": 20
  },
  "manager_confidence": 0.72
}
```

## 11. 动画与交互细节

### 11.1 运行中的动画

```css
/* 流水线节点呼吸灯 */
.pipeline-node.running {
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 8px var(--node-brand); }
  50% { box-shadow: 0 0 20px var(--node-brand); }
}

/* 阶段卡片 loading 指示器 */
.stage-card.running .stage-body::before {
  content: "";
  display: block;
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-soft);
  border-top-color: var(--card-brand);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: auto;
}
```

### 11.2 完成时的反馈

- 状态徽章从 "运行" → "完成" 时有 scale(1.1) → scale(1) 弹性过渡
- 流水线节点边框从呼吸动画切换到静态品牌色
- 结果 Tab 出现绿色圆点（表示有新内容）

### 11.3 错误处理

- 单个 Agent 失败：该卡片标红，后续依赖阶段显示 "跳过"
- 全局失败：顶部显示错误横幅，可关闭
- 网络断开：左侧显示重连提示

## 12. 开发实施计划

### Phase 1: 基础扩展 (1-2 天)

| 任务 | 文件 | 说明 |
|------|------|------|
| 扩展 `STAGE_ORDER` 和 `STAGE_META` | `app.js` | 新增总经理、交易计划等阶段 |
| 扩展左侧输入面板 | `index.html` + `app.js` | A 股模式字段 + 三段式模式切换 |
| 扩展后端 API 路由 | `server.py` | 支持 A 股模式的 mode 参数 |
| 测试端到端流程 | - | Mock 模式验证全流程 |

### Phase 2: 三视图 + 自动展开 (1-2 天)

| 任务 | 文件 | 说明 |
|------|------|------|
| 实现三视图 Tab 切换 | `app.js` + `styles.css` | 摘要/原文/数据源 |
| 摘要生成 fallback 逻辑 | `app.js` | 后端无 summary 时取前 200 字 |
| Agent 完成自动展开 | `app.js` | 完成时自动聚焦对应卡片和 Tab |
| 交易计划面板 | `index.html` + `app.js` | 底部条件展开面板 |

### Phase 3: 细节打磨 (1 天)

| 任务 | 文件 | 说明 |
|------|------|------|
| 响应式优化 | `styles.css` | 三断点适配 |
| 动画优化 | `styles.css` | 呼吸灯、弹性过渡 |
| 错误处理优化 | `app.js` | 局部失败、网络断开 |
| 性能优化 | `app.js` | 大文本渲染、滚动优化 |

## 13. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 后端 `summary` 字段未就绪 | 摘要 Tab 为空 | 前端 fallback 截取前 200 字符 |
| Agent 输出过长 | 卡片溢出/性能 | 限制卡片 body 高度，内部滚动 |
| 多个 Agent 并行完成 | 状态竞争 | NDJSON 是顺序事件流，不存在竞争 |
| CDN 依赖 (marked, DOMPurify) | 离线不可用 | P2 考虑打包为本依赖 |
| 大量阶段导致页面拥挤 | 用户体验差 | 流水线指示条用紧凑模式，详细看卡片 |

## 14. 与现有代码的兼容性

| 现有能力 | 兼容策略 |
|---------|---------|
| 现有 5 阶段 (`server.py` `STAGES`) | 向后兼容，新阶段通过 `mode` 区分 |
| `web/index.html` 现有结构 | 在现有三栏基础上扩展，不推翻 |
| NDJSON 协议 | 向后兼容，新增可选字段 |
| CSS 设计令牌 | 沿用现有 `--brand-*` 变量体系 |
| Markdown 渲染 | 复用现有 `renderMarkdown()` 函数 |
