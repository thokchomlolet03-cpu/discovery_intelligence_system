import {
  BATTLEFIELD_MODEL,
  CAPABILITY_SOURCE_REFS,
  MATURITY_META,
  MATURITY_ORDER,
} from "./first-battlefield-inspection-data.js";

const state = {
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
  snapshot: null,
  model: null,
};

const elements = {
  overallScore: document.getElementById("overall-score"),
  criticalScore: document.getElementById("critical-score"),
  coreScore: document.getElementById("core-score"),
  inspectabilityScore: document.getElementById("inspectability-score"),
  gateScore: document.getElementById("gate-score"),
  overallFill: document.getElementById("overall-fill"),
  criticalFill: document.getElementById("critical-fill"),
  coreFill: document.getElementById("core-fill"),
  inspectabilityFill: document.getElementById("inspectability-fill"),
  gateFill: document.getElementById("gate-fill"),
  overallSummary: document.getElementById("overall-summary"),
  criticalSummary: document.getElementById("critical-summary"),
  coreSummary: document.getElementById("core-summary"),
  inspectabilitySummary: document.getElementById("inspectability-summary"),
  gateSummary: document.getElementById("gate-summary"),
  generatedAt: document.getElementById("inspection-generated-at"),
  commitLabel: document.getElementById("inspection-commit"),
  trackedPathsLabel: document.getElementById("inspection-tracked-paths"),
  criticalBlockerCount: document.getElementById("critical-blocker-count"),
  filteredCount: document.getElementById("filtered-capability-count"),
  familyFilter: document.getElementById("family-filter"),
  maturityFilter: document.getElementById("maturity-filter"),
  scopeFilter: document.getElementById("scope-filter"),
  searchInput: document.getElementById("inspection-search"),
  resetButton: document.getElementById("reset-filters"),
  graphSvg: document.getElementById("inspection-graph"),
  graphReset: document.getElementById("graph-reset"),
  graphZoomIn: document.getElementById("graph-zoom-in"),
  graphZoomOut: document.getElementById("graph-zoom-out"),
  heatmap: document.getElementById("inspection-heatmap"),
  blockerList: document.getElementById("inspection-blocker-list"),
  gateList: document.getElementById("battlefield-gates-list"),
  readinessBars: document.getElementById("inspection-readiness-bars"),
  detailPanel: document.getElementById("inspection-detail-panel"),
  dependencyChain: document.getElementById("inspection-dependency-chain"),
  downstreamImpact: document.getElementById("inspection-downstream-impact"),
  highestLeverage: document.getElementById("highest-leverage-list"),
  recentChanges: document.getElementById("inspection-recent-changes"),
};

function baseModel() {
  return state.snapshot?.model || BATTLEFIELD_MODEL;
}

function snapshotMeta() {
  return state.snapshot || {};
}

function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function repoCommitUrl(commitSha) {
  const repoUrl = snapshotMeta().repo_url || "";
  if (!repoUrl || !commitSha) return "";
  return `${repoUrl}/commit/${commitSha}`;
}

