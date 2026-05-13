import { useCallback, useRef } from "react";
import type { Dispatch } from "react";
import { streamDecision } from "../api/client";
import type { DecisionRequest, NdjsonEvent } from "../api/types";
import type { AppAction, AppState, RunMode } from "../store/types";
import { currentStageOrder, normalizeStageOrder } from "../store/stageMeta";
import { normalizeSources, summarizeMarkdown } from "../utils";

function backendMode(state: AppState): DecisionRequest["mode"] {
  return state.runMode === "common" ? state.modelMode : state.runMode;
}

function buildRequest(state: AppState): DecisionRequest {
  const isAShare = state.runMode !== "common";
  return {
    task: state.task.trim(),
    symbols: !isAShare || state.runMode === "a_share_deep" ? state.symbols.trim() : "",
    sectors: state.runMode === "a_share_sector" ? state.sectors.trim() : "",
    mode: backendMode(state),
    risk_tolerance: state.riskTolerance,
    capital: Number.isFinite(state.capital) ? state.capital : 1000000,
    config_path: "config.yaml",
  };
}

export function useDecisionRun(state: AppState, dispatch: Dispatch<AppAction>) {
  const abortRef = useRef<AbortController | null>(null);
  const runningRef = useRef(false);

  const pauseRun = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    runningRef.current = false;
    dispatch({ type: "RUN_PAUSE" });
  }, [dispatch]);

  const runDecision = useCallback(() => {
    if (runningRef.current || state.running) return;

    const stageOrder = currentStageOrder(state.runMode);
    const controller = new AbortController();
    abortRef.current = controller;
    runningRef.current = true;
    dispatch({ type: "RUN_START", payload: { stageOrder } });

    const handleEvent = (event: NdjsonEvent) => {
      if (event.type === "start") {
        const ids = Array.isArray(event.stages) ? event.stages.map((stage) => stage.id) : [];
        dispatch({ type: "RESET_OUTPUTS", payload: { stageOrder: normalizeStageOrder(ids, state.runMode as RunMode) } });
        return;
      }

      if (event.type === "stage_status") {
        dispatch({ type: "STAGE_STATUS", payload: { node: event.node, status: event.status } });
        return;
      }

      if (event.type === "stage") {
        const content = event.content || "";
        dispatch({
          type: "STAGE_COMPLETE",
          payload: {
            node: event.node,
            content,
            summary: event.summary || summarizeMarkdown(content),
            sources: normalizeSources(event.source_trace),
          },
        });
        return;
      }

      if (event.type === "complete") {
        runningRef.current = false;
        abortRef.current = null;
        dispatch({
          type: "RUN_COMPLETE",
          payload: { finalOutput: event.final_output || "", state: event.state || {} },
        });
        return;
      }

      if (event.type === "error") {
        runningRef.current = false;
        abortRef.current = null;
        dispatch({ type: "RUN_ERROR", payload: event.message || event.hint || "后端返回未知错误" });
      }
    };

    void streamDecision(buildRequest(state), controller.signal, handleEvent).catch((error: unknown) => {
      runningRef.current = false;
      abortRef.current = null;
      if (error instanceof DOMException && error.name === "AbortError") return;
      dispatch({ type: "RUN_ERROR", payload: error instanceof Error ? error.message : String(error) });
    });
  }, [dispatch, state]);

  const copyFinal = useCallback(() => {
    const text = state.finalOutput || "";
    if (!text.trim()) return;
    void navigator.clipboard?.writeText(text);
  }, [state.finalOutput]);

  return { runDecision, pauseRun, copyFinal };
}
