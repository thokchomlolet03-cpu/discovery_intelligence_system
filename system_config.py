from dataclasses import asdict, dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    random_state: int = 42
    n_estimators: int = 200
    min_samples_leaf: int = 2
    class_weight: str = "balanced_subsample"
    test_size: float = 0.2
    evaluation_cv_splits: int = 5
    calibration_methods: tuple[str, ...] = ("isotonic", "sigmoid")
    calibration_cv: int = 3
    probability_clip: float = 1e-6


@dataclass(frozen=True)
class GeneratorConfig:
    candidate_pool_multiplier: int = 3
    max_attempt_multiplier: int = 50
    prefer_balanced_sources: bool = True
    reference_similarity_threshold: float = 0.85
    batch_similarity_threshold: float = 0.85
    min_mw: float = 50.0
    max_mw: float = 500.0
    functional_groups: tuple[str, ...] = ("O", "N", "C(=O)O")
    chain_extensions: tuple[str, ...] = ("C", "CC", "CO", "OC")
    ring_fragments: tuple[str, ...] = ("c1ccccc1",)


@dataclass(frozen=True)
class AcquisitionConfig:
    exploit_fraction: float = 0.4
    uncertainty_fraction: float = 0.3
    novelty_fraction: float = 0.3
    w_conf: float = 0.5
    w_novelty: float = 0.3
    w_uncertainty: float = 0.2


@dataclass(frozen=True)
class PseudoLabelConfig:
    positive: float = 0.7
    negative: float = 0.3
    min_confidence_std: float = 0.05
    min_confidence_span: float = 0.25


@dataclass(frozen=True)
class FeasibilityConfig:
    max_mw: float = 1000.0
    max_atoms: int = 80
    max_rings: int = 5


@dataclass(frozen=True)
class DecisionConfig:
    top_k: int = 10
    high_risk_uncertainty: float = 0.7
    low_risk_confidence: float = 0.8
    w_uncertainty: float = 0.5
    w_novelty: float = 0.3
    w_low_confidence: float = 0.2


@dataclass(frozen=True)
class LoopConfig:
    iterations: int = 3
    candidates_per_round: int = 30
    feedback_per_class: int = 5
    seed: int = 42
    dry_run: bool = False


@dataclass(frozen=True)
class SystemConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    acquisition: AcquisitionConfig = field(default_factory=AcquisitionConfig)
    pseudo_label: PseudoLabelConfig = field(default_factory=PseudoLabelConfig)
    feasibility: FeasibilityConfig = field(default_factory=FeasibilityConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)


def default_system_config(seed: int = 42) -> SystemConfig:
    base = SystemConfig()
    return replace(
        base,
        model=replace(base.model, random_state=seed),
        loop=replace(base.loop, seed=seed),
    )


def config_to_dict(config: SystemConfig) -> dict[str, Any]:
    return asdict(config)


def system_config_from_dict(payload: dict[str, Any] | None) -> SystemConfig:
    if not payload:
        return default_system_config()

    model = ModelConfig(**payload.get("model", {}))
    generator = GeneratorConfig(**payload.get("generator", {}))
    acquisition = AcquisitionConfig(**payload.get("acquisition", {}))
    pseudo_label = PseudoLabelConfig(**payload.get("pseudo_label", {}))
    feasibility = FeasibilityConfig(**payload.get("feasibility", {}))
    decision = DecisionConfig(**payload.get("decision", {}))
    loop = LoopConfig(**payload.get("loop", {}))
    return SystemConfig(
        model=model,
        generator=generator,
        acquisition=acquisition,
        pseudo_label=pseudo_label,
        feasibility=feasibility,
        decision=decision,
        loop=loop,
    )
