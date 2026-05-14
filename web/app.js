/* ============================================================
   Stage metadata
   ============================================================ */

const ICONS = {
  radar: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>`,
  bank: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 10 9-7 9 7"/><path d="M5 10v10"/><path d="M19 10v10"/><path d="M9 10v10"/><path d="M15 10v10"/><path d="M3 20h18"/></svg>`,
  up: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
  down: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>`,
  scale: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>`,
  shield: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,
  briefcase: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1"/><rect width="20" height="14" x="2" y="6" rx="2"/><path d="M2 12h20"/><path d="M12 12v2"/></svg>`,
  clipboard: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M8 12h8"/><path d="M8 16h5"/></svg>`,
};

const STAGE_META = {
  question_planning: { agent: "问题理解", title: "数据源规划", color: "#38BDF8", icon: ICONS.radar },
  information_analysis: { agent: "信息分析", title: "市场数据汇总", color: "#3B82F6", icon: ICONS.radar },
  bull_debate: { agent: "多头", title: "看多逻辑", color: "#22C55E", icon: ICONS.up },
  bear_debate: { agent: "空头", title: "风险反驳", color: "#EF4444", icon: ICONS.down },
  judge_decision: { agent: "裁判", title: "综合裁决", color: "#A78BFA", icon: ICONS.scale },
  risk_review: { agent: "风控", title: "风险复核", color: "#F59E0B", icon: ICONS.shield },
  portfolio_manager: { agent: "总经理", title: "最终建议", color: "#EC4899", icon: ICONS.briefcase },
  save_trade_plan: { agent: "交易计划", title: "计划落盘", color: "#14B8A6", icon: ICONS.clipboard },
};

const DOCUMENTED_STAGE_ORDER = [
  "question_planning",
  "information_analysis",
  "bull_debate",
  "bear_debate",
  "judge_decision",
  "risk_review",
  "portfolio_manager",
  "save_trade_plan",
];
const COMMON_STAGE_ORDER = [
  "question_planning",
  "information_analysis",
];
const A_SHARE_STAGE_ORDER = [...DOCUMENTED_STAGE_ORDER];

/* ============================================================
   App state
   ============================================================ */

const state = {
  runMode: "common",
  modelMode: "openrouter",
  riskTolerance: "moderate",
  running: false,
  paused: false,
  abortController: null,
  finalText: "",
  startedAt: 0,
  timer: null,
  stageOrder: [...COMMON_STAGE_ORDER],
  stageContent: {},
  stageSummary: {},
  sourceTrace: {},
  activeStageTab: null,
  activeStageView: "summary",
  completeState: {},
};

/* ============================================================
   DOM refs
   ============================================================ */

const els = {
  symbols: document.querySelector("#symbols"),
  sectors: document.querySelector("#sectors"),
  capital: document.querySelector("#capital"),
  task: document.querySelector("#task"),
  runButton: document.querySelector("#runButton"),
  pauseButton: document.querySelector("#pauseButton"),
  copyButton: document.querySelector("#copyButton"),
  pipeline: document.querySelector("#pipeline"),
  stageGrid: document.querySelector("#stageGrid"),
  finalOutput: document.querySelector("#finalOutput"),
  elapsed: document.querySelector("#elapsed"),
  statusText: document.querySelector("#statusText"),
  healthBadge: document.querySelector("#healthBadge"),
  runModeSegments: document.querySelectorAll("[data-run-mode]"),
  modelModeSegments: document.querySelectorAll("[data-model-mode]"),
  riskSegments: document.querySelectorAll("[data-risk]"),
  resultTabs: document.querySelector("#resultTabs"),
  viewTabs: document.querySelector("#viewTabs"),
  resultViewer: document.querySelector("#resultViewer"),
  tradePlanPanel: document.querySelector("#tradePlanPanel"),
};

init();

/* ============================================================
   Init
   ============================================================ */

function init() {
  configureMarkdown();
  renderStageShell();
  renderResultTabs();
  updateVisibleFields();
  bindEvents();
  loadHealth();
}

