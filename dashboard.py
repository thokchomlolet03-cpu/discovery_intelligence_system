from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
DATASET_PATHS = ("data/data.csv", "data.csv")
CANDIDATE_PATHS = ("predicted_candidates.csv", "candidates_results.csv")
EVOLUTION_PATHS = ("iteration_history.csv", "data/logs.json", "logs.json")
EVALUATION_PATHS = ("evaluation_summary.json",)
RUN_CONFIG_PATHS = ("run_config.json",)
REVIEW_QUEUE_PATHS = ("review_queue.csv",)
KNOWLEDGE_PATHS = ("data/knowledge.json",)
DECISION_PATHS = ("decision_output.json", "data/decision_output.json")


def compute_uncertainty(confidence: pd.Series | list[float] | tuple[float, ...]) -> pd.Series:
    series = pd.Series(confidence, dtype="float64")
    return 1.0 - (series.sub(0.5).abs() * 2.0)


def resolve_run_dir(run_dir: str) -> Path:
    return Path(run_dir).expanduser()


def find_artifact(run_root: Path, candidates: tuple[str, ...]) -> Path | None:
    roots = [run_root]
    if run_root.resolve() != REPO_ROOT.resolve():
        roots.append(REPO_ROOT)

    for root in roots:
        for relative in candidates:
            target = root / relative
            if target.exists():
                return target
    return None


@st.cache_data(show_spinner=False)
def load_csv_artifact(path_str: str) -> pd.DataFrame:
    return pd.read_csv(Path(path_str))


@st.cache_data(show_spinner=False)
def load_json_artifact(path_str: str) -> Any:
    return json.loads(Path(path_str).read_text())


