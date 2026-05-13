# 前后端升级技术方案

## 后端升级技术方案

### 一、问题诊断

#### 1.1 核心 Bug：板块模式 candidates 为空

**现象**：用户在前端选择「指定板块」模式，输入 `半导体,白酒`，点击运行后，系统输出：

```
Candidate stocks:
未提供明确候选股票。
```

**数据流断裂点**：

```
前端发送: { mode: "a_share_sector", sectors: "半导体,白酒", symbols: "" }
  → server.py build_graph_inputs()
     → symbols = "" → candidates = []  (空数组)
     → sectors = ["半导体", "白酒"] → scan_scope.sectors
  → LangGraph START → information_analysis
     → collect_market_information(state)
        → extract_candidate_symbols(state) → []  (candidates 为空)
        → infer_auto_candidate_universe(task="分析指定 A 股板块并给出买入建议")
           检查 tokens: "a-share", "china", "a股", "沪深", "中国股票"
           → 全不匹配！因为 task 文本中没有这些 token
           → 返回 None
        → discover_candidate_universe = None
        → symbols = [] → 所有 china_equity 任务无目标
  → 后续所有 Agent 收到空股票池
```

**根因是两层断裂**：

| 层 | 问题 | 代码位置 |
|----|------|---------|
| 意图识别 | `infer_auto_candidate_universe()` 不认识 "板块" 这个词 | `digital_oracle_collector.py:422` |
| 板块解析 | 系统没有 "板块名 → 成分股列表" 的转换能力 | 整条链路缺失 |

#### 1.2 架构问题清单

| # | 问题 | 影响 |
|---|------|------|
| 1 | 板块模式无成分股解析 | 指定板块/每日扫描都无法形成股票池 |
| 2 | 意图识别 token 列表过窄 | "分析半导体板块" 不被识别为 A 股任务 |
| 3 | `a_share_context` 只处理已有的 candidates | 不主动发现股票 |
| 4 | 数据源只覆盖腾讯行情 + Mootdx K线 | 缺少板块指数、北向资金、融资融券、新闻舆情 |
| 5 | `infer_data_gaps()` 列出缺口但不修复 | `ROE/营收增速` 来自腾讯但不返回 |

---

### 二、系统拆分

#### 2.1 当前架构全貌

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI (server.py)                       │
│  POST /api/decide/stream → NDJSON StreamingResponse             │
├─────────────────────────────────────────────────────────────────┤
│                       LangGraph Stream                          │
│                                                                 │
│  START → information_analysis → a_share_context                 │
│           ↓                      ↓                              │
│       [collect_market_       [build_stock_pool]                 │
│        information()]          ↓                                │
│           ↓                 [bull_debate] ←→ [bear_debate]      │
│           ↓                      ↓                  ↓           │
│           ↓                 [bull_cases]     [bear_cases]       │
│           └──────────────────────┼──────────────┘               │
│                                  ↓                              │
│                           [judge_decision]                      │
│                                  ↓                              │
│                           [judge_rulings]                       │
│                                  ↓                              │
│                            [risk_review]                        │
│                                  ↓                              │
│                        [portfolio_manager]                      │
│                               /    \                            │
│                    BUY → [save]  [skip] ← WAIT/SELL             │
│                               \    /                            │
│                            [format_output] → END                │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2 数据采集层拆分

`collect_market_information()` 是数据入口，它把任务分发到 6 个 connector：

```
collect_market_information()
  │
  ├── build_equity_tasks()          ← 美股 (Yahoo Finance / yfinance)
  │     ├── price_daily
  │     ├── price_weekly
  │     ├── options_nearest
  │     └── edgar_form4
  │
  ├── build_china_equity_tasks()    ← A 股 (腾讯 + Mootdx)
  │     ├── tencent_metrics         [已实现]
  │     ├── tencent_index_metrics   [已实现]
  │     ├── mootdx_bars             [可开启]
  │     ├── mootdx_realtime         [已开启]
  │     ├── mootdx_financials       [已开启]
  │     ├── mootdx_intraday         [可开启]
  │     ├── mootdx_order_book       [可开启]
  │     └── mootdx_transactions     [可开启]
  │
  ├── build_macro_tasks()           ← 宏观
  │     ├── yield_curve             [Treasury API]
  │     ├── fear_greed              [CNN API]
  │     ├── cme_fedwatch            [CME FedWatch]
  │     ├── cftc                    [CFTC.gov]
  │     ├── bis                     [可开启]
  │     └── worldbank               [可开启]
  │
  ├── build_prediction_market_tasks()  ← 预测市场
  │     ├── kalshi                    [Kalshi API]
  │     └── polymarket                [Polymarket API]
  │
  ├── build_crypto_tasks()          ← 加密资产
  │     ├── coingecko                 [CoinGecko API]
  │     └── deribit                   [Deribit API]
  │
  └── build_web_search_tasks()      ← 网页搜索
        ├── search                    [DuckDuckGo]
        └── page_fetch                [HTTP fetch]
```