function bindEvents() {
  els.runButton.addEventListener("click", runDecision);
  els.pauseButton.addEventListener("click", pauseRun);
  els.copyButton.addEventListener("click", copyFinal);
  els.stageGrid.addEventListener("click", toggleSourceInspector);

  els.runModeSegments.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.runMode = btn.dataset.runMode;
      setActiveSegment(els.runModeSegments, btn);
      updateVisibleFields();
      applyModeDefaults();
      renderStageShell();
      renderResultTabs();
      resetViewer();
    });
  });

  els.modelModeSegments.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.modelMode = btn.dataset.modelMode;
      setActiveSegment(els.modelModeSegments, btn);
    });
  });

  els.riskSegments.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.riskTolerance = btn.dataset.risk;
      setActiveSegment(els.riskSegments, btn);
    });
  });

  els.viewTabs.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-view]");
    if (!tab) return;
    state.activeStageView = tab.dataset.view;
    setActiveSegment(els.viewTabs.querySelectorAll("[data-view]"), tab);
    renderResultViewer();
  });
}

function setActiveSegment(group, activeButton) {
  group.forEach((button) => button.classList.toggle("active", button === activeButton));
}

/* ============================================================
   Health check
   ============================================================ */

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    els.healthBadge.classList.toggle("ready", Boolean(data.ok));
    els.healthBadge.classList.toggle("warn", !data.ok);
    els.healthBadge.querySelector("span:last-child").textContent =
      data.ok ? "服务已连接" : "服务异常";
  } catch {
    els.healthBadge.classList.add("warn");
    els.healthBadge.querySelector("span:last-child").textContent = "未连接";
  }
}

/* ============================================================
   Mode-aware inputs
   ============================================================ */

function updateVisibleFields() {
  const isAShare = isAShareMode();
  setFieldVisible("modelMode", !isAShare);
  setFieldVisible("riskTolerance", isAShare);
  setFieldVisible("capital", isAShare);
  setFieldVisible("sectors", state.runMode === "a_share_sector");
  setFieldVisible("symbols", state.runMode === "a_share_deep");
}

function setFieldVisible(name, visible) {
  const field = document.querySelector(`[data-field="${name}"]`);
  if (field) field.classList.toggle("hidden", !visible);
}

function applyModeDefaults() {
  if (state.runMode === "common") {
    els.symbols.value = "";
    els.task.value = "分析用户问题相关的宏观、市场和数据源信息，只输出信息分析报告，不生成股票交易决策。";
    return;
  }
  if (state.runMode === "a_share_daily") {
    els.task.value = "扫描全市场，找出未来1个月最具投资价值的 A 股标的，并生成价格触发式交易计划。";
    return;
  }
  if (state.runMode === "a_share_sector") {
    els.task.value = "分析指定 A 股板块并给出买入建议和交易触发条件。";
    return;
  }
  if (state.runMode === "a_share_deep") {
    if (!els.symbols.value.trim() || !isLikelyAShareSymbolList(els.symbols.value)) {
      els.symbols.value = "600519,000858,300750";
    }
    els.task.value = "深度分析指定 A 股并给出交易策略。";
  }
}

function isAShareMode() {
  return state.runMode !== "common";
}

function isLikelyAShareSymbolList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .every((item) => /^(SH|SZ)?\d{6}(\.(SH|SZ))?$/i.test(item));
}

/* ============================================================
   Stage shell
   ============================================================ */

function currentStageOrder() {
  return isAShareMode() ? [...A_SHARE_STAGE_ORDER] : [...COMMON_STAGE_ORDER];
}

