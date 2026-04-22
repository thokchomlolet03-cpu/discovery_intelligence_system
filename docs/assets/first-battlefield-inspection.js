import { CAPABILITY_FAMILIES, MATURITY_META, MATURITY_ORDER } from "./first-battlefield-inspection-data.js";

const state = {
  families: CAPABILITY_FAMILIES,
  familyFilter: "all",
  maturityFilter: "all",
  scopeFilter: "all",
  search: "",
  selectedId: "",
  graphScale: 1,
  graphOffsetX: 0,
  graphOffsetY: 0,
  dragging: false,
  dragStartX: 0,
  dragStartY: 0,
};

const elements = {
  overallScore: document.getElementById("overall-score"),
  criticalScore: document.getElementById("critical-score"),
  coreScore: document.getElementById("core-score"),
  inspectabilityScore: document.getElementById("inspectability-score"),
  overallFill: document.getElementById("overall-fill"),
  criticalFill: document.getElementById("critical-fill"),
  coreFill: document.getElementById("core-fill"),
  inspectabilityFill: document.getElementById("inspectability-fill"),
  overallSummary: document.getElementById("overall-summary"),
  criticalSummary: document.getElementById("critical-summary"),
  coreSummary: document.getElementById("core-summary"),
  inspectabilitySummary: document.getElementById("inspectability-summary"),
  criticalBlockerCount: document.getElementById("critical-blocker-count"),
  filteredCount: document.getElementById("filtered-capability-count"),
  familyFilter: document.getElementById("family-filter"),
  maturityFilter: document.getElementById("maturity-filter"),
  scopeFilter: document.getElementById("scope-filter"),
  searchInput: document.getElementById("inspection-search"),
  resetButton: document.getElementById("reset-filters"),
  graphSvg: document.getElementById("inspection-graph"),
  graphViewport: document.getElementById("graph-viewport"),
  graphReset: document.getElementById("graph-reset"),
  graphZoomIn: document.getElementById("graph-zoom-in"),
  graphZoomOut: document.getElementById("graph-zoom-out"),
  heatmap: document.getElementById("inspection-heatmap"),
  blockerList: document.getElementById("inspection-blocker-list"),
  readinessBars: document.getElementById("inspection-readiness-bars"),
  detailPanel: document.getElementById("inspection-detail-panel"),
  dependencyChain: document.getElementById("inspection-dependency-chain"),
  downstreamImpact: document.getElementById("inspection-downstream-impact"),
  highestLeverage: document.getElementById("highest-leverage-list"),
};

function flattenCapabilities() {
  return state.families.flatMap((family) => {
    const familyNode = {
      ...family,
      type: "family",
      maturity: family.current_status,
      parent: "",
    };
    const children = (family.children || []).map((child) => ({
      ...child,
      type: "capability",
      parent: family.id,
      category: family.category,
      familyLabel: family.label,
      familyId: family.id,
      why_it_matters: family.why_it_matters,
    }));
    return [familyNode, ...children];
  });
}

function getCapabilityById(id) {
  return flattenCapabilities().find((item) => item.id === id) || null;
}

function maturityValue(status) {
  return MATURITY_META[status]?.value ?? 0;
}

function capabilityMatchesFilters(item) {
  const haystack = [
    item.label,
    item.description,
    item.implementation_basis,
    item.blocker,
    item.recommended_next_step,
  ]
    .join(" ")
    .toLowerCase();
  const searchMatch = !state.search || haystack.includes(state.search);
  const familyMatch =
    state.familyFilter === "all" ||
    item.id === state.familyFilter ||
    item.familyId === state.familyFilter;
  const maturityMatch = state.maturityFilter === "all" || item.maturity === state.maturityFilter;
  const scopeMatch =
    state.scopeFilter === "all" ||
    (state.scopeFilter === "critical" && item.criticality === "critical") ||
    (state.scopeFilter === "scientific_core" && item.category === "scientific_core") ||
    (state.scopeFilter === "surface_and_governance" && item.category === "surface_and_governance") ||
    (state.scopeFilter === "blockers" && maturityValue(item.maturity) <= 0.4);
  return searchMatch && familyMatch && maturityMatch && scopeMatch;
}