#### 2.3 A 股专属数据链路

A 股模式 (`a_share_*`) 走 `build_a_share_auto_trade_graph()`，比通用图多出 3 个节点：

| 节点 | 职责 | 数据来源 |
|------|------|---------|
| `information_analysis` | 拉取市场数据 | 腾讯行情 + Mootdx + 宏观 + 预测市场 |
| `a_share_context` | 构建股票池 + 板块摘要 | 从 candidates + tencent_metrics 合并 |
| `save_trade_plan` | 落盘交易计划 | `data/trade_plan.json` |

---

### 三、数据源规划

#### 3.1 已接入数据源

| 数据源 | Provider | 能力 | 默认状态 | A 股覆盖 |
|--------|----------|------|---------|---------|
| **腾讯财经** | `TencentFinanceProvider` | 个股实时行情、PE/PB、换手率、量比、成交额、市值 | 开启 | 核心 |
| **Mootdx/通达信** | `MootdxProvider` | K线(日/分钟)、实时报价、分时、逐笔、财务摘要、公司简介、股东信息 | 部分开启 | 增强 |
| **Yahoo Finance** | `yfinance` | 美股/ETF/指数价格、期权链 | A 股模式不启用 | - |
| **SEC EDGAR** | `EdgarProvider` | Form 4 内部人交易 | A 股模式不启用 | - |
| **U.S. Treasury** | `TreasuryProvider` | 国债收益率曲线 | 开启 | 宏观参考 |
| **CNN Fear & Greed** | `FearGreedProvider` | 市场情绪指数 | 开启 | 宏观参考 |
| **CME FedWatch** | `CmeFedwatchProvider` | 联邦利率期货隐含概率 | 开启 | 宏观参考 |
| **CFTC** | `CftcProvider` | 期货持仓报告 | 开启 | 宏观参考 |
| **CoinGecko** | `CoingeckoProvider` | 加密现货价格 | 开启 | 风险偏好代理 |
| **Deribit** | `DeribitProvider` | 加密期权/期货 | 开启 | 风险偏好代理 |

#### 3.2 缺失数据源（按优先级排序）

| # | 数据源 | 解决什么问题 | 推荐方案 | 优先级 |
|---|--------|------------|---------|--------|
| 1 | **板块成分股解析** | "半导体" → [688008, 600519, ...] | 方案 A: Excel/JSON 静态映射<br>方案 B: Mootdx 板块接口<br>方案 C: AKShare 动态获取 | P0 |
| 2 | **板块指数行情** | 板块整体涨跌幅、趋势 | 腾讯板块指数 (`qt.gtimg.cn/q=bk`) | P0 |
| 3 | **北向资金** | 外资流向，A 股重要资金指标 | 东方财富 API (AKShare) 或腾讯 | P1 |
| 4 | **融资融券** | 杠杆资金情绪 | 东方财富 API (AKShare) | P1 |
| 5 | **A 股新闻/公告** | 事件驱动分析 | web_search 已支持，需结构化 | P1 |
| 6 | **财务增强数据** | ROE、营收增速、净利润增速 | Mootdx `finance()` 已返回但字段提取不全 | P1 |
| 7 | **主力资金流向** | 机构/游资动向 | 东方财富 API (AKShare) | P2 |
| 8 | **龙虎榜** | 涨停/异动股票 | 东方财富 API (AKShare) | P2 |
| 9 | **行业 PE/PB 分位** | 板块估值历史位置 | 中证指数官网 / AKShare | P2 |

#### 3.3 板块成分股解析 — 详细方案对比

**方案 A：JSON 静态映射（推荐首选）**

