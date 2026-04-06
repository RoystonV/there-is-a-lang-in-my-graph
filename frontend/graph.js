/* =====================================================================
   graph.js — SVG/DOM node-graph renderer for TARA TARA Visualizer
   Renders nodes, groups, edges with pan/zoom and click interaction
   ===================================================================== */

const Graph = (() => {

  let _container = null;  // the #graph-canvas div
  let _svg       = null;  // main SVG element
  let _gRoot     = null;  // transform group
  let _data      = null;  // current { nodes, edges }

  // Viewport transform
  let _tx = 0, _ty = 0, _scale = 1;
  let _dragging = false;
  let _dragStart = { x: 0, y: 0, tx: 0, ty: 0 };

  // Selection
  let _selectedNodeId = null;
  let _onNodeClick = null;   // callback(nodeId, nodeData)
  let _tooltip     = null;

  const CANVAS_W = 3000;
  const CANVAS_H = 2000;

  /* ── Init ──────────────────────────────────────────────────────────── */
  function init(containerId, onNodeClickCb) {
    _container   = document.getElementById(containerId);
    _onNodeClick = onNodeClickCb;

    // Create SVG
    _svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    _svg.setAttribute("width",  "100%");
    _svg.setAttribute("height", "100%");
    _svg.setAttribute("viewBox", `0 0 ${CANVAS_W} ${CANVAS_H}`);
    _svg.style.cursor = "grab";

    // Defs: arrowhead markers + animated dash
    _buildDefs(_svg);

    // Root transform group
    _gRoot = document.createElementNS("http://www.w3.org/2000/svg", "g");
    _gRoot.setAttribute("id", "g-root");
    _svg.appendChild(_gRoot);

    _container.innerHTML = "";
    _container.appendChild(_svg);

    // Tooltip
    _tooltip = document.querySelector(".graph-tooltip");
    if (!_tooltip) {
      _tooltip = document.createElement("div");
      _tooltip.className = "graph-tooltip";
      document.body.appendChild(_tooltip);
    }

    _bindEvents();
  }

  /* ── Defs (markers) ────────────────────────────────────────────────── */
  function _buildDefs(svg) {
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");

    const makeMarker = (id, color) => {
      const m = document.createElementNS("http://www.w3.org/2000/svg", "marker");
      m.setAttribute("id",          id);
      m.setAttribute("markerWidth",  "8");
      m.setAttribute("markerHeight", "8");
      m.setAttribute("refX",  "6");
      m.setAttribute("refY",  "3");
      m.setAttribute("orient", "auto");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", "M0,0 L0,6 L8,3 z");
      path.setAttribute("fill", color);
      m.appendChild(path);
      defs.appendChild(m);
    };

    makeMarker("arrow-blue",  "#64B5F6");
    makeMarker("arrow-gray",  "#808080");
    makeMarker("arrow-green", "#10b981");
    makeMarker("arrow-sel",   "#3b82f6");
    svg.appendChild(defs);
  }

  /* ── Render ─────────────────────────────────────────────────────────── */
  function render(templateData) {
    _data = templateData;
    _selectedNodeId = null;
    _gRoot.innerHTML = "";

    if (!templateData || !templateData.nodes) {
       console.warn("Graph.render: No nodes to render");
       return;
    }

    const nodes = templateData.nodes || [];
    const edges = templateData.edges || [];

    // 1. apply auto-layout
    try {
      _applyLayout(nodes, edges);
    } catch (e) {
      console.error("Layout Error:", e);
    }

    // Build lookup
    const nodeMap = {};
    nodes.forEach(n => { if (n && n.id) nodeMap[n.id] = n; });

    // 2. Render groups first
    const groups  = nodes.filter(n => n && n.type === "group");
    const regular = nodes.filter(n => n && n.type !== "group");

    groups.forEach(g  => _renderGroup(g));
    regular.forEach(n => _renderNode(n));
    edges.forEach(e   => _renderEdge(e, nodeMap));

    requestAnimationFrame(() => fitToView(nodes));
  }

  /* ── Auto Layout (Dagre) ───────────────────────────────────────────── */
  function _applyLayout(nodes, edges) {
    if (!window.dagre) return;

    try {
      const g = new dagre.graphlib.Graph({ compound: true });
      g.setGraph({ rankdir: 'LR', nodesep: 70, ranksep: 100, marginx: 50, marginy: 50 });
      g.setDefaultEdgeLabel(() => ({}));

      // Add nodes & groups
      nodes.forEach(node => {
        if (!node || !node.id) return;
        const isGroup = node.type === 'group';
        g.setNode(node.id, { 
          width: parseFloat(node.width || 150), 
          height: parseFloat(node.height || (isGroup ? 300 : 50))
        });
        if (node.parentId && nodes.some(n => n.id === node.parentId)) {
          g.setParent(node.id, node.parentId);
        }
      });

      // Add edges
      edges.forEach(edge => {
        if (edge.source && edge.target && g.hasNode(edge.source) && g.hasNode(edge.target)) {
           g.setEdge(edge.source, edge.target);
        }
      });

      dagre.layout(g);

      // Apply back
      nodes.forEach(node => {
        const ln = g.node(node.id);
        if (ln) {
          node.position = { x: ln.x - ln.width/2, y: ln.y - ln.height/2 };
        }
      });
    } catch (e) {
      console.error("Dagre Layout failed:", e);
    }
  }

  /* ── Render Group ──────────────────────────────────────────────────── */
  function _renderGroup(node) {
    const pos  = node.positionAbsolute || node.position || { x: 0, y: 0 };
    const w    = parseFloat(node.width  || 400);
    const h    = parseFloat(node.height || 300);
    const data = node.data || {};
    const style = data.style || {};

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("data-id", node.id);
    g.setAttribute("class", "graph-group");

    // Background rect
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x",      pos.x);
    rect.setAttribute("y",      pos.y);
    rect.setAttribute("width",  w);
    rect.setAttribute("height", h);
    rect.setAttribute("rx", "10");
    rect.setAttribute("fill",   style.background || "rgba(59,130,246,0.04)");
    rect.setAttribute("stroke", style.border ? _extractBorderColor(style.border) : "#3b82f6");
    rect.setAttribute("stroke-width", "1");
    rect.setAttribute("stroke-dasharray", "6,4");
    g.appendChild(rect);

    // Label
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", pos.x + 12);
    label.setAttribute("y", pos.y + 20);
    label.setAttribute("fill", "#94a3b8");
    label.setAttribute("font-size", "11");
    label.setAttribute("font-family", "Inter, sans-serif");
    label.setAttribute("font-weight", "600");
    label.textContent = data.label || "";
    g.appendChild(label);

    _gRoot.appendChild(g);
  }

  function _extractBorderColor(borderStr) {
    // "1px dashed #2196F3" → "#2196F3"
    const m = borderStr.match(/#[0-9a-fA-F]{3,6}/);
    return m ? m[0] : "#3b82f6";
  }

  /* ── Render Node ───────────────────────────────────────────────────── */
  function _renderNode(node) {
    const pos  = node.positionAbsolute || node.position || { x: 0, y: 0 };
    const w    = parseFloat(node.width  || 150);
    const h    = parseFloat(node.height ||  50);
    const data = node.data  || {};
    const style = data.style || {};
    const label = data.label || node.id;

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("data-id",   node.id);
    g.setAttribute("data-type", node.type || "default");
    g.setAttribute("class",     "graph-node");
    g.style.cursor = "pointer";

    const isData = node.type === "data";
    const bg     = style.backgroundColor || (isData ? "#e3e896" : "#dadada");
    const border = style.borderColor || "#666";

    if (isData) {
      // Diamond / parallelogram for data nodes
      const rx  = pos.x + w / 2;
      const ry  = pos.y + h / 2;
      const hw  = w / 2 - 2;
      const hh  = h / 2 - 2;
      const pts = `${rx},${ry - hh} ${rx + hw},${ry} ${rx},${ry + hh} ${rx - hw},${ry}`;
      const diamond = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      diamond.setAttribute("points", pts);
      diamond.setAttribute("fill",         bg);
      diamond.setAttribute("stroke",       border);
      diamond.setAttribute("stroke-width", "1.5");
      diamond.setAttribute("class", "node-shape");
      g.appendChild(diamond);
    } else {
      // Regular rounded rect
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x",      pos.x);
      rect.setAttribute("y",      pos.y);
      rect.setAttribute("width",  w);
      rect.setAttribute("height", h);
      rect.setAttribute("rx", "5");
      rect.setAttribute("fill",         bg);
      rect.setAttribute("stroke",       border);
      rect.setAttribute("stroke-width", style.borderWidth ? parseFloat(style.borderWidth) : 1.5);
      rect.setAttribute("class", "node-shape");
      g.appendChild(rect);
    }

    // Label text — centered, split long labels
    const words = label.split(" ");
    const lines = _wrapText(label, Math.floor(w / 7));
    const totalH = lines.length * 13;
    const startY = pos.y + (h - totalH) / 2 + 10;

    lines.forEach((line, i) => {
      const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      txt.setAttribute("x", pos.x + w / 2);
      txt.setAttribute("y", startY + i * 13);
      txt.setAttribute("text-anchor", "middle");
      txt.setAttribute("dominant-baseline", "auto");
      txt.setAttribute("fill", style.color || "#111");
      txt.setAttribute("font-size", style.fontSize ? parseFloat(style.fontSize) : 11);
      txt.setAttribute("font-family", "Inter, sans-serif");
      txt.setAttribute("font-weight", style.fontWeight || "500");
      txt.textContent = line;
      g.appendChild(txt);
    });

    // Hover & click
    g.addEventListener("mouseenter", (e) => _showTooltip(e, node));
    g.addEventListener("mousemove",  (e) => _moveTooltip(e));
    g.addEventListener("mouseleave", ()  => _hideTooltip());
    g.addEventListener("click",      (e) => {
      e.stopPropagation();
      _selectNode(node.id, node);
    });

    _gRoot.appendChild(g);
  }

  function _wrapText(text, maxChars) {
    const words = text.split(" ");
    const lines = [];
    let cur = "";
    words.forEach(w => {
      if ((cur + " " + w).trim().length <= maxChars) {
        cur = (cur + " " + w).trim();
      } else {
        if (cur) lines.push(cur);
        cur = w;
      }
    });
    if (cur) lines.push(cur);
    return lines.length ? lines : [text];
  }

  /* ── Render Edge ───────────────────────────────────────────────────── */
  function _renderEdge(edge, nodeMap) {
    const src = nodeMap[edge.source];
    const tgt = nodeMap[edge.target];
    if (!src || !tgt) return;

    const sp = src.positionAbsolute || src.position || { x: 0, y: 0 };
    const tp = tgt.positionAbsolute || tgt.position || { x: 0, y: 0 };
    const sw = parseFloat(src.width  || 150);
    const sh = parseFloat(src.height ||  50);
    const tw = parseFloat(tgt.width  || 150);
    const th = parseFloat(tgt.height ||  50);

    const p1 = _getIntersectionPoint(src, tgt);
    const p2 = _getIntersectionPoint(tgt, src);

    const x1 = p1.x, y1 = p1.y;
    const x2 = p2.x, y2 = p2.y;

    // Cubic bezier control points
    const dx = x2 - x1, dy = y2 - y1;
    const cx1 = x1 + dx * 0.4;
    const cy1 = y1;
    const cx2 = x2 - dx * 0.4;
    const cy2 = y2;

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "graph-edge");
    g.setAttribute("data-edge-id", edge.id);

    const edgeStyle = edge.style || {};
    const stroke = edgeStyle.stroke || "#808080";
    const sw_val = edgeStyle.strokeWidth || 1.5;

    // Main path
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const d = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
    path.setAttribute("d", d);
    path.setAttribute("fill",         "none");
    path.setAttribute("stroke",       stroke);
    path.setAttribute("stroke-width", sw_val);
    path.setAttribute("stroke-opacity", "0.7");
    path.setAttribute("marker-end",   "url(#arrow-gray)");
    if (edge.animated) {
      path.setAttribute("stroke-dasharray", "6 4");
      path.style.animation = `dash-anim ${1.5 + Math.random() * 0.5}s linear infinite`;
    }
    path.setAttribute("class", "edge-path");
    g.appendChild(path);

    // Edge label
    const lbl = (edge.data && edge.data.label) || "";
    if (lbl) {
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2 - 7;
      const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      const estimatedW = lbl.length * 6 + 8;
      bg.setAttribute("x",      mx - estimatedW / 2);
      bg.setAttribute("y",      my - 8);
      bg.setAttribute("width",  estimatedW);
      bg.setAttribute("height", "14");
      bg.setAttribute("rx",     "3");
      bg.setAttribute("fill",   "#111621");
      bg.setAttribute("fill-opacity", "0.85");
      g.appendChild(bg);

      const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      txt.setAttribute("x", mx);
      txt.setAttribute("y", my + 1);
      txt.setAttribute("text-anchor",       "middle");
      txt.setAttribute("dominant-baseline", "middle");
      txt.setAttribute("fill",         "#94a3b8");
      txt.setAttribute("font-size",    "9");
      txt.setAttribute("font-family",  "JetBrains Mono, monospace");
      txt.textContent = lbl;
      g.appendChild(txt);
    }

    _gRoot.insertBefore(g, _gRoot.firstChild); // behind nodes
  }

  function _getIntersectionPoint(fromNode, toNode) {
    const fA = fromNode.positionAbsolute || fromNode.position || { x: 0, y: 0 };
    const tA = toNode.positionAbsolute || toNode.position || { x: 0, y: 0 };
    const fW = parseFloat(fromNode.width || 150);
    const fH = parseFloat(fromNode.height || 50);
    const tW = parseFloat(toNode.width || 150);
    const tH = parseFloat(toNode.height || 50);

    const c1 = { x: fA.x + fW / 2, y: fA.y + fH / 2 };
    const c2 = { x: tA.x + tW / 2, y: tA.y + tH / 2 };

    const dx = c2.x - c1.x;
    const dy = c2.y - c1.y;

    if (Math.abs(dx / fW) > Math.abs(dy / fH)) {
      // Intersects left or right
      return { x: dx > 0 ? fA.x + fW : fA.x, y: c1.y + (dy * (fW / 2)) / Math.abs(dx) };
    } else {
      // Intersects top or bottom
      return { x: c1.x + (dx * (fH / 2)) / Math.abs(dy), y: dy > 0 ? fA.y + fH : fA.y };
    }
  }

  /* ── Selection ─────────────────────────────────────────────────────── */
  function _selectNode(nodeId, nodeData) {
    // Deselect previous
    if (_selectedNodeId) {
      const prev = _gRoot.querySelector(`[data-id="${_selectedNodeId}"] .node-shape`);
      if (prev) { prev.setAttribute("stroke-width", "1.5"); prev.removeAttribute("filter"); }
    }

    _selectedNodeId = nodeId;

    // Highlight new
    const shape = _gRoot.querySelector(`[data-id="${nodeId}"] .node-shape`);
    if (shape) {
      shape.setAttribute("stroke", "#3b82f6");
      shape.setAttribute("stroke-width", "2.5");
    }

    if (_onNodeClick) _onNodeClick(nodeId, nodeData);
  }

  function clearSelection() {
    if (_selectedNodeId) {
      const prev = _gRoot.querySelector(`[data-id="${_selectedNodeId}"] .node-shape`);
      if (prev) {
        prev.removeAttribute("stroke");
        prev.setAttribute("stroke-width", "1.5");
      }
      _selectedNodeId = null;
    }
    if (_onNodeClick) _onNodeClick(null, null);
  }

  /* ── Fit to view ───────────────────────────────────────────────────── */
  function fitToView(nodes) {
    if (!nodes || !nodes.length) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    nodes.forEach(n => {
      const p = n.positionAbsolute || n.position || { x: 0, y: 0 };
      const w = parseFloat(n.width  || 150);
      const h = parseFloat(n.height ||  50);
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x + w);
      maxY = Math.max(maxY, p.y + h);
    });

    const cw = _container.clientWidth;
    const ch = _container.clientHeight;
    const padX = 60, padY = 60;
    const contentW = maxX - minX + padX * 2;
    const contentH = maxY - minY + padY * 2;

    const scale = Math.min(cw / contentW, ch / contentH, 1.2);
    _scale = Math.max(0.25, Math.min(scale, 1.5));

    const scaledW = contentW * _scale;
    const scaledH = contentH * _scale;
    _tx = (cw - scaledW) / 2 - (minX - padX) * _scale;
    _ty = (ch - scaledH) / 2 - (minY - padY) * _scale;

    _applyTransform();
  }

  function _applyTransform() {
    _svg.setAttribute("viewBox", `${-_tx / _scale} ${-_ty / _scale} ${CANVAS_W / _scale} ${CANVAS_H / _scale}`);
  }

  /* ── Pan / Zoom events ─────────────────────────────────────────────── */
  function _bindEvents() {
    _svg.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      _dragging  = true;
      _dragStart = { x: e.clientX, y: e.clientY, tx: _tx, ty: _ty };
      _svg.style.cursor = "grabbing";
    });

    window.addEventListener("mousemove", (e) => {
      if (!_dragging) return;
      const dx = e.clientX - _dragStart.x;
      const dy = e.clientY - _dragStart.y;
      _tx = _dragStart.tx + dx;
      _ty = _dragStart.ty + dy;
      _applyTransform();
    });

    window.addEventListener("mouseup", () => {
      _dragging = false;
      _svg.style.cursor = "grab";
    });

    _svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const delta  = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.2, Math.min(3, _scale * delta));
      const rect = _svg.getBoundingClientRect();
      const mx = (e.clientX - rect.left);
      const my = (e.clientY - rect.top);
      _tx = mx - (mx - _tx) * (newScale / _scale);
      _ty = my - (my - _ty) * (newScale / _scale);
      _scale = newScale;
      _applyTransform();
    }, { passive: false });

    _svg.addEventListener("click", (e) => {
      if (e.target === _svg || e.target === _gRoot) clearSelection();
    });
  }

  /* ── Tooltip ───────────────────────────────────────────────────────── */
  function _showTooltip(e, node) {
    if (!_tooltip) return;
    const data  = node.data || {};
    const props = (node.properties || []).join(", ") || "—";
    _tooltip.innerHTML = `
      <div class="tooltip-title">${data.label || node.id}</div>
      <div class="tooltip-detail">Type: ${node.type || "default"}</div>
      <div class="tooltip-detail">Properties: ${props}</div>
    `;
    _tooltip.classList.add("visible");
    _moveTooltip(e);
  }

  function _moveTooltip(e) {
    if (!_tooltip) return;
    _tooltip.style.left = (e.clientX + 14) + "px";
    _tooltip.style.top  = (e.clientY - 10) + "px";
  }

  function _hideTooltip() {
    if (_tooltip) _tooltip.classList.remove("visible");
  }

  /* ── Zoom controls ─────────────────────────────────────────────────── */
  function zoomIn()  { _scale = Math.min(3,   _scale * 1.2); _applyTransform(); }
  function zoomOut() { _scale = Math.max(0.2, _scale * 0.8); _applyTransform(); }
  function resetZoom(nodes) { fitToView(nodes || (_data && _data.nodes)); }

  /* ── Public API ────────────────────────────────────────────────────── */
  return { init, render, fitToView, zoomIn, zoomOut, resetZoom, clearSelection };

})();

/* ── Animated edge CSS (injected) ── */
const _edgeStyle = document.createElement("style");
_edgeStyle.textContent = `
  @keyframes dash-anim {
    to { stroke-dashoffset: -20; }
  }
`;
document.head.appendChild(_edgeStyle);
