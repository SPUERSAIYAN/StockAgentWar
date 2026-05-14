import { useMemo, useReducer } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { ProcessPanel } from "./components/ProcessPanel";
import { ResultPanel } from "./components/ResultPanel";
import { Topbar } from "./components/Topbar";
import { useDecisionRun } from "./hooks/useDecisionRun";
import { useTimer } from "./hooks/useTimer";
import { AppContext } from "./store/context";
import { appReducer } from "./store/reducer";
import { initialState } from "./store/state";

export function App() {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const { runDecision, pauseRun, copyFinal } = useDecisionRun(state, dispatch);
  useTimer(state, dispatch);

  const value = useMemo(
    () => ({ state, dispatch, runDecision, pauseRun, copyFinal }),
    [copyFinal, pauseRun, runDecision, state],
  );

  return (
    <AppContext.Provider value={value}>
      <div className="app-shell">
        <Topbar />
        <main className="workspace">
          <ControlPanel />
          <ProcessPanel />
          <ResultPanel />
        </main>
      </div>
    </AppContext.Provider>
  );
}
