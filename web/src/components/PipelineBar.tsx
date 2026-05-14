import type { CSSProperties } from "react";
import { STAGE_META } from "../store/stageMeta";
import { useAppContext } from "../store/context";
import { statusText } from "../utils";

export function PipelineBar() {
  const { state } = useAppContext();

  return (
    <div className="pipeline">
      {state.stageOrder.map((id) => {
        const meta = STAGE_META[id];
        const stage = state.stages[id];
        if (!meta) return null;
        return (
          <div key={id} className={`pipeline-node ${stage?.status || "waiting"}`} data-node={id} style={{ "--node-brand": meta.color } as CSSProperties}>
            <div className="node-topline">
              <span className="node-icon">{meta.icon}</span>
              <span className="pipeline-status">{statusText(stage?.status || "waiting")}</span>
            </div>
            <strong>{meta.agent}</strong>
            <span className="node-description">{meta.title}</span>
          </div>
        );
      })}
    </div>
  );
}