```json
// data/sector_mapping.json
{
  "半导体": {
    "keywords": ["半导体", "芯片", "IC", "semiconductor"],
    "symbols": ["688008.SH", "600519.SH", "002371.SZ", "603501.SH", "300661.SZ", "512480.SH"],
    "etf_symbols": ["512480.SH", "159995.SZ"]
  },
  "白酒": {
    "keywords": ["白酒", "liquor", "wine"],
    "symbols": ["600519.SH", "000858.SZ", "000568.SZ", "002304.SZ", "603369.SH"]
  },
  "新能源车": {
    "keywords": ["新能源车", "新能源", "EV", "电动车"],
    "symbols": ["300750.SZ", "002594.SZ", "300014.SZ", "603799.SH", "159995.SZ"]
  }
}
```

- 优点：零依赖、可离线、即时可用
- 缺点：需手动维护
- 适合：覆盖 10-20 个高频板块，立即修复 bug

**方案 B：Mootdx 板块接口**

```python
# mootdx 通达信内置板块
mootdx.client.blocks()           # 获取所有板块列表
mootdx.client.get_block("半导体")  # 获取板块成分股
```

- 优点：成分股随通达信数据更新
- 缺点：接口文档不完善，板块名匹配是模糊的
- 适合：作为方案 A 的补充

**方案 C：AKShare 动态获取**

```python
import akshare as ak
# 东方财富行业板块列表
ak.stock_board_industry_name_em()
# 板块成分股
ak.stock_board_industry_cons_em(symbol="半导体")
# 概念板块
ak.stock_board_concept_name_em()
ak.stock_board_concept_cons_em(symbol="人工智能")
```

- 优点：东方财富权威数据，实时更新，覆盖面最广
- 缺点：新增第三方依赖，偶发限流
- 适合：长期方案

#### 3.4 推荐实施路径

```
Phase 1 (立即)   : 方案 A — JSON 静态映射，覆盖 10 个高频板块
Phase 2 (1 周)   : 方案 C — AKShare 动态获取，作为主力方案
Phase 3 (2 周)   : 板块指数行情 + 北向资金接入
Phase 4 (后续)   : 财务增强 + 新闻/公告结构化
```

#### 3.5 修改点定位

| 文件 | 修改内容 |
|------|---------|
| `collectors/digital_oracle_collector.py` | 1. `infer_auto_candidate_universe()` 增加板块 token<br>2. 新增 `resolve_sector_to_symbols()` 函数<br>3. `discover_candidate_universe()` 调用板块解析 |
| `collectors/connectors/china.py` | 新增 `build_sector_tasks()` — 板块指数查询 |
| `collectors/digital_oracle/providers/tencent_finance.py` | 新增板块指数查询方法 |
| `data/sector_mapping.json` | 新增静态板块映射文件 |
| `graph/a_share_auto_trade_graph.py` | `build_a_share_context()` 增加板块解析 fallback |
| `server.py` | `build_graph_inputs()` 增加板块模式校验 |

---

## 前端 React 升级技术方案

### 1. 背景

> 当前前端 `web/` 目录使用原生 HTML + CSS + Vanilla JS 实现，包含：

| 文件 | 代码量 | 说明 |
|------|--------|------|
| `index.html` | ~156 行 | 单页面骨架 |
| `styles.css` | ~1579 行 | 完整设计令牌 + 组件样式 |
| `app.js` | ~862 行 | 状态管理 + DOM 操作 + 事件绑定 + 渲染逻辑 |

**现有能力**（必须完整保留）：
- 三栏布局（控制面板 / 流程进度 / 阶段输出）
- 四种运行模式切换（通用分析 / 每日扫描 / 指定板块 / 指定个股）
- NDJSON 流式消费 + AbortController 暂停
- 8 阶段 Agent 流水线（含 A 股扩展）
- 三视图切换（摘要 / 原文 / 数据源）
- 交易计划面板（条件展开）
- 健康检查 + Markdown 渲染（marked + DOMPurify）
- 深色主题设计令牌体系

**痛点驱动升级**：
1. `app.js` 862 行单文件，`renderStageShell` / `renderResultTabs` / `renderResultViewer` 等函数通过 `innerHTML` 拼接 HTML，难以维护和测试
2. 状态散落在 `state` 对象和 DOM 属性中，缺乏单一数据源
3. 每次模式切换要同时调用 `renderStageShell()` + `renderResultTabs()` + `updateVisibleFields()` + `resetViewer()`，容易遗漏
4. 板块解析 bug（`a_share_sector` 模式下 candidates 为空）需要在前端/后端间协调修复，缺乏统一的状态流转