function renderStageShell(stagesFromServer) {
  state.stageOrder = stagesFromServer?.length
    ? stagesFromServer.map((item) => item.id).filter((id) => STAGE_META[id])
    : currentStageOrder();

  els.pipeline.innerHTML = state.stageOrder
    .map((id) => {
      const meta = STAGE_META[id];
      return `
        <div class="pipeline-node" data-node="${id}" style="--node-brand:${meta.color}">
          <span class="node-icon">${meta.icon}</span>
          <strong>${meta.agent}</strong>
          <span>${meta.title}</span>
        </div>`;
    })
    .join("");

  els.stageGrid.innerHTML = state.stageOrder
    .map((id) => {
      const meta = STAGE_META[id];
      return `
        <article class="stage-card" data-node="${id}" style="--card-brand:${meta.color}">
          <div class="stage-head">
            <span class="stage-icon">${meta.icon}</span>
            <div class="stage-title">
              <h3>${meta.agent}</h3>
              <span>${meta.title}</span>
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

function renderResultTabs() {
  els.resultTabs.innerHTML = state.stageOrder
    .map((id) => {
      const meta = STAGE_META[id];
      return `
        <button class="rtab" data-node="${id}" style="--tab-brand:${meta.color}" type="button">
          <span class="rtab-dot"></span>
          ${meta.agent}
        </button>`;
    })
    .join("");

  els.resultTabs.querySelectorAll(".rtab").forEach((tab) => {
    tab.addEventListener("click", () => switchStageTab(tab.dataset.node));
  });
}

function switchStageTab(node) {
  state.activeStageTab = node;
  document.querySelectorAll(".rtab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.node === node);
  });
  renderResultViewer();
}

/* ============================================================
   Run lifecycle
   ============================================================ */

function resetRun() {
  state.paused = false;
  state.abortController = null;
  state.finalText = "";
  state.stageContent = {};
  state.stageSummary = {};
  state.sourceTrace = {};
  state.activeStageTab = null;
  state.activeStageView = "summary";
  state.completeState = {};
  state.startedAt = Date.now();

  renderStageShell();
  renderResultTabs();
  setActiveSegment(els.viewTabs.querySelectorAll("[data-view]"), els.viewTabs.querySelector('[data-view="summary"]'));
  resetViewer();
  resetTradePlanPanel();

  els.finalOutput.className = "markdown empty";
  els.finalOutput.textContent = "等待模型输出。";
  els.statusText.textContent = "运行中";
  setElapsed(0);

  clearInterval(state.timer);
  state.timer = setInterval(() => setElapsed(Date.now() - state.startedAt), 200);
}

function resetViewer() {
  els.resultViewer.innerHTML = `
    <div class="viewer-placeholder">
      <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
      <span>运行后显示各阶段报告</span>
    </div>`;
}

function resetTradePlanPanel() {
  els.tradePlanPanel.className = "trade-plan-panel hidden";
  els.tradePlanPanel.innerHTML = "";
}

function setRunningControls(isRunning) {
  els.runButton.disabled = isRunning;
  els.pauseButton.disabled = !isRunning;
  els.pauseButton.classList.toggle("active", isRunning);
  els.pauseButton.setAttribute("aria-pressed", String(isRunning));
}

function pauseRun() {
  if (!state.running || !state.abortController) return;
  state.paused = true;
  els.pauseButton.disabled = true;
  els.statusText.textContent = "暂停中";
  state.abortController.abort();
}

async function runDecision() {
  if (state.running) return;
  state.running = true;
  resetRun();
  state.abortController = new AbortController();
  setRunningControls(true);

  try {
    const response = await fetch("/api/decide/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildRequestPayload()),
      signal: state.abortController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }

    await readNdjson(response.body, handleEvent);
  } catch (error) {
    if (state.paused || error.name === "AbortError") {
      renderPaused();
    } else {
      renderError(error.message || String(error));
    }
  } finally {
    state.running = false;
    state.abortController = null;
    setRunningControls(false);
    clearInterval(state.timer);
    setElapsed(Date.now() - state.startedAt);
  }
}

function buildRequestPayload() {
  const mode = state.runMode === "common" ? state.modelMode : state.runMode;
  return {
    task: els.task.value.trim(),
    symbols: state.runMode === "a_share_deep" ? els.symbols.value.trim() : "",
    sectors: state.runMode === "a_share_sector" ? els.sectors.value.trim() : "",
    mode,
    risk_tolerance: state.riskTolerance,
    capital: Number(String(els.capital.value).replace(/,/g, "")) || 1000000,
    config_path: "config.yaml",
  };
}

/* ============================================================
   NDJSON
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

function handleEvent(event) {
  if (event.type === "start") {
    if (Array.isArray(event.stages)) {
      renderStageShell(event.stages);
      renderResultTabs();
    }
    return;
  }

  if (event.type === "stage_status") {
    updateStageStatus(event.node, event.status);
    return;
  }

  if (event.type === "stage") {
    updateStageContent(event.node, event.content, event.summary);
    if (event.node === "information_analysis") {
      updateSourceTrace(event.node, event.source_trace || []);
    }
    updateStageStatus(event.node, "done");
    const tab = document.querySelector(`.rtab[data-node="${event.node}"]`);
    if (tab) tab.classList.add("has-content");
    if (!state.activeStageTab) switchStageTab(event.node);
    els.statusText.textContent = `${STAGE_META[event.node]?.agent || "节点"}完成`;
    return;
  }

  if (event.type === "complete") {
    state.finalText = event.final_output || "";
    state.completeState = event.state || {};
    els.finalOutput.className = "markdown";
    els.finalOutput.innerHTML = renderMarkdown(state.finalText);
    els.statusText.textContent = "完成";
    els.pauseButton.disabled = true;
    els.pauseButton.classList.remove("active");
    els.pauseButton.setAttribute("aria-pressed", "false");
    renderTradePlanPanel();
    if (!state.activeStageTab) {
      const firstWithContent = state.stageOrder.find((id) => state.stageContent[id]);
      if (firstWithContent) switchStageTab(firstWithContent);
    }
    return;
  }

  if (event.type === "error") {
    renderError(`${event.message}\n\n${event.hint || ""}`);
  }
}

/* ============================================================
   Stage rendering
   ============================================================ */

function updateStageStatus(node, status) {
  const pipelineNode = document.querySelector(`.pipeline-node[data-node="${node}"]`);
  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (!pipelineNode || !card) return;

  pipelineNode.classList.remove("running", "done", "error", "paused");
  card.classList.remove("running", "done", "error", "paused");
  pipelineNode.classList.add(status);
  card.classList.add(status);
  card.querySelector(".badge").textContent = statusText(status);
}

function updateStageContent(node, content, summary) {
  const renderedContent = content || "无输出。";
  state.stageContent[node] = renderedContent;
  state.stageSummary[node] = summary || summarizeContent(renderedContent);

  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (card) {
    const body = card.querySelector(".stage-body");
    body.className = "stage-body markdown";
    body.innerHTML = renderMarkdown(renderedContent);
  }

  if (state.activeStageTab === node) renderResultViewer();
}

function renderResultViewer() {
  const node = state.activeStageTab;
  if (!node) {
    resetViewer();
    return;
  }
  if (state.activeStageView === "summary") {
    const summary = state.stageSummary[node] || summarizeContent(state.stageContent[node] || "");
    els.resultViewer.innerHTML = `<div class="summary-view markdown">${renderMarkdown(summary || "暂无摘要。")}</div>`;
    return;
  }
  if (state.activeStageView === "raw") {
    const content = state.stageContent[node];
    els.resultViewer.innerHTML = content
      ? `<div class="stage-body markdown">${renderMarkdown(content)}</div>`
      : renderEmptyViewer(node, "暂无原文输出");
    return;
  }
  if (state.activeStageView === "sources") {
    const trace = state.sourceTrace[node] || [];
    els.resultViewer.innerHTML = trace.length
      ? `<div class="source-view">${trace.map(renderSourceRow).join("")}</div>`
      : renderEmptyViewer(node, node === "information_analysis" ? "本次没有返回数据源明细" : "此阶段无独立数据源");
  }
}

function renderEmptyViewer(node, text) {
  const meta = STAGE_META[node] || STAGE_META.information_analysis;
  return `
    <div class="viewer-placeholder">
      ${meta.icon}
      <span>${escapeHtml(meta.agent)} — ${escapeHtml(text)}</span>
    </div>`;
}

function summarizeContent(content) {
  const text = String(content || "")
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/^#+\s*/, "").replace(/^[-*]\s*/, ""))
    .filter((line) => line && !line.startsWith("|") && !line.startsWith("```"))
    .join(" ");
  return text.length > 220 ? `${text.slice(0, 220).trim()}...` : text;
}

/* ============================================================
   Source trace
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
    summary.textContent = trace.length ? `${successCount} 成功 / ${failedCount} 失败` : "无外部接通";
  }
  if (!list) return;
  list.hidden = false;
  if (button) button.setAttribute("aria-expanded", "true");
  list.innerHTML = trace.length
    ? trace.map(renderSourceRow).join("")
    : `<div class="source-empty">本次没有返回外部网站或 provider 接通明细。</div>`;
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
   Trade plan panel
   ============================================================ */

function renderTradePlanPanel() {
  const content = state.stageContent.save_trade_plan || "";
  if (!content) {
    resetTradePlanPanel();
    return;
  }
  els.tradePlanPanel.className = "trade-plan-panel compact";
  els.tradePlanPanel.innerHTML = `
    <div class="trade-plan-head">
      <strong>交易计划</strong>
      <span>报告</span>
    </div>
    <div class="markdown">${renderMarkdown(content)}</div>`;
}

/* ============================================================
   Error rendering
   ============================================================ */

function renderPaused() {
  els.statusText.textContent = "已暂停";
  state.stageOrder.forEach((id) => {
    const card = document.querySelector(`.stage-card[data-node="${id}"]`);
    const pipelineNode = document.querySelector(`.pipeline-node[data-node="${id}"]`);
    if (card?.classList.contains("running")) {
      card.classList.remove("running", "error");
      card.classList.add("paused");
      card.querySelector(".badge").textContent = "已暂停";
    }
    if (pipelineNode?.classList.contains("running")) {
      pipelineNode.classList.remove("running", "error");
      pipelineNode.classList.add("paused");
    }
  });

  const completedCount = Object.keys(state.stageContent).length;
  els.finalOutput.className = "markdown";
  els.finalOutput.innerHTML = renderMarkdown(`## 运行已暂停\n\n已保留 ${completedCount} 个阶段输出。可以调整参数后重新运行。`);
}

function renderError(message) {
  els.statusText.textContent = "失败";
  state.stageOrder.forEach((id) => {
    const card = document.querySelector(`.stage-card[data-node="${id}"]`);
    const pipelineNode = document.querySelector(`.pipeline-node[data-node="${id}"]`);
    if (card?.classList.contains("running")) {
      card.classList.remove("running");
      card.classList.add("error");
      card.querySelector(".badge").textContent = "失败";
    }
    if (pipelineNode?.classList.contains("running")) {
      pipelineNode.classList.remove("running");
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
  const map = { running: "运行", done: "完成", error: "失败", paused: "已暂停" };
  return map[status] || "等待";
}

function configureMarkdown() {
  const markedApi = window.marked;
  const setOptions =
    markedApi?.setOptions ||
    (typeof markedApi?.marked?.setOptions === "function"
      ? markedApi.marked.setOptions.bind(markedApi.marked)
      : null);
  if (typeof setOptions === "function") setOptions({ breaks: true, gfm: true });
}

function renderMarkdown(text) {
  const raw = String(text ?? "");
  const parser = getMarkdownParser();
  if (parser && window.DOMPurify) return window.DOMPurify.sanitize(parser(raw));
  return renderBasicMarkdown(raw);
}

function getMarkdownParser() {
  const markedApi = window.marked;
  if (typeof markedApi?.parse === "function") return markedApi.parse.bind(markedApi);
  if (typeof markedApi?.marked?.parse === "function") return markedApi.marked.parse.bind(markedApi.marked);
  if (typeof markedApi === "function") return markedApi;
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
    html.push(`<table>${rows.map(renderTableRow).join("")}</table>`);
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

function renderTableRow(row, index) {
  const cells = row
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => renderInlineMarkdown(cell.trim()));
  const tag = index === 0 ? "th" : "td";
  return `<tr>${cells.map((cell) => `<${tag}>${cell}</${tag}>`).join("")}</tr>`;
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
