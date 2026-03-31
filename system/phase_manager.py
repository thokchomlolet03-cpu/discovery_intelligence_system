from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GoalDefinition:
    title: str
    statement: str
    system_role: str
    value_statement: str
    completion_definition: str
    current_gap: str
    target_users: tuple[str, ...]


@dataclass(frozen=True)
class CapabilitySnapshot:
    title: str
    summary: str
    evidence: str


@dataclass(frozen=True)
class ScoreGroup:
    group_id: str
    name: str
    question: str
    current_state: str
    target_state: str
    why_it_matters: str
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class LoopStep:
    order: int
    name: str
    summary: str
    output: str


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    phase_id: str
    title: str
    source: str
    summary: str
    implication: str
    status: str


@dataclass(frozen=True)
class IterationDefinition:
    iteration_id: str
    phase_id: str
    name: str
    status: str
    hypothesis: str
    why_now: str
    scope: tuple[str, ...]
    focus_metrics: tuple[str, ...]
    success_signals: tuple[str, ...]
    ship_decision: str
    revise_trigger: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhaseDefinition:
    phase_id: str
    order: int
    name: str
    track: str
    status: str
    objective: str
    why_now: str
    outcome: str
    deliverables: tuple[str, ...]
    target_files: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    entry_criteria: tuple[str, ...] = ()
    exit_criteria: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


GOAL = GoalDefinition(
    title="North-star goal",
    statement="Help a small molecular R&D team choose better next experiments faster, with explanations they can trust and challenge.",
    system_role="Discovery Intelligence is a scientific decision-support workbench, not an autonomous discovery engine.",
    value_statement="The product should reduce decision friction, preserve evidence, and keep recommendations honest enough that a scientist can act on them without pretending certainty the model does not have.",
    completion_definition="The goal is being reached when the shortlist consistently leads to better follow-up experiments than a naive baseline, explanations are candidate-specific and challengeable, and the workspace remembers how later evidence changes future decisions.",
    current_gap="The product surface is coherent, but the scientific core still needs stronger trust contracts, more neutral target semantics, and truly measurement-first modeling before the loop can claim durable decision quality gains.",
    target_users=(
        "Small chemistry, materials, or polymer R&D teams deciding what to test next",
        "Individual researchers who need session-backed molecular prioritization instead of one-off scripts",
        "Scientific leads who need recommendation context, reviewability, and workspace continuity",
    ),
)


CAPABILITY_SNAPSHOT: tuple[CapabilitySnapshot, ...] = (
    CapabilitySnapshot(
        title="Session-aware workbench",
        summary="Upload, Discovery, Dashboard, Sessions, Billing, and About now behave like one connected product surface.",
        evidence="The UI flow is session-backed and consistent across the main workbench routes.",
    ),
    CapabilitySnapshot(
        title="Measurement-aware ingestion",
        summary="The system accepts measurement datasets, structure-only inputs, labeled datasets, text SMILES lists, and SDF files.",
        evidence="Canonical ingestion and semantic mapping are already wired through upload inspection and validation.",
    ),
    CapabilitySnapshot(
        title="Decision guidance",
        summary="Discovery and Dashboard already promote next-step recommendations rather than exposing only raw rankings.",
        evidence="Priority score, recommendation summaries, and trust panels are part of the live product surface.",
    ),
    CapabilitySnapshot(
        title="Workspace control plane",
        summary="Authentication, workspace scoping, billing enforcement, review actions, and session history are in place.",
        evidence="The control-plane foundations are tested and part of the deployed app workflow.",
    ),
)


