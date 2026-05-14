import { createContext, useContext, type Dispatch } from "react";
import type { AppAction, AppState } from "./types";

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<AppAction>;
  runDecision: () => void;
  pauseRun: () => void;
  copyFinal: () => void;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function useAppContext(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useAppContext must be used inside AppContext.Provider");
  return value;
}
