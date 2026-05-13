import { useAppContext } from "../store/context";
import { createStageState } from "../store/state";
import { StageCard } from "./StageCard";

export function StageGrid() {
  const { state } = useAppContext();

  return (
    <div className="stage-grid">
      {state.stageOrder.map((id) => (
        <StageCard key={id} id={id} stage={state.stages[id] || createStageState()} />
      ))}
    </div>
  );
}