function filteredCapabilities() {
  return flattenCapabilities().filter((item) => item.type === "capability" && capabilityMatchesFilters(item));
}

function scoreFamilies() {
  return state.families.map((family) => {
    const children = family.children || [];
    const totalWeight = children.reduce((sum, item) => sum + (item.weight || 1), 0) || 1;
    const readiness =
      children.reduce((sum, item) => sum + maturityValue(item.maturity) * (item.weight || 1), 0) / totalWeight;
    const blockerPenalty = children.some((item) => item.criticality === "critical" && maturityValue(item.maturity) < 0.62) ? 0.12 : 0;
    return {
      id: family.id,
      label: family.label,
      category: family.category,
      readiness,
      effectiveReadiness: Math.max(0, readiness - blockerPenalty),
      weight: family.weight || 1,
      criticality: family.criticality,
      blockerPenalty,
      blockers: children.filter((item) => maturityValue(item.maturity) <= 0.4),
    };
  });
}

function computeReadinessSummary() {
  const familyScores = scoreFamilies();
  const totalWeight = familyScores.reduce((sum, item) => sum + item.weight, 0) || 1;
  const overall =
    familyScores.reduce((sum, item) => sum + item.effectiveReadiness * item.weight, 0) / totalWeight;
  const criticalFamilies = familyScores.filter((item) => item.criticality === "critical");
  const criticalWeight = criticalFamilies.reduce((sum, item) => sum + item.weight, 0) || 1;
  const critical =
    criticalFamilies.reduce((sum, item) => sum + item.effectiveReadiness * item.weight, 0) / criticalWeight;
  const scientificFamilies = familyScores.filter((item) => item.category === "scientific_core");
  const scientificWeight = scientificFamilies.reduce((sum, item) => sum + item.weight, 0) || 1;
  const scientific =
    scientificFamilies.reduce((sum, item) => sum + item.effectiveReadiness * item.weight, 0) / scientificWeight;
  const inspectabilityFamilies = familyScores.filter((item) =>
    ["continuity-inspection", "traceability", "epistemic-conservatism"].includes(item.id)
  );
  const inspectabilityWeight = inspectabilityFamilies.reduce((sum, item) => sum + item.weight, 0) || 1;
  const inspectability =
    inspectabilityFamilies.reduce((sum, item) => sum + item.effectiveReadiness * item.weight, 0) / inspectabilityWeight;
  const criticalBlockers = flattenCapabilities().filter(
    (item) => item.type === "capability" && item.criticality === "critical" && maturityValue(item.maturity) <= 0.4
  );
  return {
    familyScores,
    overall,
    critical,
    scientific,
    inspectability,
    criticalBlockers,
  };
}

function setMetric(node, fillNode, value, summaryNode, summary) {
  const score = Math.round(value * 100);
  if (node) node.textContent = `${score}`;
  if (fillNode) fillNode.style.width = `${score}%`;
  if (summaryNode) summaryNode.textContent = summary;
}

function overviewSummary(summary) {
  if (summary.overall < 0.35) {
    return "The system has meaningful battlefield-shaped layers, but the critical scientific path is still far from ready.";
  }
  if (summary.overall < 0.6) {
    return "The architecture is structurally moving toward the first battlefield, but core readiness is still bottlenecked by evidence depth and contradiction handling.";
  }
  return "The system is approaching a coherent first-battlefield shape, but still depends on resolving key scientific blockers before it can honestly claim readiness.";
}

function renderScorecards() {
  const summary = computeReadinessSummary();
  setMetric(elements.overallScore, elements.overallFill, summary.overall, elements.overallSummary, overviewSummary(summary));
  setMetric(
    elements.criticalScore,
    elements.criticalFill,
    summary.critical,
    elements.criticalSummary,
    "Critical-path readiness punishes weak core dependencies that still block battlefield readiness."
  );
  setMetric(
    elements.coreScore,
    elements.coreFill,
    summary.scientific,
    elements.coreSummary,
    "Scientific-core readiness measures the actual discovery engine, not the broader product shell."
  );
  setMetric(
    elements.inspectabilityScore,
    elements.inspectabilityFill,
    summary.inspectability,
    elements.inspectabilitySummary,
    "Inspectability readiness measures whether the system can explain what it supports, what it does not, and why."
  );
  if (elements.criticalBlockerCount) {
    elements.criticalBlockerCount.textContent = `${summary.criticalBlockers.length}`;
  }
  if (elements.filteredCount) {
    elements.filteredCount.textContent = `${filteredCapabilities().length}`;
  }
}