---

## 2. 技术选型

| 维度 | 选型 | 理由 |
|------|------|------|
| 框架 | **React 18** (函数组件 + Hooks) | 组件化拆分、声明式渲染 |
| 语言 | **TypeScript** | 类型安全，NDJSON 事件结构、Stage 元数据等都有明确定义 |
| 构建工具 | **Vite 5** | 零配置启动、HMR 快、产物体积小 |
| 状态管理 | **useReducer + Context** | 足够覆盖当前复杂度，无需引入 Redux/Zustand |
| 样式方案 | **保留现有 CSS** + CSS Modules | 设计令牌系统 (`:root` variables) 完整保留，仅做作用域隔离 |
| Markdown | **react-markdown** + remark-gfm | 替代 marked + DOMPurify，内置 XSS 防护 |
| HTTP 客户端 | **原生 fetch** | 已有 NDJSON 流式逻辑，无需 axios |

---

## 3. 目录结构

```
web/                          # 替换现有的 web/ 目录
├── index.html                # Vite 入口 shell（极薄）
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx              # React 挂载入口
│   ├── App.tsx               # 根组件（布局 + 全局 Context）
│   ├── index.css             # 设计令牌 + 全局重置（从 styles.css 提取 :root 和 reset）
│   │
│   ├── components/
│   │   ├── Topbar.tsx        # 顶部栏：标题 + 健康状态
│   │   ├── ControlPanel.tsx  # 左侧：模式切换 + 输入表单
│   │   ├── PipelineBar.tsx   # 顶部流水线指示条
│   │   ├── StageCard.tsx     # 单个 Agent 阶段卡片
│   │   ├── StageGrid.tsx     # 阶段卡片列表
│   │   ├── ResultTabs.tsx    # 右侧阶段 Tab 切换
│   │   ├── ViewTabs.tsx      # 摘要/原文/数据源 Tab
│   │   ├── ResultViewer.tsx  # 内容渲染区
│   │   ├── TradePlanPanel.tsx# 底部交易计划面板
│   │   ├── Markdown.tsx      # Markdown 渲染封装
│   │   └── Segmented.tsx     # 分段控制器（复用组件）
│   │
│   ├── hooks/
│   │   ├── useDecisionRun.ts # 核心：NDJSON 流式消费 + 状态分发
│   │   ├── useHealth.ts      # 健康检查
│   │   └── useTimer.ts       # 耗时计时器
│   │
│   ├── store/
│   │   ├── types.ts          # 全局类型定义
│   │   ├── state.ts          # Reducer + ActionType 定义
│   │   └── reducer.ts        # 状态机逻辑
│   │
│   ├── api/
│   │   ├── client.ts         # fetch 封装 + NDJSON 解析器
│   │   └── types.ts          # API 请求/响应类型
│   │
│   └── styles/
│       ├── tokens.css        # 设计令牌（从 styles.css 提取 :root）
│       ├── layout.css        # 三栏 grid 布局
│       ├── components.css    # 卡片、按钮、badge 等
│       ├── pipeline.css      # 流水线节点样式
│       └── markdown.css      # Markdown 渲染样式
```

---

## 4. 类型系统设计

```typescript
// store/types.ts

export type RunMode = "common" | "a_share_daily" | "a_share_sector" | "a_share_deep";
export type ModelMode = "openrouter" | "mock";
export type RiskTolerance = "conservative" | "moderate" | "aggressive";
export type StageStatus = "waiting" | "running" | "done" | "error" | "paused";
export type StageView = "summary" | "raw" | "sources";

export interface StageMeta {
  id: string;
  agent: string;
  title: string;
  color: string;
  icon: React.ReactNode;  // SVG icon
}

export interface SourceItem {
  label: string;
  site: string;
  url: string;
  data: string;
  status: "success" | "failed";
  detail: string;
  message: string;
}

export interface StageState {
  status: StageStatus;
  content: string;
  summary: string;
  sources: SourceItem[];
}

// NDJSON 事件类型
export type NdjsonEvent =
  | { type: "start"; stages: StageMeta[] }
  | { type: "stage_status"; node: string; status: StageStatus }
  | {
      type: "stage";
      node: string;
      content: string;
      summary?: string;
      source_trace?: SourceItem[];
      node_meta?: StageMeta;
    }
  | { type: "complete"; final_output: string; state: Record<string, unknown> }
  | { type: "error"; message: string; hint: string };

// API 请求体
export interface DecisionRequest {
  task: string;
  symbols: string;
  sectors: string;
  mode: "openrouter" | "mock" | "a_share_daily" | "a_share_sector" | "a_share_deep";
  risk_tolerance: RiskTolerance;
  capital: number;
  config_path: string;
}
```

