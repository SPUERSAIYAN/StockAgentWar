import { PipelineBar } from "./PipelineBar";
import { StageGrid } from "./StageGrid";

export function ProcessPanel() {
  return (
    <section className="process-panel">
      <div className="panel-header">
        <h2>决策流程</h2>
      </div>
      <PipelineBar />
      <StageGrid />
    </section>
  );
}
