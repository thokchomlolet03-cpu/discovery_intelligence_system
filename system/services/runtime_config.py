from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from system_config import SystemConfig, config_to_dict, default_system_config, system_config_from_dict


@dataclass(frozen=True)
class ThresholdConfig:
    positive: float = 0.7
    negative: float = 0.3
    min_confidence_std: float = 0.05
    min_confidence_span: float = 0.25


def resolve_system_config(config=None, seed=None):
    if config is None:
        return default_system_config(seed=42 if seed is None else seed)
    if isinstance(config, SystemConfig):
        if seed is None:
            return config
        return replace(
            config,
            model=replace(config.model, random_state=seed),
            loop=replace(config.loop, seed=seed),
        )
    merged = system_config_from_dict(config)
    return resolve_system_config(merged, seed=seed)


def bundle_config(bundle):
    return resolve_system_config(bundle.get("config"))


__all__ = [
    "ThresholdConfig",
    "asdict",
    "bundle_config",
    "config_to_dict",
    "default_system_config",
    "resolve_system_config",
]

