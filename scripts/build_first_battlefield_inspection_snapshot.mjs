#!/usr/bin/env node

import { copyFileSync, existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const dataModulePath = path.join(repoRoot, "docs", "assets", "first-battlefield-inspection-data.js");
const outputPath = path.join(repoRoot, "docs", "assets", "first-battlefield-inspection.snapshot.json");
const fileTextCache = new Map();

function git(args) {
  return execFileSync("git", args, {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function normalizeRemote(value) {
  if (!value) return "";
  if (value.startsWith("git@github.com:")) {
    return `https://github.com/${value.slice("git@github.com:".length).replace(/\.git$/, "")}`;
  }
  if (value.startsWith("https://github.com/") || value.startsWith("http://github.com/")) {
    return value.replace(/\.git$/, "").replace(/^http:\/\//, "https://");
  }
  return "";
}

function parseGitLog(output) {
  return output
    .split("\x1e")
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const [commit_sha, commit_short, committed_on, author, subject] = chunk.split("\x1f");
      return {
        commit_sha,
        commit_short,
        committed_on,
        author,
        subject,
      };
    });
}

function gitLogForPaths(paths, limit = 5) {
  const cleaned = Array.from(new Set((paths || []).filter(Boolean)));
  if (!cleaned.length) {
    return [];
  }
  try {
    const output = execFileSync(
      "git",
      [
        "log",
        `-n${limit}`,
        "--date=short",
        "--pretty=format:%H%x1f%h%x1f%ad%x1f%an%x1f%s%x1e",
        "--",
        ...cleaned,
      ],
      {
        cwd: repoRoot,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      }
    );
    return parseGitLog(output);
  } catch {
    return [];
  }
}

function dedupeSourceRefs(refs) {
  const seen = new Set();
  const result = [];
  for (const ref of refs || []) {
    const key = `${ref.path}::${ref.label || ""}`;
    if (!ref.path || seen.has(key)) continue;
    seen.add(key);
    result.push(ref);
  }
  return result;
}

function fileText(relativePath) {
  if (!fileTextCache.has(relativePath)) {
    const absolutePath = path.join(repoRoot, relativePath);
    fileTextCache.set(relativePath, existsSync(absolutePath) ? readFileSync(absolutePath, "utf8") : "");
  }
  return fileTextCache.get(relativePath) || "";
}

function hasText(relativePath, needle) {
  return fileText(relativePath).includes(needle);
}

function check(relativePath, needle, description) {
  return {
    path: relativePath,
    needle,
    description,
  };
}

function evaluateAll(checks) {
  const evidence = [];
  const missing = [];
  for (const item of checks) {
    if (hasText(item.path, item.needle)) {
      evidence.push(`${item.description} (${item.path})`);
    } else {
      missing.push(`${item.description} (${item.path})`);
    }
  }
  return {
    passed: missing.length === 0,
    evidence,
    missing,
  };
}

function rule(result) {
  return result;
}

const CRITERION_REPO_RULES = {
  "persist-structured-goal": rule({
    checks: [
      check("system/scientific_state/contracts.py", "class MaterialGoalSpecificationRecord", "MaterialGoalSpecification contract exists"),
      check("system/services/material_goal_service.py", '"requirement_status": requirement_status', "Goal service writes requirement sufficiency into the structured record"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found a first-class MaterialGoalSpecification contract plus goal-intake shaping that writes requirement status into the structured goal.",
      gap: "Historical goal revision lineage is still not first-class.",
    },
    onFail: {
      status: "minimal",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected persisted goal structure in the current source footprint.",
      gap: "Material-goal persistence/source linkage needs repair before this can be considered strong.",
    },
  }),
  "session-continuity-goal": rule({
    checks: [
      check("system/services/scientific_session_projection_service.py", "_material_goal_summary", "Projection service still builds a material-goal summary"),
      check("tests/test_scientific_session_projection.py", "test_scientific_session_projection_surfaces_material_goal_answer_decision_for_session_reopen", "Projection continuity test covers session reopen"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found material-goal projection shaping plus a session-reopen test covering the first-battlefield projection path.",
      gap: "Continuity is still recomputed rather than historically versioned.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection did not find the expected projection/test continuity footprint for structured goals.",
      gap: "Session reopen continuity for the material goal path is no longer strongly evidenced in source.",
    },
  }),
  "explicit-battlefield-scope": rule({
    checks: [
      check("system/services/material_goal_service.py", '"domain_scope": "polymer_material"', "Goal service fixes the domain scope to polymer_material"),
      check("system/scientific_state/contracts.py", 'domain_scope: str = "polymer_material"', "Material-goal contract defaults to polymer_material"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found explicit polymer_material scope in both the goal service and the persisted contract shape.",
      gap: "Subdomain semantics are still bounded and bridge-state.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm explicit battlefield scoping in both the service and contract layers.",
      gap: "Domain bounding may have drifted away from the fixed first battlefield.",
    },
  }),
  "dimension-presence": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", '("desired_properties", "Target properties / performance requirements", True)', "Support trace config includes desired properties"),
      check("system/services/material_goal_support_trace_service.py", '("operating_environment", "Environment compatibility", True)', "Support trace config includes operating environment"),
      check("system/services/material_goal_support_trace_service.py", '("lifecycle_window", "Lifecycle / degradation context", True)', "Support trace config includes lifecycle"),
      check("system/services/material_goal_support_trace_service.py", '("target_material_function", "Target material function", True)', "Support trace config includes target material function"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found explicit first-battlefield requirement dimensions in the support-trace layer.",
      gap: "Richer second-order material semantics are still not present.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection did not find the full expected first-battlefield dimension set in the trace layer.",
      gap: "Requirement dimensions may have drifted or become incomplete.",
    },
  }),
  "dimension-propagation": rule({
    checks: [
      check("system/services/material_goal_retrieval_service.py", "query_summary = _query_summary(goal_spec)", "Retrieval consumes structured goal dimensions"),
      check("system/services/material_goal_support_trace_service.py", "for requirement_key, requirement_label, critical in _dimension_config()", "Support trace iterates the dimension set"),
      check("system/services/material_goal_coverage_service.py", '"primary_substrate": "material_goal_support_trace"', "Coverage is built from the support trace"),
      check("system/services/material_goal_answer_service.py", "coverage_result: dict[str, Any] | None = None,", "Answer service consumes coverage output"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found the dimension structure propagating through retrieval, support trace, coverage, and answer decision layers.",
      gap: "Propagation still depends on bridge-state matching semantics rather than a richer ontology.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm end-to-end dimension propagation across the main first-battlefield services.",
      gap: "Structured requirement flow appears incomplete or drifted.",
    },
  }),
  "sufficiency-status": rule({
    checks: [
      check("system/services/material_goal_service.py", 'requirement_status = "sufficiently_specified" if not missing else "insufficient_needs_clarification"', "Goal service computes sufficiency status explicitly"),
      check("system/scientific_state/contracts.py", 'requirement_status: str = "insufficient_needs_clarification"', "Contract stores requirement status explicitly"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found explicit requirement sufficiency computation and storage in the material-goal path.",
      gap: "Finer-grained insufficiency semantics remain limited.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm explicit sufficiency computation plus storage in the current source footprint.",
      gap: "Requirement sufficiency handling may no longer be explicit enough.",
    },
  }),
  "critical-gaps-block-flow": rule({
    checks: [
      check("tests/test_scientific_session_projection.py", "test_material_goal_retrieval_blocks_when_goal_is_not_sufficiently_specified", "Test covers retrieval blocking on insufficient goals"),
      check("system/services/material_goal_answer_service.py", '_clean_text(goal_spec.get("requirement_status")) == "sufficiently_specified"', "Answer service requires sufficiently specified goals"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found both source logic and tests confirming that insufficient goals do not flow into answer promotion.",
      gap: "Blocking logic is still bounded to current first-battlefield semantics.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection did not find the expected source-and-test evidence for blocking insufficient goals.",
      gap: "Flow blocking around critical insufficiencies may be weaker than the manifest suggests.",
    },
  }),
  "environment-gap-detection": rule({
    checks: [
      check("system/services/material_goal_service.py", "environment", "Goal service contains environment-sensitive missing-constraint logic"),
      check("system/services/material_goal_service.py", "_clarification_questions", "Goal service builds clarification questions from missing constraints"),
    ],
    onPass: {
      status: "strong",
      confidence: "medium",
      current_evidence: "Repo inspection found environment-sensitive missing-constraint and clarification logic in the goal service.",
      gap: "Environment semantics remain bounded and phrase-driven.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected environment-related clarification logic.",
      gap: "Environment-gap detection may have drifted from the intended battlefield path.",
    },
  }),
  "lifecycle-trigger-safety-gaps": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", "weak_lifecycle_match", "Lifecycle gap code exists"),
      check("system/services/material_goal_support_trace_service.py", "weak_trigger_match", "Trigger gap code exists"),
      check("system/services/material_goal_support_trace_service.py", "safety_or_regulatory_gap", "Safety/regulatory gap code exists"),
    ],
    onPass: {
      status: "strong",
      confidence: "medium",
      current_evidence: "Repo inspection found explicit lifecycle, trigger, and safety gap categories in the first-battlefield support-trace path.",
      gap: "Detection remains bounded and still depends on current dimension semantics.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected lifecycle/trigger/safety gap footprint.",
      gap: "These missing-constraint categories may no longer be consistently surfaced.",
    },
  }),
  "explicit-retrieval-sufficiency": rule({
    checks: [
      check("system/services/material_goal_retrieval_service.py", 'retrieval_sufficiency="no_grounded_evidence"', "Retrieval emits no_grounded_evidence"),
      check("system/services/material_goal_retrieval_service.py", 'sufficiency = "weak_partial_evidence"', "Retrieval emits weak_partial_evidence"),
      check("system/services/material_goal_retrieval_service.py", 'sufficiency = "candidate_directions_available"', "Retrieval emits candidate_directions_available"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found explicit retrieval sufficiency states in the retrieval service.",
      gap: "These states still summarize a relatively thin evidence basis.",
    },
    onFail: {
      status: "minimal",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected explicit retrieval sufficiency states.",
      gap: "Retrieval may no longer expose an honest sufficiency boundary.",
    },
  }),
  "honest-thin-retrieval-surfacing": rule({
    checks: [
      check("tests/test_scientific_session_projection.py", "test_material_goal_retrieval_surfaces_weak_partial_evidence_without_claiming_answer", "Tests cover weak_partial_evidence surfacing"),
      check("tests/test_scientific_session_projection.py", "test_material_goal_answer_decision_does_not_fabricate_answer_from_weak_partial_evidence", "Tests cover no fabricated answer from weak partial evidence"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found tests explicitly covering weak-partial retrieval surfacing and answer withholding.",
      gap: "This honesty still depends on the upstream retrieval layer staying disciplined.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected weak-retrieval non-promotion tests.",
      gap: "Thin retrieval may no longer be as explicitly guarded as intended.",
    },
  }),
  "trace-basis-explicit": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", "matched_support_lines=", "Support trace records matched support lines"),
      check("system/services/material_goal_support_trace_service.py", "uncovered_requirement_terms=", "Support trace records uncovered terms"),
      check("system/services/material_goal_support_trace_service.py", "contradiction_indicators=", "Support trace records contradiction indicators"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found explicit support, uncovered-term, and contradiction fields inside the support-trace service output.",
      gap: "Trace provenance is still limited by the richness of the underlying evidence lines.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected explicit support-trace fields in the current source footprint.",
      gap: "Support trace explicitness may have regressed.",
    },
  }),
  "observed-vs-indirect-distinction": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", '_clean_text(line.get("evidence_kind")) == "observed"', "Support trace separates observed evidence lines"),
      check("system/services/material_goal_support_trace_service.py", "indirect.append(line)", "Support trace preserves indirect support lines"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found explicit observed-versus-indirect separation in the support-trace service.",
      gap: "The distinction is explicit, but the evidence basis itself remains bridge-state.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected observed-versus-indirect split in the support-trace logic.",
      gap: "Dimension support quality may no longer be differentiated cleanly.",
    },
  }),
  "coverage-derived-from-trace": rule({
    checks: [
      check("system/services/material_goal_coverage_service.py", '"primary_substrate": "material_goal_support_trace"', "Coverage provenance records the support trace as its substrate"),
      check("system/services/material_goal_coverage_service.py", 'status = _clean_text(trace_item.get("support_status"), default="unknown")', "Coverage derives status from trace items"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found coverage explicitly consuming the support trace as its primary substrate.",
      gap: "Coverage still inherits bridge-state limits from the trace beneath it.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm that coverage still derives primarily from support traces.",
      gap: "Coverage may have drifted back toward coarser summary logic.",
    },
  }),
  "trace-linked-contradictions": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", "def _dimension_contradictions(", "Support trace contains dimension contradiction attribution logic"),
      check("system/services/material_goal_support_trace_service.py", '"contradiction_attribution": "dimension_specific"', "Support trace provenance distinguishes contradiction attribution mode"),
    ],
    onPass: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection found explicit dimension contradiction attribution logic plus provenance about whether attribution is dimension-specific or coarse.",
      gap: "Contradiction objects are still not richly dimension-tagged.",
    },
    onFail: {
      status: "minimal",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected contradiction-to-dimension linkage logic in the support-trace layer.",
      gap: "Contradiction traceability may have regressed materially.",
    },
  }),
  "unknowns-derived-from-coverage": rule({
    checks: [
      check("system/services/material_goal_answer_service.py", "def _collect_unknowns_from_trace(", "Answer service derives unknowns from trace/coverage structure"),
      check("system/services/material_goal_answer_service.py", 'unknowns = list(_as_list(coverage_result.get("critical_unknowns")))', "Answer service starts unknowns from coverage critical unknowns"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found explicit derivation of unknowns from coverage and support-trace structure.",
      gap: "Unknown typing and prioritization are still first-version.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected trace/coverage-based unknown derivation path.",
      gap: "Unknowns may no longer be as directly tied to current requirement gaps.",
    },
  }),
  "unknown-codes-are-machine-readable": rule({
    checks: [
      check("system/services/material_goal_support_trace_service.py", "gap_codes=gap_codes", "Support trace emits machine-readable gap codes"),
      check("system/services/material_goal_answer_service.py", '"request_mode": "bounded_first_battlefield_answer_gap_closure"', "Answer request payload keeps structured provenance"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found machine-readable gap codes and structured answer-gap request payloads in the current source.",
      gap: "The ontology remains intentionally bounded.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected machine-readable unknown/gap output structure.",
      gap: "Structured insufficiency signaling may be weaker than the manifest suggests.",
    },
  }),
  "coverage-primary-gate": rule({
    checks: [
      check("system/services/material_goal_answer_service.py", "coverage_result: dict[str, Any] | None = None,", "Answer service accepts explicit coverage input"),
      check("system/services/material_goal_answer_service.py", "supported_critical = [item for item in critical_items if _clean_text(item.get(\"status\")) == \"supported\"]", "Answer service gates on critical coverage status"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found answer logic explicitly gating on critical coverage outcomes.",
      gap: "The gate is meaningful now, but upstream evidence depth still limits answerability.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm that answer logic still uses coverage as an explicit primary gate.",
      gap: "Answer decision may have drifted back toward shallower heuristics.",
    },
  }),
  "unsupported-answers-withheld": rule({
    checks: [
      check("tests/test_scientific_session_projection.py", "test_material_goal_answer_decision_does_not_fabricate_answer_from_weak_partial_evidence", "Tests cover no fabricated answer from weak partial evidence"),
      check("tests/test_scientific_session_projection.py", "test_material_goal_answer_decision_requires_coverage_of_critical_dimensions", "Tests cover critical-dimension blocking"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found tests explicitly covering answer withholding for weak evidence and uncovered critical dimensions.",
      gap: "Withholding is only as strong as the upstream traces that feed it.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection did not find the expected source-linked tests for withholding weak or under-covered answers.",
      gap: "Answer restraint may be less well-defended than intended.",
    },
  }),
  "follow-up-only-when-insufficient": rule({
    checks: [
      check("tests/test_scientific_session_projection.py", 'self.assertEqual(decision["required_additional_data"], [])', "Tests assert no extra data requests when an answer is supportable"),
      check("tests/test_scientific_session_projection.py", 'self.assertEqual(decision["required_experiments"], [])', "Tests assert no experiment requests when an answer is supportable"),
      check("tests/test_scientific_session_projection.py", 'self.assertTrue(decision["required_additional_data"] or decision["required_experiments"])', "Tests assert requests appear in insufficient cases"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found tests covering the boundary between no requests in supported cases and requests in insufficient cases.",
      gap: "Request specificity and prioritization remain first-version.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected tests around when additional requests should appear.",
      gap: "The request boundary may no longer be as explicitly guarded.",
    },
  }),
  "follow-up-linked-to-gap": rule({
    checks: [
      check("system/services/material_goal_answer_service.py", '"linked_unknowns": linked_unknowns,', "Answer requests preserve linked unknowns"),
      check("system/services/material_goal_answer_service.py", '"contradiction_resolving_experiment"', "Answer service emits contradiction-linked experiment requests"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found answer requests carrying linked unknowns and specific insufficiency-closing request kinds.",
      gap: "The mapping is structured but still bounded in specificity.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm linked-unknown request shaping in the current answer service source.",
      gap: "Follow-up requests may no longer be tightly coupled to the triggering insufficiency.",
    },
  }),
  "projection-includes-first-battlefield-state": rule({
    checks: [
      check("system/services/scientific_session_projection_service.py", '"material_goal_support_trace": material_goal_support_trace,', "Projection includes support trace"),
      check("system/services/scientific_session_projection_service.py", '"material_goal_coverage": material_goal_coverage,', "Projection includes coverage"),
      check("system/services/scientific_session_projection_service.py", '"material_goal_answer_decision": material_goal_answer_decision,', "Projection includes answer decision"),
      check("tests/test_scientific_session_projection.py", 'self.assertIn("material_goal_answer_decision", projection)', "Tests assert answer decision is projected"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found the projected first-battlefield state stack in source and in projection tests.",
      gap: "Historical diffing across policy revisions is still limited.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the full projected first-battlefield state stack in source and tests.",
      gap: "Session reopen continuity may be weaker than the manifest suggests.",
    },
  }),
  "overview-to-detail-navigation": rule({
    checks: [
      check("docs/first-battlefield-inspection.html", 'id="inspection-graph"', "Inspection page includes the capability graph"),
      check("docs/first-battlefield-inspection.html", 'id="inspection-detail-panel"', "Inspection page includes the detail inspector"),
      check("docs/assets/first-battlefield-inspection.js", "function renderDetailPanel()", "Page JS renders selection-driven detail"),
    ],
    onPass: {
      status: "strong",
      confidence: "high",
      current_evidence: "Repo inspection found linked overview and detail surfaces in the page shell and runtime.",
      gap: "Audit depth is still growing, but the overview-to-detail path is explicit.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm the expected overview-to-detail inspection path in the current page source.",
      gap: "The inspection surface may have lost part of its multi-level navigation.",
    },
  }),
  "linked-view-coherence": rule({
    checks: [
      check("docs/assets/first-battlefield-inspection.js", "renderGraph();", "Page runtime re-renders the graph from shared state"),
      check("docs/assets/first-battlefield-inspection.js", "renderHeatmap();", "Page runtime re-renders the heatmap from shared state"),
      check("docs/assets/first-battlefield-inspection.js", "renderBlockers();", "Page runtime re-renders blocker ranking from shared state"),
      check("docs/assets/first-battlefield-inspection.js", "renderDetailPanel();", "Page runtime re-renders the detail inspector from shared state"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found the main linked views being driven from a shared render cycle in the page runtime.",
      gap: "This still reflects the generated inspection snapshot, not live runtime telemetry.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm shared-state rendering across the main inspection views.",
      gap: "Linked-view coherence may have regressed.",
    },
  }),
  "current-vs-target-legibility": rule({
    checks: [
      check("docs/assets/first-battlefield-inspection.js", "<strong>Current State</strong>", "Capability detail shows current state"),
      check("docs/assets/first-battlefield-inspection.js", "<strong>Target State</strong>", "Capability detail shows target state"),
      check("docs/assets/first-battlefield-inspection.js", "<strong>Score Rationale</strong>", "Capability detail shows score rationale"),
    ],
    onPass: {
      status: "substantial",
      confidence: "high",
      current_evidence: "Repo inspection found explicit current-state, target-state, and score-rationale detail cards in the capability inspector.",
      gap: "Those cards still summarize a modeled inspection layer rather than live runtime metrics.",
    },
    onFail: {
      status: "partial",
      confidence: "medium",
      current_evidence: "Repo inspection could not confirm explicit current-versus-target inspection detail in the page runtime.",
      gap: "The instrument may no longer surface enough state justification.",
    },
  }),
};

function applyRepoInspectionToCriterion(criterion) {
  const ruleDefinition = CRITERION_REPO_RULES[criterion.id];
  if (!ruleDefinition) {
    return {
      ...criterion,
      manifest_status: criterion.status,
      status_source: "seed_manifest",
      repo_inspection_summary: "This criterion is currently seeded from the inspection manifest and not yet repo-inspected.",
      repo_inspection_evidence: [],
      repo_inspection_missing: [],
    };
  }

  const result = evaluateAll(ruleDefinition.checks);
  const shape = result.passed ? ruleDefinition.onPass : ruleDefinition.onFail;
  return {
    ...criterion,
    status: shape.status,
    confidence: shape.confidence || criterion.confidence,
    current_evidence: shape.current_evidence || criterion.current_evidence,
    gap: shape.gap || criterion.gap,
    manifest_status: criterion.status,
    status_source: "repo_inspected",
    repo_inspection_summary: result.passed
      ? "Repo inspection confirmed the expected source footprint for this criterion."
      : "Repo inspection could not confirm the full expected source footprint for this criterion.",
    repo_inspection_evidence: result.evidence,
    repo_inspection_missing: result.missing,
  };
}

function attachRefMetadata(refs, repoUrl, commitSha) {
  return dedupeSourceRefs(refs).map((ref) => ({
    path: ref.path,
    label: ref.label || ref.path,
    exists: existsSync(path.join(repoRoot, ref.path)),
    url: repoUrl ? `${repoUrl}/blob/${commitSha}/${ref.path}` : "",
  }));
}

async function loadInspectionModule() {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "first-battlefield-inspection-"));
  const tempModulePath = path.join(tempDir, "first-battlefield-inspection-data.mjs");
  copyFileSync(dataModulePath, tempModulePath);
  try {
    return await import(`${pathToFileURL(tempModulePath).href}?t=${Date.now()}`);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

async function main() {
  const inspectionModule = await loadInspectionModule();
  const {
    BATTLEFIELD_MODEL,
    MATURITY_META,
    MATURITY_ORDER,
    CAPABILITY_SOURCE_REFS = {},
  } = inspectionModule;

  const commitSha = git(["rev-parse", "HEAD"]);
  const commitShort = git(["rev-parse", "--short", "HEAD"]);
  const branch = git(["rev-parse", "--abbrev-ref", "HEAD"]);
  const repoUrl = normalizeRemote(git(["remote", "get-url", "origin"]));

  const pageSourceRefs = attachRefMetadata(
    [
      { path: "docs/first-battlefield-inspection.html", label: "Inspection page shell" },
      { path: "docs/assets/first-battlefield-inspection.js", label: "Inspection interaction logic" },
      { path: "docs/assets/first-battlefield-inspection.css", label: "Inspection page styling" },
      { path: "docs/assets/first-battlefield-inspection-data.js", label: "Inspection capability manifest" },
    ],
    repoUrl,
    commitSha
  );

  const families = BATTLEFIELD_MODEL.families.map((family) => {
    const children = family.children.map((capability) => {
      const inspectedCriteria = capability.criteria.map((criterion) => applyRepoInspectionToCriterion(criterion));
      const sourceRefs = attachRefMetadata(CAPABILITY_SOURCE_REFS[capability.id] || [], repoUrl, commitSha);
      return {
        ...capability,
        criteria: inspectedCriteria,
        source_refs: sourceRefs,
        recent_changes: gitLogForPaths(
          sourceRefs.map((ref) => ref.path),
          3
        ),
      };
    });

    const familySourceRefs = attachRefMetadata(
      children.flatMap((child) => child.source_refs || []),
      repoUrl,
      commitSha
    );

    return {
      ...family,
      source_refs: familySourceRefs.slice(0, 12),
      recent_changes: gitLogForPaths(
        familySourceRefs.map((ref) => ref.path),
        4
      ),
      children,
    };
  });

  const trackedPaths = Array.from(
    new Set([
      ...pageSourceRefs.map((ref) => ref.path),
      ...families.flatMap((family) => family.source_refs.map((ref) => ref.path)),
    ])
  );

  const allCriteria = families.flatMap((family) =>
    family.children.flatMap((capability) => capability.criteria || [])
  );
  const repoInspectedCriteriaCount = allCriteria.filter((criterion) => criterion.status_source === "repo_inspected").length;
  const seededCriteriaCount = allCriteria.length - repoInspectedCriteriaCount;

  const snapshot = {
    version: 2,
    generated_at: new Date().toISOString(),
    commit_sha: commitSha,
    commit_short: commitShort,
    branch,
    repo_url: repoUrl,
    tracked_paths: trackedPaths,
    tracked_paths_count: trackedPaths.length,
    repo_inspected_criteria_count: repoInspectedCriteriaCount,
    seeded_criteria_count: seededCriteriaCount,
    provenance_note:
      "Generated from the first-battlefield inspection manifest plus repo-inspection rules and git metadata so the portal can expose source references, recent implementation changes, and a bounded set of repo-derived criterion states.",
    page_source_refs: pageSourceRefs,
    recent_changes: gitLogForPaths(trackedPaths, 8),
    maturity_order: MATURITY_ORDER,
    maturity_meta: MATURITY_META,
    model: {
      ...BATTLEFIELD_MODEL,
      source_mode: "generated_snapshot",
      families,
    },
  };

  mkdirSync(path.dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`, "utf8");
  process.stdout.write(`Generated ${path.relative(repoRoot, outputPath)} at ${snapshot.generated_at}\n`);
}

main().catch((error) => {
  process.stderr.write(`${String(error && error.stack ? error.stack : error)}\n`);
  process.exit(1);
});
