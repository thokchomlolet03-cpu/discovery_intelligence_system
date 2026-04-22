export const MATURITY_ORDER = [
  "missing",
  "minimal",
  "partial",
  "substantial",
  "strong",
  "battlefield_ready",
];

export const MATURITY_META = {
  missing: { value: 0.0, label: "Missing", short: "M", color: "#7f1d1d" },
  minimal: { value: 0.18, label: "Minimal", short: "Mi", color: "#9a3412" },
  partial: { value: 0.4, label: "Partial", short: "P", color: "#a16207" },
  substantial: { value: 0.63, label: "Substantial", short: "S", color: "#0f766e" },
  strong: { value: 0.82, label: "Strong", short: "St", color: "#2563eb" },
  battlefield_ready: { value: 1.0, label: "Battlefield Ready", short: "BR", color: "#7c3aed" },
};

function criterion(id, label, status, details = {}) {
  return {
    id,
    label,
    status,
    weight: details.weight ?? 1,
    confidence: details.confidence ?? "medium",
    measurement_basis: details.measurement_basis ?? "",
    current_evidence: details.current_evidence ?? "",
    gap: details.gap ?? "",
    rationale: details.rationale ?? "",
    critical: details.critical ?? false,
  };
}

function capability(id, label, details = {}) {
  return {
    id,
    label,
    description: details.description ?? "",
    target_state: details.target_state ?? "",
    implementation_basis: details.implementation_basis ?? "",
    current_evidence: details.current_evidence ?? "",
    limitation: details.limitation ?? "",
    blocker: details.blocker ?? "",
    recommended_next_step: details.recommended_next_step ?? "",
    why_it_matters: details.why_it_matters ?? "",
    weight: details.weight ?? 1,
    confidence: details.confidence ?? "medium",
    criticality: details.criticality ?? "important",
    dependencies: details.dependencies ?? [],
    battlefield_gate: details.battlefield_gate ?? null,
    criteria: details.criteria ?? [],
  };
}

function family(id, label, details = {}) {
  return {
    id,
    label,
    description: details.description ?? "",
    target_state: details.target_state ?? "",
    why_it_matters: details.why_it_matters ?? "",
    category: details.category ?? "scientific_core",
    weight: details.weight ?? 1,
    confidence: details.confidence ?? "medium",
    criticality: details.criticality ?? "important",
    dependencies: details.dependencies ?? [],
    children: details.children ?? [],
  };
}