---

## 5. 状态管理设计

### 5.1 Reducer 定义

```typescript
// store/state.ts

export interface AppState {
  // 输入参数
  runMode: RunMode;
  modelMode: ModelMode;
  symbols: string;
  sectors: string;
  riskTolerance: RiskTolerance;
  capital: number;
  task: string;

  // 运行状态
  running: boolean;
  paused: boolean;
  startedAt: number | null;
  elapsedMs: number;

  // 阶段数据
  stageOrder: string[];
  stages: Record<string, StageState>;  // nodeId -> StageState

  // UI 状态
  activeStageTab: string | null;
  activeStageView: StageView;

  // 最终结果
  finalOutput: string;
  completeState: Record<string, unknown>;
}

export type AppAction =
  | { type: "SET_RUN_MODE"; payload: RunMode }
  | { type: "SET_SYMBOLS"; payload: string }
  | { type: "SET_SECTORS"; payload: string }
  | { type: "SET_TASK"; payload: string }
  | { type: "SET_RISK"; payload: RiskTolerance }
  | { type: "SET_CAPITAL"; payload: number }
  | { type: "RUN_START"; payload: { stageOrder: string[] } }
  | { type: "STAGE_STATUS"; payload: { node: string; status: StageStatus } }
  | { type: "STAGE_COMPLETE"; payload: { node: string; content: string; summary: string; sources: SourceItem[] } }
  | { type: "RUN_COMPLETE"; payload: { finalOutput: string; state: Record<string, unknown> } }
  | { type: "RUN_ERROR"; payload: string }
  | { type: "RUN_PAUSE" }
  | { type: "RESET" }
  | { type: "SET_ACTIVE_TAB"; payload: string }
  | { type: "SET_ACTIVE_VIEW"; payload: StageView }
  | { type: "TICK"; payload: number };
```

### 5.2 Context 封装

```typescript
const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  runDecision: () => Promise<void>;
  pauseRun: () => void;
} | null>(null);
```

所有组件通过 `useContext(AppContext)` 获取状态和 dispatch，彻底消除 DOM 操作。

---

## 6. 核心组件设计

### 6.1 App.tsx — 根组件

```tsx
function App() {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const runDecision = useDecisionRun(state, dispatch);
  const pauseRun = useCallback(() => {
    dispatch({ type: "RUN_PAUSE" });
  }, []);

  return (
    <AppContext.Provider value={{ state, dispatch, runDecision, pauseRun }}>
      <div className="app-shell">
        <Topbar />
        <main className="workspace">
          <ControlPanel />
          <section className="process-panel">
            <PipelineBar />
            <StageGrid />
          </section>
          <ResultPanel />
        </main>
        <TradePlanPanel />
      </div>
    </AppContext.Provider>
  );
}
```

### 6.2 ControlPanel.tsx — 左侧控制面板