async function loadInspectionSnapshot() {
  try {
    const response = await fetch("./assets/first-battlefield-inspection.snapshot.json", {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`snapshot fetch failed: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    return {
      generated_at: "",
      commit_sha: "",
      commit_short: "",
      repo_url: "",
      tracked_paths: [],
      tracked_paths_count: 0,
      provenance_note:
        "Snapshot unavailable, so the page is using the local inspection manifest without generated repo metadata.",
      recent_changes: [],
      model: BATTLEFIELD_MODEL,
    };
  }
}

function maturityValue(status) {
  return MATURITY_META[status]?.value ?? 0;
}

function scoreToNearestMaturity(value) {
  return MATURITY_ORDER.reduce((best, status) => {
    const currentDistance = Math.abs(maturityValue(status) - value);
    const bestDistance = Math.abs(maturityValue(best) - value);
    return currentDistance < bestDistance ? status : best;
  }, "missing");
}

function scorePercent(value) {
  return Math.round((value || 0) * 100);
}

function criticalityFactor(value) {
  return value === "critical" ? 1.35 : 1;
}

function confidenceRank(value) {
  if (value === "high") return 3;
  if (value === "medium") return 2;
  return 1;
}

function formatStatusLabel(status) {
  return MATURITY_META[status]?.label ?? status;
}

function colorForMaturity(status) {
  return MATURITY_META[status]?.color ?? "#475569";
}

function createStatusBadge(status) {
  return `<span class="inspection-status-badge" style="background:${colorForMaturity(status)}22; color:${colorForMaturity(
    status
  )}; border:1px solid ${colorForMaturity(status)}55;">${formatStatusLabel(status)}</span>`;
}

function buildInspectionModel() {
  const capabilities = [];
  const capabilityMap = new Map();
  const rootModel = baseModel();

  const families = rootModel.families.map((family) => {
    const children = family.children.map((capability) => {
      const criteria = capability.criteria.map((criterion) => ({
        ...criterion,
        score: maturityValue(criterion.status),
      }));
      const totalWeight = criteria.reduce((sum, criterion) => sum + (criterion.weight || 1), 0) || 1;
      const score =
        criteria.reduce((sum, criterion) => sum + criterion.score * (criterion.weight || 1), 0) / totalWeight;
      const maturity = scoreToNearestMaturity(score);
      const criticalWeakCriteria = criteria.filter(
        (criterion) => criterion.critical && criterion.score < maturityValue("substantial")
      );
      const weakCriteria = criteria.filter((criterion) => criterion.score < maturityValue("substantial"));
      const battlefieldGate = capability.battlefield_gate
        ? {
            ...capability.battlefield_gate,
            requiredValue: maturityValue(capability.battlefield_gate.required_status),
          }
        : null;
      const gateSatisfied = !battlefieldGate || score >= battlefieldGate.requiredValue;
      const derivedCapability = {
        ...capability,
        type: "capability",
        familyId: family.id,
        familyLabel: family.label,
        category: family.category,
        score,
        maturity,
        criteria,
        totalCriterionWeight: totalWeight,
        criticalWeakCriteriaCount: criticalWeakCriteria.length,
        weakCriteriaCount: weakCriteria.length,
        battlefieldGate,
        gateSatisfied,
        source_refs: capability.source_refs || CAPABILITY_SOURCE_REFS[capability.id] || [],
        recent_changes: capability.recent_changes || [],
      };
      capabilities.push(derivedCapability);
      capabilityMap.set(derivedCapability.id, derivedCapability);
      return derivedCapability;
    });

    const totalWeight = children.reduce((sum, child) => sum + (child.weight || 1), 0) || 1;
    const baseScore = children.reduce((sum, child) => sum + child.score * (child.weight || 1), 0) / totalWeight;
    const unmetGateCount = children.filter((child) => child.battlefieldGate && !child.gateSatisfied).length;
    const criticalWeakChildren = children.filter(
      (child) => child.criticality === "critical" && child.score < maturityValue("substantial")
    ).length;
    const effectiveScore = Math.max(
      0,
      baseScore - Math.min(0.18, unmetGateCount * 0.05 + criticalWeakChildren * 0.03)
    );
    return {
      ...family,
      type: "family",
      score: effectiveScore,
      baseScore,
      maturity: scoreToNearestMaturity(effectiveScore),
      children,
      unmetGateCount,
      criticalWeakChildren,
      familyId: family.id,
      source_refs:
        family.source_refs ||
        Array.from(
          new Map(
            children
              .flatMap((child) => child.source_refs || [])
              .filter((item) => item?.path)
              .map((item) => [item.path, item])
          ).values()
        ),
      recent_changes: family.recent_changes || [],
    };
  });

  const familyMap = new Map(families.map((family) => [family.id, family]));
  const capabilityDependentsMap = new Map(capabilities.map((capability) => [capability.id, []]));
  const familyDependentsMap = new Map(families.map((family) => [family.id, []]));

  capabilities.forEach((capability) => {
    (capability.dependencies || []).forEach((dependencyId) => {
      const dependents = capabilityDependentsMap.get(dependencyId) || [];
      dependents.push(capability.id);
      capabilityDependentsMap.set(dependencyId, dependents);
    });
  });

  families.forEach((family) => {
    (family.dependencies || []).forEach((dependencyId) => {
      const dependents = familyDependentsMap.get(dependencyId) || [];
      dependents.push(family.id);
      familyDependentsMap.set(dependencyId, dependents);
    });
  });

  return {
    raw: rootModel,
    families,
    familyMap,
    capabilities,
    capabilityMap,
    capabilityDependentsMap,
    familyDependentsMap,
  };
}

function getNodeById(id) {
  if (!state.model) return null;
  return state.model.capabilityMap.get(id) || state.model.familyMap.get(id) || null;
}

function capabilityHaystack(capability) {
  const criteriaText = (capability.criteria || [])
    .flatMap((criterion) => [criterion.label, criterion.measurement_basis, criterion.current_evidence, criterion.gap])
    .join(" ");
  const sourceText = (capability.source_refs || []).map((item) => `${item.label || ""} ${item.path || ""}`).join(" ");
  return [
    capability.label,
    capability.familyLabel,
    capability.description,
    capability.target_state,
    capability.implementation_basis,
    capability.current_evidence,
    capability.limitation,
    capability.blocker,
    capability.recommended_next_step,
    capability.why_it_matters,
    criteriaText,
    sourceText,
  ]
    .join(" ")
    .toLowerCase();
}

function capabilityMatchesFilters(capability, { ignoreMaturity = false } = {}) {
  const searchMatch = !state.search || capabilityHaystack(capability).includes(state.search);
  const familyMatch = state.familyFilter === "all" || capability.familyId === state.familyFilter;
  const maturityMatch = ignoreMaturity || state.maturityFilter === "all" || capability.maturity === state.maturityFilter;
  const scopeMatch =
    state.scopeFilter === "all" ||
    (state.scopeFilter === "critical" && capability.criticality === "critical") ||
    (state.scopeFilter === "scientific_core" && capability.category === "scientific_core") ||
    (state.scopeFilter === "surface_and_governance" && capability.category === "surface_and_governance") ||
    (state.scopeFilter === "blockers" &&
      (capability.score < maturityValue("substantial") || (capability.battlefieldGate && !capability.gateSatisfied)));
  return searchMatch && familyMatch && maturityMatch && scopeMatch;
}

function getFilteredCapabilities({ ignoreMaturity = false } = {}) {
  if (!state.model) return [];
  return state.model.capabilities.filter((capability) =>
    capabilityMatchesFilters(capability, {
      ignoreMaturity,
    })
  );
}

function familyHasVisibleCapability(familyId, { ignoreMaturity = false } = {}) {
  return getFilteredCapabilities({ ignoreMaturity }).some((capability) => capability.familyId === familyId);
}

function countClosure(startIds, nextIds) {
  const visited = new Set();
  const stack = [...startIds];
  while (stack.length) {
    const next = stack.pop();
    if (!next || visited.has(next)) continue;
    visited.add(next);
    nextIds(next).forEach((id) => {
      if (!visited.has(id)) stack.push(id);
    });
  }
  return visited;
}

function capabilityUpstreamClosure(id) {
  return countClosure([id], (current) => getNodeById(current)?.dependencies || []);
}

function capabilityDownstreamClosure(id) {
  return countClosure([id], (current) => state.model?.capabilityDependentsMap.get(current) || []);
}

function familyUpstreamClosure(id) {
  return countClosure([id], (current) => state.model?.familyMap.get(current)?.dependencies || []);
}

function familyDownstreamClosure(id) {
  return countClosure([id], (current) => state.model?.familyDependentsMap.get(current) || []);
}

function capabilityDependencyDepth(id, memo = new Map(), visiting = new Set()) {
  if (memo.has(id)) return memo.get(id);
  if (visiting.has(id)) return 0;
  visiting.add(id);
  const capability = state.model.capabilityMap.get(id);
  const dependencies = capability?.dependencies || [];
  const depth = dependencies.length
    ? Math.max(...dependencies.map((dependencyId) => capabilityDependencyDepth(dependencyId, memo, visiting) + 1))
    : 0;
  visiting.delete(id);
  memo.set(id, depth);
  return depth;
}

function getSummary() {
  if (!state.model) return null;
  const families = state.model.families;
  const totalWeight = families.reduce((sum, family) => sum + (family.weight || 1), 0) || 1;
  const overall = families.reduce((sum, family) => sum + family.score * (family.weight || 1), 0) / totalWeight;

  const criticalFamilies = families.filter((family) => family.criticality === "critical");
  const criticalWeight = criticalFamilies.reduce((sum, family) => sum + (family.weight || 1), 0) || 1;
  const critical =
    criticalFamilies.reduce((sum, family) => sum + family.score * (family.weight || 1), 0) / criticalWeight;

  const scientificFamilies = families.filter((family) => family.category === "scientific_core");
  const scientificWeight = scientificFamilies.reduce((sum, family) => sum + (family.weight || 1), 0) || 1;
  const scientific =
    scientificFamilies.reduce((sum, family) => sum + family.score * (family.weight || 1), 0) / scientificWeight;

  const inspectabilityFamilies = families.filter((family) =>
    ["traceability", "continuity-inspection", "epistemic-conservatism"].includes(family.id)
  );
  const inspectabilityWeight = inspectabilityFamilies.reduce((sum, family) => sum + (family.weight || 1), 0) || 1;
  const inspectability =
    inspectabilityFamilies.reduce((sum, family) => sum + family.score * (family.weight || 1), 0) / inspectabilityWeight;

  const gateCapabilities = state.model.capabilities.filter((capability) => capability.battlefieldGate);
  const unmetGates = gateCapabilities
    .filter((capability) => !capability.gateSatisfied)
    .sort((left, right) => {
      const leftRatio = left.score / left.battlefieldGate.requiredValue;
      const rightRatio = right.score / right.battlefieldGate.requiredValue;
      return leftRatio - rightRatio;
    });
  const gateSatisfaction =
    gateCapabilities.reduce((sum, capability) => {
      if (!capability.battlefieldGate) return sum;
      return sum + Math.min(1, capability.score / capability.battlefieldGate.requiredValue);
    }, 0) / (gateCapabilities.length || 1);

  return {
    overall,
    critical,
    scientific,
    inspectability,
    gateSatisfaction,
    unmetGates,
    gateCapabilities,
  };
}

function setMetric(node, fillNode, value, summaryNode, summary) {
  const score = scorePercent(value);
  if (node) node.textContent = `${score}`;
  if (fillNode) fillNode.style.width = `${score}%`;
  if (summaryNode) summaryNode.textContent = summary;
}

function overviewSummary(summary) {
  if (summary.overall < 0.38) {
    return "The system has real first-battlefield architecture, but the scientific core is still far from trustworthy answer readiness.";
  }
  if (summary.overall < 0.62) {
    return "The system is structurally moving toward the first battlefield, but major evidence and contradiction gates still limit honest readiness claims.";
  }
  return "The architecture is materially closer to the first battlefield, but hard scientific gates still separate current progress from trustworthy battlefield readiness.";
}

function gateSummary(summary) {
  if (!summary.gateCapabilities.length) {
    return "No hard battlefield gates are currently configured in the inspection model.";
  }
  if (!summary.unmetGates.length) {
    return "All configured hard gates are currently satisfied by the seeded inspection model.";
  }
  return `${summary.unmetGates.length} hard gate${summary.unmetGates.length === 1 ? "" : "s"} still block battlefield readiness.`;
}

function renderScorecards() {
  const summary = getSummary();
  if (!summary) return;

  setMetric(elements.overallScore, elements.overallFill, summary.overall, elements.overallSummary, overviewSummary(summary));
  setMetric(
    elements.criticalScore,
    elements.criticalFill,
    summary.critical,
    elements.criticalSummary,
    "Critical-path readiness weights the families that most directly determine whether the system can answer honestly."
  );
  setMetric(
    elements.coreScore,
    elements.coreFill,
    summary.scientific,
    elements.coreSummary,
    "Scientific-core readiness measures the discovery engine rather than the broader product shell."
  );
  setMetric(
    elements.inspectabilityScore,
    elements.inspectabilityFill,
    summary.inspectability,
    elements.inspectabilitySummary,
    "Inspectability readiness measures whether the current answer boundary can be audited, reopened, and explained."
  );
  setMetric(
    elements.gateScore,
    elements.gateFill,
    summary.gateSatisfaction,
    elements.gateSummary,
    gateSummary(summary)
  );

  const criticalBlockers = state.model.capabilities.filter(
    (capability) =>
      capability.criticality === "critical" &&
      (capability.score < maturityValue("substantial") || (capability.battlefieldGate && !capability.gateSatisfied))
  );
  if (elements.criticalBlockerCount) {
    elements.criticalBlockerCount.textContent = `${criticalBlockers.length}`;
  }
  if (elements.filteredCount) {
    elements.filteredCount.textContent = `${getFilteredCapabilities().length}`;
  }
}

function renderProvenance() {
  const meta = snapshotMeta();
  if (elements.generatedAt) {
    elements.generatedAt.textContent = meta.generated_at
      ? `Generated ${formatDateTime(meta.generated_at)}`
      : "Using local manifest fallback without generated snapshot metadata.";
  }
  if (elements.commitLabel) {
    elements.commitLabel.textContent = meta.commit_short
      ? `Snapshot base ${meta.commit_short}${meta.branch ? ` on ${meta.branch}` : ""}`
      : "";
  }
  if (elements.trackedPathsLabel) {
    const note = meta.provenance_note || "";
    const tracked = meta.tracked_paths_count ? `${meta.tracked_paths_count} tracked source paths.` : "";
    const criteria = meta.repo_inspected_criteria_count
      ? `${meta.repo_inspected_criteria_count} repo-inspected criteria, ${meta.seeded_criteria_count || 0} still seeded.`
      : "";
    elements.trackedPathsLabel.textContent = [tracked, criteria, note].filter(Boolean).join(" ");
  }
}

function renderRecentChanges() {
  if (!elements.recentChanges) return;
  const selected = selectedNode();
  const changes = selected?.recent_changes?.length ? selected.recent_changes : snapshotMeta().recent_changes || [];

  renderList(elements.recentChanges, changes, (change) => {
    const button = document.createElement("button");
    const commitLink = repoCommitUrl(change.commit_sha);
    button.innerHTML = `
      <strong>${change.subject || "Repository change"}</strong>
      <div class="inspection-helper">${change.commit_short || ""} · ${change.committed_on || ""} · ${
      change.author || ""
    }</div>
      <div class="inspection-helper">${selected?.recent_changes?.length ? "Selection-linked source change" : "Tracked first-battlefield source change"}</div>
      ${commitLink ? `<div class="inspection-helper">${commitLink}</div>` : ""}
    `;
    if (commitLink) {
      button.addEventListener("click", () => {
        window.open(commitLink, "_blank", "noopener,noreferrer");
      });
    }
    return button;
  });
}

function graphLayout(graphCapabilityIds) {
  const familySpacingY = 185;
  const familyX = 180;
  const capabilityBaseX = 620;
  const depthSpacingX = 320;
  const baseY = 135;
  const positions = new Map();
  const depthMemo = new Map();
  const visibleChildrenByFamily = new Map();

  graphCapabilityIds.forEach((id) => {
    const capability = state.model.capabilityMap.get(id);
    if (!capability) return;
    const list = visibleChildrenByFamily.get(capability.familyId) || [];
    list.push(capability);
    visibleChildrenByFamily.set(capability.familyId, list);
  });

  state.model.families.forEach((family, familyIndex) => {
    const familyY = baseY + familyIndex * familySpacingY;
    positions.set(family.id, { x: familyX, y: familyY });
    const children = (visibleChildrenByFamily.get(family.id) || []).sort((left, right) => {
      const leftDepth = capabilityDependencyDepth(left.id, depthMemo);
      const rightDepth = capabilityDependencyDepth(right.id, depthMemo);
      if (leftDepth !== rightDepth) return leftDepth - rightDepth;
      return left.label.localeCompare(right.label);
    });
    const offsets = children.map((_, index) => (index - (children.length - 1) / 2) * 88);
    children.forEach((capability, index) => {
      const depth = capabilityDependencyDepth(capability.id, depthMemo);
      positions.set(capability.id, {
        x: capabilityBaseX + depth * depthSpacingX,
        y: familyY + offsets[index],
      });
    });
  });

  const maxDepth = Math.max(
    1,
    ...Array.from(graphCapabilityIds).map((id) => capabilityDependencyDepth(id, depthMemo))
  );

  return {
    positions,
    width: capabilityBaseX + maxDepth * depthSpacingX + 420,
    height: baseY + state.model.families.length * familySpacingY + 80,
  };
}

function selectedNode() {
  return getNodeById(state.selectedId);
}

function directNeighborIds(selected) {
  if (!selected) return new Set();
  const ids = new Set();
  if (selected.type === "capability") {
    ids.add(selected.familyId);
    (selected.dependencies || []).forEach((id) => ids.add(id));
    (state.model.capabilityDependentsMap.get(selected.id) || []).forEach((id) => ids.add(id));
  } else {
    (selected.dependencies || []).forEach((id) => ids.add(id));
    (state.model.familyDependentsMap.get(selected.id) || []).forEach((id) => ids.add(id));
    selected.children.forEach((child) => ids.add(child.id));
  }
  return ids;
}

function selectionRelations(selected) {
  if (!selected) {
    return {
      upstream: new Set(),
      downstream: new Set(),
      neighbors: new Set(),
    };
  }
  const upstream =
    selected.type === "capability" ? capabilityUpstreamClosure(selected.id) : familyUpstreamClosure(selected.id);
  const downstream =
    selected.type === "capability" ? capabilityDownstreamClosure(selected.id) : familyDownstreamClosure(selected.id);
  upstream.delete(selected.id);
  downstream.delete(selected.id);
  return {
    upstream,
    downstream,
    neighbors: directNeighborIds(selected),
  };
}

function graphCapabilityIds(selected) {
  const filtered = getFilteredCapabilities();
  const ids = new Set(filtered.map((capability) => capability.id));

  filtered.forEach((capability) => {
    (capability.dependencies || []).forEach((dependencyId) => ids.add(dependencyId));
    (state.model.capabilityDependentsMap.get(capability.id) || []).forEach((dependentId) => ids.add(dependentId));
  });

  if (selected?.type === "capability") {
    capabilityUpstreamClosure(selected.id).forEach((id) => ids.add(id));
    capabilityDownstreamClosure(selected.id).forEach((id) => ids.add(id));
  }

  if (selected?.type === "family") {
    selected.children.forEach((child) => ids.add(child.id));
    familyUpstreamClosure(selected.id).forEach((familyId) => {
      state.model.familyMap.get(familyId)?.children.forEach((child) => ids.add(child.id));
    });
    familyDownstreamClosure(selected.id).forEach((familyId) => {
      state.model.familyMap.get(familyId)?.children.forEach((child) => ids.add(child.id));
    });
  }

  return ids;
}

function graphFamilyIds(graphCapabilitySet, selected) {
  const ids = new Set(state.model.families.map((family) => family.id));
  graphCapabilitySet.forEach((capabilityId) => {
    const capability = state.model.capabilityMap.get(capabilityId);
    if (capability) ids.add(capability.familyId);
  });
  if (selected?.type === "capability") {
    ids.add(selected.familyId);
  }
  if (selected?.type === "family") {
    familyUpstreamClosure(selected.id).forEach((id) => ids.add(id));
    familyDownstreamClosure(selected.id).forEach((id) => ids.add(id));
  }
  return ids;
}

function renderGraph() {
  const svg = elements.graphSvg;
  if (!svg || !state.model) return;

  const selected = selectedNode();
  const capabilityIds = graphCapabilityIds(selected);
  const familyIds = graphFamilyIds(capabilityIds, selected);
  const { positions, width, height } = graphLayout(capabilityIds);
  const relations = selectionRelations(selected);

  const familyEdges = [];
  const membershipEdges = [];
  const dependencyEdges = [];

  state.model.families.forEach((family) => {
    (family.dependencies || []).forEach((dependencyId) => {
      if (familyIds.has(family.id) && familyIds.has(dependencyId)) {
        familyEdges.push({ source: dependencyId, target: family.id, kind: "family-dependency" });
      }
    });
    family.children.forEach((child) => {
      if (capabilityIds.has(child.id)) {
        membershipEdges.push({ source: family.id, target: child.id, kind: "membership" });
      }
    });
  });

  state.model.capabilities.forEach((capability) => {
    if (!capabilityIds.has(capability.id)) return;
    (capability.dependencies || []).forEach((dependencyId) => {
      if (capabilityIds.has(dependencyId)) {
        dependencyEdges.push({ source: dependencyId, target: capability.id, kind: "dependency" });
      }
    });
  });

  svg.innerHTML = "";
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const root = document.createElementNS("http://www.w3.org/2000/svg", "g");
  root.setAttribute("transform", `translate(${state.graphOffsetX} ${state.graphOffsetY}) scale(${state.graphScale})`);

  const renderEdge = (edge) => {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) return;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const sourceOffset = edge.kind === "family-dependency" ? 120 : edge.kind === "membership" ? 100 : 88;
    const targetOffset = edge.kind === "family-dependency" ? 120 : 86;
    const controlOffset = edge.kind === "family-dependency" ? 200 : 160;
    const curve = `M ${source.x + sourceOffset} ${source.y} C ${source.x + controlOffset} ${source.y}, ${target.x - controlOffset} ${target.y}, ${target.x - targetOffset} ${target.y}`;
    path.setAttribute("d", curve);
    const classes = ["inspection-link"];
    if (edge.kind === "membership") classes.push("is-membership");
    if (edge.kind === "family-dependency") classes.push("is-family-dependency");

    if (selected) {
      const sourceInUpstream = relations.upstream.has(edge.source);
      const targetInUpstream = relations.upstream.has(edge.target);
      const sourceInDownstream = relations.downstream.has(edge.source);
      const targetInDownstream = relations.downstream.has(edge.target);
      const isNeighbor = edge.source === selected.id || edge.target === selected.id;

      const isUpstreamChain = sourceInUpstream && (targetInUpstream || edge.target === selected.id);
      const isDownstreamChain =
        (edge.source === selected.id && targetInDownstream) || (sourceInDownstream && targetInDownstream);

      if (isNeighbor) {
        classes.push("is-neighbor");
      } else if (isUpstreamChain) {
        classes.push("is-upstream");
      } else if (isDownstreamChain) {
        classes.push("is-downstream");
      } else if (
        selected.type === "family" &&
        edge.kind === "membership" &&
        (edge.source === selected.id || relations.neighbors.has(edge.target))
      ) {
        classes.push("is-neighbor");
      } else {
        classes.push("is-muted");
      }
    }

    path.setAttribute("class", classes.join(" "));
    root.appendChild(path);
  };

  [...familyEdges, ...membershipEdges, ...dependencyEdges].forEach(renderEdge);

  const renderNode = (node) => {
    const position = positions.get(node.id);
    if (!position) return;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const classes = ["inspection-node", node.type === "family" ? "is-family" : "is-capability"];
    if (selected?.id === node.id) {
      classes.push("is-selected");
    } else if (selected) {
      if (relations.upstream.has(node.id)) classes.push("is-upstream");
      else if (relations.downstream.has(node.id)) classes.push("is-downstream");
      else if (relations.neighbors.has(node.id)) classes.push("is-neighbor");
      else classes.push("is-muted");
    }

    group.setAttribute("transform", `translate(${position.x} ${position.y})`);
    group.setAttribute("class", classes.join(" "));
    group.addEventListener("click", () => {
      state.selectedId = node.id;
      renderAll();
    });

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", node.type === "family" ? "-118" : "-94");
    rect.setAttribute("y", node.type === "family" ? "-40" : "-34");
    rect.setAttribute("width", node.type === "family" ? "236" : "188");
    rect.setAttribute("height", node.type === "family" ? "80" : "68");
    rect.setAttribute("fill", colorForMaturity(node.maturity));
    rect.setAttribute("fill-opacity", node.type === "family" ? "0.22" : "0.15");
    rect.setAttribute("stroke", colorForMaturity(node.maturity));
    rect.setAttribute("stroke-width", "1.6");
    group.appendChild(rect);

    const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
    title.setAttribute("text-anchor", "middle");
    title.setAttribute("y", "-6");
    title.setAttribute("class", "inspection-node-label");
    title.textContent = truncate(node.label, node.type === "family" ? 28 : 22);
    group.appendChild(title);

    const meta = document.createElementNS("http://www.w3.org/2000/svg", "text");
    meta.setAttribute("text-anchor", "middle");
    meta.setAttribute("y", "18");
    meta.setAttribute("class", "inspection-node-meta");
    meta.textContent =
      node.type === "family"
        ? `${formatStatusLabel(node.maturity)} · ${scorePercent(node.score)}`
        : `${node.familyLabel} · ${formatStatusLabel(node.maturity)} · ${scorePercent(node.score)}`;
    group.appendChild(meta);

    root.appendChild(group);
  };

  state.model.families.filter((family) => familyIds.has(family.id)).forEach(renderNode);
  state.model.capabilities.filter((capability) => capabilityIds.has(capability.id)).forEach(renderNode);

  svg.appendChild(root);
  svg.classList.toggle("is-dragging", state.dragging);
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function renderHeatmap() {
  if (!elements.heatmap || !state.model) return;
  elements.heatmap.innerHTML = "";

  const header = document.createElement("div");
  header.className = "inspection-heatmap-header";
  header.innerHTML = `<span>Family</span>${MATURITY_ORDER.map((status) => `<span>${MATURITY_META[status].label}</span>`).join("")}`;
  elements.heatmap.appendChild(header);

  state.model.families.forEach((family) => {
    const capabilities = state.model.capabilities.filter(
      (capability) =>
        capability.familyId === family.id &&
        capabilityMatchesFilters(capability, {
          ignoreMaturity: true,
        })
    );

    const row = document.createElement("div");
    row.className = "inspection-heatmap-row";

    const familyButton = document.createElement("button");
    familyButton.className = "inspection-family-name inspection-matrix-cell";
    familyButton.innerHTML = `<strong>${family.label}</strong><small>${scorePercent(family.score)} readiness</small>`;
    familyButton.addEventListener("click", () => {
      state.selectedId = family.id;
      state.familyFilter = family.id;
      renderAll();
    });
    row.appendChild(familyButton);

    MATURITY_ORDER.forEach((status) => {
      const count = capabilities.filter((capability) => capability.maturity === status).length;
      const weightShare =
        capabilities.reduce((sum, capability) => {
          if (capability.maturity !== status) return sum;
          return sum + (capability.weight || 1);
        }, 0) / (capabilities.reduce((sum, capability) => sum + (capability.weight || 1), 0) || 1);
      const cell = document.createElement("button");
      const classes = ["inspection-matrix-cell"];
      if (count > 0) classes.push("has-data");
      if (state.familyFilter === family.id && state.maturityFilter === status) classes.push("is-active");
      cell.className = classes.join(" ");
      cell.style.background = count
        ? `linear-gradient(180deg, ${colorForMaturity(status)}${count > 1 ? "66" : "3d"}, rgba(9,18,27,0.92))`
        : "rgba(148, 163, 184, 0.04)";
      cell.innerHTML = count
        ? `<div><strong>${count}</strong><small>${Math.round(weightShare * 100)}% weight</small></div>`
        : "";
      cell.addEventListener("click", () => {
        state.familyFilter = family.id;
        state.maturityFilter = status;
        state.selectedId = family.children[0]?.id || family.id;
        renderAll();
      });
      row.appendChild(cell);
    });

    elements.heatmap.appendChild(row);
  });
}

function blockerScore(capability) {
  const downstreamCount = capabilityDownstreamClosure(capability.id).size - 1;
  const upstreamCount = capabilityUpstreamClosure(capability.id).size - 1;
  const gatePenalty = capability.battlefieldGate && !capability.gateSatisfied ? 0.32 : 0;
  const confidencePenalty = (4 - confidenceRank(capability.confidence)) * 0.03;
  return (
    (1 - capability.score) * criticalityFactor(capability.criticality) * (capability.weight || 1) +
    gatePenalty +
    downstreamCount * 0.04 +
    upstreamCount * 0.02 +
    confidencePenalty
  );
}

function leverageScore(capability) {
  const downstreamCount = capabilityDownstreamClosure(capability.id).size - 1;
  const gateLift = capability.battlefieldGate && !capability.gateSatisfied ? 0.35 : 0;
  return blockerScore(capability) + downstreamCount * 0.08 + gateLift;
}

function rankedBlockers() {
  return getFilteredCapabilities()
    .filter(
      (capability) =>
        capability.score < maturityValue("strong") || (capability.battlefieldGate && !capability.gateSatisfied)
    )
    .sort((left, right) => blockerScore(right) - blockerScore(left))
    .slice(0, 8);
}

function rankedLeverage() {
  return getFilteredCapabilities()
    .filter(
      (capability) =>
        capability.score < maturityValue("strong") || (capability.battlefieldGate && !capability.gateSatisfied)
    )
    .sort((left, right) => leverageScore(right) - leverageScore(left))
    .slice(0, 5);
}

function renderList(container, items, renderItem) {
  if (!container) return;
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<li><div class="inspection-empty-state">No items match the current inspection filters.</div></li>';
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.appendChild(renderItem(item));
    container.appendChild(li);
  });
}