SCORE_GROUPS: tuple[ScoreGroup, ...] = (
    ScoreGroup(
        group_id="decision_quality",
        name="Decision quality",
        question="Does the shortlist help the team choose better next experiments than a naive baseline?",
        current_state="The system produces ranked shortlists and recommendation buckets, but value-model evidence is still partial and classification heuristics still carry too much weight.",
        target_state="Top-k lift, rank correlation, shortlist acceptance, and experiment follow-through all point in the same direction: the workbench helps users choose better experiments.",
        why_it_matters="If shortlist quality is weak, everything else becomes interface theater around mediocre decisions.",
        metrics=(
            "Top-k enrichment and shortlist acceptance rate",
            "Rank correlation for measurement-backed sessions",
            "Share of recommendations later validated positively",
        ),
    ),
    ScoreGroup(
        group_id="trust_quality",
        name="Trust quality",
        question="Can a scientist understand, challenge, and responsibly use the recommendation?",
        current_state="Discovery and Dashboard are clearer than before, but explanations are still too heuristic and candidate-level trust signals are not yet structured enough.",
        target_state="Every leading candidate explains why it is recommended now, what evidence supports it, and how uncertainty or out-of-domain risk should change user behavior.",
        why_it_matters="Users will not act on a shortlist they cannot interrogate or when different surfaces imply different truths.",
        metrics=(
            "Top candidates with structured rationale",
            "Runs with no semantic inconsistency across pages",
            "Candidate-level OOD visibility and caution coverage",
        ),
    ),
    ScoreGroup(
        group_id="workflow_quality",
        name="Workflow quality",
        question="Can the user move from upload to an actionable shortlist without losing context?",
        current_state="The session-aware UX is strong and reopening works, but comparison, feedback continuity, and some deeper interpretive flows are still missing.",
        target_state="Users can move from upload to recommendation quickly, reopen work naturally, and compare how new evidence changes the shortlist.",
        why_it_matters="A strong model is not enough if the workbench cannot preserve continuity and reduce user effort.",
        metrics=(
            "Upload-to-shortlist completion rate",
            "Time to first usable recommendation",
            "Session reopen and continuation rate",
        ),
    ),
    ScoreGroup(
        group_id="learning_quality",
        name="Learning quality",
        question="Does the workspace improve as more evidence accumulates over time?",
        current_state="Sessions are preserved, but explicit feedback memory, session comparison, and model-improvement loops are still early.",
        target_state="The workspace can show how new evidence changed trust, shortlist ordering, and future experiment guidance.",
        why_it_matters="Without a learning loop, the product stays a static ranking tool instead of becoming a scientific workbench.",
        metrics=(
            "Sessions with feedback captured",
            "Session comparisons completed",
            "Observed improvement in later ranking or trust diagnostics after feedback cycles",
        ),
    ),
)


LOOP_CYCLE: tuple[LoopStep, ...] = (
    LoopStep(order=1, name="Observe", summary="Collect evidence from sessions, diagnostics, failures, reviews, and model behavior.", output="Current bottleneck evidence"),
    LoopStep(order=2, name="Diagnose", summary="Identify the single biggest blocker to trusted decision quality.", output="Primary bottleneck selection"),
    LoopStep(order=3, name="Choose phase goal", summary="Select the active phase that best addresses that bottleneck.", output="Active phase commitment"),
    LoopStep(order=4, name="Write hypothesis", summary="State what improvement should change and why it should help users decide better.", output="Iteration hypothesis"),
    LoopStep(order=5, name="Define exit criteria", summary="Make success concrete enough to ship or revise without hand-waving.", output="Ship and revise gates"),
    LoopStep(order=6, name="Implement", summary="Make the smallest coherent system change that satisfies the hypothesis.", output="Working code change"),
    LoopStep(order=7, name="Verify", summary="Run tests, QA, and live checks against the target behaviors.", output="Evidence package"),
    LoopStep(order=8, name="Deploy", summary="Ship to production through the existing pipeline.", output="Live system state"),
    LoopStep(order=9, name="Measure", summary="Compare outcome signals against the expected impact.", output="Post-ship outcome read"),
    LoopStep(order=10, name="Decide", summary="Continue, revise, complete, or move to the next phase.", output="Next iteration decision"),
)


EXECUTION_PRINCIPLES: tuple[str, ...] = (
    "Preserve session continuity and current route behavior while improving the scientific core underneath.",
    "Make trust and explanation quality stronger before adding large new workflow surfaces.",
    "Remove legacy biodegradability assumptions from core modeling paths before claiming target-agnostic discovery support.",
    "Only harden infrastructure after the scientific and trust contracts are cleaner and easier to observe.",
)


