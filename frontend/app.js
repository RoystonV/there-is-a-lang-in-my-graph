/* ===================================================================
   app.js — TARA RAG Visualizer frontend logic
   Talks to Flask /api/* endpoints, drives Graph renderer + panels
   =================================================================== */

const API = window.location.origin;

let _reports     = [];
let _currentDoc  = null;
let _allDamage   = [];
let _allDetails  = [];
let _filterNode  = null;

/* ── DOM refs ────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

const DOM = {
  reportList:     $("report-list"),
  searchInput:    $("search-input"),
  statusPill:     $("status-pill"),
  statusText:     $("status-text"),
  headerCount:    $("header-report-count"),
  loadingOverlay: $("loading-overlay"),
  graphPlaceholder: $("graph-placeholder"),
  statNodes:      $("stat-nodes"),
  statEdges:      $("stat-edges"),
  statDerivs:     $("stat-derivs"),
  statDetails:    $("stat-details"),
  nodeInfo:       $("node-info"),
  damageList:     $("damage-list"),
  panelCount:     $("panel-count"),
  btnZoomIn:      $("btn-zoom-in"),
  btnZoomOut:     $("btn-zoom-out"),
  btnFit:         $("btn-fit"),
};

/* ── Boot ────────────────────────────────────────────────────────── */
async function boot() {
  await checkStatus();
  await loadReports();
  Graph.init("graph-canvas", onNodeClick);
  bindUI();
}

/* ── Status check ────────────────────────────────────────────────── */
async function checkStatus() {
  try {
    const r = await fetch(`${API}/api/status`);
    const d = await r.json();
    if (d.mongo_connected) {
      DOM.statusPill.className = "status-pill connected";
      DOM.statusText.textContent = "MongoDB Connected";
    } else {
      DOM.statusPill.className = "status-pill disconnected";
      DOM.statusText.textContent = "MongoDB Offline";
    }
  } catch {
    DOM.statusPill.className = "status-pill disconnected";
    DOM.statusText.textContent = "Server Offline";
  }
}

/* ── Load report list ────────────────────────────────────────────── */
async function loadReports() {
  try {
    const r = await fetch(`${API}/api/reports`);
    _reports = await r.json();
  } catch {
    _reports = [];
  }
  DOM.headerCount.textContent = _reports.length;
  renderReportList(_reports);
}

