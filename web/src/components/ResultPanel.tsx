import { useAppContext } from "../store/context";
import { CopyIcon } from "./Icons";
import { Markdown } from "./Markdown";
import { ResultTabs } from "./ResultTabs";
import { ResultViewer } from "./ResultViewer";
import { TradePlanPanel } from "./TradePlanPanel";
import { ViewTabs } from "./ViewTabs";

export function ResultPanel() {
  const { state, copyFinal } = useAppContext();

  return (
    <section className="result-panel">
      <div className="panel-header">
        <h2>输出分析</h2>
        <button className="icon-button" type="button" title="复制最终输出" aria-label="复制最终输出" onClick={copyFinal}>
          <CopyIcon />
        </button>
      </div>

      <ResultTabs />
      <ViewTabs />
      <ResultViewer />

      <div className="final-divider">
        <span>最终输出</span>
      </div>
      <Markdown text={state.finalOutput} emptyText="等待模型输出。" />
      <TradePlanPanel />
    </section>
  );
}
