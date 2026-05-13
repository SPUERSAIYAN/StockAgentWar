import { useEffect } from "react";
import type { Dispatch } from "react";
import type { AppAction, AppState } from "../store/types";

export function useTimer(state: AppState, dispatch: Dispatch<AppAction>) {
  useEffect(() => {
    if (!state.running || !state.startedAt) return;
    const timer = window.setInterval(() => {
      dispatch({ type: "TICK", payload: Date.now() - state.startedAt! });
    }, 200);
    return () => window.clearInterval(timer);
  }, [dispatch, state.running, state.startedAt]);
}