```tsx
function ControlPanel() {
  const { state, dispatch, runDecision } = useAppContext();
  const isAShare = state.runMode !== "common";

  return (
    <section className="control-panel">
      <div className="panel-header"><h2>决策参数</h2></div>

      <Segmented
        label="运行模式"
        options={[
          { value: "common", label: "通用分析" },
          { value: "a_share_daily", label: "每日扫描" },
          { value: "a_share_sector", label: "指定板块" },
          { value: "a_share_deep", label: "指定个股" },
        ]}
        value={state.runMode}
        onChange={(v) => dispatch({ type: "SET_RUN_MODE", payload: v as RunMode })}
      />

      {!isAShare && (
        <Segmented
          label="模型模式"
          options={[
            { value: "openrouter", label: "OpenRouter" },
            { value: "mock", label: "Mock" },
          ]}
          value={state.modelMode}
          onChange={(v) => dispatch({ type: "SET_MODEL_MODE", payload: v as ModelMode })}
        />
      )}

      {state.runMode === "a_share_sector" && (
        <Field label="板块名称">
          <input
            value={state.sectors}
            onChange={(e) => dispatch({ type: "SET_SECTORS", payload: e.target.value })}
            placeholder="逗号分隔，如 白酒,半导体"
          />
        </Field>
      )}

      {(!isAShare || state.runMode === "a_share_deep") && (
        <Field label="股票代码">
          <input
            value={state.symbols}
            onChange={(e) => dispatch({ type: "SET_SYMBOLS", payload: e.target.value })}
            placeholder="逗号分隔，如 AAPL,MSFT"
          />
        </Field>
      )}

      {isAShare && (
        <>
          <Segmented
            label="风险偏好"
            options={[
              { value: "conservative", label: "保守" },
              { value: "moderate", label: "稳健" },
              { value: "aggressive", label: "激进" },
            ]}
            value={state.riskTolerance}
            onChange={(v) => dispatch({ type: "SET_RISK", payload: v as RiskTolerance })}
          />
          <Field label="可用资金（元）">
            <input
              type="number"
              value={state.capital}
              onChange={(e) => dispatch({ type: "SET_CAPITAL", payload: Number(e.target.value) })}
            />
          </Field>
        </>
      )}

      <Field label="任务描述">
        <textarea
          value={state.task}
          rows={5}
          onChange={(e) => dispatch({ type: "SET_TASK", payload: e.target.value })}
        />
      </Field>

      <div className="action-row">
        <button onClick={runDecision} disabled={state.running}>
          <PlayIcon /> 运行决策
        </button>
        <button onClick={pauseRun} disabled={!state.running}>
          <PauseIcon /> 暂停
        </button>
      </div>

      <RunMeta />
    </section>
  );
}
```

### 6.3 useDecisionRun.ts — 核心 Hook

这是替代现有 `runDecision()` + `readNdjson()` + `handleEvent()` 的核心逻辑：

```typescript
function useDecisionRun(state: AppState, dispatch: Dispatch<AppAction>) {
  const abortRef = useRef<AbortController | null>(null);

  return useCallback(async () => {
    if (state.running) return;

    dispatch({ type: "RESET" });
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: "RUN_START" }); // 设置 startedAt, running=true

    const payload: DecisionRequest = buildPayload(state);

    try {
      const response = await fetch("/api/decide/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      await readNdjson(response.body, (event) => {
        switch (event.type) {
          case "start":
            dispatch({ type: "RUN_START", payload: { stageOrder: event.stages.map(s => s.id) } });
            break;
          case "stage_status":
            dispatch({ type: "STAGE_STATUS", payload: event });
            break;
          case "stage":
            dispatch({
              type: "STAGE_COMPLETE",
              payload: {
                node: event.node,
                content: event.content,
                summary: event.summary || "",
                sources: event.source_trace || [],
              },
            });
            break;
          case "complete":
            dispatch({ type: "RUN_COMPLETE", payload: event });
            break;
          case "error":
            dispatch({ type: "RUN_ERROR", payload: `${event.message}\n${event.hint}` });
            break;
        }
      });
    } catch (error) {
      if (error.name === "AbortError") {
        dispatch({ type: "RUN_PAUSE" });
      } else {
        dispatch({ type: "RUN_ERROR", payload: String(error) });
      }
    } finally {
      abortRef.current = null;
    }
  }, [state, dispatch]);
}

// NDJSON 解析器（纯函数，与 React 解耦）
async function readNdjson(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: NdjsonEvent) => void
) {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}
```

### 6.4 StageCard.tsx — 阶段卡片

```tsx
function StageCard({ nodeId }: { nodeId: string }) {
  const stage = useStage(nodeId);
  const meta = STAGE_META[nodeId];

  return (
    <article className={`stage-card ${stage.status}`} style={{ "--card-brand": meta.color }}>
      <div className="stage-head">
        <span className="stage-icon">{meta.icon}</span>
        <div className="stage-title">
          <h3>{meta.agent}</h3>
          <span>{meta.title}</span>
        </div>
        <span className="badge">{statusText(stage.status)}</span>
      </div>
      <div className="stage-body markdown">
        {stage.status === "running" && <LoadingSpinner brand={meta.color} />}
        {stage.content ? (
          <Markdown content={stage.content} />
        ) : (
          <span className="placeholder">等待输出。</span>
        )}
      </div>
      {nodeId === "information_analysis" && (
        <SourceInspector sources={stage.sources} />
      )}
    </article>
  );
}
```

### 6.5 ResultPanel — 右侧输出面板

