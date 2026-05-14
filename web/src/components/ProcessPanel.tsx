import { PipelineBar } from "./PipelineBar";
import { StageGrid } from "./StageGrid";
import { useAppContext } from "../store/context";
import { downloadDecisionFlowSnapshot, hasDecisionFlowSnapshot } from "../share";
import { ShareIcon } from "./Icons";

export function ProcessPanel() {
  const { state } = useAppContext();
  const canShare = hasDecisionFlowSnapshot(state);

  return (
    <section className="process-panel" id="process-panel">
      <div className="panel-header">
        <h2>决策流程</h2>
        <button
          className="share-button"
          type="button"
          disabled={!canShare}
          title={canShare ? "下载决策流程静态页面" : "运行后可分享决策流程"}
          onClick={() => downloadDecisionFlowSnapshot(state)}
        >
          <ShareIcon />
          <span>分享</span>
        </button>
      </div>
      <PipelineBar />
      <StageGrid />
    </section>
  );
}
