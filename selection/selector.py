from pipeline_utils import select_acquisition_portfolio
from selection.scorer import score_candidates


def select_candidates(df, k, config=None):
    scored = score_candidates(df, config=config)
    return select_acquisition_portfolio(scored, total_candidates=k, config=config)