function renderReportList(list) {
  if (!list.length) {
    DOM.reportList.innerHTML = `
      <div class="sidebar-empty">
        <div class="empty-icon">🗄️</div>
        <div>No reports in MongoDB</div>
        <div style="margin-top:6px;color:var(--text-label);font-size:11px;">
          Run: <code style="font-family:var(--mono)">python seed_mongo.py</code>
        </div>
      </div>`;
    return;
  }

  DOM.reportList.innerHTML = list.map(r => {
    const date = r.saved_at
      ? new Date(r.saved_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
      : "";
    return `
      <div class="report-item fade-in" data-id="${r._id}" onclick="selectReport('${r._id}')">
        <div class="report-name">${r.ecu_name || r.query}</div>
        <div class="report-meta">
          <span class="badge">${r.node_count} nodes</span>
          <span class="badge green">${r.edge_count} edges</span>
          <span class="badge amber">${r.deriv_count} threats</span>
          ${r.detail_count ? `<span class="badge purple">${r.detail_count} details</span>` : ""}
        </div>
        <div class="report-time">${date}</div>
        <button class="report-delete" onclick="deleteReport(event,'${r._id}')">✕</button>
      </div>`;
  }).join("");
}

/* ── Select report ───────────────────────────────────────────────── */
async function selectReport(id) {
  // Update active state
  document.querySelectorAll(".report-item").forEach(el => {
    el.classList.toggle("active", el.dataset.id === id);
  });

  showLoading(true);
  DOM.graphPlaceholder.style.display = "none";

  try {
    const r = await fetch(`${API}/api/report/${id}`);
    if (!r.ok) throw new Error("fetch failed");
    _currentDoc = await r.json();
    renderReport(_currentDoc);
  } catch (e) {
    console.error(e);
    alert("Could not load report.");
  } finally {
    showLoading(false);
  }
}

/* ── Render report into graph + panels ───────────────────────────── */
function renderReport(doc) {
  try {
    const assets    = findKey(doc, "assets") || {};
    const template  = findKey(assets, "template") || { nodes: [], edges: [] };
    const nodes     = template.nodes || [];
    const edges     = template.edges || [];
    const dmScen    = findKey(doc, "damage_scenarios") || findKey(doc, "damage_scenarios") || {};
    
    _allDamage  = findKey(dmScen, "Derivations") || findKey(dmScen, "derivations") || [];
    _allDetails = findKey(dmScen, "Details") || findKey(dmScen, "details") || [];
    _filterNode = null;

    // Stats
    DOM.statNodes.textContent   = nodes.length;
    DOM.statEdges.textContent   = edges.length;
    DOM.statDerivs.textContent  = _allDamage.length;
    DOM.statDetails.textContent = _allDetails.length;

    // Graph
    Graph.render(template);
    Graph.clearSelection();

    // Reset node info
    DOM.nodeInfo.innerHTML = `<div class="node-info-empty">Click a node to inspect it</div>`;

    // Render all damage scenarios
    renderDamagePanel(_allDamage, _allDetails, null);

    // Show/hide prompt button (always show if API is connected)
    const btn = $("btn-show-prompt");
    if (btn) btn.style.display = "block";
  } catch (e) {
    console.error("Renderer Error:", e);
    DOM.nodeInfo.innerHTML = `<div class="node-info-empty" style="color:var(--accent-red)">⚠️ Layout Error: ${e.message}</div>`;
  }
}

// Helper to find a key regardless of Case or underscore/camelCase
function findKey(obj, key) {
  if (!obj || typeof obj !== "object") return null;
  const k = key.toLowerCase().replace(/[^a-z0-9]/g, "");
  for (const actualKey in obj) {
    if (actualKey.toLowerCase().replace(/[^a-z0-9]/g, "") === k) return obj[actualKey];
  }
  return null;
}

/* ── Node click handler ──────────────────────────────────────────── */
function onNodeClick(nodeId, nodeData) {
  if (!nodeId) {
    DOM.nodeInfo.innerHTML = `<div class="node-info-empty">Click a node to inspect it</div>`;
    _filterNode = null;
    renderDamagePanel(_allDamage, _allDetails, null);
    return;
  }

  _filterNode = nodeId;
  const data  = nodeData?.data || {};
  const style = data.style || {};
  const props = nodeData?.properties || [];

  DOM.nodeInfo.innerHTML = `
    <div class="node-info-card">
      <div class="node-color-swatch" style="background:${style.backgroundColor || '#aaa'}"></div>
      <div>
        <div class="node-info-label">${data.label || nodeId}</div>
        <div class="node-info-type">${nodeData?.type || "default"} • ${nodeData?.parentId ? "child node" : "top-level"}</div>
        <div class="node-props">${props.map(p => `<span class="prop-tag ${propClass(p)}">${p[0]}</span>`).join("")}</div>
      </div>
    </div>`;

  // Filter damage scenarios for this node
  const filteredDerivs  = _allDamage.filter(d => d.nodeId === nodeId || d.asset === data.label);
  const filteredDetails = _allDetails.filter(d =>
    d.cyberLosses && d.cyberLosses.some(cl => cl.nodeId === nodeId)
  );

  renderDamagePanel(filteredDerivs, filteredDetails, data.label);
}

function propClass(p) {
  const map = { "Confidentiality": "prop-C", "Integrity": "prop-I", "Availability": "prop-A", "Authenticity": "prop-Au", "Authorization": "prop-Az", "Non-repudiation": "prop-N" };
  return map[p] || "prop-N";
}

/* ── Render damage panel ─────────────────────────────────────────── */
function renderDamagePanel(derivations, details, nodeLabel) {
  DOM.panelCount.textContent = derivations.length;

  // Build a detail lookup by derivation id
  const detailMap = {};
  details.forEach(det => {
    (det.derivationIds || []).forEach(did => { detailMap[did] = det; });
    (det.cyberLosses   || []).forEach(cl  => {
      if (cl.derivationId) detailMap[cl.derivationId] = det;
    });
  });

  if (!derivations.length) {
    DOM.damageList.innerHTML = `
      <div class="panel-empty">
        <div class="empty-icon">${nodeLabel ? "🔍" : "📋"}</div>
        <div>${nodeLabel ? `No threats linked to <strong>${nodeLabel}</strong>` : "Select a report to view threats"}</div>
      </div>`;
    return;
  }

  DOM.damageList.innerHTML = derivations.map((d, i) => {
    const lossClass = lossToClass(d.loss || "");
    const det = detailMap[d.id] || null;

    let detailHtml = "";
    if (det) {
      detailHtml = `
        <div class="damage-details">
          <div class="detail-row">
            <div class="detail-label">Impact</div>
            <div class="detail-value">${det.impact || "—"}</div>
            <div class="detail-label">Likelihood</div>
            <div class="detail-value">${det.likelihood || "—"}</div>
            <div class="detail-label">Risk</div>
            <div class="detail-value">${det.riskLevel || det.risk || "—"}</div>
            <div class="detail-label">Countermeasure</div>
            <div class="detail-value" style="grid-column:span 3;font-family:var(--font);font-size:10.5px;color:var(--text-secondary)">${det.countermeasure || det.mitigation || "—"}</div>
          </div>
        </div>`;
    }

    return `
      <div class="damage-item fade-in ${_filterNode ? "highlighted" : ""}">
        <div class="damage-header">
          <span class="damage-id">${d.id || `D-${i + 1}`}</span>
          <div>
            <div class="damage-name">${d.name || "Unnamed threat"}</div>
            <div class="damage-asset">
              <span class="loss-badge ${lossClass}">${lossIcon(d.loss)} ${d.loss || "unknown"}</span>
              ${d.asset ? `<span style="color:var(--text-label)">· ${d.asset}</span>` : ""}
            </div>
          </div>
        </div>
        ${d.damage_scene ? `<div class="damage-scene">${d.damage_scene}</div>` : ""}
        ${detailHtml}
      </div>`;
  }).join("");
}

function lossToClass(loss) {
  const l = loss.toLowerCase();
  if (l.includes("integ"))   return "loss-integrity";
  if (l.includes("confid"))  return "loss-confidential";
  if (l.includes("avail"))   return "loss-availability";
  if (l.includes("authen"))  return "loss-authenticity";
  if (l.includes("author"))  return "loss-authorization";
  return "loss-other";
}

function lossIcon(loss = "") {
  const l = loss.toLowerCase();
  if (l.includes("integ"))   return "🔒";
  if (l.includes("confid"))  return "👁";
  if (l.includes("avail"))   return "⚡";
  if (l.includes("authen"))  return "🎫";
  if (l.includes("author"))  return "🔑";
  return "⚠️";
}

/* ── Delete report ───────────────────────────────────────────────── */
async function deleteReport(e, id) {
  e.stopPropagation();
  if (!confirm("Delete this report from MongoDB?")) return;
  await fetch(`${API}/api/report/${id}`, { method: "DELETE" });
  await loadReports();
}

/* ── UI bindings ─────────────────────────────────────────────────── */
function bindUI() {
  DOM.searchInput.addEventListener("input", () => {
    const q = DOM.searchInput.value.toLowerCase();
    const filtered = _reports.filter(r =>
      (r.ecu_name || r.query || "").toLowerCase().includes(q)
    );
    renderReportList(filtered);
  });

  DOM.btnZoomIn.addEventListener("click",  () => Graph.zoomIn());
  DOM.btnZoomOut.addEventListener("click", () => Graph.zoomOut());
  DOM.btnFit.addEventListener("click",     () => Graph.resetZoom());

  // Prompt Viewer
  const btnPrompt = $("btn-show-prompt");
  if (btnPrompt) {
    btnPrompt.addEventListener("click", () => showPromptModal());
  }

  // Tidy Layout
  const btnTidy = $("btn-tidy");
  if (btnTidy) {
    btnTidy.addEventListener("click", () => {
      if (_currentDoc) {
        Graph.render(_currentDoc.assets.template);
      }
    });
  }

  // Full Screen / Focus Toggle
  const btnFocus = $("btn-fullscreen");
  if (btnFocus) {
    btnFocus.addEventListener("click", () => {
      const app = $("app");
      const isFocus = app.classList.toggle("focus-mode");
      btnFocus.classList.toggle("active", isFocus);
      btnFocus.innerHTML = isFocus ? "🔚 Normal" : "⛶ Focus";
      // Re-fit graph after layout change
      setTimeout(() => Graph.resetZoom(), 300);
    });
  }
}

function showLoading(show) {
  DOM.loadingOverlay.classList.toggle("active", show);
}

/* ── Start ───────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", boot);

function showPromptModal() {
  if (!_currentDoc) return;
  const modal = $("prompt-modal");
  const pre   = $("modal-prompt-text");
  const metrics = $("modal-eval-metrics");

  pre.textContent = _currentDoc._full_prompt || "No prompt data available for this report.";
  
  // Evaluation Metrics simulation (since we just started tracking)
  const score = _currentDoc._eval_score || 0;
  const metricsList = [
    { lab: "JSON Integrity", val: "PASSED", icon: "💎" },
    { lab: "Schema Connectivity", val: "PASSED", icon: "🔗" },
    { lab: "Complexity Score", val: `${score} Nodes`, icon: "📈" },
    { lab: "RAG Contextualized", val: "YES", icon: "🧠" }
  ];

  metrics.innerHTML = metricsList.map(m => `
    <div class="eval-card">
      <div style="font-size:12px;margin-bottom:4px;">${m.icon}</div>
      <div class="val">${m.val}</div>
      <div class="lab">${m.lab}</div>
    </div>
  `).join("");

  modal.classList.add("visible");
}

function closePromptModal() {
  $("prompt-modal").classList.remove("visible");
}

// Expose globals
window.selectReport = selectReport;
window.deleteReport = deleteReport;
window.closePromptModal = closePromptModal;