function colorForMaturity(status) {
  return MATURITY_META[status]?.color || "#475569";
}

function graphLayout() {
  const families = state.families;
  const familySpacingY = 150;
  const childSpacingX = 280;
  const baseX = 150;
  const childX = 480;
  const positions = new Map();
  families.forEach((family, familyIndex) => {
    const familyY = 110 + familyIndex * familySpacingY;
    positions.set(family.id, { x: baseX, y: familyY });
    (family.children || []).forEach((child, childIndex) => {
      positions.set(child.id, {
        x: childX + childIndex * childSpacingX,
        y: familyY + (childIndex % 2 === 0 ? -36 : 36),
      });
    });
  });
  return positions;
}

function visibleIds() {
  const ids = new Set(filteredCapabilities().map((item) => item.id));
  filteredCapabilities().forEach((item) => ids.add(item.familyId));
  return ids;
}

function selectedCapability() {
  return getCapabilityById(state.selectedId) || filteredCapabilities()[0] || flattenCapabilities().find((item) => item.type === "capability") || null;
}

function linkedIdsForSelection(selected) {
  if (!selected) return new Set();
  const ids = new Set([selected.id]);
  (selected.dependencies || []).forEach((item) => ids.add(item));
  flattenCapabilities().forEach((item) => {
    if ((item.dependencies || []).includes(selected.id) || item.parent === selected.id) {
      ids.add(item.id);
    }
    if (item.id === selected.parent) {
      ids.add(item.id);
    }
  });
  return ids;
}

