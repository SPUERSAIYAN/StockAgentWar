import type { CSSProperties } from "react";
import { STAGE_META } from "../store/stageMeta";
import { useAppContext } from "../store/context";

export function ResultTabs() {
  const { state, dispatch } = useAppContext();

  return (
    <div className="result-tabs">
      {state.stageOrder.map((id) => {
        const meta = STAGE_META[id];
        const stage = state.stages[id];
        if (!meta) return null;
        return (
          <button
            key={id}
            className={`rtab${state.activeStageTab === id ? " active" : ""}${stage?.content ? " has-content" : ""}`}
            data-node={id}
            style={{ "--tab-brand": meta.color } as CSSProperties}
            type="button"
            onClick={() => dispatch({ type: "SET_ACTIVE_TAB", payload: id })}
          >
            <span className="rtab-dot" />
            {meta.agent}
          </button>
        );
      })}
    </div>
  );
}
