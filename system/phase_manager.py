from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilitySnapshot:
    title: str
    summary: str
    evidence: str


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


EXECUTION_PRINCIPLES: tuple[str, ...] = (
    "Preserve session continuity and current route behavior while improving the scientific core underneath.",
    "Make trust and explanation quality stronger before adding large new workflow surfaces.",
    "Remove legacy biodegradability assumptions from core modeling paths before claiming target-agnostic discovery support.",
    "Only harden infrastructure after the scientific and trust contracts are cleaner and easier to observe.",
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

        phase_items.append(
            {
                "phase_id": phase.phase_id,
                "order": phase.order,
                "order_label": f"Phase {phase.order}",
                "name": phase.name,
                "track": phase.track,
                "status": computed_status,
                "status_label": _status_label(computed_status),
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

    counts = {
        "total": len(phase_items),
        "completed": sum(1 for item in phase_items if item["status"] == "completed"),
        "active": sum(1 for item in phase_items if item["status"] == "active"),
        "ready": sum(1 for item in phase_items if item["status"] == "ready"),
        "blocked": sum(1 for item in phase_items if item["status"] == "blocked"),
    }
    completion_ratio = counts["completed"] / counts["total"] if counts["total"] else 0.0

    return {
        "title": "Discovery Intelligence Phase Manager",
        "last_updated": "2026-03-31",
        "program_summary": {
            "current_state": "The product surface is coherent and session-aware, but the scientific core still needs trust and modeling upgrades.",
            "current_focus": recommended_phase["name"] if recommended_phase is not None else "No active phase",
            "current_focus_reason": (
                recommended_phase["why_now"]
                if recommended_phase is not None
                else "No current phase is configured."
            ),
            "completion_ratio": completion_ratio,
        },
        "capability_snapshot": [
            {"title": item.title, "summary": item.summary, "evidence": item.evidence}
            for item in CAPABILITY_SNAPSHOT
        ],
        "execution_principles": list(EXECUTION_PRINCIPLES),
        "phases": sorted(phase_items, key=lambda item: item["order"]),
        "recommended_phase": recommended_phase,
        "next_up_phase": next_up_phase,
        "counts": counts,
    }
