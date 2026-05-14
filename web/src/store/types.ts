import type { ReactNode } from "react";

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
  icon: ReactNode;
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

export interface AppState {
  runMode: RunMode;
  modelMode: ModelMode;
  symbols: string;
  sectors: string;
  openrouterApiKey: string;
  riskTolerance: RiskTolerance;
  capital: number;
  task: string;
  running: boolean;
  paused: boolean;
  startedAt: number | null;
  elapsedMs: number;
  stageOrder: string[];
  stages: Record<string, StageState>;
  activeStageTab: string | null;
  activeStageView: StageView;
  finalOutput: string;
  completeState: Record<string, unknown>;
  error: string | null;
}

export type AppAction =
  | { type: "SET_RUN_MODE"; payload: RunMode }
  | { type: "SET_MODEL_MODE"; payload: ModelMode }
  | { type: "SET_SYMBOLS"; payload: string }
  | { type: "SET_SECTORS"; payload: string }
  | { type: "SET_OPENROUTER_API_KEY"; payload: string }
  | { type: "SET_TASK"; payload: string }
  | { type: "SET_RISK"; payload: RiskTolerance }
  | { type: "SET_CAPITAL"; payload: number }
  | { type: "RUN_START"; payload: { stageOrder: string[] } }
  | { type: "STAGE_STATUS"; payload: { node: string; status: StageStatus } }
  | {
      type: "STAGE_COMPLETE";
      payload: { node: string; content: string; summary: string; sources: SourceItem[] };
    }
  | { type: "RUN_COMPLETE"; payload: { finalOutput: string; state: Record<string, unknown> } }
  | { type: "RUN_ERROR"; payload: string }
  | { type: "RUN_PAUSE" }
  | { type: "RESET_OUTPUTS"; payload: { stageOrder: string[] } }
  | { type: "SET_ACTIVE_TAB"; payload: string | null }
  | { type: "SET_ACTIVE_VIEW"; payload: StageView }
  | { type: "TICK"; payload: number };
