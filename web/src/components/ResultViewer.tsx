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
      <span>{text}<i className="terminal-cursor" /></span>
    </div>
  );
}

function TerminalHeader({ title, status, view }: { title: string; status: string; view: string }) {
  return (
    <div className="terminal-titlebar">
      <div className="terminal-tabs">
        <span className="terminal-light" />
        <strong>{title}</strong>
      </div>
      <div className="terminal-meta">
        <span>{view}</span>
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
        <TerminalHeader title="AGENT_OUTPUT" status="IDLE" view="SUMMARY" />
        <Placeholder text="运行后显示各阶段报告" />
      </div>
    );
  }

  const stage = state.stages[node];
  const meta = STAGE_META[node];
  if (!stage || !meta) {
    return (
      <div className="result-viewer">
        <TerminalHeader title="AGENT_OUTPUT" status="ERROR" view="SUMMARY" />
        <Placeholder text="未找到阶段输出" />
      </div>
    );
  }

  const viewLabel = state.activeStageView === "summary" ? "SUMMARY" : state.activeStageView === "raw" ? "RAW" : "SOURCES";
  const stageStatus = statusText(stage.status);

  if (state.activeStageView === "summary") {
    return (
      <div className="result-viewer">
        <TerminalHeader title={meta.agent} status={stageStatus} view={viewLabel} />
        <Markdown className="summary-view" text={stage.summary} emptyText={`${meta.agent} — 暂无摘要`} />
      </div>
    );
  }

  if (state.activeStageView === "raw") {
    return (
      <div className="result-viewer">
        <TerminalHeader title={meta.agent} status={stageStatus} view={viewLabel} />
        {stage.content.trim() ? <pre className="raw-view">{stage.content}</pre> : <Placeholder text={`${meta.agent} — 暂无原文`} />}
      </div>
    );
  }

  return (
    <div className="result-viewer">
      <TerminalHeader title={meta.agent} status={stageStatus} view={viewLabel} />
      <div className="source-view">
        <SourceList sources={stage.sources} />
      </div>
    </div>
  );
}
