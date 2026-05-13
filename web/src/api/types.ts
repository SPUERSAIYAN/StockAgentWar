import type { RiskTolerance, SourceItem, StageStatus } from "../store/types";

export interface StageDescriptor {
  id: string;
  agent?: string;
  title?: string;
  color?: string;
}

export interface DecisionRequest {
  task: string;
  symbols: string;
  sectors: string;
  mode: "openrouter" | "mock" | "a_share_daily" | "a_share_sector" | "a_share_deep";
  risk_tolerance: RiskTolerance;
  capital: number;
  config_path: string;
}

export type NdjsonEvent =
  | { type: "start"; task: string; symbols: string; sectors: string; mode: string; stages: StageDescriptor[] }
  | { type: "stage_status"; node: string; status: StageStatus; elapsed_ms?: number }
  | {
      type: "stage";
      node: string;
      status?: StageStatus;
      content: string;
      summary?: string;
      source_trace?: SourceItem[];
      node_meta?: StageDescriptor;
    }
  | { type: "complete"; final_output: string; state: Record<string, unknown>; elapsed_ms?: number }
  | { type: "error"; message: string; hint?: string; elapsed_ms?: number };

export interface HealthResponse {
  ok: boolean;
  config_exists: boolean;
  openrouter_key_ready: boolean;
  stages: StageDescriptor[];
  stage_sets?: Record<string, StageDescriptor[]>;
}
