import type { ModelMode, RiskTolerance, RunMode } from "../store/types";
import { useAppContext } from "../store/context";
import { formatElapsed } from "../utils";
import { PauseIcon, PlayIcon } from "./Icons";
import { Segmented } from "./Segmented";

export function ControlPanel() {
  const { state, dispatch, runDecision, pauseRun } = useAppContext();
  const isAShare = state.runMode !== "common";
  const status = state.running ? "运行中" : state.paused ? "已暂停" : state.error ? "失败" : state.finalOutput ? "完成" : "已就绪";

  return (
    <aside className="control-panel">
      <div className="panel-header">
        <h2>决策参数</h2>
      </div>

      <Segmented<RunMode>
        label="运行模式"
        className="mode-segments"
        options={[
          { value: "common", label: "通用分析" },
          { value: "a_share_daily", label: "每日扫描" },
          { value: "a_share_sector", label: "指定板块" },
          { value: "a_share_deep", label: "指定个股" },
        ]}
        value={state.runMode}
        onChange={(payload) => dispatch({ type: "SET_RUN_MODE", payload })}
      />

      {!isAShare && (
        <Segmented<ModelMode>
          label="模型模式"
          options={[
            { value: "openrouter", label: "OpenRouter" },
            { value: "mock", label: "Mock" },
          ]}
          value={state.modelMode}
          onChange={(payload) => dispatch({ type: "SET_MODEL_MODE", payload })}
        />
      )}

      {state.runMode === "a_share_sector" && (
        <div className="field">
          <label htmlFor="sectors">股票板块</label>
          <input
            id="sectors"
            value={state.sectors}
            placeholder="例如：半导体,白酒,新能源"
            onChange={(event) => dispatch({ type: "SET_SECTORS", payload: event.target.value })}
          />
        </div>
      )}

      {(!isAShare || state.runMode === "a_share_deep") && (
        <div className="field">
          <label htmlFor="symbols">股票代码</label>
          <input
            id="symbols"
            value={state.symbols}
            placeholder={isAShare ? "例如：600519,300750" : "例如：AAPL,MSFT,NVDA"}
            onChange={(event) => dispatch({ type: "SET_SYMBOLS", payload: event.target.value })}
          />
        </div>
      )}

      {isAShare && (
        <>
          <Segmented<RiskTolerance>
            label="风险偏好"
            className="risk-segments"
            options={[
              { value: "conservative", label: "保守" },
              { value: "moderate", label: "稳健" },
              { value: "aggressive", label: "激进" },
            ]}
            value={state.riskTolerance}
            onChange={(payload) => dispatch({ type: "SET_RISK", payload })}
          />

          <div className="field">
            <label htmlFor="capital">可用资金（元）</label>
            <input
              id="capital"
              type="number"
              min={0}
              value={state.capital}
              onChange={(event) => dispatch({ type: "SET_CAPITAL", payload: Number(event.target.value) })}
            />
          </div>
        </>
      )}

      <div className="field">
        <label htmlFor="task">任务描述</label>
        <textarea
          id="task"
          value={state.task}
          onChange={(event) => dispatch({ type: "SET_TASK", payload: event.target.value })}
        />
      </div>

      <div className="action-row">
        <button className="run-button" type="button" disabled={state.running} onClick={runDecision}>
          {!state.running && <PlayIcon />}
          <span>{state.running ? "运行中" : "运行决策"}</span>
        </button>
        <button className="pause-button" type="button" disabled={!state.running} onClick={pauseRun}>
          <PauseIcon />
          <span>暂停</span>
        </button>
      </div>

      <div className="run-meta">
        <div>
          <span>耗时</span>
          <strong>{formatElapsed(state.elapsedMs)}</strong>
        </div>
        <div>
          <span>状态</span>
          <strong>{status}</strong>
        </div>
      </div>
    </aside>
  );
}