EVIDENCE_LOG: tuple[EvidenceItem, ...] = (
    EvidenceItem(
        evidence_id="surface_coherence_live",
        phase_id="workflow_surface_coherence",
        title="Session-aware workbench is now the baseline",
        source="templates/upload.html, templates/discovery.html, templates/dashboard.html, templates/sessions.html",
        summary="The product surface now preserves session continuity across the primary workflow instead of behaving like disconnected tools.",
        implication="Future iterations can target trust and scientific correctness instead of basic navigation continuity.",
        status="confirmed",
    ),
    EvidenceItem(
        evidence_id="tests_green_baseline",
        phase_id="workflow_surface_coherence",
        title="Current baseline is regression-tested",
        source="Full local suite and GitHub CI",
        summary="The recent product-surface work is already protected by a passing test and deploy pipeline.",
        implication="The next loop can tighten interpretation without destabilizing the whole app blindly.",
        status="confirmed",
    ),
    EvidenceItem(
        evidence_id="explanations_still_heuristic",
        phase_id="trust_contract_explanations",
        title="Candidate explanations are still too heuristic",
        source="system/explanation_engine.py and current Discovery/Dashboard rationale flow",
        summary="The workbench is better at presenting recommendations than before, but the primary rationale is still not structured enough to answer why this, why now, and how risky with enough specificity.",
        implication="Trust contract work remains the highest-leverage active phase.",
        status="active",
    ),
    EvidenceItem(
        evidence_id="measurement_surface_ahead_of_model",
        phase_id="measurement_first_modeling",
        title="Measurement support is ahead of measurement modeling",
        source="Ingestion, reporting, and dashboard surfaces versus current scoring core",
        summary="Measurement datasets are visible and first-class in workflow terms, but the modeling core still leans too heavily on classification-style behavior.",
        implication="Measurement-first modeling should follow once trust and target semantics are cleaner.",
        status="monitoring",
    ),
    EvidenceItem(
        evidence_id="legacy_biodegradable_bias",
        phase_id="neutral_scientific_core",
        title="Legacy target semantics still leak through the scientific core",
        source="system/services/data_service.py, system/services/analysis_service.py, decision/decision_engine.py",
        summary="The product now presents itself as a broader decision-support system, but internal naming and some rule text still reflect the earlier biodegradability focus.",
        implication="The core should be neutralized before making stronger target-agnostic claims.",
        status="monitoring",
    ),
    EvidenceItem(
        evidence_id="jobs_still_in_process",
        phase_id="execution_durability",
        title="Execution still depends on in-process workers",
        source="system/job_manager.py",
        summary="Background runs are session-aware and user-friendly, but they still rely on the current process rather than a durable worker path.",
        implication="Operational hardening matters, but only after the scientific and trust contract are stable enough to preserve.",
        status="planned",
    ),
)


