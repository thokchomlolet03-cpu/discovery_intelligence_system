from system_config import (
    AcquisitionConfig,
    DecisionConfig,
    FeasibilityConfig,
    GeneratorConfig,
    LoopConfig,
    ModelConfig,
    PseudoLabelConfig,
    SystemConfig,
    config_to_dict,
    default_system_config,
    system_config_from_dict,
)


HIGH_CONF = PseudoLabelConfig().positive
LOW_CONF = PseudoLabelConfig().negative

W_CONF = AcquisitionConfig().w_conf
W_NOVELTY = AcquisitionConfig().w_novelty
W_UNCERTAINTY = AcquisitionConfig().w_uncertainty

MAX_FEEDBACK_PER_ITERATION = LoopConfig().feedback_per_class * 2
RANDOM_SEED = LoopConfig().seed


__all__ = [
    "AcquisitionConfig",
    "DecisionConfig",
    "FeasibilityConfig",
    "GeneratorConfig",
    "LoopConfig",
    "ModelConfig",
    "PseudoLabelConfig",
    "SystemConfig",
    "config_to_dict",
    "default_system_config",
    "system_config_from_dict",
    "HIGH_CONF",
    "LOW_CONF",
    "W_CONF",
    "W_NOVELTY",
    "W_UNCERTAINTY",
    "MAX_FEEDBACK_PER_ITERATION",
    "RANDOM_SEED",
]
