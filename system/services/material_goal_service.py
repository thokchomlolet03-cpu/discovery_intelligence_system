from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()

POLYMER_HINTS = {
    "polymer",
    "plastic",
    "film",
    "barrier",
    "coating",
    "packaging",
    "biodegradable",
    "compostable",
    "transient",
    "responsive",
    "hydrogel",
    "membrane",
    "adhesive",
}
PROPERTY_HINTS = {
    "barrier",
    "oxygen",
    "moisture",
    "water resistance",
    "strength",
    "flexible",
    "toughness",
    "transparent",
    "biodegradable",
    "compostable",
    "thermal",
    "heat resistant",
    "chemical resistance",
    "degrade",
    "dissolve",
    "shelf life",
}
APPLICATION_HINTS = {
    "packaging",
    "food packaging",
    "medical",
    "coating",
    "film",
    "membrane",
    "adhesive",
    "device",
    "encapsulation",
}
ENVIRONMENT_HINTS = {
    "humidity",
    "humid",
    "water",
    "aqueous",
    "temperature",
    "heat",
    "cold",
    "outdoor",
    "marine",
    "soil",
    "compost",
    "ph",
    "solvent",
}
LIFECYCLE_HINTS = {
    "days",
    "weeks",
    "months",
    "years",
    "shelf life",
    "stable",
    "degrade",
    "degradation",
    "compostable",
    "transient",
    "lifetime",
}
TRIGGER_HINTS = {
    "ph",
    "humidity",
    "temperature",
    "light",
    "uv",
    "enzyme",
    "enzymatic",
    "solvent",
    "water",
    "trigger",
    "dissolve",
}
REGULATORY_HINTS = {
    "food contact",
    "medical",
    "biocompatible",
    "fda",
    "echa",
    "reach",
    "toxicity",
    "safe",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _contains_any(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _extract_matches(text: str, keywords: set[str]) -> list[str]:
    lowered = text.lower()
    found = [keyword for keyword in sorted(keywords) if keyword in lowered]
    return found[:8]


def _structured_requirements(raw_user_goal: str) -> dict[str, Any]:
    text = _clean_text(raw_user_goal)
    lowered = text.lower()
    return {
        "domain_scope": "polymer_material" if _contains_any(lowered, POLYMER_HINTS) else "unspecified_material_domain",
        "target_material_function": _extract_matches(lowered, APPLICATION_HINTS),
        "desired_properties": _extract_matches(lowered, PROPERTY_HINTS),
        "operating_environment": _extract_matches(lowered, ENVIRONMENT_HINTS),
        "lifecycle_window": _extract_matches(lowered, LIFECYCLE_HINTS),
        "trigger_conditions": _extract_matches(lowered, TRIGGER_HINTS),
        "safety_or_regulatory_constraints": _extract_matches(lowered, REGULATORY_HINTS),
        "constraint_mode": "mixed" if "must" in lowered or "require" in lowered or "prefer" in lowered else "unspecified",
    }


def _missing_critical_requirements(structured: dict[str, Any], raw_user_goal: str) -> list[str]:
    lowered = _clean_text(raw_user_goal).lower()
    missing: list[str] = []
    if not structured.get("target_material_function"):
        missing.append("target_material_function")
    if not structured.get("desired_properties"):
        missing.append("desired_properties")
    if (
        any(token in lowered for token in {"barrier", "packaging", "film", "coating", "humid", "water", "marine", "outdoor", "temperature", "heat"})
        and not structured.get("operating_environment")
    ):
        missing.append("operating_environment")
    if (
        any(token in lowered for token in {"stable", "degrade", "degradation", "compostable", "transient", "shelf life", "lifetime"})
        and not structured.get("lifecycle_window")
    ):
        missing.append("lifecycle_window")
    if (
        any(token in lowered for token in {"trigger", "responsive", "dissolve", "ph", "humidity", "temperature", "light", "uv", "enzyme"})
        and not structured.get("trigger_conditions")
    ):
        missing.append("trigger_conditions")
    if (
        any(token in lowered for token in {"food contact", "medical", "safe", "toxicity", "biocompatible", "fda", "reach"})
        and not structured.get("safety_or_regulatory_constraints")
    ):
        missing.append("safety_or_regulatory_constraints")
    return missing


def _clarification_questions(missing: list[str], structured: dict[str, Any]) -> list[str]:
    prompts: dict[str, str] = {
        "target_material_function": "What is the intended material function or application, for example packaging film, coating, membrane, adhesive, or medical use?",
        "desired_properties": "Which material properties are critical to optimize, for example moisture barrier, oxygen barrier, flexibility, strength, biodegradability, or transparency?",
        "operating_environment": "What operating or use environment should the material withstand, for example humidity range, water exposure, temperature range, solvent contact, or compost/soil conditions?",
        "lifecycle_window": "What stability or lifetime window is required before degradation, transition, or replacement becomes acceptable?",
        "trigger_conditions": "Is the material expected to respond or transition under a specific trigger such as pH, humidity, temperature, light, enzymatic exposure, or water contact?",
        "safety_or_regulatory_constraints": "Are there hard safety, toxicity, food-contact, medical, or regulatory constraints that must be respected?",
    }
    return [prompts[item] for item in missing if item in prompts][:4]


def _scientific_target_summary(structured: dict[str, Any], missing: list[str]) -> str:
    function = ", ".join(structured.get("target_material_function") or [])
    properties = ", ".join(structured.get("desired_properties") or [])
    environment = ", ".join(structured.get("operating_environment") or [])
    lifecycle = ", ".join(structured.get("lifecycle_window") or [])
    if missing:
        return "Material goal remains insufficiently specified for scientific retrieval because critical constraints are still missing."
    parts = []
    if function:
        parts.append(f"Target function: {function}.")
    if properties:
        parts.append(f"Desired properties: {properties}.")
    if environment:
        parts.append(f"Use environment: {environment}.")
    if lifecycle:
        parts.append(f"Lifecycle window: {lifecycle}.")
    return " ".join(parts) or "Material goal is sufficiently specified for the current first-battlefield intake layer."


def build_material_goal_specification(
    *,
    session_id: str,
    workspace_id: str,
    raw_user_goal: str,
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    structured = _structured_requirements(raw_user_goal)
    missing = _missing_critical_requirements(structured, raw_user_goal)
    questions = _clarification_questions(missing, structured)
    requirement_status = "sufficiently_specified" if not missing else "insufficient_needs_clarification"
    return {
        "goal_id": _make_id("material_goal"),
        "session_id": session_id,
        "workspace_id": workspace_id,
        "created_by_user_id": created_by_user_id or "",
        "raw_user_goal": _clean_text(raw_user_goal),
        "domain_scope": "polymer_material",
        "requirement_status": requirement_status,
        "structured_requirements": structured,
        "missing_critical_requirements": missing,
        "clarification_questions": questions,
        "scientific_target_summary": _scientific_target_summary(structured, missing),
        "provenance_markers": {
            "goal_spec_mode": "bounded_first_battlefield_requirement_sufficiency",
            "silent_fill_of_critical_requirements": False,
        },
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


def persist_material_goal_specification(
    *,
    session_id: str,
    workspace_id: str,
    raw_user_goal: str,
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    spec = build_material_goal_specification(
        session_id=session_id,
        workspace_id=workspace_id,
        raw_user_goal=raw_user_goal,
        created_by_user_id=created_by_user_id,
    )
    try:
        existing = scientific_state_repository.get_material_goal_specification(session_id=session_id, workspace_id=workspace_id)
        spec["goal_id"] = _clean_text(existing.get("goal_id")) or spec["goal_id"]
        spec["created_at"] = existing.get("created_at") or spec["created_at"]
    except FileNotFoundError:
        pass
    return scientific_state_repository.upsert_material_goal_specification(spec)
