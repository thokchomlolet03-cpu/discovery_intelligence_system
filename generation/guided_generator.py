from system.services.candidate_service import generate_candidate_pool, process_candidate_dataframe
from system.services.runtime_config import resolve_system_config


def generate_candidates(df, n, config=None, seed=None):
    cfg = resolve_system_config(config, seed=seed)
    pool_size = max(n, n * cfg.generator.candidate_pool_multiplier)
    raw_candidates = generate_candidate_pool(
        df,
        n=pool_size,
        seed=cfg.loop.seed if seed is None else seed,
        max_attempt_multiplier=cfg.generator.max_attempt_multiplier,
        prefer_balanced_sources=cfg.generator.prefer_balanced_sources,
        config=cfg,
    )
    _, processed = process_candidate_dataframe(raw_candidates, df, config=cfg)
    return processed


def generate_candidate_artifacts(df, n, config=None, seed=None):
    cfg = resolve_system_config(config, seed=seed)
    pool_size = max(n, n * cfg.generator.candidate_pool_multiplier)
    raw_candidates = generate_candidate_pool(
        df,
        n=pool_size,
        seed=cfg.loop.seed if seed is None else seed,
        max_attempt_multiplier=cfg.generator.max_attempt_multiplier,
        prefer_balanced_sources=cfg.generator.prefer_balanced_sources,
        config=cfg,
    )
    generated, processed = process_candidate_dataframe(raw_candidates, df, config=cfg)
    return generated, processed
