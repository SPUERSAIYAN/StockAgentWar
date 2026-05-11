const STAGE_ORDER = [
  "information_analysis",
  "bull_debate",
  "bear_debate",
  "judge_decision",
  "risk_review",
];

const STAGE_META = {
  information_analysis: { agent: "信息分析", title: "市场信息汇总" },
  bull_debate: { agent: "多头", title: "上涨逻辑" },
  bear_debate: { agent: "空头", title: "风险反驳" },
  judge_decision: { agent: "裁判", title: "综合裁决" },
  risk_review: { agent: "风控", title: "风险复核" },
};

const state = {
  mode: "openrouter",
  running: false,
  finalText: "",
  startedAt: 0,
  timer: null,
};

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
};

init();

function init() {
  renderSkeleton();
  bindEvents();
  loadHealth();
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function bindEvents() {
  els.runButton.addEventListener("click", runDecision);
  els.copyButton.addEventListener("click", copyFinal);
  els.segments.forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      els.segments.forEach((item) => item.classList.toggle("active", item === button));
    });
  });
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    els.healthBadge.classList.toggle("ready", data.openrouter_key_ready);
    els.healthBadge.classList.toggle("warn", !data.openrouter_key_ready);
    els.healthBadge.querySelector("span:last-child").textContent = data.openrouter_key_ready
      ? "OpenRouter 已就绪"
      : "缺少 OpenRouter Key";
  } catch {
    els.healthBadge.classList.add("warn");
    els.healthBadge.querySelector("span:last-child").textContent = "服务未连接";
  }
}

function renderSkeleton() {
  els.pipeline.innerHTML = STAGE_ORDER.map((id) => {
    const meta = STAGE_META[id];
    return `
      <div class="pipeline-node" data-node="${id}">
        <strong>${meta.agent}</strong>
        <span>${meta.title}</span>
      </div>
    `;
  }).join("");

  els.stageGrid.innerHTML = STAGE_ORDER.map((id) => {
    const meta = STAGE_META[id];
    return `
      <article class="stage-card" data-node="${id}">
        <div class="stage-head">
          <div class="stage-title">
            <h3>${meta.agent}</h3>
            <span>${meta.title}</span>
          </div>
          <div class="badge">等待</div>
        </div>
        <div class="stage-body markdown empty">等待输出。</div>
      </article>
    `;
  }).join("");
}

function resetRun() {
  state.finalText = "";
  state.startedAt = Date.now();
  els.finalOutput.className = "markdown empty";
  els.finalOutput.textContent = "等待模型输出。";
  els.statusText.textContent = "运行中";
  setElapsed(0);

  document.querySelectorAll(".pipeline-node").forEach((node) => {
    node.className = "pipeline-node";
  });
  document.querySelectorAll(".stage-card").forEach((card) => {
    card.className = "stage-card";
    card.querySelector(".badge").textContent = "等待";
    const body = card.querySelector(".stage-body");
    body.className = "stage-body markdown empty";
    body.textContent = "等待输出。";
  });

  clearInterval(state.timer);
  state.timer = setInterval(() => {
    setElapsed(Date.now() - state.startedAt);
  }, 200);
}

async function runDecision() {
  if (state.running) {
    return;
  }
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
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }
}

async function readNdjson(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) {
        onEvent(JSON.parse(line));
      }
    }
  }

  if (buffer.trim()) {
    onEvent(JSON.parse(buffer));
  }
}

function handleEvent(event) {
  if (event.type === "stage_status") {
    updateStageStatus(event.node, event.status);
    return;
  }

  if (event.type === "stage") {
    updateStageContent(event.node, event.content);
    updateStageStatus(event.node, "done");
    els.statusText.textContent = `${STAGE_META[event.node]?.agent || "节点"}完成`;
    return;
  }

  if (event.type === "complete") {
    state.finalText = event.final_output || "";
    els.finalOutput.className = "markdown";
    els.finalOutput.innerHTML = renderMarkdown(state.finalText);
    els.statusText.textContent = "完成";
    return;
  }

  if (event.type === "error") {
    renderError(`${event.message}\n\n${event.hint || ""}`);
  }
}

function updateStageStatus(node, status) {
  const pipelineNode = document.querySelector(`.pipeline-node[data-node="${node}"]`);
  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (!pipelineNode || !card) {
    return;
  }
  pipelineNode.classList.remove("running", "done", "error");
  card.classList.remove("running", "done", "error");
  pipelineNode.classList.add(status);
  card.classList.add(status);
  card.querySelector(".badge").textContent = statusText(status);
}

function updateStageContent(node, content) {
  const card = document.querySelector(`.stage-card[data-node="${node}"]`);
  if (!card) {
    return;
  }
  const body = card.querySelector(".stage-body");
  body.className = "stage-body markdown";
  body.innerHTML = renderMarkdown(content || "无输出。");
}

function renderError(message) {
  els.statusText.textContent = "失败";
  STAGE_ORDER.forEach((id) => {
    const card = document.querySelector(`.stage-card[data-node="${id}"]`);
    const pipelineNode = document.querySelector(`.pipeline-node[data-node="${id}"]`);
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

function statusText(status) {
  if (status === "running") {
    return "运行";
  }
  if (status === "done") {
    return "完成";
  }
  if (status === "error") {
    return "失败";
  }
  return "等待";
}

function renderMarkdown(text) {
  if (window.marked && window.DOMPurify) {
    return window.DOMPurify.sanitize(window.marked.parse(text || ""));
  }
  return escapeHtml(text || "").replace(/\n/g, "<br>");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setElapsed(ms) {
  els.elapsed.textContent = `${(ms / 1000).toFixed(1)}s`;
}

async function copyFinal() {
  if (!state.finalText) {
    return;
  }
  await navigator.clipboard.writeText(state.finalText);
  els.statusText.textContent = "已复制";
}
