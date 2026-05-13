import { useEffect, useState } from "react";
import type { HealthResponse } from "../api/types";

interface HealthState {
  status: "checking" | "ready" | "warn";
  text: string;
}

export function useHealth(): HealthState {
  const [health, setHealth] = useState<HealthState>({ status: "checking", text: "检查中" });

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await fetch("/api/health");
        const data = (await response.json()) as HealthResponse;
        if (!active) return;
        if (response.ok && data.ok) {
          setHealth({
            status: data.openrouter_key_ready ? "ready" : "warn",
            text: data.openrouter_key_ready ? "模型已就绪" : "Mock 可用",
          });
        } else {
          setHealth({ status: "warn", text: "服务异常" });
        }
      } catch {
        if (active) setHealth({ status: "warn", text: "服务未连接" });
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  return health;
}