```tsx
function ResultPanel() {
  const { state, dispatch } = useAppContext();

  return (
    <section className="result-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Decision Output</p>
          <h2>阶段输出</h2>
        </div>
        <CopyButton />
      </div>

      {/* 阶段 Tab */}
      <div className="result-tabs">
        {state.stageOrder.map((id) => (
          <button
            key={id}
            className={`rtab ${state.activeStageTab === id ? "active" : ""} ${
              state.stages[id]?.content ? "has-content" : ""
            }`}
            style={{ "--tab-brand": STAGE_META[id].color" }}
            onClick={() => dispatch({ type: "SET_ACTIVE_TAB", payload: id })}
          >
            <span className="rtab-dot" />
            {STAGE_META[id].agent}
          </button>
        ))}
      </div>

      {/* 视图 Tab */}
      <ViewTabs
        view={state.activeStageView}
        onChange={(v) => dispatch({ type: "SET_ACTIVE_VIEW", payload: v })}
      />

      {/* 内容区 */}
      <ResultViewer />

      <div className="final-divider"><span>完整汇总</span></div>
      <div className="markdown">
        {state.finalOutput ? (
          <Markdown content={state.finalOutput} />
        ) : (
          "等待模型输出。"
        )}
      </div>
    </section>
  );
}
```

---

## 7. NDJSON 流式协议（保持不变）

React 升级**不修改**后端 API 协议，现有 `server.py` 的 NDJSON 事件体系完全复用：

| 事件 | 前端 action 映射 |
|------|-----------------|
| `start` | `RUN_START` — 设置 stageOrder |
| `stage_status` | `STAGE_STATUS` — 更新单个阶段状态 |
| `stage` | `STAGE_COMPLETE` — 写入 content + summary + sources |
| `complete` | `RUN_COMPLETE` — 写入 finalOutput + completeState |
| `error` | `RUN_ERROR` — 显示错误 |

---

## 8. 板块解析 Bug 修复进度

> 详细诊断见上方「后端升级技术方案」第一章。

### 8.1 前端侧（React 升级时同步处理）

在 `ControlPanel` 的 `useEffect` 中添加模式切换时的校验：

```typescript
// 当切换到 a_share_sector 模式且 sectors 为空时，提示用户输入
useEffect(() => {
  if (state.runMode === "a_share_sector" && !state.sectors.trim()) {
    // 保持空值 + UI 提示，不自动填充
  }
}, [state.runMode, state.sectors]);
```

### 8.2 后端侧（独立 PR，见上方 3.5 修改点定位）

| 修改 | 文件 | 说明 |
|------|------|------|
| 增加板块 token | `digital_oracle_collector.py` | `infer_auto_candidate_universe()` 匹配 "板块" |
| JSON 静态映射 | `data/sector_mapping.json` | 覆盖 10 个高频板块 |
| 板块解析函数 | `digital_oracle_collector.py` | `resolve_sector_to_symbols()` |
| 输入校验 | `server.py` | `build_graph_inputs()` 空板块报错 |

---

## 9. CSS 迁移策略

### 9.1 不重写，只迁移

现有 `styles.css` 的 1579 行 CSS 质量很高（完整的设计令牌系统），**不做重写**。

迁移步骤：
1. `:root { ... }` 设计令牌 → `tokens.css`
2. `*` reset + `body` → `tokens.css` 底部
3. `.app-shell` ~ `.topbar` ~ `.workspace` → `layout.css`
4. `.control-panel` ~ `.field` ~ `.segmented` ~ `.run-button` → `components.css`
5. `.pipeline` ~ `.pipeline-node` → `pipeline.css`
6. `.stage-card` ~ `.stage-head` ~ `.stage-body` → `components.css`
7. `.result-tabs` ~ `.rtab` ~ `.view-tabs` ~ `.result-viewer` → `components.css`
8. `.trade-plan-panel` ~ `.markdown` → `components.css` + `markdown.css`
9. `@media` 响应式 → 各自对应的文件底部

### 9.2 CSS Modules 封装

对新建的组件特有样式使用 CSS Modules，避免全局污染：

```tsx
// components/StageCard.module.css (仅新增的样式)
.card {
  composes: stage-card from "../styles/components.css";
}

.card:hover {
  box-shadow: var(--glow-sm);
}
```

已有全局 class 名（如 `stage-card`, `pipeline-node`, `rtab`）保持不变，继续在 CSS 全局作用域中工作。

---

## 10. 构建与部署