ITERATIONS: tuple[IterationDefinition, ...] = (
    IterationDefinition(
        iteration_id="iteration_surface_coherence_baseline",
        phase_id="workflow_surface_coherence",
        name="Session-aware surface coherence baseline",
        status="completed",
        hypothesis="If the app behaves like one connected workbench instead of separate tools, users will stop losing context between Upload, Discovery, Dashboard, and Sessions.",
        why_now="This was the prerequisite for all later trust and scientific-core work.",
        scope=(
            "Unify page roles and design language",
            "Make session continuity visible across the main workbench routes",
            "Reduce tool-like page fragmentation",
        ),
        focus_metrics=(
            "Session reopen continuity",
            "Cross-page navigation consistency",
            "Worksurface coherence under regression tests",
        ),
        success_signals=(
            "Primary workbench routes reopen the same session naturally",
            "Users do not hit empty-state confusion after a successful run",
        ),
        ship_decision="This phase is complete enough to treat as the new product baseline.",
        revise_trigger="Reopen this phase only if new scientific-core work breaks continuity again.",
        evidence_refs=("surface_coherence_live", "tests_green_baseline"),
    ),
    IterationDefinition(
        iteration_id="iteration_trust_contract_v1",
        phase_id="trust_contract_explanations",
        name="Candidate trust contract v1",
        status="active",
        hypothesis="If each leading candidate exposes structured rationale, score decomposition, and explicit domain-risk context, users will trust and challenge the shortlist more effectively.",
        why_now="The product surface is already coherent enough that trust quality is now the biggest bottleneck to decision value.",
        scope=(
            "Replace generic explanation text with structured rationale objects",
            "Persist score contribution breakdowns for confidence, uncertainty, novelty, and experiment value",
            "Surface candidate-level domain status consistently across Discovery and Dashboard",
        ),
        focus_metrics=(
            "Top candidates with structured rationale",
            "Candidate-level OOD visibility",
            "Cross-page trust consistency for the same session",
        ),
        success_signals=(
            "Top candidates answer why this, why now, and how risky in user-facing language",
            "Discovery and Dashboard present the same trust story for the same shortlist",
            "Primary rationale is no longer just a heuristic sentence template",
        ),
        ship_decision="Ship when the top of the shortlist is auditable enough that a scientist can challenge the recommendation without reading raw internals.",
        revise_trigger="Revise if trust surfaces get noisier, score contributions become confusing, or primary recommendation hierarchy collapses under new detail.",
        evidence_refs=("tests_green_baseline", "explanations_still_heuristic"),
    ),
    IterationDefinition(
        iteration_id="iteration_neutral_core_v1",
        phase_id="neutral_scientific_core",
        name="Neutral target semantics v1",
        status="planned",
        hypothesis="If the internal model and rule layers stop leaking biodegradability-specific assumptions, the platform can honestly support broader molecular decision workflows.",
        why_now="This should begin only after the trust contract is stable enough that changing scientific-core semantics does not move too many foundations at once.",
        scope=(
            "Introduce target-agnostic internal semantics",
            "Preserve backward compatibility for legacy sessions and artifacts",
            "Remove biodegradability-specific decision language from user-facing outputs",
        ),
        focus_metrics=(
            "Legacy session compatibility",
            "Reduction in biodegradability-specific naming across core data flow",
            "Stable artifact loading after semantic neutralization",
        ),
        success_signals=(
            "The system can describe itself honestly as target-agnostic at the contract level",
            "Legacy sessions still load without migration regressions",
        ),
        ship_decision="Ship when core naming and rule language are neutralized without breaking existing artifacts.",
        revise_trigger="Revise if compatibility fixes start leaking target-specific assumptions back into the new contracts.",
        evidence_refs=("legacy_biodegradable_bias",),
    ),
    IterationDefinition(
        iteration_id="iteration_measurement_modeling_v1",
        phase_id="measurement_first_modeling",
        name="Measurement-first modeling v1",
        status="planned",
        hypothesis="If measurement sessions use a native value-model path instead of classification-style fallbacks, the shortlist will align better with observed-value evidence.",
        why_now="This depends on both trust-contract visibility and neutral target semantics being stable enough first.",
        scope=(
            "Add native regression or value-model scoring",
            "Expose measurement-specific diagnostics and ranking alignment",
            "Reduce dependence on derived binary labels for measurement-backed runs",
        ),
        focus_metrics=(
            "Rank correlation for measurement-backed sessions",
            "Measurement shortlist alignment",
            "Value-model trust diagnostics on Dashboard",
        ),
        success_signals=(
            "Measurement datasets no longer feel secondary to label derivation",
            "Dashboard diagnostics reflect real value-model trust signals",
        ),
        ship_decision="Ship when measurement-backed sessions are first-class in both modeling and explanation terms.",
        revise_trigger="Revise if value-model diagnostics stay harder to interpret than the current classification-style outputs.",
        evidence_refs=("measurement_surface_ahead_of_model",),
    ),
    IterationDefinition(
        iteration_id="iteration_session_memory_v1",
        phase_id="session_comparison_feedback_memory",
        name="Session comparison and feedback memory v1",
        status="planned",
        hypothesis="If users can compare sessions and see how later evidence changes trust and shortlist ordering, the workspace becomes a learning system instead of a run archive.",
        why_now="The sessions surface exists already, but the product still lacks comparative memory and explicit feedback continuity.",
        scope=(
            "Add session comparison framing",
            "Connect review and experiment feedback back into later sessions",
            "Make memory part of the workspace instead of hidden artifact state",
        ),
        focus_metrics=(
            "Session comparisons completed",
            "Feedback captured per workspace",
            "Continuation rate across related sessions",
        ),
        success_signals=(
            "Users can explain how one session changed the next",
            "Feedback memory is visible without digging through artifacts",
        ),
        ship_decision="Ship when a workspace can compare runs and show what later evidence changed.",
        revise_trigger="Revise if comparison reads as noise because trust or scoring semantics are still unstable.",
        evidence_refs=("surface_coherence_live",),
    ),
    IterationDefinition(
        iteration_id="iteration_execution_durability_v1",
        phase_id="execution_durability",
        name="Durable worker hardening v1",
        status="planned",
        hypothesis="If job execution becomes durable and observable without changing the user-facing session model, the system will be safer to operate as usage increases.",
        why_now="This should happen after the scientific and trust contracts are stable enough that we know what behavior deserves hardening.",
        scope=(
            "Add a more durable execution path",
            "Improve retry and observability",
            "Preserve current session-backed product behavior during infrastructure changes",
        ),
        focus_metrics=(
            "Job failure rate",
            "Recoverability after interruption",
            "Operational debugging visibility",
        ),
        success_signals=(
            "Jobs survive process-level issues more gracefully",
            "Operators can diagnose failures without reconstructing them manually",
        ),
        ship_decision="Ship when infrastructure hardening improves reliability without changing trusted product behavior.",
        revise_trigger="Revise if infra changes destabilize the current session and artifact contract.",
        evidence_refs=("jobs_still_in_process",),
    ),
)


