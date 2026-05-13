import type { SourceItem, StageStatus } from "./store/types";

export function formatElapsed(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}

export function statusText(status: StageStatus): string {
  const map: Record<StageStatus, string> = {
    waiting: "等待",
    running: "运行中",
    done: "完成",
    error: "失败",
    paused: "已暂停",
  };
  return map[status];
}

export function summarizeMarkdown(content: string): string {
  const normalized = String(content || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[#>*_`|~-]/g, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n\n");
  return normalized.slice(0, 900);
}

export function normalizeSources(value: unknown): SourceItem[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    const source = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
    const rawStatus = String(source.status || "");
    return {
      label: String(source.label || source.site || `source-${index + 1}`),
      site: String(source.site || source.label || "未知来源"),
      url: String(source.url || ""),
      data: String(source.data || ""),
      status: rawStatus === "success" ? "success" : "failed",
      detail: String(source.detail || ""),
      message: String(source.message || ""),
    };
  });
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function asString(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  return String(value);
}

export function asNumber(value: unknown, fallback = 0): number {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}