function renderGraph() {
  const svg = elements.graphSvg;
  if (!svg) return;
  const positions = graphLayout();
  const visible = visibleIds();
  const selected = selectedCapability();
  const linked = linkedIdsForSelection(selected);
  const nodes = flattenCapabilities().filter((item) => visible.has(item.id));
  const links = [];

  state.families.forEach((family) => {
    (family.children || []).forEach((child) => {
      if (visible.has(family.id) && visible.has(child.id)) {
        links.push({ source: family.id, target: child.id, kind: "family" });
      }
      (child.dependencies || []).forEach((dependency) => {
        if (visible.has(child.id) && visible.has(dependency)) {
          links.push({ source: dependency, target: child.id, kind: "dependency" });
        }
      });
    });
  });

  svg.innerHTML = "";
  svg.setAttribute("viewBox", `0 0 1800 1500`);
  const root = document.createElementNS("http://www.w3.org/2000/svg", "g");
  root.setAttribute("transform", `translate(${state.graphOffsetX} ${state.graphOffsetY}) scale(${state.graphScale})`);
  root.setAttribute("id", "graph-root");

  links.forEach((link) => {
    const source = positions.get(link.source);
    const target = positions.get(link.target);
    if (!source || !target) return;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const curve = `M ${source.x + 90} ${source.y} C ${source.x + 180} ${source.y}, ${target.x - 160} ${target.y}, ${target.x - 70} ${target.y}`;
    path.setAttribute("d", curve);
    path.setAttribute("class", `inspection-link${selected && linked.has(link.source) && linked.has(link.target) ? " is-highlighted" : ""}${selected && !(linked.has(link.source) && linked.has(link.target)) ? " is-muted" : ""}`);
    root.appendChild(path);
  });

  nodes.forEach((node) => {
    const position = positions.get(node.id);
    if (!position) return;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const isFamily = node.type === "family";
    group.setAttribute("transform", `translate(${position.x} ${position.y})`);
    group.setAttribute(
      "class",
      `inspection-node ${isFamily ? "is-family" : "is-capability"}${selected?.id === node.id ? " is-selected" : ""}${
        selected && !linked.has(node.id) ? " is-muted" : ""
      }`
    );
    group.addEventListener("click", () => {
      state.selectedId = node.id;
      renderAll();
    });

    const shape = document.createElementNS("http://www.w3.org/2000/svg", isFamily ? "rect" : "rect");
    shape.setAttribute("x", isFamily ? "-95" : "-78");
    shape.setAttribute("y", isFamily ? "-38" : "-30");
    shape.setAttribute("width", isFamily ? "190" : "156");
    shape.setAttribute("height", isFamily ? "76" : "60");
    shape.setAttribute("fill", colorForMaturity(node.maturity));
    shape.setAttribute("fill-opacity", isFamily ? "0.24" : "0.16");
    shape.setAttribute("stroke", colorForMaturity(node.maturity));
    shape.setAttribute("stroke-width", "1.5");
    group.appendChild(shape);

    const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
    title.setAttribute("text-anchor", "middle");
    title.setAttribute("y", isFamily ? "-4" : "-2");
    title.setAttribute("class", "inspection-node-label");
    title.textContent = truncate(node.label, isFamily ? 24 : 18);
    group.appendChild(title);

    const meta = document.createElementNS("http://www.w3.org/2000/svg", "text");
    meta.setAttribute("text-anchor", "middle");
    meta.setAttribute("y", isFamily ? "18" : "16");
    meta.setAttribute("class", "inspection-node-meta");
    meta.textContent = isFamily ? MATURITY_META[node.maturity].label : `${node.familyLabel} / ${MATURITY_META[node.maturity].label}`;
    group.appendChild(meta);

    root.appendChild(group);
  });

  svg.appendChild(root);
  svg.classList.toggle("is-dragging", state.dragging);
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function renderHeatmap() {
  if (!elements.heatmap) return;
  const summary = computeReadinessSummary();
  elements.heatmap.innerHTML = "";
  const header = document.createElement("div");
  header.className = "inspection-heatmap-header";
  header.innerHTML = `<span>Family</span>${MATURITY_ORDER.map((item) => `<span>${MATURITY_META[item].label}</span>`).join("")}`;
  elements.heatmap.appendChild(header);

  summary.familyScores.forEach((familyScore) => {
    const family = state.families.find((item) => item.id === familyScore.id);
    if (!family) return;
    const row = document.createElement("div");
    row.className = "inspection-heatmap-row";
    const familyCell = document.createElement("button");
    familyCell.className = "inspection-family-name inspection-matrix-cell";
    familyCell.textContent = family.label;
    familyCell.addEventListener("click", () => {
      state.selectedId = family.children?.[0]?.id || family.id;
      renderAll();
    });
    row.appendChild(familyCell);
    MATURITY_ORDER.forEach((status) => {
      const cell = document.createElement("button");
      const dominant = family.current_status === status;
      cell.className = `inspection-matrix-cell${dominant ? " is-dominant" : ""}`;
      cell.style.background = dominant ? colorForMaturity(status) : "rgba(148, 163, 184, 0.05)";
      cell.style.opacity = dominant ? "0.9" : "0.42";
      cell.textContent = dominant ? family.children.length.toString() : "";
      cell.addEventListener("click", () => {
        state.familyFilter = family.id;
        state.maturityFilter = status;
        renderAll();
      });
      row.appendChild(cell);
    });
    elements.heatmap.appendChild(row);
  });
}

function rankedBlockers() {
  return flattenCapabilities()
    .filter((item) => item.type === "capability")
    .sort((left, right) => {
      const leftScore = (left.criticality === "critical" ? 2 : 1) * (1 - maturityValue(left.maturity)) * (left.weight || 1);
      const rightScore = (right.criticality === "critical" ? 2 : 1) * (1 - maturityValue(right.maturity)) * (right.weight || 1);
      return rightScore - leftScore;
    })
    .slice(0, 8);
}

function renderBlockers() {
  if (!elements.blockerList) return;
  elements.blockerList.innerHTML = "";
  rankedBlockers().forEach((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.className = item.id === state.selectedId ? "is-selected" : "";
    button.innerHTML = `
      <strong>${item.label}</strong>
      <div class="inspection-helper">${item.familyLabel}</div>
      <div class="inspection-helper">${MATURITY_META[item.maturity].label} · ${item.blocker || item.limitation}</div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = item.id;
      renderAll();
    });
    li.appendChild(button);
    elements.blockerList.appendChild(li);
  });
}

function renderReadinessBars() {
  if (!elements.readinessBars) return;
  const summary = computeReadinessSummary();
  elements.readinessBars.innerHTML = "";
  summary.familyScores.forEach((item) => {
    const row = document.createElement("div");
    row.className = "inspection-bar-row";
    row.innerHTML = `
      <span>${item.label}</span>
      <div class="inspection-bar-rail"><div class="inspection-bar-fill" style="width:${Math.round(
        item.effectiveReadiness * 100
      )}%; background:${colorForMaturity(scoreToNearestMaturity(item.effectiveReadiness))};"></div></div>
      <strong>${Math.round(item.effectiveReadiness * 100)}</strong>
    `;
    elements.readinessBars.appendChild(row);
  });
}

function scoreToNearestMaturity(value) {
  return MATURITY_ORDER.reduce((best, status) => {
    const currentDistance = Math.abs(maturityValue(status) - value);
    const bestDistance = Math.abs(maturityValue(best) - value);
    return currentDistance < bestDistance ? status : best;
  }, "missing");
}

function renderHighestLeverage() {
  if (!elements.highestLeverage) return;
  elements.highestLeverage.innerHTML = "";
  rankedBlockers().slice(0, 5).forEach((item) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.innerHTML = `
      <strong>${item.label}</strong>
      <div class="inspection-helper">${item.recommended_next_step}</div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = item.id;
      renderAll();
    });
    li.appendChild(button);
    elements.highestLeverage.appendChild(li);
  });
}