def safe_dataframe(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    try:
        return load_csv_artifact(str(path))
    except Exception as exc:
        st.warning(f"Could not read `{path}`: {exc}")
        return None


def safe_json(path: Path | None) -> Any | None:
    if path is None:
        return None
    try:
        return load_json_artifact(str(path))
    except Exception as exc:
        st.warning(f"Could not read `{path}`: {exc}")
        return None


def threshold_defaults(run_config: dict[str, Any] | None) -> tuple[float, float]:
    pseudo = (run_config or {}).get("pseudo_label", {})
    high = float(pseudo.get("positive", 0.7))
    low = float(pseudo.get("negative", 0.3))
    return high, low


def normalize_candidates(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    for column in ("confidence", "novelty", "final_score"):
        if column not in normalized.columns:
            normalized[column] = 0.0
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0.0)

    if "uncertainty" not in normalized.columns:
        normalized["uncertainty"] = compute_uncertainty(normalized["confidence"])
    normalized["uncertainty"] = pd.to_numeric(normalized["uncertainty"], errors="coerce").fillna(
        compute_uncertainty(normalized["confidence"])
    )

    if "selection_bucket" not in normalized.columns:
        normalized["selection_bucket"] = ""
    if "pseudo_label" not in normalized.columns:
        normalized["pseudo_label"] = pd.NA

    return normalized


def ui_labels(df: pd.DataFrame, low_threshold: float, high_threshold: float) -> pd.Series:
    labels = pd.Series("uncertain", index=df.index, dtype="object")
    labels = labels.mask(df["confidence"] >= high_threshold, "1")
    labels = labels.mask(df["confidence"] <= low_threshold, "0")
    return labels


def normalize_logs_payload(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in payload:
        if not isinstance(record, dict):
            continue
        holdout = record.get("holdout", {})
        selection = record.get("selection_counts", {})
        label_counts = record.get("label_counts", {})
        rows.append(
            {
                "iteration": record.get("iteration"),
                "dataset_size": record.get("dataset_size"),
                "selected_feedback": record.get("selected_feedback"),
                "review_queue": record.get("review_queue"),
                "processed_candidates": record.get("processed_candidates"),
                "generated_candidates": record.get("generated_candidates"),
                "portfolio_selected": record.get("portfolio_selected"),
                "appended_feedback": record.get("appended_feedback"),
                "dry_run": record.get("dry_run"),
                "selected_model": (record.get("selected_model") or {}).get("name"),
                "calibration_method": (record.get("selected_model") or {}).get("calibration_method"),
                "holdout_accuracy": holdout.get("accuracy"),
                "holdout_balanced_accuracy": holdout.get("balanced_accuracy"),
                "holdout_f1_macro": holdout.get("f1_macro"),
                "holdout_brier_score": holdout.get("brier_score"),
                "holdout_log_loss": holdout.get("log_loss"),
                "holdout_exact_confidence_rate_raw": holdout.get("exact_confidence_rate_raw"),
                "feasible_candidates": record.get("feasible_candidates"),
                "infeasible_candidates": record.get("infeasible_candidates"),
                "decision_high_risk": (record.get("decision_risk_counts") or {}).get("high", 0),
                "decision_medium_risk": (record.get("decision_risk_counts") or {}).get("medium", 0),
                "decision_low_risk": (record.get("decision_risk_counts") or {}).get("low", 0),
                "top_experiment_value": record.get("top_experiment_value"),
                "selection_exploit": selection.get("exploit", 0),
                "selection_learn": selection.get("learn", 0),
                "selection_explore": selection.get("explore", 0),
                "label_1": label_counts.get("1", 0),
                "label_0": label_counts.get("0", 0),
                "label_-1": label_counts.get("-1", 0),
            }
        )
    return pd.DataFrame(rows)


def normalize_evolution_data(iteration_history: pd.DataFrame | None, logs_payload: Any) -> pd.DataFrame:
    if iteration_history is not None and not iteration_history.empty:
        return iteration_history.copy()
    return normalize_logs_payload(logs_payload)


def normalize_decision_payload(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, dict):
        return pd.DataFrame()
    rows = payload.get("top_experiments", [])
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def metric_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def artifact_status(label: str, path: Path | None) -> None:
    if path is None:
        st.warning(f"{label}: artifact not found")
    else:
        st.caption(f"{label}: `{path}`")


def render_dataset_overview(dataset: pd.DataFrame) -> None:
    st.header("Dataset Overview")
    if dataset.empty:
        st.warning("Dataset artifact is missing or empty.")
        return

    metric_col, unlabeled_col = st.columns(2)
    metric_col.metric("Dataset size", int(len(dataset)))
    unlabeled_count = int((pd.to_numeric(dataset.get("biodegradable"), errors="coerce") == -1).sum())
    unlabeled_col.metric("Unlabeled rows", unlabeled_count)

    class_counts = (
        pd.to_numeric(dataset["biodegradable"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .map({1: "1", 0: "0", -1: "-1 (unlabeled)"})
        .value_counts()
        .rename_axis("class")
        .reset_index(name="count")
    )
    chart = px.bar(class_counts, x="class", y="count", title="Class distribution")
    st.plotly_chart(chart, use_container_width=True)

    preview_columns = [column for column in ("polymer", "smiles", "biodegradable", "mw", "rdkit_logp") if column in dataset.columns]
    if preview_columns:
        st.dataframe(dataset[preview_columns].head(25), use_container_width=True)
    else:
        st.dataframe(dataset.head(25), use_container_width=True)


def render_model_performance(evaluation_summary: dict[str, Any] | None) -> None:
    st.header("Model Performance")
    if not evaluation_summary:
        st.warning("Evaluation summary not found.")
        return

    holdout = ((evaluation_summary.get("metrics") or {}).get("holdout") or {})
    selected_model = evaluation_summary.get("selected_model") or {}

    metric_cols = st.columns(5)
    metric_cols[0].metric("Accuracy", metric_value(holdout.get("accuracy")))
    metric_cols[1].metric("Balanced Accuracy", metric_value(holdout.get("balanced_accuracy")))
    metric_cols[2].metric("Macro F1", metric_value(holdout.get("f1_macro")))
    metric_cols[3].metric("Brier Score", metric_value(holdout.get("brier_score")))
    metric_cols[4].metric("Log Loss", metric_value(holdout.get("log_loss")))

    st.caption(
        f"Selected model: `{selected_model.get('name', 'n/a')}` | "
        f"Calibration: `{selected_model.get('calibration_method', 'n/a')}`"
    )

    confusion_matrix = holdout.get("confusion_matrix")
    if confusion_matrix:
        heatmap = go.Figure(
            data=go.Heatmap(
                z=confusion_matrix,
                x=["Pred 0", "Pred 1"],
                y=["True 0", "True 1"],
                colorscale="Blues",
                text=confusion_matrix,
                texttemplate="%{text}",
            )
        )
        heatmap.update_layout(title="Confusion Matrix")
        st.plotly_chart(heatmap, use_container_width=True)

    saturation_cols = st.columns(3)
    saturation_cols[0].metric("Exact 0 Rate", metric_value(holdout.get("exact_zero_rate_raw")))
    saturation_cols[1].metric("Exact 1 Rate", metric_value(holdout.get("exact_one_rate_raw")))
    saturation_cols[2].metric("Exact 0/1 Rate", metric_value(holdout.get("exact_confidence_rate_raw")))


def filter_candidates(
    candidates: pd.DataFrame,
    min_conf: float,
    max_conf: float,
    min_unc: float,
    max_unc: float,
) -> pd.DataFrame:
    filtered = candidates[
        candidates["confidence"].between(min_conf, max_conf)
        & candidates["uncertainty"].between(min_unc, max_unc)
    ].copy()
    return filtered


def render_candidate_predictions(
    candidates: pd.DataFrame,
    low_threshold: float,
    high_threshold: float,
    max_rows: int,
    sort_column: str,
    ascending: bool,
) -> pd.DataFrame:
    st.header("Candidate Predictions")
    if candidates.empty:
        st.warning("Candidate artifact is missing or empty.")
        return candidates

    display = candidates.copy()
    display["ui_label"] = ui_labels(display, low_threshold=low_threshold, high_threshold=high_threshold)
    if sort_column in display.columns:
        display = display.sort_values(sort_column, ascending=ascending)

    columns = [
        column
        for column in (
            "polymer",
            "smiles",
            "confidence",
            "uncertainty",
            "novelty",
            "final_score",
            "experiment_value",
            "risk_level",
            "selection_bucket",
            "pseudo_label",
            "ui_label",
        )
        if column in display.columns
    ]
    st.dataframe(display[columns].head(max_rows), use_container_width=True)
    return display


def render_exploration_map(candidates: pd.DataFrame, low_threshold: float, high_threshold: float) -> None:
    st.header("Exploration Map")
    if candidates.empty:
        st.warning("No candidate predictions available for exploration map.")
        return

    plot_frame = candidates.copy()
    if "selection_bucket" in plot_frame.columns and plot_frame["selection_bucket"].fillna("").ne("").any():
        color_column = "selection_bucket"
    else:
        plot_frame["ui_label"] = ui_labels(plot_frame, low_threshold=low_threshold, high_threshold=high_threshold)
        color_column = "ui_label"

    hover_data = {
        "polymer": True if "polymer" in plot_frame.columns else False,
        "smiles": True if "smiles" in plot_frame.columns else False,
        "novelty": True,
        "final_score": True,
    }
    scatter = px.scatter(
        plot_frame,
        x="confidence",
        y="uncertainty",
        color=color_column,
        hover_data=hover_data,
        title="Confidence vs Uncertainty",
    )
    scatter.add_vline(x=low_threshold, line_dash="dash", line_color="red")
    scatter.add_vline(x=high_threshold, line_dash="dash", line_color="green")
    scatter.update_layout(xaxis_title="Confidence", yaxis_title="Uncertainty")
    st.plotly_chart(scatter, use_container_width=True)


def build_experiment_queue(
    decision_frame: pd.DataFrame | None,
    review_queue: pd.DataFrame | None,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    if decision_frame is not None and not decision_frame.empty:
        return decision_frame.sort_values(["experiment_value", "uncertainty", "novelty"], ascending=[False, False, False])
    if review_queue is not None and not review_queue.empty:
        queue = normalize_candidates(review_queue)
        sort_columns = ["experiment_value", "uncertainty", "novelty"] if "experiment_value" in queue.columns else ["uncertainty", "novelty"]
        ascending = [False] * len(sort_columns)
        return queue.sort_values(sort_columns, ascending=ascending)
    if candidates.empty:
        return pd.DataFrame()
    sort_columns = ["experiment_value", "uncertainty", "novelty"] if "experiment_value" in candidates.columns else ["uncertainty", "novelty"]
    ascending = [False] * len(sort_columns)
    return candidates.sort_values(sort_columns, ascending=ascending)


def render_experiment_suggestions(queue: pd.DataFrame) -> None:
    st.header("Experiment Suggestions")
    if queue.empty:
        st.warning("No experiment suggestion candidates available.")
        return

    columns = [
        column
        for column in ("rank", "polymer", "smiles", "confidence", "uncertainty", "novelty", "experiment_value", "risk", "selection_bucket")
        if column in queue.columns
    ]
    st.dataframe(queue[columns].head(10), use_container_width=True)


def render_system_evolution(evolution: pd.DataFrame) -> None:
    st.header("System Evolution")
    if evolution.empty:
        st.warning("No iteration history or logs available.")
        return

    metric_chart = px.line(
        evolution.sort_values("iteration"),
        x="iteration",
        y=[column for column in ("dataset_size",) if column in evolution.columns],
        markers=True,
        title="Dataset Size vs Iteration",
    )
    st.plotly_chart(metric_chart, use_container_width=True)

    metric_columns = [column for column in ("holdout_accuracy", "holdout_f1_macro") if column in evolution.columns]
    if metric_columns:
        score_chart = px.line(
            evolution.sort_values("iteration"),
            x="iteration",
            y=metric_columns,
            markers=True,
            title="Model Metrics vs Iteration",
        )
        st.plotly_chart(score_chart, use_container_width=True)

    selection_columns = [column for column in ("selection_exploit", "selection_learn", "selection_explore") if column in evolution.columns]
    if selection_columns:
        selection_frame = evolution[["iteration", *selection_columns]].copy()
        selection_frame = selection_frame.melt(id_vars="iteration", var_name="bucket", value_name="count")
        bucket_chart = px.bar(
            selection_frame,
            x="iteration",
            y="count",
            color="bucket",
            barmode="group",
            title="Selection Counts by Iteration",
        )
        st.plotly_chart(bucket_chart, use_container_width=True)

    feasibility_columns = [column for column in ("feasible_candidates", "infeasible_candidates") if column in evolution.columns]
    if feasibility_columns:
        feasibility_chart = px.line(
            evolution.sort_values("iteration"),
            x="iteration",
            y=feasibility_columns,
            markers=True,
            title="Feasibility Counts vs Iteration",
        )
        st.plotly_chart(feasibility_chart, use_container_width=True)

    risk_columns = [column for column in ("decision_high_risk", "decision_medium_risk", "decision_low_risk") if column in evolution.columns]
    if risk_columns:
        risk_frame = evolution[["iteration", *risk_columns]].copy()
        risk_frame = risk_frame.melt(id_vars="iteration", var_name="risk", value_name="count")
        risk_chart = px.bar(
            risk_frame,
            x="iteration",
            y="count",
            color="risk",
            barmode="group",
            title="Decision Risk Counts by Iteration",
        )
        st.plotly_chart(risk_chart, use_container_width=True)

    if "top_experiment_value" in evolution.columns:
        value_chart = px.line(
            evolution.sort_values("iteration"),
            x="iteration",
            y="top_experiment_value",
            markers=True,
            title="Top Experiment Value vs Iteration",
        )
        st.plotly_chart(value_chart, use_container_width=True)

    st.dataframe(evolution.sort_values("iteration"), use_container_width=True)


def render_knowledge_summary(knowledge_payload: Any) -> None:
    if not isinstance(knowledge_payload, list) or not knowledge_payload:
        return
    with st.expander("Knowledge Entries", expanded=False):
        st.caption(f"Stored knowledge entries: {len(knowledge_payload)}")
        st.dataframe(pd.DataFrame(knowledge_payload).tail(20), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Discovery Intelligence Dashboard", layout="wide")
    st.title("Discovery Intelligence Dashboard")
    st.caption("Read-only observability for discovery runs and pipeline artifacts.")

    with st.sidebar:
        st.header("Controls")
        run_dir_input = st.text_input("Run directory", value=".")
        run_root = resolve_run_dir(run_dir_input)

        run_config_path = find_artifact(run_root, RUN_CONFIG_PATHS)
        run_config = safe_json(run_config_path)
        default_high, default_low = threshold_defaults(run_config if isinstance(run_config, dict) else None)

        low_threshold = st.slider("Low confidence threshold", min_value=0.0, max_value=1.0, value=float(default_low), step=0.01)
        high_threshold = st.slider("High confidence threshold", min_value=0.0, max_value=1.0, value=float(default_high), step=0.01)
        min_conf, max_conf = st.slider("Confidence filter", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.01)
        min_unc, max_unc = st.slider("Uncertainty filter", min_value=0.0, max_value=1.0, value=(0.0, 1.0), step=0.01)
        max_rows = st.slider("Max table rows", min_value=10, max_value=200, value=50, step=10)

    dataset_path = find_artifact(run_root, DATASET_PATHS)
    candidates_path = find_artifact(run_root, CANDIDATE_PATHS)
    evaluation_path = find_artifact(run_root, EVALUATION_PATHS)
    evolution_path = find_artifact(run_root, EVOLUTION_PATHS)
    review_queue_path = find_artifact(run_root, REVIEW_QUEUE_PATHS)
    knowledge_path = find_artifact(run_root, KNOWLEDGE_PATHS)
    decision_path = find_artifact(run_root, DECISION_PATHS)

    artifact_status("Dataset", dataset_path)
    artifact_status("Candidates", candidates_path)
    artifact_status("Evaluation", evaluation_path)
    artifact_status("Evolution", evolution_path)
    artifact_status("Decision", decision_path)

    dataset = safe_dataframe(dataset_path)
    if dataset is None:
        dataset = pd.DataFrame()
    candidates = normalize_candidates(safe_dataframe(candidates_path))
    evaluation_summary = safe_json(evaluation_path)
    review_queue = safe_dataframe(review_queue_path)
    knowledge_payload = safe_json(knowledge_path)
    decision_payload = safe_json(decision_path)
    decision_frame = normalize_decision_payload(decision_payload)

    iteration_history_path = run_root / "iteration_history.csv"
    iteration_history = safe_dataframe(iteration_history_path) if iteration_history_path.exists() else None
    logs_payload = None
    if evolution_path is not None and evolution_path.suffix.lower() == ".json":
        logs_payload = safe_json(evolution_path)
    evolution = normalize_evolution_data(iteration_history, logs_payload)

    filtered_candidates = filter_candidates(candidates, min_conf=min_conf, max_conf=max_conf, min_unc=min_unc, max_unc=max_unc)
    sort_options = [column for column in ("final_score", "confidence", "uncertainty", "novelty", "polymer") if column in filtered_candidates.columns]
    sort_column = st.selectbox("Candidate sort", options=sort_options or ["confidence"], index=0)
    ascending = st.checkbox("Sort ascending", value=False)

    render_dataset_overview(dataset)
    render_model_performance(evaluation_summary if isinstance(evaluation_summary, dict) else None)
    displayed_candidates = render_candidate_predictions(
        filtered_candidates,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        max_rows=max_rows,
        sort_column=sort_column,
        ascending=ascending,
    )
    render_exploration_map(displayed_candidates, low_threshold=low_threshold, high_threshold=high_threshold)
    render_experiment_suggestions(build_experiment_queue(decision_frame, review_queue, displayed_candidates))
    render_system_evolution(evolution)
    render_knowledge_summary(knowledge_payload)


if __name__ == "__main__":
    main()
