import type { CSSProperties } from "react";
import { STAGE_META } from "../store/stageMeta";
import type { StageState } from "../store/types";
import { statusText } from "../utils";
import { Markdown } from "./Markdown";
import { SourceInspector } from "./SourceInspector";

interface StageCardProps {
  id: string;
  stage: StageState;
}

export function StageCard({ id, stage }: StageCardProps) {
  const meta = STAGE_META[id];
  if (!meta) return null;

  const emptyText = stage.status === "running" ? "正在等待阶段输出。" : "等待输出。";

  return (
    <article className={`stage-card ${stage.status}`} data-node={id} style={{ "--card-brand": meta.color } as CSSProperties}>
      <div className="stage-head">
        <span className="stage-icon">{meta.icon}</span>
        <div className="stage-title">
          <h3>{meta.agent}</h3>
          <span>{meta.title}</span>
        </div>
        <div className="badge">{statusText(stage.status)}</div>
      </div>
      <Markdown className="stage-body" text={stage.content} emptyText={emptyText} />
      {id === "information_analysis" && <SourceInspector sources={stage.sources} />}
    </article>
  );
}
