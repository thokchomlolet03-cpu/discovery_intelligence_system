from reasoning.rules import HIGH_H_ACCEPTORS_THRESHOLD, HYDROPHILIC_LOGP_THRESHOLD, LOW_MW_THRESHOLD


def explain_prediction(row):
    reasons = []
    logp = row.get("rdkit_logp", row.get("logp"))
    mw = row.get("mw")
    h_acceptors = row.get("h_acceptors")

    if logp is not None and logp < HYDROPHILIC_LOGP_THRESHOLD:
        reasons.append("hydrophilic profile suggests easier environmental interaction")
    if mw is not None and mw < LOW_MW_THRESHOLD:
        reasons.append("lower molecular weight favors degradability")
    if h_acceptors is not None and h_acceptors >= HIGH_H_ACCEPTORS_THRESHOLD:
        reasons.append("higher hydrogen-bond acceptor count is consistent with biodegradable behavior")

    if not reasons:
        return "No strong rule-based driver detected from the current feature set"
    return "; ".join(reasons)