function renderBlockers() {
  renderList(elements.blockerList, rankedBlockers(), (capability) => {
    const button = document.createElement("button");
    if (state.selectedId === capability.id) button.classList.add("is-selected");
    button.innerHTML = `
      <strong>${capability.label}</strong>
      <div class="inspection-helper">${capability.familyLabel} · ${formatStatusLabel(capability.maturity)} · ${scorePercent(
      capability.score
    )}</div>
      <div class="inspection-helper">${capability.blocker || capability.limitation}</div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = capability.id;
      renderAll();
    });
    return button;
  });
}

function renderGates() {
  if (!elements.gateList || !state.model) return;
  const relevantCapabilities = getFilteredCapabilities({ ignoreMaturity: true });
  const gates = relevantCapabilities
    .filter((capability) => capability.battlefieldGate && !capability.gateSatisfied)
    .sort((left, right) => {
      const leftRatio = left.score / left.battlefieldGate.requiredValue;
      const rightRatio = right.score / right.battlefieldGate.requiredValue;
      return leftRatio - rightRatio;
    })
    .slice(0, 6);

  renderList(elements.gateList, gates, (capability) => {
    const button = document.createElement("button");
    if (state.selectedId === capability.id) button.classList.add("is-selected");
    button.innerHTML = `
      <strong>${capability.label}</strong>
      <div class="inspection-helper">${capability.familyLabel} · current ${formatStatusLabel(
      capability.maturity
    )} · needs ${formatStatusLabel(capability.battlefieldGate.required_status)}</div>
      <div class="inspection-helper">${capability.battlefieldGate.rationale}</div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = capability.id;
      renderAll();
    });
    return button;
  });
}