function downstreamDependents(id) {
  return flattenCapabilities().filter((item) => (item.dependencies || []).includes(id));
}

function renderDetailPanel() {
  const selected = selectedCapability();
  if (!elements.detailPanel || !selected) return;
  elements.detailPanel.innerHTML = `
    <div class="inspection-detail-grid">
      <div>
        <p class="eyebrow">${selected.type === "family" ? "Capability Family" : selected.familyLabel || "Capability"}</p>
        <h3 class="inspection-detail-title">${selected.label}</h3>
        <p class="inspection-detail-copy">${selected.description || selected.evidence_summary || ""}</p>
      </div>
      <div class="inspection-detail-pills">
        <span class="inspection-chip">Maturity ${MATURITY_META[selected.maturity].label}</span>
        <span class="inspection-chip">Criticality ${selected.criticality || "important"}</span>
        <span class="inspection-chip">Confidence ${selected.confidence || "medium"}</span>
        <span class="inspection-chip">Weight ${(selected.weight || 1).toFixed(1)}</span>
      </div>
      <div class="inspection-definition-grid">
        <article class="inspection-definition-card">
          <strong>Why It Matters</strong>
          <div class="inspection-helper">${selected.why_it_matters || "This capability is part of the battlefield path and affects downstream readiness."}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Current Implementation Basis</strong>
          <div class="inspection-helper">${selected.implementation_basis || "Not yet described."}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Current Limitation / Blocker</strong>
          <div class="inspection-helper">${selected.blocker || selected.limitation || "No blocker recorded."}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Recommended Next Move</strong>
          <div class="inspection-helper">${selected.recommended_next_step || "No next move recorded."}</div>
        </article>
      </div>
    </div>
  `;
  renderDependencyChain(selected);
  renderDownstreamImpact(selected);
}

function renderDependencyChain(selected) {
  if (!elements.dependencyChain) return;
  elements.dependencyChain.innerHTML = "";
  const deps = (selected.dependencies || []).map((id) => getCapabilityById(id)).filter(Boolean);
  if (!deps.length) {
    elements.dependencyChain.innerHTML = '<div class="inspection-empty-state">No direct dependency chain is recorded for the selected capability.</div>';
    return;
  }
  const wrap = document.createElement("div");
  wrap.className = "inspection-dependency-map";
  deps.forEach((item) => {
    const button = document.createElement("button");
    button.textContent = item.label;
    button.addEventListener("click", () => {
      state.selectedId = item.id;
      renderAll();
    });
    wrap.appendChild(button);
  });
  elements.dependencyChain.appendChild(wrap);
}

