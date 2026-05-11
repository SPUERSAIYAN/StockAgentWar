/* ============================================================
   Stage metadata — agent identity, icons, brands
   ============================================================ */

const STAGE_ORDER = [
  "information_analysis",
  "bull_debate",
  "bear_debate",
  "judge_decision",
  "risk_review",
];

const STAGE_META = {
  information_analysis: {
    agent: "信息分析",
    title: "市场数据汇总",
    color: "#3B82F6",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>`,
  },
  bull_debate: {
    agent: "多头",
    title: "看涨逻辑",
    color: "#22C55E",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
  },
  bear_debate: {
    agent: "空头",
    title: "看跌反驳",
    color: "#EF4444",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>`,
  },
  judge_decision: {
    agent: "裁判",
    title: "综合裁决",
    color: "#A78BFA",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>`,
  },
  risk_review: {
    agent: "风控",
    title: "风险复核",
    color: "#F59E0B",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,
  },
};

/* ============================================================
   App state
   ============================================================ */

const state = {
  mode: "openrouter",
  running: false,
  finalText: "",
  startedAt: 0,
  timer: null,
  stageContent: {},      // { nodeId: markdownString }
  sourceTrace: {},        // { nodeId: [{ site, data, status, ... }] }
  activeTab: null,        // currently selected result tab
};

/* ============================================================
   DOM refs  (all IDs match app.js deps + new result UI)
   ============================================================ */

const els = {
  symbols: document.querySelector("#symbols"),
  task: document.querySelector("#task"),
  runButton: document.querySelector("#runButton"),
  copyButton: document.querySelector("#copyButton"),
  pipeline: document.querySelector("#pipeline"),
  stageGrid: document.querySelector("#stageGrid"),
  finalOutput: document.querySelector("#finalOutput"),
  elapsed: document.querySelector("#elapsed"),
  statusText: document.querySelector("#statusText"),
  healthBadge: document.querySelector("#healthBadge"),
  segments: document.querySelectorAll(".segment"),
  resultTabs: document.querySelector("#resultTabs"),
  resultViewer: document.querySelector("#resultViewer"),
};

init();

/* ============================================================
   Init
   ============================================================ */

function init() {
  configureMarkdown();
  renderSkeleton();
  renderResultTabs();
  bindEvents();
  loadHealth();
}

function bindEvents() {
  els.runButton.addEventListener("click", runDecision);
  els.copyButton.addEventListener("click", copyFinal);
  els.stageGrid.addEventListener("click", toggleSourceInspector);
  els.segments.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.mode = btn.dataset.mode;
      els.segments.forEach((s) => s.classList.toggle("active", s === btn));
    });
  });
}

/* ============================================================
   Health check
   ============================================================ */

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    els.healthBadge.classList.toggle("ready", data.openrouter_key_ready);
    els.healthBadge.classList.toggle("warn", !data.openrouter_key_ready);
    els.healthBadge.querySelector("span:last-child").textContent =
      data.openrouter_key_ready ? "已就绪" : "缺少 Key";
  } catch {
    els.healthBadge.classList.add("warn");
    els.healthBadge.querySelector("span:last-child").textContent = "未连接";
  }
}

/* ============================================================
   Render skeleton (pipeline + stage cards)
   ============================================================ */

function renderSkeleton() {
  // Pipeline nodes
  els.pipeline.innerHTML = STAGE_ORDER
    .map((id) => {
      const m = STAGE_META[id];
      return `
        <div class="pipeline-node" data-node="${id}">
          <span class="node-icon">${m.icon}</span>
          <strong>${m.agent}</strong>
          <span>${m.title}</span>
        </div>`;
    })
    .join("");

  // Stage cards
  els.stageGrid.innerHTML = STAGE_ORDER
    .map((id) => {
      const m = STAGE_META[id];
      return `
        <article class="stage-card" data-node="${id}">
          <div class="stage-head">
            <span class="stage-icon">${m.icon}</span>
            <div class="stage-title">
              <h3>${m.agent}</h3>
              <span>${m.title}</span>
            </div>
            <div class="badge">等待</div>
          </div>
          <div class="stage-body markdown empty">等待输出。</div>
          ${id === "information_analysis" ? renderSourceInspectorShell() : ""}
        </article>`;
    })
    .join("");
}

function renderSourceInspectorShell() {
  return `
    <div class="source-inspector" data-source-node="information_analysis">
      <button class="source-toggle" type="button" aria-expanded="false">
        <span class="source-toggle-title">浏览来源与数据</span>
        <strong class="source-toggle-summary">等待接通</strong>
      </button>
      <div class="source-list" hidden>
        <div class="source-empty">运行后显示浏览的网站、获取的数据和接通状态。</div>
      </div>
    </div>`;
}

/* ============================================================
   Render result tabs (5 stage tabs in result panel)
   ============================================================ */

function renderResultTabs() {
  els.resultTabs.innerHTML = STAGE_ORDER
    .map((id) => {
      const m = STAGE_META[id];
      return `
        <button class="rtab" data-node="${id}" type="button">
          <span class="rtab-dot"></span>
          ${m.agent}
        </button>`;
    })
    .join("");

  els.resultTabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".rtab");
    if (!tab) return;
    const node = tab.dataset.node;
    switchTab(node);
  });
}

function switchTab(node) {
  // update active tab
  document.querySelectorAll(".rtab").forEach((t) => {
    t.classList.toggle("active", t.dataset.node === node);
  });
  state.activeTab = node;

  // show content in viewer
  const viewer = els.resultViewer;
  const content = state.stageContent[node];
  if (content) {
    viewer.innerHTML = `<div class="stage-body markdown">${renderMarkdown(content)}</div>`;
  } else {
    const m = STAGE_META[node];
    viewer.innerHTML = `
      <div class="viewer-placeholder">
        ${m.icon}
        <span>${m.agent} — 暂无输出</span>
      </div>`;
  }
}

/* ============================================================
   Reset before a new run
   ============================================================ */

function resetRun() {
  state.finalText = "";
  state.stageContent = {};
  state.sourceTrace = {};
  state.activeTab = null;
  state.startedAt = Date.now();

  els.finalOutput.className = "markdown empty";
  els.finalOutput.textContent = "等待模型输出。";
  els.statusText.textContent = "运行中";
  setElapsed(0);

  // reset pipeline
  document.querySelectorAll(".pipeline-node").forEach((n) => {
    n.className = "pipeline-node";
  });

  // reset stage cards
  document.querySelectorAll(".stage-card").forEach((c) => {
    c.className = "stage-card";
    c.querySelector(".badge").textContent = "等待";
    const body = c.querySelector(".stage-body");
    body.className = "stage-body markdown empty";
    body.textContent = "等待输出。";
  });
  resetSourceInspector();

  // reset result tabs
  document.querySelectorAll(".rtab").forEach((t) => {
    t.classList.remove("active", "has-content");
  });

  // reset viewer
  els.resultViewer.innerHTML = `
    <div class="viewer-placeholder">
      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
      <span>运行后显示各阶段报告</span>
    </div>`;

  clearInterval(state.timer);
  state.timer = setInterval(() => {
    setElapsed(Date.now() - state.startedAt);
  }, 200);
}

/* ============================================================
   Run decision (POST /api/decide/stream)
   ============================================================ */

async function runDecision() {
  if (state.running) return;
  state.running = true;
  els.runButton.disabled = true;
  resetRun();

  try {
    const response = await fetch("/api/decide/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: els.task.value.trim(),
        symbols: els.symbols.value.trim(),
        mode: state.mode,
        config_path: "config.yaml",
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }

    await readNdjson(response.body, handleEvent);
  } catch (error) {
    renderError(error.message || String(error));
  } finally {
    state.running = false;
    els.runButton.disabled = false;
    clearInterval(state.timer);
    setElapsed(Date.now() - state.startedAt);
  }
}

/* ============================================================
   NDJSON reader
   ============================================================ */

async function readNdjson(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }

  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

/* ============================================================
   Event handler
   ============================================================ */

function handleEvent(event) {
  if (event.type === "stage_status") {
    updateStageStatus(event.node, event.status);
    return;
  }

  if (event.type === "stage") {
    updateStageContent(event.node, event.content);
    if (event.node === "information_analysis") {
      updateSourceTrace(event.node, event.source_trace || []);
    }
    updateStageStatus(event.node, "done");
    // mark result tab as having content
    const tab = document.querySelector(`.rtab[data-node="${event.node}"]`);
    if (tab) tab.classList.add("has-content");
    els.statusText.textContent = `${STAGE_META[event.node]?.agent || "节点"}完成`;
    return;
  }

  if (event.type === "complete") {
    state.finalText = event.final_output || "";
    els.finalOutput.className = "markdown";
    els.finalOutput.innerHTML = renderMarkdown(state.finalText);
    els.statusText.textContent = "完成";
    // auto-select first tab that has content
    const firstWithContent = STAGE_ORDER.find(
      (id) => state.stageContent[id],
    );
    if (firstWithContent) switchTab(firstWithContent);
    return;
  }

  if (event.type === "error") {
    renderError(`${event.message}\n\n${event.hint || ""}`);
  }
}

/* ============================================================
   Update stage status (pipeline + card)
   ============================================================ */

function updateStageStatus(node, status) {
  const pipelineNode = document.querySelector(
    `.pipeline-node[data-node="${node}"]`,
  );
  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (!pipelineNode || !card) return;

  pipelineNode.classList.remove("running", "done", "error");
  card.classList.remove("running", "done", "error");
  pipelineNode.classList.add(status);
  card.classList.add(status);
  card.querySelector(".badge").textContent = statusText(status);
}

/* ============================================================
   Update stage content (card body + result viewer)
   ============================================================ */

function updateStageContent(node, content) {
  // card body
  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (card) {
    const body = card.querySelector(".stage-body");
    body.className = "stage-body markdown";
    body.innerHTML = renderMarkdown(content || "无输出。");
  }

  // store for result tabs
  state.stageContent[node] = content || "";

  // refresh viewer if this node is active
  if (state.activeTab === node) {
    switchTab(node);
  }
}

/* ============================================================
   Information source trace
   ============================================================ */

function toggleSourceInspector(event) {
  const button = event.target.closest(".source-toggle");
  if (!button) return;
  const inspector = button.closest(".source-inspector");
  const list = inspector?.querySelector(".source-list");
  if (!inspector || !list) return;

  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!expanded));
  list.hidden = expanded;
}

function resetSourceInspector() {
  const inspector = document.querySelector(
    '.source-inspector[data-source-node="information_analysis"]',
  );
  if (!inspector) return;
  inspector.className = "source-inspector";
  const button = inspector.querySelector(".source-toggle");
  const summary = inspector.querySelector(".source-toggle-summary");
  const list = inspector.querySelector(".source-list");
  if (button) button.setAttribute("aria-expanded", "false");
  if (summary) summary.textContent = "等待接通";
  if (list) {
    list.hidden = true;
    list.innerHTML = `<div class="source-empty">运行后显示浏览的网站、获取的数据和接通状态。</div>`;
  }
}

function updateSourceTrace(node, trace) {
  state.sourceTrace[node] = trace;
  const inspector = document.querySelector(`.source-inspector[data-source-node="${node}"]`);
  if (!inspector) return;

  const successCount = trace.filter((item) => item.status === "success").length;
  const failedCount = trace.filter((item) => item.status === "failed").length;
  const summary = inspector.querySelector(".source-toggle-summary");
  const button = inspector.querySelector(".source-toggle");
  const list = inspector.querySelector(".source-list");

  inspector.classList.toggle("has-data", trace.length > 0);
  inspector.classList.toggle("has-failure", failedCount > 0);

  if (summary) {
    summary.textContent =
      trace.length > 0 ? `${successCount} 成功 / ${failedCount} 失败` : "无外部接通";
  }

  if (!list) return;
  list.hidden = false;
  if (button) button.setAttribute("aria-expanded", "true");

  if (!trace.length) {
    list.innerHTML = `<div class="source-empty">本次没有返回外部网站或 provider 接通明细。</div>`;
    return;
  }

  list.innerHTML = trace.map(renderSourceRow).join("");
}

function renderSourceRow(item) {
  const statusClass = item.status === "success" ? "success" : "failed";
  const statusText = item.status === "success" ? "接通成功" : "接通失败";
  const link = isHttpUrl(item.url)
    ? `<a class="source-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.url)}</a>`
    : "";

  return `
    <div class="source-row ${statusClass}">
      <span class="source-status-dot" aria-hidden="true"></span>
      <div class="source-main">
        <div class="source-row-head">
          <strong>${escapeHtml(item.site || item.label || "未知数据源")}</strong>
          <span>${statusText}</span>
        </div>
        <div class="source-data">${escapeHtml(item.data || item.label || "数据摘要")}</div>
        ${link}
        <div class="source-detail">${escapeHtml(item.detail || item.message || "")}</div>
      </div>
    </div>`;
}

/* ============================================================
   Error rendering
   ============================================================ */

function renderError(message) {
  els.statusText.textContent = "失败";
  STAGE_ORDER.forEach((id) => {
    const card = document.querySelector(`.stage-card[data-node="${id}"]`);
    const pipelineNode = document.querySelector(
      `.pipeline-node[data-node="${id}"]`,
    );
    if (card?.classList.contains("running")) {
      card.classList.add("error");
      card.querySelector(".badge").textContent = "失败";
    }
    if (pipelineNode?.classList.contains("running")) {
      pipelineNode.classList.add("error");
    }
  });
  els.finalOutput.className = "markdown";
  els.finalOutput.innerHTML = renderMarkdown(`## 运行失败\n\n${message}`);
}

/* ============================================================
   Helpers
   ============================================================ */

function statusText(status) {
  const map = { running: "运行", done: "完成", error: "失败" };
  return map[status] || "等待";
}

function configureMarkdown() {
  const markedApi = window.marked;
  const setOptions =
    markedApi?.setOptions ||
    (typeof markedApi?.marked?.setOptions === "function"
      ? markedApi.marked.setOptions.bind(markedApi.marked)
      : null);

  if (typeof setOptions === "function") {
    setOptions({
      breaks: true,
      gfm: true,
    });
  }
}

function renderMarkdown(text) {
  const raw = String(text ?? "");
  const parser = getMarkdownParser();
  if (parser && window.DOMPurify) {
    return window.DOMPurify.sanitize(parser(raw));
  }
  return renderBasicMarkdown(raw);
}

function getMarkdownParser() {
  const markedApi = window.marked;
  if (typeof markedApi?.parse === "function") {
    return markedApi.parse.bind(markedApi);
  }
  if (typeof markedApi?.marked?.parse === "function") {
    return markedApi.marked.parse.bind(markedApi.marked);
  }
  if (typeof markedApi === "function") {
    return markedApi;
  }
  return null;
}

function renderBasicMarkdown(text) {
  const lines = text.split(/\r?\n/);
  const html = [];
  let paragraph = [];
  let listItems = [];
  let tableRows = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${paragraph.map(renderInlineMarkdown).join("<br>")}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };

  const flushTable = () => {
    if (tableRows.length < 2) {
      tableRows.forEach((row) => paragraph.push(row));
      tableRows = [];
      return;
    }
    const rows = tableRows.filter((row) => !/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(row));
    const renderedRows = rows.map((row, index) => {
      const cells = row
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => renderInlineMarkdown(cell.trim()));
      const tag = index === 0 ? "th" : "td";
      return `<tr>${cells.map((cell) => `<${tag}>${cell}</${tag}>`).join("")}</tr>`;
    });
    html.push(`<table>${renderedRows.join("")}</table>`);
    tableRows = [];
  };

  lines.forEach((line) => {
    if (line.includes("|") && /^\s*\|?.+\|.+\|?\s*$/.test(line)) {
      flushParagraph();
      flushList();
      tableRows.push(line);
      return;
    }

    flushTable();

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      return;
    }

    const list = line.match(/^\s*[-*]\s+(.+)$/);
    if (list) {
      flushParagraph();
      listItems.push(list[1]);
      return;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      return;
    }

    paragraph.push(line);
  });

  flushTable();
  flushParagraph();
  flushList();
  return html.join("");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function isHttpUrl(value) {
  return typeof value === "string" && /^https?:\/\//i.test(value);
}

function setElapsed(ms) {
  els.elapsed.textContent = `${(ms / 1000).toFixed(1)}s`;
}

async function copyFinal() {
  if (!state.finalText) return;
  await navigator.clipboard.writeText(state.finalText);
  els.statusText.textContent = "已复制";
}