function renderReadinessBars() {
  if (!elements.readinessBars || !state.model) return;
  elements.readinessBars.innerHTML = "";

  const families = state.model.families.filter(
    (family) => state.familyFilter === "all" || family.id === state.familyFilter || familyHasVisibleCapability(family.id, { ignoreMaturity: true })
  );

  families.forEach((family) => {
    const row = document.createElement("div");
    row.className = "inspection-detail-section";
    row.addEventListener("click", () => {
      state.selectedId = family.id;
      renderAll();
    });

    const gateCount = family.children.filter((child) => child.battlefieldGate && !child.gateSatisfied).length;
    row.innerHTML = `
      <div class="inspection-bar-row">
        <span class="inspection-bar-label">${family.label}</span>
        <div>
          <div class="inspection-bar-rail">
            <div class="inspection-bar-fill" style="width:${scorePercent(family.score)}%; background:${colorForMaturity(
      family.maturity
    )};"></div>
          </div>
          <div class="inspection-bar-annotation">${formatStatusLabel(family.maturity)} · ${
      gateCount ? `${gateCount} hard gate ${gateCount === 1 ? "issue" : "issues"}` : "no unresolved hard gates"
    }</div>
        </div>
        <strong>${scorePercent(family.score)}</strong>
      </div>
    `;
    elements.readinessBars.appendChild(row);
  });
}