export const BATTLEFIELD_MODEL = {
  id: "first-battlefield",
  label: "First Battlefield Readiness",
  goal_statement:
    "Build a goal-directed polymer/material discovery system that interprets user-specified material requirements, asks clarifying questions when critical scientific constraints are missing, searches and organizes evidence, returns the best-supported material answer when current evidence is sufficient, and only requests additional data or experiments when the evidence is insufficient.",
  scoring_note:
    "Readiness is computed from weighted criteria inside each capability. Hard battlefield gates prevent the page from confusing broad architectural progress with trustworthy first-battlefield readiness.",
  families: [
    family("goal-understanding", "Goal Understanding", {
      category: "scientific_core",
      weight: 1.15,
      confidence: "high",
      criticality: "critical",
      description:
        "Interpret the incoming request as a bounded polymer/material discovery objective instead of a generic prompt or upload summary.",
      target_state:
        "The system consistently treats the user request as a first-battlefield material goal with stable target semantics and session continuity.",
      why_it_matters:
        "If the goal is not interpreted as a bounded discovery objective, every downstream scientific judgment becomes unstable.",
      dependencies: [],
      children: [
        capability("goal-understanding.goal-intake-persistence", "Goal intake and persistence", {
          weight: 1.05,
          confidence: "high",
          criticality: "critical",
          description:
            "Capture the raw goal, structure it, and keep it available across session/workspace continuity.",
          target_state:
            "Every first-battlefield goal is persisted as a first-class record with enough provenance to drive later scientific steps.",
          implementation_basis:
            "MaterialGoalSpecification is persisted per session/workspace and fed into later projection and workbench shaping.",
          current_evidence:
            "Goal specifications, requirement sufficiency state, and clarification questions already survive session reopen.",
          limitation:
            "Revision-to-revision goal provenance is still lighter than the rest of the scientific-state model.",
          blocker:
            "The system still lacks a richer audit trail for how a goal evolves after multiple clarifications.",
          recommended_next_step:
            "Add stronger goal-revision framing so later answer decisions can compare current intent versus earlier intent.",
          why_it_matters:
            "This is the anchor for every later coverage, retrieval, and answer decision step.",
          criteria: [
            criterion("persist-structured-goal", "Structured goal record exists", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the system persists a first-class material goal record rather than only raw text.",
              current_evidence: "MaterialGoalSpecification is already persisted and reused across the first-battlefield path.",
              gap: "Historical goal revision framing is still limited.",
            }),
            criterion("session-continuity-goal", "Goal survives session reopen", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether reopening a session restores the structured goal context.",
              current_evidence: "Projection/workbench continuity already reconstructs the material goal layer on reopen.",
              gap: "Continuity is recomputed rather than versioned.",
            }),
            criterion("goal-provenance-depth", "Goal provenance depth", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system preserves a rich explanation of goal revision history.",
              current_evidence: "Current continuity preserves the active structured goal but not yet a deeper revision graph.",
              gap: "Goal revision lineage is still shallow.",
            }),
          ],
        }),
        capability("goal-understanding.domain-bounding", "Polymer/material domain bounding", {
          weight: 0.95,
          confidence: "medium",
          criticality: "important",
          description:
            "Bound the first battlefield to polymer/material discovery and avoid fake target-agnostic behavior.",
          target_state:
            "The system reliably keeps the goal inside the fixed polymer/material battlefield while honestly surfacing bridge-state limits.",
          implementation_basis:
            "The intake path is explicitly scoped to polymer_material and the broader doctrine is now visible in the workbench and docs.",
          current_evidence:
            "The battlefield-specific goal path is now explicitly named and carried through the current system surfaces.",
          limitation:
            "Domain semantics are still bridge-state and do not yet express richer chemistry/material ontologies.",
          blocker:
            "Complex material intents can still be flattened into broad requirement phrases.",
          recommended_next_step:
            "Strengthen first-battlefield material semantics without claiming unsupported target-agnostic reach.",
          why_it_matters:
            "Truthful domain bounding protects the scientific core from unsupported generalization.",
          dependencies: ["goal-understanding.goal-intake-persistence"],
          criteria: [
            criterion("explicit-battlefield-scope", "Explicit battlefield scope is enforced", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the path explicitly constrains itself to the first battlefield.",
              current_evidence: "The current path is intentionally framed around polymer/material discovery rather than a generic target.",
              gap: "No deeper type system for subdomains yet.",
            }),
            criterion("target-function-normalization", "Target function normalization", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the goal is converted into a bounded target material function rather than left as free text.",
              current_evidence: "Target material function is represented in the current structured goal shape.",
              gap: "Normalization still depends on a bounded semantic vocabulary.",
            }),
            criterion("bridge-state-honesty", "Bridge-state honesty is surfaced", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether the surface is explicit about what remains bridge-state or legacy-constrained.",
              current_evidence: "The current doctrine and inspection framing openly describe bridge-state limitations.",
              gap: "This is still curated doctrine rather than auto-derived runtime annotation.",
            }),
          ],
        }),
      ],
    }),
    family("requirement-structuring", "Requirement Structuring", {
      category: "scientific_core",
      weight: 1.22,
      confidence: "high",
      criticality: "critical",
      description:
        "Turn the raw material goal into explicit scientific requirement dimensions that later evidence can be tested against.",
      target_state:
        "The system can represent the user’s material requirements as explicit, inspectable, and sufficiently complete decision dimensions.",
      why_it_matters:
        "Without structured requirements, evidence matching and answer sufficiency judgment are not scientifically grounded.",
      dependencies: ["goal-understanding"],
      children: [
        capability("requirement-structuring.structured-dimensions", "Structured requirement dimensions", {
          weight: 1.05,
          confidence: "high",
          criticality: "critical",
          description:
            "Extract target properties, environment, lifecycle, trigger, safety, and function dimensions into a structured goal shape.",
          target_state:
            "Every goal exposes the first-battlefield requirement dimensions in a stable structure that can be covered or left unknown.",
          implementation_basis:
            "MaterialGoalSpecification already carries named requirement groups for properties, environment, lifecycle, triggers, safety, and target function.",
          current_evidence:
            "These dimensions are already threaded into retrieval, support trace, coverage, and answer decision logic.",
          limitation:
            "Dimension semantics are still template-bounded rather than a richer material ontology.",
          blocker:
            "Synonym handling and deeper requirement semantics remain limited.",
          recommended_next_step:
            "Strengthen dimension normalization so coverage can rely less on direct term overlap.",
          why_it_matters:
            "Coverage and support tracing need explicit requirement slots rather than a free-form request blob.",
          dependencies: ["goal-understanding.domain-bounding"],
          criteria: [
            criterion("dimension-presence", "Major requirement dimensions are present", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the goal model exposes the major first-battlefield dimensions.",
              current_evidence: "Desired properties, environment, lifecycle, trigger, safety, and function are already first-class.",
              gap: "Some second-order dimensions are not yet represented.",
            }),
            criterion("dimension-propagation", "Dimensions propagate into downstream services", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the structured dimensions are actually consumed downstream.",
              current_evidence: "Retrieval, support traces, coverage, and answer decisions all consume these dimensions.",
              gap: "Propagation still depends on bridge-state matching logic.",
            }),
            criterion("semantic-richness", "Dimension semantics are richer than keywords", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether dimensions capture deeper semantics beyond templated phrases.",
              current_evidence: "The structure exists, but interpretation is still conservative and bounded.",
              gap: "Richer material semantics and uncertainty representation are still missing.",
            }),
          ],
        }),
        capability("requirement-structuring.critical-completeness", "Critical requirement completeness", {
          weight: 1.1,
          confidence: "high",
          criticality: "critical",
          description:
            "Judge whether the current goal is sufficiently specified to proceed toward retrieval and answer logic.",
          target_state:
            "The system reliably distinguishes between sufficiently specified and scientifically incomplete goals before answer work begins.",
          implementation_basis:
            "Requirement sufficiency is already computed during intake and blocks later progression when critical constraints are absent.",
          current_evidence:
            "The system now refuses to proceed to answer logic when the goal remains insufficiently specified.",
          limitation:
            "Criticality logic is still bridge-state and can miss nuanced insufficiencies.",
          blocker:
            "The system still lacks richer prioritization of which missing requirement most distorts the answer boundary.",
          recommended_next_step:
            "Expand criticality rules using the same disciplined first-battlefield requirement structure.",
          why_it_matters:
            "Answer sufficiency is meaningless if the goal itself is not sufficiently specified.",
          dependencies: ["requirement-structuring.structured-dimensions"],
          criteria: [
            criterion("sufficiency-status", "Sufficiency status is explicit", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the goal path explicitly records requirement sufficiency status.",
              current_evidence: "Sufficiently specified versus incomplete goals are already distinguished in the goal layer.",
              gap: "Richer gradations of insufficiency are still limited.",
            }),
            criterion("critical-gaps-block-flow", "Critical gaps block downstream flow", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether insufficient goals are prevented from being treated as answer-ready.",
              current_evidence: "Insufficient goals stop before answer progression and generate clarification prompts.",
              gap: "Some nuanced insufficiencies may still get compressed into broad categories.",
            }),
            criterion("impact-aware-prioritization", "Missing constraints are prioritized by answer impact", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system ranks missing requirements by how much they affect answer trustworthiness.",
              current_evidence: "Clarifications are targeted, but their ranking is still relatively static.",
              gap: "No stronger answer-impact ranking yet.",
            }),
          ],
        }),
      ],
    }),
    family("clarification", "Clarification / Missing Constraint Detection", {
      category: "scientific_core",
      weight: 1.08,
      confidence: "high",
      criticality: "critical",
      description:
        "Ask for missing scientific constraints when the goal is incomplete, rather than pretending an answer is already possible.",
      target_state:
        "The system asks bounded, decision-relevant clarification questions exactly where missing requirements still block scientific trustworthiness.",
      why_it_matters:
        "The first battlefield requires the system to ask clarifying questions only when critical scientific constraints are missing.",
      dependencies: ["requirement-structuring"],
      children: [
        capability("clarification.missing-constraint-detection", "Missing constraint detection", {
          weight: 1.0,
          confidence: "high",
          criticality: "critical",
          description:
            "Detect missing environment, lifecycle, trigger, and safety constraints that materially affect answerability.",
          target_state:
            "The system recognizes the major first-battlefield missing-constraint patterns and exposes them before retrieval or answer promotion.",
          implementation_basis:
            "The intake layer already generates clarification questions when environment, lifecycle, trigger, or safety constraints are missing.",
          current_evidence:
            "Current goal intake explicitly detects missing environment and other key requirement families.",
          limitation:
            "Detection is still rule-driven and can miss more subtle ambiguity patterns.",
          blocker:
            "Nuanced ambiguity is still flattened into broad missing-constraint categories.",
          recommended_next_step:
            "Expand bounded ambiguity detection while preserving conservative behavior.",
          why_it_matters:
            "This keeps the system from mistaking underspecified intent for answerable intent.",
          dependencies: ["requirement-structuring.critical-completeness"],
          criteria: [
            criterion("environment-gap-detection", "Environment gaps are detected", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether environment omissions trigger a clarification path.",
              current_evidence: "Environment-related insufficiency is explicitly recognized today.",
              gap: "Finer environment compatibility semantics are still limited.",
            }),
            criterion("lifecycle-trigger-safety-gaps", "Lifecycle, trigger, and safety gaps are detected", "strong", {
              confidence: "medium",
              critical: true,
              measurement_basis: "Check whether other critical scientific constraints are explicitly detected when absent.",
              current_evidence: "Lifecycle, trigger, and safety constraints are represented in the goal model and surfaced when absent.",
              gap: "Edge-case ambiguity is still relatively coarse.",
            }),
            criterion("subtle-ambiguity-detection", "Subtle ambiguity detection", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the system catches nuanced incompleteness beyond obvious missing fields.",
              current_evidence: "The current path goes beyond one missing field, but it is still bounded.",
              gap: "More subtle scientific ambiguity remains only partly handled.",
            }),
          ],
        }),
        capability("clarification.prioritized-clarification", "Prioritized clarification generation", {
          weight: 0.95,
          confidence: "medium",
          criticality: "important",
          description:
            "Generate the next most useful clarification question instead of dumping broad forms of generic caution.",
          target_state:
            "Clarification requests are ranked by how much they reduce first-battlefield answer uncertainty.",
          implementation_basis:
            "The current goal layer already generates targeted clarification prompts when critical constraints are missing.",
          current_evidence:
            "Clarification output is bounded and domain-shaped instead of generic.",
          limitation:
            "Questions are still relatively template-driven rather than ranked by downstream leverage.",
          blocker:
            "The system cannot yet compare which clarification would most increase answer readiness.",
          recommended_next_step:
            "Add answer-impact ranking so clarification output becomes more strategically ordered.",
          why_it_matters:
            "Good clarification is part of discovery steering, not just form completion.",
          dependencies: ["clarification.missing-constraint-detection"],
          criteria: [
            criterion("bounded-question-generation", "Clarification questions are bounded and domain-specific", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether clarification output stays within the first battlefield rather than generic assistant behavior.",
              current_evidence: "The current prompts are targeted to material-goal requirement gaps.",
              gap: "Prompt ranking remains limited.",
            }),
            criterion("answer-impact-ranking", "Clarifications are ranked by answer impact", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system knows which missing constraint matters most to the answer boundary.",
              current_evidence: "Current questions are targeted but not deeply ranked by readiness leverage.",
              gap: "No stronger answer-impact model yet.",
            }),
            criterion("minimal-over-asking", "The system avoids unnecessary clarification", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system asks only the missing questions that materially matter.",
              current_evidence: "The current path is bounded, but its selectivity is still heuristic.",
              gap: "Clarification precision is still evolving.",
            }),
          ],
        }),
      ],
    }),
    family("evidence-retrieval", "Evidence Retrieval and Organization", {
      category: "scientific_core",
      weight: 1.32,
      confidence: "medium",
      criticality: "critical",
      description:
        "Search and organize grounded support for candidate material directions without fabricating evidence depth that does not exist.",
      target_state:
        "The system can retrieve, organize, and bound real evidence against the structured material goal, with enough depth to support later answer decisions.",
      why_it_matters:
        "This is the main bridge-state bottleneck between a capable product workbench and a real discovery engine.",
      dependencies: ["requirement-structuring", "clarification"],
      children: [
        capability("evidence-retrieval.grounded-evidence-matching", "Grounded evidence matching", {
          weight: 1.15,
          confidence: "medium",
          criticality: "critical",
          description:
            "Map the structured goal onto grounded evidence already available in the current scientific/session context.",
          target_state:
            "The system can retrieve evidence with enough grounding depth to support or refute requirement dimensions, not just match terms.",
          implementation_basis:
            "Retrieval now maps structured goal requirements onto existing session evidence, model outputs, and recommendation records.",
          current_evidence:
            "The system already distinguishes no_grounded_evidence, weak_partial_evidence, and candidate_directions_available.",
          limitation:
            "Retrieval is still session-local and relatively term-and-summary driven.",
          blocker:
            "Thin evidence retrieval remains the biggest barrier to a trustworthy first-battlefield answer.",
          recommended_next_step:
            "Increase grounding depth and richer evidence matching before widening any answer claims.",
          why_it_matters:
            "Answer sufficiency cannot become strong while evidence retrieval remains thin and shallow.",
          dependencies: ["requirement-structuring.structured-dimensions"],
          battlefield_gate: {
            required_status: "strong",
            rationale:
              "The system cannot honestly claim first-battlefield readiness until retrieval grounding is stronger than session-local term matching.",
          },
          criteria: [
            criterion("explicit-retrieval-sufficiency", "Retrieval sufficiency states are explicit", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether retrieval distinguishes no evidence, weak evidence, and candidate directions.",
              current_evidence: "The current retrieval layer now surfaces explicit sufficiency categories.",
              gap: "The categories are real but still reflect thin retrieval.",
            }),
            criterion("evidence-grounding-depth", "Grounding depth goes beyond thin summary matching", "partial", {
              confidence: "medium",
              critical: true,
              measurement_basis: "Check whether retrieved evidence is rich enough to support dimension-level scientific judgments.",
              current_evidence: "Grounding is real, but still bounded to current session traces and support summaries.",
              gap: "No deeper evidence corpus or richer evidence linking yet.",
            }),
            criterion("honest-thin-retrieval-surfacing", "Thin retrieval is surfaced honestly", "strong", {
              confidence: "high",
              measurement_basis: "Check whether weak retrieval is exposed as weak rather than promoted.",
              current_evidence: "Weak retrieval is already surfaced as weak_partial_evidence instead of a supported answer.",
              gap: "This still depends on the upstream retrieval summaries staying disciplined.",
            }),
          ],
        }),
        capability("evidence-retrieval.candidate-direction-organization", "Candidate material direction organization", {
          weight: 1.0,
          confidence: "medium",
          criticality: "critical",
          description:
            "Organize retrieved support into conservative candidate material directions with visible support boundaries.",
          target_state:
            "Candidate directions are stable, inspectable, and sufficiently differentiated to support later coverage and answer work.",
          implementation_basis:
            "Retrieval already groups matched support into conservative candidate directions with support strength and limitation lines.",
          current_evidence:
            "The workbench now shows candidate material directions rather than pretending to output a final answer directly.",
          limitation:
            "Direction identity and aggregation are still bridge-state and can remain coarse.",
          blocker:
            "Material direction identity is still not rich enough to fully support high-trust selection among close candidates.",
          recommended_next_step:
            "Improve direction identity and support aggregation without sliding into fabricated precision.",
          why_it_matters:
            "Coverage and answer decision need a coherent leading direction before they can judge sufficiency.",
          dependencies: ["evidence-retrieval.grounded-evidence-matching"],
          criteria: [
            criterion("direction-assembly", "Candidate directions are assembled explicitly", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the system groups evidence into candidate material directions.",
              current_evidence: "Retrieval now returns organized candidate directions instead of only isolated evidence snippets.",
              gap: "Direction identity is still relatively coarse.",
            }),
            criterion("support-boundary-visible", "Direction support boundaries remain visible", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether direction-level limitations and support strength remain inspectable.",
              current_evidence: "Support strength and limitation lines already accompany the candidate directions.",
              gap: "Support provenance is still summary-shaped.",
            }),
            criterion("comparative-direction-strength", "Candidate directions are comparatively differentiable", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the current evidence basis supports a strong comparison between directions.",
              current_evidence: "Direction organization exists, but it remains thin where retrieval is thin.",
              gap: "Comparative differentiation is still weak when evidence density is low.",
            }),
          ],
        }),
      ],
    }),
    family("traceability", "Requirement Coverage and Support Traceability", {
      category: "scientific_core",
      weight: 1.35,
      confidence: "medium",
      criticality: "critical",
      description:
        "Trace each requirement dimension to explicit support basis, contradiction basis, and missing-evidence basis so answer decisions become inspectable.",
      target_state:
        "Every critical requirement dimension can be traced to what supports it, what contradicts it, and what remains missing.",
      why_it_matters:
        "This is the core shift from retrieval summaries toward a more legible scientific decision substrate.",
      dependencies: ["evidence-retrieval"],
      children: [
        capability("traceability.requirement-support-trace", "Per-dimension support trace", {
          weight: 1.12,
          confidence: "medium",
          criticality: "critical",
          description:
            "Attach exact matched support lines, observed versus indirect support, contradiction indicators, uncovered terms, and gap codes to each requirement dimension.",
          target_state:
            "Each requirement dimension exposes a compact but explicit support trace that can be audited by the user and reused by later logic.",
          implementation_basis:
            "MaterialGoalSupportTrace now derives explicit per-dimension support records for the leading direction.",
          current_evidence:
            "Support traces now show matched lines, observed lines, indirect lines, contradiction indicators, uncovered terms, and gap codes.",
          limitation:
            "Support traces are still constrained by the quality of current retrieval support lines.",
          blocker:
            "Traceability cannot become stronger than the evidentiary richness of the retrieval layer beneath it.",
          recommended_next_step:
            "Increase direct evidence provenance and dimension-level grounding beneath the trace layer.",
          why_it_matters:
            "This is the mechanism that lets the system answer: what supports this requirement, what contradicts it, and what is still missing?",
          dependencies: ["evidence-retrieval.candidate-direction-organization"],
          battlefield_gate: {
            required_status: "strong",
            rationale:
              "The system cannot be battlefield-ready while critical requirement support still depends on shallow, weakly attributable traces.",
          },
          criteria: [
            criterion("trace-basis-explicit", "Support basis is explicit per dimension", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the trace explicitly lists matched support and uncovered terms per requirement dimension.",
              current_evidence: "The current trace layer already does this for the leading candidate direction.",
              gap: "Support lines are still limited by upstream retrieval richness.",
            }),
            criterion("observed-vs-indirect-distinction", "Observed versus indirect support is distinguished", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the system separates stronger observed support from indirect support.",
              current_evidence: "Support traces already distinguish observed and indirect support lines.",
              gap: "Support quality itself remains bridge-state.",
            }),
            criterion("direct-provenance-depth", "Trace provenance is rich enough for stronger audit", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the trace can show deeper evidence provenance beyond support-line summaries.",
              current_evidence: "Traceability has become explicit, but its provenance remains bounded.",
              gap: "A richer evidence-to-requirement link model is still missing.",
            }),
          ],
        }),
        capability("traceability.requirement-coverage-judgment", "Requirement coverage judgment", {
          weight: 1.08,
          confidence: "medium",
          criticality: "critical",
          description:
            "Convert support traces into explicit per-dimension coverage judgments such as supported, partially supported, unknown, or contradicted.",
          target_state:
            "Coverage expresses whether each requirement dimension is truly supported enough to participate in answer promotion.",
          implementation_basis:
            "MaterialGoalCoverage now depends on support traces rather than direct coarse term checks.",
          current_evidence:
            "Discovery surfaces now expose requirement dimensions, status per dimension, rationale, and gaps.",
          limitation:
            "Coverage status still inherits retrieval and contradiction coarseness where the underlying evidence is weak.",
          blocker:
            "Coverage is more inspectable now, but still not backed by a deeper evidence graph.",
          recommended_next_step:
            "Strengthen dimension semantics and contradiction attribution while keeping coverage conservative.",
          why_it_matters:
            "Answer promotion now depends on coverage, so this layer must stay explicit and disciplined.",
          dependencies: ["traceability.requirement-support-trace"],
          criteria: [
            criterion("coverage-derived-from-trace", "Coverage is derived from the support trace", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether coverage status now depends on explicit trace structure rather than a shallow summary.",
              current_evidence: "Coverage now consumes the support trace as its primary substrate.",
              gap: "The support trace beneath it is still bridge-state.",
            }),
            criterion("critical-dimension-gating", "Critical dimensions can block answer promotion", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether uncovered or contradicted critical dimensions are visible and decision-relevant.",
              current_evidence: "Critical requirement dimensions now drive answer withholding when under-supported.",
              gap: "Dimension criticality is still partly encoded by current field structure.",
            }),
            criterion("dimension-semantic-depth", "Coverage captures deeper requirement semantics", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether coverage can express nuanced dimension semantics beyond term coverage.",
              current_evidence: "Coverage has moved beyond raw term checks, but the semantic depth is still bounded.",
              gap: "Richer requirement semantics remain to be built.",
            }),
          ],
        }),
      ],
    }),
    family("contradiction-unknowns", "Contradiction Handling and Unknown Detection", {
      category: "scientific_core",
      weight: 1.24,
      confidence: "medium",
      criticality: "critical",
      description:
        "Treat contradiction pressure and explicit unknowns as first-class reasons not to return an answer prematurely.",
      target_state:
        "The system can say not just that a dimension is weak, but whether it is unsupported, indirectly supported, contradicted, or still missing decisive evidence.",
      why_it_matters:
        "A truth-seeking discovery system must know why not to trust apparent support.",
      dependencies: ["traceability"],
      children: [
        capability("contradiction-unknowns.dimension-contradiction-attribution", "Dimension-aware contradiction attribution", {
          weight: 1.12,
          confidence: "medium",
          criticality: "critical",
          description:
            "Map contradiction indicators to the requirement dimensions they pressure, while honestly marking when the attribution is still coarse.",
          target_state:
            "Contradictions can be linked to specific requirement dimensions whenever the current scientific state genuinely supports that precision.",
          implementation_basis:
            "Support traces now attempt dimension-aware contradiction attribution and surface when attribution is still coarse.",
          current_evidence:
            "The current system now exposes when contradiction pressure is dimension-specific versus direction-level.",
          limitation:
            "Contradiction objects are still not inherently dimension-tagged, so attribution remains partly coarse.",
          blocker:
            "Without stronger dimension tagging, contradiction handling still caps answer trustworthiness.",
          recommended_next_step:
            "Carry stronger provenance and dimension tags into contradiction records and support traces.",
          why_it_matters:
            "Contradiction handling is one of the main barriers between plausible support and trustworthy support.",
          dependencies: ["traceability.requirement-support-trace"],
          battlefield_gate: {
            required_status: "strong",
            rationale:
              "The system cannot honestly claim battlefield readiness while contradiction pressure remains only partly attributable to the dimensions it may invalidate.",
          },
          criteria: [
            criterion("trace-linked-contradictions", "Contradictions can be linked into support traces", "partial", {
              confidence: "medium",
              critical: true,
              measurement_basis: "Check whether contradiction indicators can be surfaced inside the per-dimension trace layer.",
              current_evidence: "Support traces now include contradiction indicators and explain when they are coarse.",
              gap: "Many contradictions still remain direction-level rather than dimension-level.",
            }),
            criterion("dimension-specific-attribution", "Dimension-specific attribution is available when justified", "partial", {
              confidence: "medium",
              critical: true,
              measurement_basis: "Check whether the system can attach contradiction pressure to the correct requirement dimension.",
              current_evidence: "Some dimension-aware mapping is now present, but it is still cautious and limited.",
              gap: "Dimension tags are not yet first-class in contradiction records.",
            }),
            criterion("contradiction-provenance-depth", "Contradiction provenance is rich enough for strong blocking", "minimal", {
              confidence: "medium",
              measurement_basis: "Check whether contradiction evidence is deep enough to support stronger dimension-level blocking logic.",
              current_evidence: "Current contradiction provenance remains coarser than the new support trace model.",
              gap: "Evidence-level contradiction attribution remains largely unbuilt.",
            }),
          ],
        }),
        capability("contradiction-unknowns.requirement-linked-unknowns", "Requirement-linked explicit unknowns", {
          weight: 1.0,
          confidence: "medium",
          criticality: "critical",
          description:
            "Derive explicit unknowns from uncovered dimensions, indirect-only support, sparse evidence, and unresolved contradiction pressure.",
          target_state:
            "Every insufficient case exposes the concrete requirement-linked unknowns that still prevent a trustworthy answer.",
          implementation_basis:
            "Unknowns now derive from support-trace and coverage gaps rather than vague caution language.",
          current_evidence:
            "Insufficient cases now surface codes like sparse_evidence_basis, weak_environmental_match, and unresolved_contradiction_pressure.",
          limitation:
            "The unknown ontology is still first-version and intentionally bounded.",
          blocker:
            "Unknowns are now explicit, but they are not yet deeply typed or prioritized by experimental value.",
          recommended_next_step:
            "Expand the unknown ontology and tie it more directly to experiment-closing value.",
          why_it_matters:
            "Unknowns are the bridge between honest withholding and useful next-step guidance.",
          dependencies: ["traceability.requirement-coverage-judgment"],
          criteria: [
            criterion("unknowns-derived-from-coverage", "Unknowns are derived from uncovered critical dimensions", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the unknowns correspond to real gaps in the current requirement coverage.",
              current_evidence: "Unknowns now come from trace and coverage gaps instead of generic caution language.",
              gap: "Unknown typing is still relatively broad.",
            }),
            criterion("unknown-codes-are-machine-readable", "Unknowns remain machine-readable and inspectable", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether the system exposes explicit unknown categories rather than only prose summaries.",
              current_evidence: "The current answer layer exposes bounded insufficiency and gap codes.",
              gap: "The ontology still needs richer internal structure.",
            }),
            criterion("unknown-prioritization", "Unknowns are prioritized by closure value", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system knows which unknown is most important to close first.",
              current_evidence: "The system now narrows the unknown list, but prioritization is still coarse.",
              gap: "No stronger value-of-information logic yet.",
            }),
          ],
        }),
      ],
    }),
    family("answer-decision", "Answer Sufficiency Judgment and Follow-up Actioning", {
      category: "scientific_core",
      weight: 1.38,
      confidence: "high",
      criticality: "critical",
      description:
        "Make the central battlefield decision: answer now when support is sufficient, or withhold and ask only for the data that would close the insufficiency.",
      target_state:
        "The system returns a best-supported material answer only when coverage, support trace, contradiction handling, and evidence grounding justify it.",
      why_it_matters:
        "This is the fixed first-battlefield decision boundary around which the current architecture is being rebuilt.",
      dependencies: ["traceability", "contradiction-unknowns"],
      children: [
        capability("answer-decision.bounded-answer-promotion", "Bounded answer promotion", {
          weight: 1.12,
          confidence: "high",
          criticality: "critical",
          description:
            "Promote a best-supported answer only when critical requirement dimensions are actually covered and contradiction pressure is not blocking.",
          target_state:
            "Answer promotion depends on explicit coverage and support sufficiency, not shallow retrieval optimism.",
          implementation_basis:
            "MaterialGoalAnswerDecision now uses coverage as its primary gate and still retains conservative secondary guards.",
          current_evidence:
            "Answer promotion now requires supported critical dimensions and blocks weak/partial retrieval from masquerading as a supported answer.",
          limitation:
            "The logic is stronger than before, but upstream evidence depth still caps how often a trustworthy answer can be returned.",
          blocker:
            "The answer boundary is now meaningful, but the evidence basis beneath it is still not battlefield-strong.",
          recommended_next_step:
            "Keep the answer policy conservative while deepening the support basis beneath it.",
          why_it_matters:
            "This is where the system stops being a recommendation shell and starts acting like a disciplined discovery engine.",
          dependencies: [
            "traceability.requirement-coverage-judgment",
            "contradiction-unknowns.dimension-contradiction-attribution",
          ],
          battlefield_gate: {
            required_status: "strong",
            rationale:
              "Battlefield readiness requires a real, reliable answer boundary; this capability must stay strong and remain grounded in explicit support.",
          },
          criteria: [
            criterion("coverage-primary-gate", "Coverage is the primary answer gate", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the answer decision primarily relies on structured coverage rather than raw retrieval heuristics.",
              current_evidence: "The current answer layer now uses coverage as the primary decision gate.",
              gap: "Coverage itself still depends on bridge-state support traces.",
            }),
            criterion("unsupported-answers-withheld", "Weak or partial support does not become a supported answer", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether weak retrieval or partial critical coverage is explicitly withheld.",
              current_evidence: "Weak or partial retrieval now leads to insufficient-answer states rather than optimistic promotion.",
              gap: "The boundary still inherits upstream evidence limitations.",
            }),
            criterion("critical-dimension-justification", "Answer promotion is justified dimension by dimension", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the system can explain why each critical dimension passed the gate.",
              current_evidence: "Coverage and support trace give a more legible basis now, but not yet a deeper evidence graph.",
              gap: "Justification is explicit but still bridge-state.",
            }),
          ],
        }),
        capability("answer-decision.insufficiency-follow-up-actioning", "Insufficiency follow-up actioning", {
          weight: 1.0,
          confidence: "high",
          criticality: "critical",
          description:
            "When the answer is insufficient, request only the next data or experiment steps that directly close the explicit insufficiency.",
          target_state:
            "The system requests bounded additional data or experiments only because the current evidence basis is insufficient, not because generic caution language exists.",
          implementation_basis:
            "Insufficient cases already emit bounded additional-data and experiment requests linked to trace and coverage gaps.",
          current_evidence:
            "The current answer layer now requests more only in insufficient cases and ties follow-up to explicit insufficiency reasons.",
          limitation:
            "Follow-up specificity is still first-version and constrained by the current unknown ontology.",
          blocker:
            "Experiment request quality is still limited by the granularity of the unknown model.",
          recommended_next_step:
            "Improve follow-up prioritization and experimental specificity from the explicit unknown structure.",
          why_it_matters:
            "The first battlefield requires not just withholding, but disciplined next-step steering when current evidence is insufficient.",
          dependencies: [
            "contradiction-unknowns.requirement-linked-unknowns",
            "answer-decision.bounded-answer-promotion",
          ],
          battlefield_gate: {
            required_status: "strong",
            rationale:
              "Battlefield readiness requires the system to ask for more only when the evidence basis is insufficient and to do so in a requirement-linked way.",
          },
          criteria: [
            criterion("follow-up-only-when-insufficient", "Additional requests appear only when the answer is insufficient", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether additional data or experiments are requested only in insufficient cases.",
              current_evidence: "The current answer layer withholds requests when an answer is supportable and surfaces them only when insufficiency is explicit.",
              gap: "Specificity remains limited by the current unknown ontology.",
            }),
            criterion("follow-up-linked-to-gap", "Requests are linked to explicit insufficiency gaps", "substantial", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether each request can be traced back to a support, coverage, or contradiction gap.",
              current_evidence: "Current additional-data and experiment requests derive from explicit insufficiency categories.",
              gap: "The mapping is bounded and still relatively coarse.",
            }),
            criterion("request-prioritization-quality", "Requests are prioritized by closure value", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether the system knows which follow-up request gives the highest leverage toward answer sufficiency.",
              current_evidence: "Current requests are bounded, but prioritization quality is still early-stage.",
              gap: "No stronger closure-value model yet.",
            }),
          ],
        }),
      ],
    }),
    family("continuity-inspection", "Session Continuity and Inspection Surfaces", {
      category: "surface_and_governance",
      weight: 1.0,
      confidence: "high",
      criticality: "important",
      description:
        "Keep the scientific state legible across session reopen, Discovery workbench surfaces, and the portal-facing inspection layer.",
      target_state:
        "The system can reopen, project, and inspect first-battlefield state without losing the scientific basis of its current answer boundary.",
      why_it_matters:
        "A discovery system is only operationally useful if its reasoning survives reopen and remains inspectable.",
      dependencies: ["answer-decision"],
      children: [
        capability("continuity-inspection.session-reopen-continuity", "Session reopen continuity", {
          weight: 1.0,
          confidence: "high",
          criticality: "important",
          description:
            "Recompute and project first-battlefield state on session reopen without adding unstable persistence pressure.",
          target_state:
            "Goal specification, retrieval, support trace, coverage, and answer decision all survive reopen via truthful recomputation.",
          implementation_basis:
            "Projection/workbench continuity already recomputes the first-battlefield layers on reopen.",
          current_evidence:
            "Support trace, coverage, and answer decision are all exposed again when a session is reopened.",
          limitation:
            "This continuity is recomputed rather than historically versioned.",
          blocker:
            "The system cannot yet compare how a prior answer boundary differed from the current one after policy changes.",
          recommended_next_step:
            "Add historical comparison framing once the read-model policy is stable enough to justify it.",
          why_it_matters:
            "The instrument must show the real current scientific state, not a detached page-specific interpretation.",
          dependencies: ["answer-decision.bounded-answer-promotion"],
          criteria: [
            criterion("projection-includes-first-battlefield-state", "Projection includes the first-battlefield layers", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether reopen projection includes the current first-battlefield state stack.",
              current_evidence: "Projection already includes goal, retrieval, support trace, coverage, and answer decision.",
              gap: "Historical comparison is still missing.",
            }),
            criterion("recomputed-read-model-continuity", "Recomputed read models stay continuity-safe", "strong", {
              confidence: "high",
              measurement_basis: "Check whether recomputed read models preserve reopen continuity without new persistence.",
              current_evidence: "The new first-battlefield layers are intentionally recomputed and survive reopen.",
              gap: "Version-to-version comparison remains limited.",
            }),
            criterion("historical-diff-legibility", "Historical diffs across policy evolution remain legible", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the system can explain how the current read-model differs from earlier policy versions.",
              current_evidence: "Current projection continuity is strong, but historical comparison remains only partly present.",
              gap: "No dedicated historical readiness diff yet.",
            }),
          ],
        }),
        capability("continuity-inspection.multi-level-inspection-surface", "Multi-level inspection surface", {
          weight: 0.95,
          confidence: "medium",
          criticality: "important",
          description:
            "Expose the scientific state in layered inspection surfaces so users can move from overview to evidence-linked detail.",
          target_state:
            "The workbench and portal provide an inspection path from overview to capability to criterion to dependency/gap basis.",
          implementation_basis:
            "Discovery already exposes retrieval, support trace, coverage, and answer panels, and this portal page provides a readiness inspection surface.",
          current_evidence:
            "The page already offers graph, matrix, blockers, next moves, and selection-driven detail views.",
          limitation:
            "The inspection surface still depends on curated modeled state rather than auto-derived runtime instrumentation.",
          blocker:
            "Keeping increasing scientific detail readable without flattening it into decorative summaries remains an active design challenge.",
          recommended_next_step:
            "Continue deepening audit detail and keep linked interactions disciplined as the underlying scientific state grows.",
          why_it_matters:
            "A strategically useful inspection page has to reveal structure, relationships, and blockers rather than only status labels.",
          dependencies: ["continuity-inspection.session-reopen-continuity"],
          criteria: [
            criterion("overview-to-detail-navigation", "Overview-to-detail inspection exists", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether the surface lets the user move from overall readiness to detailed capability inspection.",
              current_evidence: "The current page now includes linked graph, matrix, blocker, and detail views.",
              gap: "Audit depth is still evolving.",
            }),
            criterion("linked-view-coherence", "Views stay synchronized under selection and filtering", "partial", {
              confidence: "medium",
              measurement_basis: "Check whether major page views remain connected and teach dependency structure.",
              current_evidence: "The page is now more connected, but it still relies on curated model data.",
              gap: "The surface is not yet live-runtime-derived instrumentation.",
            }),
            criterion("current-vs-target-legibility", "The page clearly shows current versus target state", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the detail inspector can explain current basis, target state, and blockers together.",
              current_evidence: "The detail inspector now carries target state, measurement criteria, blockers, and next steps.",
              gap: "More direct runtime trace links would improve this further.",
            }),
          ],
        }),
      ],
    }),
    family("epistemic-conservatism", "Epistemic Conservatism", {
      category: "surface_and_governance",
      weight: 1.12,
      confidence: "high",
      criticality: "critical",
      description:
        "Preserve the discipline that prevents the system from overclaiming scientific capability or answer support.",
      target_state:
        "Every visible answer, withholding decision, and readiness judgment stays bounded by what the current system can actually support.",
      why_it_matters:
        "A battlefield-ready system must be trustworthy, not just rich in surfaces or heuristics.",
      dependencies: ["answer-decision", "continuity-inspection"],
      children: [
        capability("epistemic-conservatism.answer-restraint", "Answer restraint", {
          weight: 1.0,
          confidence: "high",
          criticality: "critical",
          description:
            "Prevent weak, partial, or contradicted evidence from being promoted into a best-supported material answer.",
          target_state:
            "The system consistently under-answers rather than overclaiming when evidence is weak or contradictions remain unresolved.",
          implementation_basis:
            "Coverage-based gating and explicit insufficiency states now block unsupported answer promotion.",
          current_evidence:
            "Thin retrieval and partial critical coverage are now surfaced honestly rather than as optimistic answers.",
          limitation:
            "Restraint is only as strong as the fidelity of the upstream traces and contradiction handling.",
          blocker:
            "Pressure to look complete can still exceed what the evidence basis truly justifies.",
          recommended_next_step:
            "Keep every new capability anchored in explicit support before broadening any answer claims.",
          why_it_matters:
            "Restraint keeps the system scientifically credible while other layers mature.",
          dependencies: ["answer-decision.bounded-answer-promotion"],
          criteria: [
            criterion("thin-retrieval-not-promoted", "Thin retrieval is not promoted", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether the system refuses to turn weak retrieval into a supported answer.",
              current_evidence: "Weak/partial retrieval already blocks answer promotion.",
              gap: "Still depends on upstream retrieval discipline.",
            }),
            criterion("critical-gaps-block-answer", "Critical unsupported dimensions block answers", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether critical dimensions can stop the system from returning an answer.",
              current_evidence: "Coverage now blocks answer promotion when critical requirement support is insufficient.",
              gap: "Coverage semantics are still evolving.",
            }),
            criterion("pressure-against-overclaiming", "The page/system remains explicit about bridge-state limits", "substantial", {
              confidence: "high",
              measurement_basis: "Check whether the surfaced narrative stays honest about current limits.",
              current_evidence: "The current docs, workbench, and inspection layer all speak in bounded bridge-state terms.",
              gap: "Some parts of the broader product shell still carry legacy framing.",
            }),
          ],
        }),
        capability("epistemic-conservatism.inspectable-withholding", "Inspectable withholding", {
          weight: 1.0,
          confidence: "high",
          criticality: "critical",
          description:
            "Explain not just that the system is withholding, but exactly why it is withholding and what would close the insufficiency.",
          target_state:
            "Insufficient cases expose explicit unknowns, contradiction pressure, gap codes, and bounded next-step requests in a way users can inspect.",
          implementation_basis:
            "Support trace, coverage, and answer decision already expose explicit unknowns, insufficiency reasons, and follow-up requests.",
          current_evidence:
            "The current answer layer is much better at saying why it cannot answer yet and what is still missing.",
          limitation:
            "The insufficiency vocabulary is still evolving and not yet a deep ontology.",
          blocker:
            "Withholding is inspectable, but the precision of the explanation remains bounded by the current trace layer.",
          recommended_next_step:
            "Deepen support and contradiction provenance so inspectable withholding becomes even more specific.",
          why_it_matters:
            "This is what turns honest restraint into operationally useful scientific guidance.",
          dependencies: [
            "contradiction-unknowns.requirement-linked-unknowns",
            "continuity-inspection.multi-level-inspection-surface",
          ],
          criteria: [
            criterion("unknowns-explained", "Unknowns are explained explicitly", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether insufficient cases expose requirement-linked unknowns rather than vague summaries.",
              current_evidence: "Unknowns and insufficiency reasons are already visible and machine-readable.",
              gap: "The ontology is still first-version.",
            }),
            criterion("next-steps-explained", "Next-step requests are tied to gaps", "strong", {
              confidence: "high",
              critical: true,
              measurement_basis: "Check whether additional data or experiments are explicitly tied to the blocking gaps.",
              current_evidence: "Current follow-up requests are linked to explicit insufficiency causes.",
              gap: "Request specificity is still bounded.",
            }),
            criterion("withholding-audit-depth", "The withholding rationale has strong audit depth", "substantial", {
              confidence: "medium",
              measurement_basis: "Check whether the user can trace the withholding reason through the scientific layers.",
              current_evidence: "Audit depth is much stronger than before, but still limited by the current modeled traces.",
              gap: "Deeper runtime-derived evidence trace links remain future work.",
            }),
          ],
        }),
      ],
    }),
  ],
};