PHASES: tuple[PhaseDefinition, ...] = (
    PhaseDefinition(
        phase_id="workflow_surface_coherence",
        order=0,
        name="Workflow and Surface Coherence",
        track="Product Surface",
        status="completed",
        objective="Turn the app into a coherent, session-aware scientific workbench.",
        why_now="This baseline was required before deeper scientific and trust work could land cleanly.",
        outcome="Home, Upload, Discovery, Dashboard, Sessions, Billing, and About now read as one product instead of separate tools.",
        deliverables=(
            "Session-aware navigation and reopen flow",
            "Decision-oriented Upload, Discovery, and Dashboard surfaces",
            "Workspace memory through Sessions history",
            "Consistent product shell and design language",
        ),
        target_files=(
            "templates/upload.html",
            "templates/discovery.html",
            "templates/dashboard.html",
            "templates/sessions.html",
            "templates/index.html",
            "templates/billing.html",
            "templates/about.html",
            "static/ui-refresh.css",
        ),
        exit_criteria=(
            "Primary pages express clear page roles and session continuity",
            "The workbench surface is no longer the main product bottleneck",
        ),
    ),
    PhaseDefinition(
        phase_id="trust_contract_explanations",
        order=1,
        name="Trust Contract and Explanation Upgrade",
        track="Trust Layer",
        status="active",
        objective="Make every recommendation easier to audit, interpret, and challenge.",
        why_now="The product surface is coherent enough that explanation quality and trust are now the main user-facing gap.",
        outcome="Candidates expose structured rationale, score decomposition, and clearer domain-risk context.",
        deliverables=(
            "Structured explanation contract per candidate",
            "Score decomposition for confidence, uncertainty, novelty, and experiment-value contributions",
            "Candidate-level domain status and trust cues",
            "Shared trust language across Discovery and Dashboard",
        ),
        target_files=(
            "system/explanation_engine.py",
            "system/session_report.py",
            "system/discovery_workbench.py",
            "system/dashboard_data.py",
            "system/contracts/schemas.py",
            "templates/discovery.html",
            "templates/dashboard.html",
            "static/discovery.js",
        ),
        dependencies=("workflow_surface_coherence",),
        entry_criteria=(
            "Decision guidance and trust surfaces are already deployed",
            "Session-aware UX is stable enough to support deeper interpretation changes",
        ),
        exit_criteria=(
            "Top candidates answer why this, why now, and how risky",
            "The main explanation surface is no longer template-like or generic",
        ),
        risks=(
            "Too much diagnostic detail can drown the primary recommendation if hierarchy is not maintained",
        ),
    ),
    PhaseDefinition(
        phase_id="neutral_scientific_core",
        order=2,
        name="Neutral Scientific Core",
        track="Scientific Core",
        status="planned",
        objective="Reduce legacy biodegradability assumptions in data, modeling, and rule layers.",
        why_now="The product now presents itself as a broader molecular decision system, so the internal naming and assumptions need to catch up.",
        outcome="Core data and model paths use target-agnostic semantics while preserving backward compatibility for legacy sessions.",
        deliverables=(
            "Neutral internal target semantics instead of hardwired biodegradability naming",
            "Backward-compatible migration path for legacy artifacts and sessions",
            "Removal of biodegradability-specific rule text from decision outputs",
        ),
        target_files=(
            "system/services/data_service.py",
            "system/services/analysis_service.py",
            "system/services/training_service.py",
            "system/services/candidate_service.py",
            "system/upload_parser.py",
            "decision/decision_engine.py",
            "system/contracts/schemas.py",
        ),
        dependencies=("trust_contract_explanations",),
        entry_criteria=(
            "Trust contract work is stable enough to avoid changing multiple foundations at once",
        ),
        exit_criteria=(
            "The platform can describe itself honestly as target-agnostic at the core contract level",
            "Legacy sessions still load without schema regressions",
        ),
        risks=(
            "Renaming target semantics can break artifacts and training paths if compatibility is not handled carefully",
        ),
    ),
    PhaseDefinition(
        phase_id="measurement_first_modeling",
        order=3,
        name="Measurement-First Modeling",
        track="Scientific Core",
        status="planned",
        objective="Make measurement datasets first-class in modeling rather than only in ingestion and reporting.",
        why_now="Measurement evidence is already visible across the UX, but the scoring core still leans classification-first.",
        outcome="Measurement sessions can use native value modeling, ranking diagnostics, and decision summaries tied to observed-value alignment.",
        deliverables=(
            "Regression or value-model path for measurement-backed sessions",
            "Ranking logic that combines predicted value, uncertainty, novelty, and experiment value",
            "Dashboard diagnostics for rank correlation, lift, and value alignment",
        ),
        target_files=(
            "system/run_pipeline.py",
            "system/services/training_service.py",
            "system/services/analysis_service.py",
            "system/session_report.py",
            "system/dashboard_data.py",
        ),
        dependencies=("trust_contract_explanations", "neutral_scientific_core"),
        entry_criteria=(
            "Core target semantics are neutral enough to support value-modeling honestly",
        ),
        exit_criteria=(
            "Measurement datasets no longer rely on binary-label derivation to feel first-class",
            "The dashboard exposes value-model trust signals for those runs",
        ),
        risks=(
            "If evaluation logic stays classification-centric, the new model path will confuse users rather than help them",
        ),
    ),
    PhaseDefinition(
        phase_id="session_comparison_feedback_memory",
        order=4,
        name="Session Comparison and Feedback Memory",
        track="Learning Workspace",
        status="planned",
        objective="Turn sessions into cumulative workspace memory rather than isolated reopenable runs.",
        why_now="The session-history surface exists, but the product still lacks comparison and explicit experiment-feedback continuity.",
        outcome="Teams can compare sessions, inspect what changed, and connect later evidence back into the workbench.",
        deliverables=(
            "Session comparison surface for shortlist and trust changes",
            "Clearer experiment feedback capture and visibility",
            "Workspace-level continuity beyond a single latest session",
        ),
        target_files=(
            "system/session_history.py",
            "system/review_manager.py",
            "system/services/artifact_service.py",
            "templates/sessions.html",
            "templates/discovery.html",
        ),
        dependencies=("trust_contract_explanations",),
        entry_criteria=(
            "Candidate trust language is stable enough to compare meaningfully across sessions",
        ),
        exit_criteria=(
            "Users can inspect how two sessions differ without manual cross-reading",
            "Feedback memory is visible as part of the workspace, not just hidden in artifacts",
        ),
        risks=(
            "Comparison will feel noisy if explanation and scoring semantics are still changing underneath it",
        ),
    ),
    PhaseDefinition(
        phase_id="execution_durability",
        order=5,
        name="Execution Durability and Worker Hardening",
        track="Platform Ops",
        status="planned",
        objective="Make background execution more durable and observable than the current in-process thread model.",
        why_now="This matters, but it should happen after the scientific and trust contracts are worth hardening operationally.",
        outcome="Jobs gain stronger retry, observability, and operational safety without changing the user-facing session model.",
        deliverables=(
            "Durable worker execution path",
            "Retry and observability improvements for analysis jobs",
            "Operational hardening without regressing the current session-backed product flow",
        ),
        target_files=(
            "system/job_manager.py",
            "app.py",
            "scripts/deploy.sh",
            "docker-compose.yml",
        ),
        dependencies=("neutral_scientific_core", "measurement_first_modeling", "session_comparison_feedback_memory"),
        entry_criteria=(
            "The scientific core and trust layer are stable enough that operational hardening locks in the right behavior",
        ),
        exit_criteria=(
            "Job execution can survive process-level interruption more gracefully",
            "Operational observability is strong enough for real production debugging",
        ),
        risks=(
            "Hardening the wrong execution contract too early would add complexity without raising product truth",
        ),
    ),
)


