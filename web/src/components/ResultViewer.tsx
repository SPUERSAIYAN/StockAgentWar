import { STAGE_META } from "../store/stageMeta";
import { useAppContext } from "../store/context";
import { statusText } from "../utils";
import { DocumentIcon } from "./Icons";
import { Markdown } from "./Markdown";
import { SourceList } from "./SourceList";

function Placeholder({ text }: { text: string }) {
  return (
    <div className="viewer-placeholder">
      <DocumentIcon />
      <span>{text}</span>
    </div>
  );
}

function ViewerHeader({ title, status, view }: { title: string; status: string; view: string }) {
  return (
    <div className="viewer-header">
      <div>
        <strong>{title}</strong>
        <span>{view}</span>
      </div>
      <div className="viewer-meta">
        <span>{status}</span>
      </div>
    </div>
  );
}

export function ResultViewer() {
  const { state } = useAppContext();
  const node = state.activeStageTab;

  if (!node) {
    return (
      <div className="result-viewer">
        <ViewerHeader title="阶段输出" status="待运行" view="摘要" />
        <Placeholder text="运行后显示各阶段报告" />
      </div>
    );
  }

  const stage = state.stages[node];
  const meta = STAGE_META[node];
  if (!stage || !meta) {
    return (
      <div className="result-viewer">
        <ViewerHeader title="阶段输出" status="异常" view="摘要" />
        <Placeholder text="未找到阶段输出" />
      </div>
    );
  }

  const viewLabel = state.activeStageView === "summary" ? "摘要" : state.activeStageView === "raw" ? "原文" : "来源";
  const stageStatus = statusText(stage.status);

  if (state.activeStageView === "summary") {
    return (
      <div className="result-viewer">
        <ViewerHeader title={meta.agent} status={stageStatus} view={viewLabel} />
        <Markdown className="summary-view" text={stage.summary} emptyText={`${meta.agent} — 暂无摘要`} />
      </div>
    );
  }

  if (state.activeStageView === "raw") {
    return (
      <div className="result-viewer">
        <ViewerHeader title={meta.agent} status={stageStatus} view={viewLabel} />
        {stage.content.trim() ? <pre className="raw-view">{stage.content}</pre> : <Placeholder text={`${meta.agent} — 暂无原文`} />}
      </div>
    );
  }

  return (
    <div className="result-viewer">
      <ViewerHeader title={meta.agent} status={stageStatus} view={viewLabel} />
      <div className="source-view">
        <SourceList sources={stage.sources} />
      </div>
    </div>
  );
}