function renderHighestLeverage() {
  renderList(elements.highestLeverage, rankedLeverage(), (capability) => {
    const button = document.createElement("button");
    if (state.selectedId === capability.id) button.classList.add("is-selected");
    button.innerHTML = `
      <strong>${capability.label}</strong>
      <div class="inspection-helper">${capability.familyLabel}</div>
      <div class="inspection-helper">${capability.recommended_next_step}</div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = capability.id;
      renderAll();
    });
    return button;
  });
}

function capabilityScoreSummary(capability) {
  if (capability.battlefieldGate && !capability.gateSatisfied) {
    return `This capability is below its hard battlefield gate because critical criteria remain under-supported relative to the required ${formatStatusLabel(
      capability.battlefieldGate.required_status
    )} level.`;
  }
  if (capability.score < maturityValue("substantial")) {
    return "This capability is structurally present but still too weak to support a trustworthy first-battlefield claim.";
  }
  if (capability.score < maturityValue("strong")) {
    return "This capability is materially implemented, but key criteria still remain only partial or bridge-state.";
  }
  return "This is one of the stronger current capabilities, though its strength still depends on weaker upstream layers.";
}

function familyScoreSummary(family) {
  if (family.unmetGateCount) {
    return `${family.unmetGateCount} child capability hard gate${family.unmetGateCount === 1 ? "" : "s"} still limit this family's honest readiness claim.`;
  }
  if (family.criticalWeakChildren) {
    return "This family is structurally present, but one or more critical child capabilities remain below substantial maturity.";
  }
  return "This family currently has no unresolved hard gate, but it still inherits broader scientific-core limits from the rest of the system.";
}

function renderSourceRefsSection(sourceRefs) {
  if (!sourceRefs?.length) {
    return `
      <div class="inspection-detail-section">
        <h4>Source References</h4>
        <div class="inspection-helper">No direct source references are recorded for this selection yet.</div>
      </div>
    `;
  }
  return `
    <div class="inspection-detail-section">
      <h4>Source References</h4>
      <div class="inspection-source-list">
        ${sourceRefs
          .map(
            (ref) => ref.url
              ? `
          <a class="inspection-source-link" href="${ref.url}" target="_blank" rel="noopener noreferrer">
            <strong>${ref.label || ref.path}</strong>
            <span>${ref.path}</span>
          </a>`
              : `
          <div class="inspection-source-link">
            <strong>${ref.label || ref.path}</strong>
            <span>${ref.path}</span>
          </div>`
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderCriterionInspectionSection(criterion) {
  const sourceLabel = criterion.status_source === "repo_inspected" ? "Repo inspected" : "Seeded";
  const evidenceLines = criterion.repo_inspection_evidence || [];
  const missingLines = criterion.repo_inspection_missing || [];
  return `
    <div class="inspection-helper"><strong>Assessment source:</strong> ${sourceLabel}${
      criterion.manifest_status ? ` · manifest ${formatStatusLabel(criterion.manifest_status)}` : ""
    }</div>
    <div class="inspection-helper"><strong>Inspection summary:</strong> ${
      criterion.repo_inspection_summary || "No repo inspection summary recorded."
    }</div>
    ${
      evidenceLines.length
        ? `<div class="inspection-helper"><strong>Confirmed in source:</strong> ${evidenceLines.join("; ")}</div>`
        : ""
    }
    ${
      missingLines.length
        ? `<div class="inspection-helper"><strong>Not confirmed:</strong> ${missingLines.join("; ")}</div>`
        : ""
    }
  `;
}

function renderRecentChangeSection(changes) {
  if (!changes?.length) {
    return `
      <div class="inspection-detail-section">
        <h4>Recent Change Signal</h4>
        <div class="inspection-helper">No recent tracked changes are currently attached to this selection.</div>
      </div>
    `;
  }
  return `
    <div class="inspection-detail-section">
      <h4>Recent Change Signal</h4>
      <ul class="inspection-impact-list">
        ${changes
          .map(
            (change) => `
          <li>
            <strong>${change.subject || "Repository change"}</strong>
            <div class="inspection-helper">${change.commit_short || ""} · ${change.committed_on || ""} · ${
              change.author || ""
            }</div>
          </li>`
          )
          .join("")}
      </ul>
    </div>
  `;
}

function renderCapabilityDetail(capability) {
  const directDependents = (state.model.capabilityDependentsMap.get(capability.id) || [])
    .map((id) => state.model.capabilityMap.get(id))
    .filter(Boolean);
  const directDependencies = (capability.dependencies || [])
    .map((id) => state.model.capabilityMap.get(id))
    .filter(Boolean);
  const gateHtml =
    capability.battlefieldGate && !capability.gateSatisfied
      ? `<div class="inspection-detail-section"><h4>Hard Battlefield Gate</h4><p class="inspection-detail-copy">${capability.battlefieldGate.rationale}</p><p class="inspection-gate-note">Current ${formatStatusLabel(
          capability.maturity
        )} (${scorePercent(capability.score)}), required ${formatStatusLabel(
          capability.battlefieldGate.required_status
        )}.</p></div>`
      : capability.battlefieldGate
      ? `<div class="inspection-detail-section"><h4>Hard Battlefield Gate</h4><p class="inspection-detail-copy">This capability currently satisfies its hard battlefield gate at ${formatStatusLabel(
          capability.battlefieldGate.required_status
        )} or better.</p></div>`
      : "";

  elements.detailPanel.innerHTML = `
    <div class="inspection-detail-grid">
      <div>
        <p class="eyebrow">${capability.familyLabel}</p>
        <h3 class="inspection-detail-title">${capability.label}</h3>
        <p class="inspection-detail-copy">${capability.description}</p>
      </div>
      <div class="inspection-detail-pills">
        ${createStatusBadge(capability.maturity)}
        <span class="inspection-chip ${capability.criticality === "critical" ? "is-critical" : ""}">Criticality ${capability.criticality}</span>
        <span class="inspection-chip">Confidence ${capability.confidence}</span>
        <span class="inspection-chip">Readiness ${scorePercent(capability.score)}</span>
        ${
          capability.battlefieldGate
            ? `<span class="inspection-chip is-gate">Gate ${formatStatusLabel(capability.battlefieldGate.required_status)}</span>`
            : ""
        }
      </div>
      <div class="inspection-stat-grid">
        <article class="inspection-stat-card">
          <strong>Current State</strong>
          <div class="inspection-helper">${capability.current_evidence}</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Target State</strong>
          <div class="inspection-helper">${capability.target_state}</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Score Rationale</strong>
          <div class="inspection-helper">${capabilityScoreSummary(capability)}</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Dependency Pressure</strong>
          <div class="inspection-helper">${directDependencies.length} direct prerequisite${
    directDependencies.length === 1 ? "" : "s"
  } and ${directDependents.length} direct downstream dependent${directDependents.length === 1 ? "" : "s"}.</div>
        </article>
      </div>
      <div class="inspection-definition-grid">
        <article class="inspection-definition-card">
          <strong>Why It Matters</strong>
          <div class="inspection-helper">${capability.why_it_matters}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Current Implementation Basis</strong>
          <div class="inspection-helper">${capability.implementation_basis}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Current Limitation / Blocker</strong>
          <div class="inspection-helper">${capability.blocker || capability.limitation}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Recommended Next Move</strong>
          <div class="inspection-helper">${capability.recommended_next_step}</div>
        </article>
      </div>
      ${gateHtml}
      ${renderSourceRefsSection(capability.source_refs)}
      ${renderRecentChangeSection(capability.recent_changes)}
      <div class="inspection-detail-section">
        <h4>Measured Criteria</h4>
        <div class="inspection-criteria-grid">
          ${capability.criteria
            .map(
              (criterion) => `
            <article class="inspection-criteria-card">
              <div class="inspection-criteria-meta">
                ${createStatusBadge(criterion.status)}
                ${criterion.critical ? '<span class="inspection-chip is-critical">Critical criterion</span>' : ""}
                <span class="inspection-chip">Weight ${Number(criterion.weight || 1).toFixed(1)}</span>
                <span class="inspection-chip">${criterion.status_source === "repo_inspected" ? "Repo inspected" : "Seeded"}</span>
              </div>
              <strong>${criterion.label}</strong>
              <p class="inspection-criteria-copy">${criterion.measurement_basis}</p>
              <div class="inspection-helper"><strong>Current evidence:</strong> ${criterion.current_evidence}</div>
              <div class="inspection-helper"><strong>Current gap:</strong> ${criterion.gap || "No explicit gap recorded."}</div>
              ${renderCriterionInspectionSection(criterion)}
            </article>`
            )
            .join("")}
        </div>
      </div>
    </div>
  `;
}

function renderFamilyDetail(family) {
  const weakestChildren = [...family.children].sort((left, right) => left.score - right.score);
  elements.detailPanel.innerHTML = `
    <div class="inspection-detail-grid">
      <div>
        <p class="eyebrow">${family.category === "scientific_core" ? "Scientific-Core Family" : "Surface / Governance Family"}</p>
        <h3 class="inspection-detail-title">${family.label}</h3>
        <p class="inspection-detail-copy">${family.description}</p>
      </div>
      <div class="inspection-detail-pills">
        ${createStatusBadge(family.maturity)}
        <span class="inspection-chip ${family.criticality === "critical" ? "is-critical" : ""}">Criticality ${family.criticality}</span>
        <span class="inspection-chip">Confidence ${family.confidence}</span>
        <span class="inspection-chip">Readiness ${scorePercent(family.score)}</span>
      </div>
      <div class="inspection-stat-grid">
        <article class="inspection-stat-card">
          <strong>Target State</strong>
          <div class="inspection-helper">${family.target_state}</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Family Score Rationale</strong>
          <div class="inspection-helper">${familyScoreSummary(family)}</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Critical Weak Children</strong>
          <div class="inspection-helper">${family.criticalWeakChildren} critical child capability${
    family.criticalWeakChildren === 1 ? "" : "s"
  } currently fall below substantial readiness.</div>
        </article>
        <article class="inspection-stat-card">
          <strong>Unmet Hard Gates</strong>
          <div class="inspection-helper">${family.unmetGateCount} child gate${
    family.unmetGateCount === 1 ? "" : "s"
  } are still unsatisfied inside this family.</div>
        </article>
      </div>
      <div class="inspection-definition-grid">
        <article class="inspection-definition-card">
          <strong>Why It Matters</strong>
          <div class="inspection-helper">${family.why_it_matters}</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Family Dependencies</strong>
          <div class="inspection-helper">${
            family.dependencies.length
              ? family.dependencies
                  .map((dependencyId) => state.model.familyMap.get(dependencyId)?.label || dependencyId)
                  .join(", ")
              : "No recorded upstream family dependency."
          }</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Most Constraining Child</strong>
          <div class="inspection-helper">${
            weakestChildren[0]
              ? `${weakestChildren[0].label}: ${weakestChildren[0].blocker || weakestChildren[0].limitation}`
              : "No child capability recorded."
          }</div>
        </article>
        <article class="inspection-definition-card">
          <strong>Recommended Next Move</strong>
          <div class="inspection-helper">${
            weakestChildren[0]?.recommended_next_step || "No next move recorded."
          }</div>
        </article>
      </div>
      <div class="inspection-detail-section">
        <h4>Capability Breakdown</h4>
        <div class="inspection-capability-breakdown">
          ${family.children
            .map(
              (child) => `
            <article class="inspection-capability-card">
              <div class="inspection-criteria-meta">
                ${createStatusBadge(child.maturity)}
                ${child.battlefieldGate ? '<span class="inspection-chip is-gate">Hard gate</span>' : ""}
              </div>
              <h5>${child.label}</h5>
              <div class="inspection-helper">${child.current_evidence}</div>
              <div class="inspection-helper"><strong>Blocker:</strong> ${child.blocker || child.limitation}</div>
            </article>`
            )
            .join("")}
        </div>
      </div>
      ${renderSourceRefsSection(family.source_refs)}
      ${renderRecentChangeSection(family.recent_changes)}
    </div>
  `;
}

function renderDetailPanel() {
  const selected = selectedNode();
  if (!elements.detailPanel || !selected) return;
  if (selected.type === "family") {
    renderFamilyDetail(selected);
  } else {
    renderCapabilityDetail(selected);
  }
  renderDependencyChain(selected);
  renderDownstreamImpact(selected);
}

function renderDependencyChain(selected) {
  if (!elements.dependencyChain || !selected) return;
  elements.dependencyChain.innerHTML = "";

  const direct =
    selected.type === "capability"
      ? (selected.dependencies || []).map((id) => state.model.capabilityMap.get(id)).filter(Boolean)
      : (selected.dependencies || []).map((id) => state.model.familyMap.get(id)).filter(Boolean);
  const closure =
    selected.type === "capability"
      ? Array.from(capabilityUpstreamClosure(selected.id))
      : Array.from(familyUpstreamClosure(selected.id));
  const extended = closure.filter((id) => id !== selected.id && !direct.some((item) => item.id === id));
  const extendedNodes = extended.map((id) => getNodeById(id)).filter(Boolean);

  if (!direct.length && !extendedNodes.length) {
    elements.dependencyChain.innerHTML =
      '<div class="inspection-empty-state">No upstream dependency chain is recorded for the current selection.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  if (direct.length) {
    const directWrap = document.createElement("div");
    directWrap.className = "inspection-detail-section";
    directWrap.innerHTML = "<h4>Direct prerequisites</h4>";
    const chips = document.createElement("div");
    chips.className = "inspection-dependency-map";
    direct.forEach((item) => {
      const button = document.createElement("button");
      button.textContent = item.label;
      button.addEventListener("click", () => {
        state.selectedId = item.id;
        renderAll();
      });
      chips.appendChild(button);
    });
    directWrap.appendChild(chips);
    fragment.appendChild(directWrap);
  }

  if (extendedNodes.length) {
    const extendedWrap = document.createElement("div");
    extendedWrap.className = "inspection-detail-section";
    extendedWrap.innerHTML = "<h4>Extended upstream chain</h4>";
    const chips = document.createElement("div");
    chips.className = "inspection-dependency-map is-vertical";
    extendedNodes.forEach((item) => {
      const button = document.createElement("button");
      button.textContent = item.label;
      button.addEventListener("click", () => {
        state.selectedId = item.id;
        renderAll();
      });
      chips.appendChild(button);
    });
    extendedWrap.appendChild(chips);
    fragment.appendChild(extendedWrap);
  }

  elements.dependencyChain.appendChild(fragment);
}

function renderDownstreamImpact(selected) {
  if (!elements.downstreamImpact || !selected) return;
  elements.downstreamImpact.innerHTML = "";

  const direct =
    selected.type === "capability"
      ? (state.model.capabilityDependentsMap.get(selected.id) || [])
          .map((id) => state.model.capabilityMap.get(id))
          .filter(Boolean)
      : (state.model.familyDependentsMap.get(selected.id) || [])
          .map((id) => state.model.familyMap.get(id))
          .filter(Boolean);
  const closure =
    selected.type === "capability"
      ? Array.from(capabilityDownstreamClosure(selected.id))
      : Array.from(familyDownstreamClosure(selected.id));
  const extended = closure.filter((id) => id !== selected.id && !direct.some((item) => item.id === id));
  const extendedNodes = extended.map((id) => getNodeById(id)).filter(Boolean);

  if (!direct.length && !extendedNodes.length) {
    elements.downstreamImpact.innerHTML =
      '<div class="inspection-empty-state">No downstream impact chain is recorded for the current selection.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  if (direct.length) {
    const directList = document.createElement("ul");
    directList.className = "inspection-impact-list";
    direct.forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${item.label}</strong><div class="inspection-helper">${
        item.recommended_next_step || item.blocker || item.description
      }</div>`;
      directList.appendChild(li);
    });
    const section = document.createElement("div");
    section.className = "inspection-detail-section";
    section.innerHTML = "<h4>Immediate downstream pressure</h4>";
    section.appendChild(directList);
    fragment.appendChild(section);
  }

  if (extendedNodes.length) {
    const extendedList = document.createElement("ul");
    extendedList.className = "inspection-impact-list";
    extendedNodes.forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${item.label}</strong><div class="inspection-helper">${
        item.type === "family" ? item.description : item.recommended_next_step || item.blocker || item.description
      }</div>`;
      extendedList.appendChild(li);
    });
    const section = document.createElement("div");
    section.className = "inspection-detail-section";
    section.innerHTML = "<h4>Extended downstream chain</h4>";
    section.appendChild(extendedList);
    fragment.appendChild(section);
  }

  elements.downstreamImpact.appendChild(fragment);
}

function syncFilters() {
  if (elements.familyFilter) elements.familyFilter.value = state.familyFilter;
  if (elements.maturityFilter) elements.maturityFilter.value = state.maturityFilter;
  if (elements.scopeFilter) elements.scopeFilter.value = state.scopeFilter;
  if (elements.searchInput) elements.searchInput.value = state.search;
}

function populateFamilyOptions() {
  if (!elements.familyFilter) return;
  const previous = elements.familyFilter.value;
  elements.familyFilter.innerHTML = '<option value="all">All families</option>';
  baseModel().families.forEach((family) => {
    const option = document.createElement("option");
    option.value = family.id;
    option.textContent = family.label;
    elements.familyFilter.appendChild(option);
  });
  if (previous) {
    elements.familyFilter.value = previous;
  }
}

function ensureValidSelection() {
  const selected = selectedNode();
  if (selected) return;
  const next =
    rankedBlockers()[0] ||
    rankedLeverage()[0] ||
    getFilteredCapabilities()[0] ||
    state.model.capabilities[0] ||
    state.model.families[0];
  state.selectedId = next?.id || "";
}

function renderAll() {
  state.model = buildInspectionModel();
  ensureValidSelection();
  syncFilters();
  renderProvenance();
  renderScorecards();
  renderGraph();
  renderHeatmap();
  renderBlockers();
  renderGates();
  renderReadinessBars();
  renderHighestLeverage();
  renderRecentChanges();
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
    state.graphScale = Math.max(0.62, Math.min(2.1, Number((state.graphScale + delta).toFixed(2))));
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
    state.familyFilter = String(event.target.value || "all");
    renderAll();
  });
  elements.maturityFilter?.addEventListener("change", (event) => {
    state.maturityFilter = String(event.target.value || "all");
    renderAll();
  });
  elements.scopeFilter?.addEventListener("change", (event) => {
    state.scopeFilter = String(event.target.value || "all");
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
    state.graphScale = Math.min(2.1, Number((state.graphScale + 0.1).toFixed(2)));
    renderGraph();
  });
  elements.graphZoomOut?.addEventListener("click", () => {
    state.graphScale = Math.max(0.62, Number((state.graphScale - 0.1).toFixed(2)));
    renderGraph();
  });
}

async function init() {
  state.snapshot = await loadInspectionSnapshot();
  populateFamilyOptions();
  bindControls();
  bindGraphInteractions();
  state.model = buildInspectionModel();
  state.selectedId = rankedBlockers()[0]?.id || state.model.capabilities[0]?.id || "";
  renderAll();
}

init();
