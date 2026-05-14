import { renderToStaticMarkup } from "react-dom/server";
import { Markdown } from "./components/Markdown";
import { STAGE_META } from "./store/stageMeta";
import type { AppState, StageState } from "./store/types";
import { statusText } from "./utils";

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(value: unknown): string {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function formatTimestamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function renderMarkdown(text: string, emptyText = "等待输出。"): string {
  return renderToStaticMarkup(<Markdown text={text} emptyText={emptyText} />);
}

function renderIcon(icon: unknown): string {
  return renderToStaticMarkup(<>{icon}</>);
}

function renderPipelineItem(id: string, stage: StageState): string {
  const meta = STAGE_META[id];
  if (!meta) return "";
  return `
    <article class="pipeline-node" style="--node-brand: ${escapeAttr(meta.color)}">
      <div class="node-topline">
        <span class="node-icon">${renderIcon(meta.icon)}</span>
        <span class="pipeline-status">${escapeHtml(statusText(stage.status))}</span>
      </div>
      <strong>${escapeHtml(meta.agent)}</strong>
      <span class="node-description">${escapeHtml(meta.title)}</span>
    </article>
  `;
}

function renderStageCard(id: string, stage: StageState): string {
  const meta = STAGE_META[id];
  if (!meta) return "";
  const content = stage.content || "";
  return `
    <article class="stage-card ${escapeAttr(stage.status)}" style="--card-brand: ${escapeAttr(meta.color)}">
      <div class="stage-head">
        <span class="stage-icon">${renderIcon(meta.icon)}</span>
        <div class="stage-title">
          <h2>${escapeHtml(meta.agent)}</h2>
          <span>${escapeHtml(meta.title)}</span>
        </div>
        <div class="badge">${escapeHtml(statusText(stage.status))}</div>
      </div>
      <div class="stage-content">${renderMarkdown(content, "等待输出。")}</div>
    </article>
  `;
}

function snapshotStyles(): string {
  return `
    :root {
      --color-primary: #0a0a0a;
      --color-on-primary: #ffffff;
      --color-charcoal: #222222;
      --color-steel: #5f5f5f;
      --color-stone: #8e8e93;
      --color-canvas: #ffffff;
      --color-surface: #f7f8fa;
      --color-surface-soft: #f2f3f5;
      --color-hairline: #e5e7eb;
      --color-hairline-soft: #eaecf0;
      --color-blue-deep: #1d4ed8;
      --color-blue-200: #bfdbfe;
      --color-success-bg: #e8ffea;
      --color-success-text: #1ba673;
      --color-error: #d45656;
      --radius-md: 8px;
      --radius-lg: 12px;
      --radius-xl: 16px;
      --radius-full: 9999px;
      --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.04);
      --font-sans: "DM Sans", "Inter", "Helvetica Neue", Arial, "Microsoft YaHei", sans-serif;
      --font-mono: "Cascadia Code", "Consolas", "SFMono-Regular", monospace;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--color-canvas);
      color: var(--color-charcoal);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }
    .page {
      width: min(1180px, calc(100% - 48px));
      margin: 32px auto;
      padding: 32px;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-xl);
      background: var(--color-canvas);
      box-shadow: var(--shadow-1);
    }
    .snapshot-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--color-hairline-soft);
    }
    .eyebrow {
      margin-bottom: 4px;
      color: var(--color-steel);
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      color: var(--color-primary);
      font-size: 28px;
      font-weight: 600;
      line-height: 1.2;
    }
    .export-time {
      color: var(--color-steel);
      font-size: 13px;
      white-space: nowrap;
    }
    .pipeline {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }
    .pipeline-node {
      padding: 16px;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-xl);
      background: var(--color-surface);
    }
    .node-topline,
    .stage-head,
    .source-row-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .node-icon,
    .stage-icon {
      display: inline-grid;
      width: 32px;
      height: 32px;
      place-items: center;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-full);
      background: var(--color-canvas);
      color: var(--node-brand, var(--card-brand, var(--color-primary)));
    }
    .node-icon svg,
    .stage-icon svg {
      width: 17px;
      height: 17px;
    }
    .pipeline-status,
    .badge {
      display: inline-flex;
      min-height: 24px;
      align-items: center;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      background: var(--color-blue-200);
      color: var(--color-blue-deep);
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
    }
    .pipeline-node strong {
      display: block;
      margin-top: 12px;
      color: var(--color-primary);
      font-weight: 600;
    }
    .node-description {
      display: block;
      margin-top: 4px;
      color: var(--color-steel);
      font-size: 13px;
    }
    .stage-grid {
      display: grid;
      gap: 20px;
    }
    .stage-card {
      overflow: hidden;
      border: 2px solid color-mix(in srgb, var(--card-brand, var(--color-primary)) 70%, var(--color-hairline));
      border-radius: var(--radius-xl);
      background: var(--color-canvas);
    }
    .stage-head {
      padding: 20px 24px;
      border-bottom: 1px solid var(--color-hairline-soft);
    }
    .stage-title {
      flex: 1;
      min-width: 0;
    }
    .stage-title h2 {
      margin: 0;
      color: var(--color-primary);
      font-size: 18px;
      font-weight: 600;
      line-height: 1.35;
    }
    .stage-title span {
      display: block;
      color: var(--color-steel);
      font-size: 13px;
    }
    .stage-content {
      padding: 24px;
    }
    .markdown {
      color: var(--color-charcoal);
      font-size: 16px;
      line-height: 1.65;
    }
    .markdown.empty,
    .markdown:empty {
      color: var(--color-stone);
    }
    .markdown > * + * {
      margin-top: 12px;
    }
    .markdown h1,
    .markdown h2,
    .markdown h3,
    .markdown h4 {
      color: var(--color-primary);
      font-weight: 600;
      line-height: 1.3;
    }
    .markdown h1 { font-size: 24px; }
    .markdown h2 { font-size: 20px; }
    .markdown h3 { font-size: 17px; }
    .markdown ul,
    .markdown ol {
      padding-left: 20px;
    }
    .markdown a {
      color: var(--color-blue-deep);
      text-decoration: underline;
      text-decoration-color: rgba(29, 78, 216, 0.28);
    }
    .markdown code {
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--color-surface-soft);
      color: var(--color-blue-deep);
      font-family: var(--font-mono);
      font-size: 0.92em;
    }
    .markdown pre {
      overflow: auto;
      padding: 16px;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-md);
      background: var(--color-surface);
    }
    .markdown table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      overflow: hidden;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-md);
      font-size: 13px;
    }
    .markdown th,
    .markdown td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--color-hairline-soft);
      text-align: left;
      vertical-align: top;
    }
    .markdown th {
      background: var(--color-surface);
      color: var(--color-steel);
      font-weight: 600;
    }
    .source-section {
      margin: 0 24px 24px;
      padding: 16px;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-lg);
      background: var(--color-surface);
    }
    .source-section-head {
      margin-bottom: 12px;
      color: var(--color-primary);
      font-weight: 600;
    }
    .source-list {
      display: grid;
      gap: 12px;
    }
    .source-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--color-hairline);
      border-radius: var(--radius-lg);
      background: var(--color-canvas);
    }
    .source-status-dot {
      width: 7px;
      height: 7px;
      margin-top: 7px;
      border-radius: var(--radius-full);
      background: var(--color-error);
    }
    .source-row.success .source-status-dot {
      background: var(--color-success-text);
    }
    .source-row-head strong {
      color: var(--color-primary);
      font-weight: 600;
    }
    .source-row-head span,
    .source-data,
    .source-detail {
      color: var(--color-steel);
      font-size: 13px;
    }
    .source-row.success .source-row-head span {
      color: var(--color-success-text);
    }
    .source-row.failed .source-row-head span {
      color: var(--color-error);
    }
    .source-data,
    .source-detail,
    .source-link {
      margin-top: 8px;
      overflow-wrap: anywhere;
    }
    .source-link {
      display: block;
      color: var(--color-blue-deep);
      font-size: 13px;
    }
    @media (max-width: 720px) {
      .page {
        width: min(100% - 24px, 1180px);
        margin: 12px auto;
        padding: 16px;
      }
      .snapshot-header {
        display: block;
      }
      .export-time {
        display: block;
        margin-top: 8px;
      }
    }
  `;
}

function buildSnapshotHtml(state: AppState, exportedAt: Date): string {
  const stageOrder = state.stageOrder.length ? state.stageOrder : Object.keys(state.stages);
  const pipeline = stageOrder.map((id) => renderPipelineItem(id, state.stages[id])).join("");
  const stages = stageOrder.map((id) => renderStageCard(id, state.stages[id])).join("");
  const exportedText = exportedAt.toLocaleString("zh-CN", { hour12: false });

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>股票决策流程</title>
    <style>${snapshotStyles()}</style>
  </head>
  <body>
    <main class="page">
      <header class="snapshot-header">
        <div>
          <div class="eyebrow">Multi-Agent Investment</div>
          <h1>股票决策流程</h1>
        </div>
        <div class="export-time">导出时间：${escapeHtml(exportedText)}</div>
      </header>
      <section class="pipeline" aria-label="流程概览">${pipeline}</section>
      <section class="stage-grid" aria-label="阶段报告">${stages}</section>
    </main>
  </body>
</html>`;
}

export function hasDecisionFlowSnapshot(state: AppState): boolean {
  return (
    state.running ||
    state.stageOrder.some((id) => {
      const stage = state.stages[id];
      return Boolean(stage && (stage.status !== "waiting" || stage.content.trim() || stage.summary.trim() || stage.sources.length));
    })
  );
}

export function downloadDecisionFlowSnapshot(state: AppState): void {
  const exportedAt = new Date();
  const html = buildSnapshotHtml(state, exportedAt);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `股票决策流程-${formatTimestamp(exportedAt)}.html`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
