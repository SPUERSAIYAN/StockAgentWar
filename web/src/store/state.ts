import type { AppState, StageState } from "./types";
import { currentStageOrder } from "./stageMeta";

export const commonTask =
  "筛选未来 1-3 个月的候选股票，输出做多/观望/回避建议，并说明风险控制条件。";

export const dailyTask =
  "扫描市场，找出未来1个月最具投资价值的A股标的，并生成价格触发式交易计划。";

export const sectorTask = "分析指定 A 股板块并给出买入建议。";

export const deepTask = "深度分析指定 A 股并给出交易策略。";

export function createStageState(): StageState {
  return {
    status: "waiting",
    content: "",
    summary: "",
    sources: [],
  };
}

export function createStages(stageOrder: string[]): Record<string, StageState> {
  return Object.fromEntries(stageOrder.map((id) => [id, createStageState()]));
}

export const initialState: AppState = {
  runMode: "common",
  modelMode: "openrouter",
  symbols: "AAPL,MSFT,NVDA",
  sectors: "半导体,白酒,新能源",
  riskTolerance: "moderate",
  capital: 1000000,
  task: commonTask,
  running: false,
  paused: false,
  startedAt: null,
  elapsedMs: 0,
  stageOrder: currentStageOrder("common"),
  stages: createStages(currentStageOrder("common")),
  activeStageTab: null,
  activeStageView: "summary",
  finalOutput: "",
  completeState: {},
  error: null,
};
