import type { StageView } from "../store/types";
import { useAppContext } from "../store/context";

const views: Array<{ value: StageView; label: string }> = [
  { value: "summary", label: "摘要" },
  { value: "raw", label: "原文" },
  { value: "sources", label: "来源" },
];

export function ViewTabs() {
  const { state, dispatch } = useAppContext();

  return (
    <div className="view-tabs">
      {views.map((view) => (
        <button
          key={view.value}
          className={`view-tab${state.activeStageView === view.value ? " active" : ""}`}
          type="button"
          onClick={() => dispatch({ type: "SET_ACTIVE_VIEW", payload: view.value })}
        >
          {view.label}
        </button>
      ))}
    </div>
  );
}