function renderDownstreamImpact(selected) {
  if (!elements.downstreamImpact) return;
  elements.downstreamImpact.innerHTML = "";
  const dependents = downstreamDependents(selected.id);
  if (!dependents.length) {
    elements.downstreamImpact.innerHTML = '<div class="inspection-empty-state">No immediate downstream impacts are recorded for the selected capability.</div>';
    return;
  }
  const list = document.createElement("ul");
  list.className = "inspection-impact-list";
  dependents.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${item.label}</strong><div class="inspection-helper">${item.recommended_next_step || item.blocker || item.limitation}</div>`;
    list.appendChild(li);
  });
  elements.downstreamImpact.appendChild(list);
}

function syncFilters() {
  if (elements.familyFilter) elements.familyFilter.value = state.familyFilter;
  if (elements.maturityFilter) elements.maturityFilter.value = state.maturityFilter;
  if (elements.scopeFilter) elements.scopeFilter.value = state.scopeFilter;
  if (elements.searchInput) elements.searchInput.value = state.search;
}

function renderAll() {
  syncFilters();
  renderScorecards();
  renderGraph();
  renderHeatmap();
  renderBlockers();
  renderReadinessBars();
  renderHighestLeverage();
  renderDetailPanel();
}

function resetFilters() {
  state.familyFilter = "all";
  state.maturityFilter = "all";
  state.scopeFilter = "all";
  state.search = "";
  renderAll();
}

function bindGraphInteractions() {
  const svg = elements.graphSvg;
  if (!svg) return;
  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    state.graphScale = Math.max(0.65, Math.min(1.9, Number((state.graphScale + delta).toFixed(2))));
    renderGraph();
  });
  svg.addEventListener("pointerdown", (event) => {
    state.dragging = true;
    state.dragStartX = event.clientX - state.graphOffsetX;
    state.dragStartY = event.clientY - state.graphOffsetY;
    renderGraph();
  });
  window.addEventListener("pointermove", (event) => {
    if (!state.dragging) return;
    state.graphOffsetX = event.clientX - state.dragStartX;
    state.graphOffsetY = event.clientY - state.dragStartY;
    renderGraph();
  });
  window.addEventListener("pointerup", () => {
    if (!state.dragging) return;
    state.dragging = false;
    renderGraph();
  });
}

function bindControls() {
  elements.familyFilter?.addEventListener("change", (event) => {
    state.familyFilter = event.target.value;
    renderAll();
  });
  elements.maturityFilter?.addEventListener("change", (event) => {
    state.maturityFilter = event.target.value;
    renderAll();
  });
  elements.scopeFilter?.addEventListener("change", (event) => {
    state.scopeFilter = event.target.value;
    renderAll();
  });
  elements.searchInput?.addEventListener("input", (event) => {
    state.search = String(event.target.value || "").trim().toLowerCase();
    renderAll();
  });
  elements.resetButton?.addEventListener("click", resetFilters);
  elements.graphReset?.addEventListener("click", () => {
    state.graphScale = 1;
    state.graphOffsetX = 0;
    state.graphOffsetY = 0;
    renderGraph();
  });
  elements.graphZoomIn?.addEventListener("click", () => {
    state.graphScale = Math.min(1.9, Number((state.graphScale + 0.1).toFixed(2)));
    renderGraph();
  });
  elements.graphZoomOut?.addEventListener("click", () => {
    state.graphScale = Math.max(0.65, Number((state.graphScale - 0.1).toFixed(2)));
    renderGraph();
  });
}

function init() {
  const firstCapability = flattenCapabilities().find((item) => item.type === "capability");
  state.selectedId = firstCapability?.id || "";
  bindControls();
  bindGraphInteractions();
  renderAll();
}

init();