### 10.1 Vite 配置

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    outDir: "dist",
    rollupOptions: {
      input: "index.html",
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",  // 开发时代理到 FastAPI
    },
  },
});
```

### 10.2 部署策略

**方案 A（推荐）：Vite build → FastAPI 静态托管**

```
server.py 保持不变：
app.mount("/", StaticFiles(directory="web/dist", html=True), name="web")

构建流程：
cd web && npm run build
产物输出到 web/dist/
FastAPI 继续托管静态文件
```

**方案 B：独立部署前端，CORS 连接**

前端部署到 Nginx/CDN，通过 CORS 请求 `:8000/api/*`。适合前后端分离部署场景，当前项目不需要。

---

## 11. 开发阶段计划

### Phase 1: 基础设施搭建 (1 天)

| 任务 | 产出 | 说明 |
|------|------|------|
| 初始化 Vite + React + TS 项目 | `web/package.json`, `vite.config.ts` | 基于现有 `web/` 目录 |
| 迁移 CSS 设计令牌 | `src/styles/tokens.css` | 验证深色主题 |
| 定义类型系统 | `src/store/types.ts`, `src/api/types.ts` | NDJSON 事件 + 状态类型 |
| 实现 AppReducer | `src/store/reducer.ts` | 覆盖所有 action 分支 |
| App 根组件 + 布局 | `src/App.tsx` | 三栏 grid 骨架 |

### Phase 2: 组件实现 (2 天)

| 任务 | 产出 | 说明 |
|------|------|------|
| Topbar + ControlPanel | 两个组件 | 模式切换 + 输入表单 |
| Segmented 通用组件 | 复用组件 | 替代现有 segmented 逻辑 |
| PipelineBar + StageCard + StageGrid | 三个组件 | 流水线指示条 + 阶段卡片 |
| ResultTabs + ViewTabs + ResultViewer | 三个组件 | 右侧输出面板 |
| TradePlanPanel | 组件 | 交易计划展示 |
| Markdown 封装 | 组件 | react-markdown + remark-gfm |

### Phase 3: 核心 Hook (1 天)

| 任务 | 产出 | 说明 |
|------|------|------|
| useDecisionRun | Hook | NDJSON 流式消费 + dispatch |
| useHealth | Hook | `/api/health` 轮询 |
| useTimer | Hook | 耗时计时 |
| NDJSON 解析器 | 纯函数 | 从 app.js 迁移 |

### Phase 4: 联调与兼容 (1 天)

| 任务 | 说明 |
|------|------|
| Mock 模式端到端验证 | 确保 5 阶段 + 8 阶段都正常 |
| A 股模式验证 | 每日扫描 / 指定板块 / 指定个股 |
| 暂停 / 错误处理 | AbortController 行为一致 |
| 响应式验证 | 三个断点 |
| 性能对比 | 首屏加载、切换响应速度与旧版对比 |

### Phase 5: 切换与清理 (0.5 天)

| 任务 | 说明 |
|------|------|
| `server.py` 修改 StaticFiles 路径 | `web/` → `web/dist/` |
| 删除旧 `index.html` / `app.js` / `styles.css` | 或移到 `web/legacy/` 备份 |
| 验证生产 build | `npm run build` 产物正常 |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| react-markdown 渲染输出与现有 marked 不一致 | 表格/列表样式差异 | 自定义 components 映射，保留现有 `.markdown` CSS |
| Vite HMR 与 FastAPI 冲突 | 开发时页面不刷新 | 使用 `server.proxy` 配置，页面走 Vite dev server，API 走 FastAPI |
| React 18 StrictMode 导致 double-invoke | useDecisionRun 可能触发两次 | 用 useRef 做幂等保护 |
| 组件拆分后 CSS class 名丢失 | 样式断裂 | 保持现有 class 名不变，仅新增 CSS Modules |
| 迁移期间功能回归 | 用户可用 | 旧版保留为 `web/legacy/`，新构建路径切换完成后才删除 |

---

## 13. 不做什么

| 范围 | 说明 |
|------|------|
| 不修改后端 API 协议 | NDJSON 事件格式完全不变 |
| 不引入路由/多页面 | 仍然是单页面应用 |
| 不引入状态管理库 | useReducer + Context 足够 |
| 不重写 CSS 设计令牌 | 现有体系完整保留 |
| 不做 SSR/SSG | 这是工具型内部应用，不需要 SEO |
| 不修改 LangGraph 流程 | 前后端交互层不变 |