def _status_label(status: str) -> str:
    mapping = {
        "completed": "Completed",
        "active": "Active now",
        "ready": "Ready next",
        "blocked": "Blocked",
        "planned": "Planned",
    }
    return mapping.get(status, "Planned")


def _status_priority(status: str) -> int:
    order = {"active": 0, "ready": 1, "blocked": 2, "planned": 3, "completed": 4}
    return order.get(status, 99)


def build_phase_manager_context() -> dict[str, Any]:
    completed_ids = {phase.phase_id for phase in PHASES if phase.status == "completed"}
    active_phase_id = next((phase.phase_id for phase in PHASES if phase.status == "active"), "")
    evidence_by_id = {item.evidence_id: item for item in EVIDENCE_LOG}
    iteration_by_phase = {item.phase_id: item for item in ITERATIONS}

    phase_items: list[dict[str, Any]] = []
    for phase in PHASES:
        base_status = phase.status
        if base_status == "planned":
            computed_status = "ready" if all(dep in completed_ids for dep in phase.dependencies) else "blocked"
        else:
            computed_status = base_status

        dependency_details = []
        for dependency in phase.dependencies:
            dependency_phase = next(item for item in PHASES if item.phase_id == dependency)
            satisfied = dependency in completed_ids
            dependency_details.append(
                {
                    "phase_id": dependency_phase.phase_id,
                    "name": dependency_phase.name,
                    "status": dependency_phase.status,
                    "status_label": _status_label(dependency_phase.status),
                    "satisfied": satisfied,
                }
            )

        phase_iteration = iteration_by_phase.get(phase.phase_id)
        iteration_summary = None
        if phase_iteration is not None:
            iteration_summary = {
                "iteration_id": phase_iteration.iteration_id,
                "name": phase_iteration.name,
                "status": phase_iteration.status,
                "hypothesis": phase_iteration.hypothesis,
                "focus_metrics": list(phase_iteration.focus_metrics),
                "success_signals": list(phase_iteration.success_signals),
            }

        if computed_status == "blocked" and dependency_details:
            blocked_by = [item["name"] for item in dependency_details if not item["satisfied"]]
            status_reason = f"Waiting on: {', '.join(blocked_by)}"
        elif computed_status == "ready":
            status_reason = "Dependencies are satisfied and this phase can start once the current focus phase closes."
        elif computed_status == "active":
            status_reason = "This is the current highest-leverage bottleneck in the loop."
        elif computed_status == "completed":
            status_reason = "This phase is already part of the current product baseline."
        else:
            status_reason = "This phase is planned but not yet activated."

        phase_items.append(
            {
                "phase_id": phase.phase_id,
                "order": phase.order,
                "order_label": f"Phase {phase.order}",
                "name": phase.name,
                "track": phase.track,
                "status": computed_status,
                "status_label": _status_label(computed_status),
                "status_reason": status_reason,
                "objective": phase.objective,
                "why_now": phase.why_now,
                "outcome": phase.outcome,
                "deliverables": list(phase.deliverables),
                "target_files": list(phase.target_files),
                "dependencies": list(phase.dependencies),
                "dependency_details": dependency_details,
                "entry_criteria": list(phase.entry_criteria),
                "exit_criteria": list(phase.exit_criteria),
                "risks": list(phase.risks),
                "is_active": phase.phase_id == active_phase_id,
                "iteration": iteration_summary,
            }
        )

    recommended_phase = next((item for item in phase_items if item["status"] == "active"), None)
    if recommended_phase is None:
        ready_candidates = sorted((item for item in phase_items if item["status"] == "ready"), key=lambda item: item["order"])
        recommended_phase = ready_candidates[0] if ready_candidates else None

    next_up_phase = None
    if recommended_phase is not None:
        future_candidates = sorted(
            (item for item in phase_items if item["order"] > recommended_phase["order"] and item["status"] != "completed"),
            key=lambda item: (item["order"], _status_priority(item["status"])),
        )
        next_up_phase = future_candidates[0] if future_candidates else None

    iteration_items: list[dict[str, Any]] = []
    for item in ITERATIONS:
        evidence_details = []
        for reference in item.evidence_refs:
            evidence_item = evidence_by_id[reference]
            evidence_details.append(
                {
                    "evidence_id": evidence_item.evidence_id,
                    "title": evidence_item.title,
                    "source": evidence_item.source,
                    "summary": evidence_item.summary,
                    "implication": evidence_item.implication,
                    "status": evidence_item.status,
                }
            )

        iteration_items.append(
            {
                "iteration_id": item.iteration_id,
                "phase_id": item.phase_id,
                "name": item.name,
                "status": item.status,
                "status_label": _status_label(item.status),
                "hypothesis": item.hypothesis,
                "why_now": item.why_now,
                "scope": list(item.scope),
                "focus_metrics": list(item.focus_metrics),
                "success_signals": list(item.success_signals),
                "ship_decision": item.ship_decision,
                "revise_trigger": item.revise_trigger,
                "evidence": evidence_details,
            }
        )

    active_iteration = next((item for item in iteration_items if item["status"] == "active"), None)
    next_iteration = None
    if active_iteration is not None:
        next_iteration = next(
            (
                item for item in iteration_items
                if item["status"] == "planned"
                and next_up_phase is not None
                and item["phase_id"] == next_up_phase["phase_id"]
            ),
            None,
        )

    evidence_items = [
        {
            "evidence_id": item.evidence_id,
            "phase_id": item.phase_id,
            "title": item.title,
            "source": item.source,
            "summary": item.summary,
            "implication": item.implication,
            "status": item.status,
        }
        for item in EVIDENCE_LOG
    ]

    counts = {
        "total": len(phase_items),
        "completed": sum(1 for item in phase_items if item["status"] == "completed"),
        "active": sum(1 for item in phase_items if item["status"] == "active"),
        "ready": sum(1 for item in phase_items if item["status"] == "ready"),
        "blocked": sum(1 for item in phase_items if item["status"] == "blocked"),
        "iterations": len(iteration_items),
        "evidence_items": len(evidence_items),
    }
    completion_ratio = counts["completed"] / counts["total"] if counts["total"] else 0.0

    return {
        "title": "Discovery Intelligence Goal Loop Manager",
        "last_updated": "2026-03-31",
        "goal": {
            "title": GOAL.title,
            "statement": GOAL.statement,
            "system_role": GOAL.system_role,
            "value_statement": GOAL.value_statement,
            "completion_definition": GOAL.completion_definition,
            "current_gap": GOAL.current_gap,
            "target_users": list(GOAL.target_users),
        },
        "program_summary": {
            "current_state": "The product surface is coherent and session-aware, but the scientific core still needs trust and modeling upgrades.",
            "current_focus": recommended_phase["name"] if recommended_phase is not None else "No active phase",
            "current_focus_reason": (
                recommended_phase["why_now"]
                if recommended_phase is not None
                else "No current phase is configured."
            ),
            "completion_ratio": completion_ratio,
            "active_iteration": active_iteration["name"] if active_iteration is not None else "No active iteration",
        },
        "capability_snapshot": [
            {"title": item.title, "summary": item.summary, "evidence": item.evidence}
            for item in CAPABILITY_SNAPSHOT
        ],
        "score_groups": [
            {
                "group_id": item.group_id,
                "name": item.name,
                "question": item.question,
                "current_state": item.current_state,
                "target_state": item.target_state,
                "why_it_matters": item.why_it_matters,
                "metrics": list(item.metrics),
            }
            for item in SCORE_GROUPS
        ],
        "loop_cycle": [
            {
                "order": item.order,
                "order_label": f"Step {item.order}",
                "name": item.name,
                "summary": item.summary,
                "output": item.output,
            }
            for item in LOOP_CYCLE
        ],
        "execution_principles": list(EXECUTION_PRINCIPLES),
        "phases": sorted(phase_items, key=lambda item: item["order"]),
        "iterations": iteration_items,
        "active_iteration": active_iteration,
        "next_iteration": next_iteration,
        "evidence_log": evidence_items,
        "recommended_phase": recommended_phase,
        "next_up_phase": next_up_phase,
        "counts": counts,
    }
