import type { AppAction, AppState, StageStatus } from "./types";
import { commonTask, createStages, dailyTask, deepTask, sectorTask } from "./state";

function isLikelyAShareSymbolList(value: string): boolean {
  return value
    .split(",")
    .map((symbol) => symbol.trim())
    .filter(Boolean)
    .some((symbol) => /^\d{6}$/.test(symbol));
}

function markRunningStages(state: AppState, status: StageStatus): AppState["stages"] {
  return Object.fromEntries(
    state.stageOrder.map((id) => {
      const stage = state.stages[id] || { status: "waiting", content: "", summary: "", sources: [] };
      return [id, stage.status === "running" ? { ...stage, status } : stage];
    }),
  );
}

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_RUN_MODE":
      if (action.payload === "common") {
        return {
          ...state,
          runMode: action.payload,
          task: commonTask,
          symbols: !state.symbols.trim() || isLikelyAShareSymbolList(state.symbols) ? "AAPL,MSFT,NVDA" : state.symbols,
        };
      }
      if (action.payload === "a_share_daily") {
        return { ...state, runMode: action.payload, task: dailyTask };
      }
      if (action.payload === "a_share_sector") {
        return {
          ...state,
          runMode: action.payload,
          task: sectorTask,
          sectors: state.sectors.trim() ? state.sectors : "半导体,白酒,新能源",
        };
      }
      return {
        ...state,
        runMode: action.payload,
        task: deepTask,
        symbols: !state.symbols.trim() || !isLikelyAShareSymbolList(state.symbols) ? "600519,000858,300750" : state.symbols,
      };
    case "SET_MODEL_MODE":
      return { ...state, modelMode: action.payload };
    case "SET_SYMBOLS":
      return { ...state, symbols: action.payload };
    case "SET_SECTORS":
      return { ...state, sectors: action.payload };
    case "SET_TASK":
      return { ...state, task: action.payload };
    case "SET_RISK":
      return { ...state, riskTolerance: action.payload };
    case "SET_CAPITAL":
      return { ...state, capital: action.payload };
    case "RUN_START":
      return {
        ...state,
        running: true,
        paused: false,
        startedAt: Date.now(),
        elapsedMs: 0,
        stageOrder: action.payload.stageOrder,
        stages: createStages(action.payload.stageOrder),
        activeStageTab: null,
        activeStageView: "summary",
        finalOutput: "",
        completeState: {},
        error: null,
      };
    case "STAGE_STATUS": {
      const existing = state.stages[action.payload.node] || { status: "waiting", content: "", summary: "", sources: [] };
      return {
        ...state,
        stages: {
          ...state.stages,
          [action.payload.node]: { ...existing, status: action.payload.status },
        },
      };
    }
    case "STAGE_COMPLETE": {
      const existing = state.stages[action.payload.node] || { status: "waiting", content: "", summary: "", sources: [] };
      return {
        ...state,
        activeStageTab: state.activeStageTab || action.payload.node,
        stages: {
          ...state.stages,
          [action.payload.node]: {
            ...existing,
            status: "done",
            content: action.payload.content,
            summary: action.payload.summary,
            sources: action.payload.sources,
          },
        },
      };
    }
    case "RUN_COMPLETE":
      return {
        ...state,
        running: false,
        paused: false,
        finalOutput: action.payload.finalOutput,
        completeState: action.payload.state,
      };
    case "RUN_ERROR":
      return {
        ...state,
        running: false,
        error: action.payload,
        finalOutput: `## 运行失败\n\n${action.payload}`,
        stages: markRunningStages(state, "error"),
      };
    case "RUN_PAUSE":
      return {
        ...state,
        running: false,
        paused: true,
        finalOutput: state.finalOutput || "## 运行已暂停\n\n当前流式任务已停止，已保留已完成阶段输出。",
        stages: markRunningStages(state, "paused"),
      };
    case "RESET_OUTPUTS":
      return {
        ...state,
        stageOrder: action.payload.stageOrder,
        stages: createStages(action.payload.stageOrder),
        activeStageTab: null,
        activeStageView: "summary",
        finalOutput: "",
        completeState: {},
        error: null,
      };
    case "SET_ACTIVE_TAB":
      return { ...state, activeStageTab: action.payload };
    case "SET_ACTIVE_VIEW":
      return { ...state, activeStageView: action.payload };
    case "TICK":
      return { ...state, elapsedMs: action.payload };
    default:
      return state;
  }
}
