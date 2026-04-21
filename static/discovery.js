(function () {
  const dataNode = document.getElementById("discovery-workbench-data");
  const root = document.getElementById("discovery-results-root");
  if (!dataNode || !root) {
    return;
  }

  const workbench = JSON.parse(dataNode.textContent || "{}");
  const config = window.discoveryWorkbenchConfig || {};
  const targetDefinition = workbench.target_definition || {};
  const trustContext = workbench.trust_context || {};
  const targetName = String(targetDefinition.target_name || "the session target");
  const targetKind = String(targetDefinition.target_kind || "classification");
  const modelingMode = String(workbench.modeling_mode || "");
  const statusBox = document.getElementById("discovery-feedback");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const resultCountNode = document.getElementById("results-count");
  const selectedCountNode = document.getElementById("selected-count");
  const summaryNodes = {
    suggested: document.getElementById("summary-suggested"),
    "under review": document.getElementById("summary-under-review"),
    approved: document.getElementById("summary-approved"),
    rejected: document.getElementById("summary-rejected"),
    tested: document.getElementById("summary-tested"),
  };

  const state = {
    candidates: Array.isArray(workbench.candidates) ? workbench.candidates.slice() : [],
    view: "table",
    sortBy: config.surfacedDefaultSort || config.defaultSort || workbench?.ranking_policy?.primary_score || "experiment_value",
    selected: new Set(),
    filters: {
      search: "",
      bucket: "all",
      risk: "all",
      status: "all",
      confidenceMin: 0,
      confidenceMax: 1,
      uncertaintyMin: 0,
      uncertaintyMax: 1,
      noveltyMin: 0,
      noveltyMax: 1,
    },
  };

  const statusOptions = ["suggested", "under review", "approved", "rejected", "tested", "ingested"];
  const riskRank = { low: 0, medium: 1, high: 2 };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function titleCase(value) {
    return String(value || "")
      .split(/[\s_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function formatNumber(value) {
    const numeric = Number(value || 0);
    return Number.isFinite(numeric) ? numeric.toFixed(3) : "0.000";
  }

  function formatObservedValue(value) {
    return value == null ? "Not available" : formatNumber(value);
  }

  function formatTimestamp(value) {
    if (!value) {
      return "Not available";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")} ${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")} UTC`;
  }

  function truncateSmiles(value, length = 28) {
    const text = String(value || "");
    return text.length > length ? `${text.slice(0, length)}...` : text;
  }

  function statusKey(value) {
    return String(value || "").replace(/\s+/g, "-");
  }

  function badgeHtml(kind, value) {
    const key = statusKey(value || "unknown");
    return `<span class="meaning-badge ${kind}-${escapeHtml(key)}">${escapeHtml(titleCase(value || "unknown"))}</span>`;
  }

  function metricHtml(label, value, tone) {
    const percent = Math.max(0, Math.min(100, Number(value || 0) * 100));
    return `
      <div class="metric-stack">
        <div class="metric-topline">
          <span>${escapeHtml(label)}</span>
          <strong>${formatNumber(value)}</strong>
        </div>
        <div class="meter" aria-hidden="true">
          <span class="meter-fill ${escapeHtml(tone)}" style="width:${percent}%"></span>
        </div>
      </div>
    `;
  }

  function metricCardHtml(label, value, tone) {
    return `<article class="score-card">${metricHtml(label, value, tone)}</article>`;
  }

  function signalLabel(kind) {
    if (kind === "confidence") {
      return targetKind === "regression" ? "Ranking compatibility" : `Model confidence for ${targetName}`;
    }
    if (kind === "uncertainty") {
      return targetKind === "regression" ? "Prediction dispersion" : "Prediction uncertainty";
    }
    if (kind === "novelty") {
      return "Structural novelty";
    }
    if (kind === "priority_score") {
      return "Policy priority score";
    }
    if (kind === "experiment_value") {
      return "Policy experiment value";
    }
    if (kind === "surfaced_order_score") {
      return "Surfaced attention order";
    }
    return titleCase(kind);
  }

  function nonEmptyLines(values) {
    if (!Array.isArray(values)) {
      return [];
    }
    return values.map((value) => String(value || "").trim()).filter(Boolean);
  }

  function candidateDataFacts(candidate) {
    const facts = candidate.data_facts && typeof candidate.data_facts === "object" ? candidate.data_facts : {};
    const datasetType = facts.dataset_type ? titleCase(facts.dataset_type) : titleCase(targetDefinition.dataset_type || "unknown");
    const observedValue = facts.observed_value ?? candidate.observed_value;
    const measurementColumn = facts.measurement_column || targetDefinition.measurement_column || "";
    const labelColumn = facts.label_column || targetDefinition.label_column || "";
    const contextText = [facts.assay || candidate.assay, facts.target || candidate.target].filter(Boolean).join(" / ");
    return {
      title: datasetType || "Unknown dataset type",
      summary: contextText || "No assay or target context was recorded from the uploaded or restored session.",
      bullets: [
        observedValue == null
          ? (targetKind === "regression"
            ? "No observed value was uploaded for this candidate, so the predicted value still needs direct measurement."
            : "No observed value was uploaded for this candidate.")
          : `Observed evidence: ${formatObservedValue(observedValue)}.`,
        measurementColumn ? `Mapped measurement column: ${measurementColumn}.` : "No measurement column is mapped for this session.",
        labelColumn ? `Mapped label column: ${labelColumn}.` : "No explicit label column is mapped for this session.",
      ],
    };
  }

  function candidateModelJudgment(candidate) {
    const judgment = candidate.model_judgment && typeof candidate.model_judgment === "object" ? candidate.model_judgment : {};
    const predictionText = candidate.normalized_explanation?.model_judgment_summary || judgment.model_summary || "Model judgment summary was not recorded.";
    const uncertaintyText = candidate.normalized_explanation?.uncertainty_summary || "Prediction uncertainty details were not recorded.";
    const bullets = [];
    if (targetKind === "regression") {
      if (judgment.predicted_value != null) {
        bullets.push(`Predicted value: ${formatNumber(judgment.predicted_value)}.`);
      }
      if (judgment.confidence != null) {
        bullets.push(`Ranking compatibility: ${formatNumber(judgment.confidence)}.`);
      }
      if (judgment.prediction_dispersion != null) {
        bullets.push(`Prediction dispersion: ${formatNumber(judgment.prediction_dispersion)}.`);
      }
    } else {
      if (judgment.confidence != null) {
        bullets.push(`${signalLabel("confidence")}: ${formatNumber(judgment.confidence)}.`);
      }
    }
    if (judgment.uncertainty != null) {
      bullets.push(`${signalLabel("uncertainty")}: ${formatNumber(judgment.uncertainty)}.`);
    }
    if (judgment.uncertainty_kind) {
      bullets.push(`Uncertainty semantics: ${titleCase(judgment.uncertainty_kind)}.`);
    }
    return {
      title: targetKind === "regression" ? "Continuous model output" : "Classification model output",
      summary: predictionText,
      bullets: [uncertaintyText].concat(bullets),
    };
  }

  function candidateDomainAndNovelty(candidate) {
    const domain = candidate.applicability_domain && typeof candidate.applicability_domain === "object" ? candidate.applicability_domain : {};
    const novelty = candidate.novelty_signal && typeof candidate.novelty_signal === "object" ? candidate.novelty_signal : {};
    const bullets = [];
    if (domain.max_reference_similarity != null) {
      bullets.push(`Max reference similarity: ${formatNumber(domain.max_reference_similarity)}.`);
    }
    if (novelty.novelty_score != null) {
      bullets.push(`Structural novelty: ${formatNumber(novelty.novelty_score)}.`);
    }
    if (novelty.reference_similarity != null) {
      bullets.push(`Reference similarity used for novelty: ${formatNumber(novelty.reference_similarity)}.`);
    }
    return {
      title: candidate.domain_label || domain.support_band || "Domain and novelty",
      summary: domain.summary || candidate.domain_summary || "Reference-similarity support was not recorded for this candidate.",
      bullets: [
        novelty.summary || candidate.normalized_explanation?.novelty_summary || "Novelty details were not recorded.",
      ].concat(bullets),
    };
  }

  function candidateDecisionPolicy(candidate) {
    const policy = candidate.decision_policy && typeof candidate.decision_policy === "object" ? candidate.decision_policy : {};
    const recommendation = candidate.final_recommendation && typeof candidate.final_recommendation === "object" ? candidate.final_recommendation : {};
    const bullets = [];
    if (policy.priority_score != null) {
      bullets.push(`${signalLabel("priority_score")}: ${formatNumber(policy.priority_score)}.`);
    }
    if (policy.experiment_value != null) {
      bullets.push(`${signalLabel("experiment_value")}: ${formatNumber(policy.experiment_value)}.`);
    }
    if (policy.acquisition_score != null) {
      bullets.push(`Acquisition score: ${formatNumber(policy.acquisition_score)}.`);
    }
    if (policy.bucket) {
      bullets.push(`Decision bucket: ${titleCase(policy.bucket)}.`);
    }
    if (targetKind === "regression") {
      bullets.push("Policy priority uses predicted value support, ranking compatibility, uncertainty, novelty, and experiment value together; it is not the predicted value itself.");
    }
    return {
      title: recommendation.recommended_action || candidate.decision_label || "Recommendation policy",
      summary: recommendation.summary || policy.policy_summary || candidate.decision_summary || "Recommendation policy details were not recorded.",
      bullets: bullets.concat(
        recommendation.follow_up_experiment
          ? [`Suggested follow-up: ${recommendation.follow_up_experiment}.`]
          : []
      ),
    };
  }

  function bulletListHtml(items) {
    const lines = nonEmptyLines(items);
    if (!lines.length) {
      return "<p class=\"helper-copy\">No additional structured details were recorded.</p>";
    }
    return `<ul class="detail-list">${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>`;
  }

  function candidateEpistemicContextHtml(candidate, compact = false) {
    const context = candidate.candidate_epistemic_context && typeof candidate.candidate_epistemic_context === "object"
      ? candidate.candidate_epistemic_context
      : {};
    const status = String(context.status || "no_epistemic_objects");
    const summary = String(
      context.summary_line
      || (context.available
        ? "Compact epistemic context is available for this candidate."
        : "No claim, experiment, or belief context is recorded for this candidate.")
    );
    const chips = [
      `Claims ${Number(context.claim_count || 0)}`,
      context.has_pending_experiment ? "Pending experiment" : "",
      context.has_recorded_result ? "Result recorded" : "",
      context.has_belief_update ? "Belief updated" : "",
      !context.has_belief_update && context.has_belief_state ? "Belief state present" : "",
      Number(context.unresolved_count || 0) > 0 ? `Unresolved ${Number(context.unresolved_count || 0)}` : "",
      context.detail_available ? `Detail available ${Number(context.detail_count || 0)}` : "",
      !context.available ? "No epistemic objects" : "",
    ].filter(Boolean);
    return `
      <section class="${compact ? "candidate-epistemic-inline" : "decision-summary-block"}" data-epistemic-rendered="candidate-context" data-epistemic-status="${escapeHtml(status)}">
        <span class="panel-label">Epistemic context</span>
        <strong>${escapeHtml(titleCase(status.replace(/_/g, " ")))}</strong>
        <p>${escapeHtml(summary)}</p>
        ${chips.length ? `<div class="decision-primary-context">${chips.map((chip) => `<span class="data-chip">${escapeHtml(chip)}</span>`).join("")}</div>` : ""}
        ${
          context.absence_reason
            ? `<p class="helper-copy">Explicit absence: ${escapeHtml(titleCase(String(context.absence_reason).replace(/_/g, " ")))}</p>`
            : ""
        }
      </section>
    `;
  }

  function candidateEpistemicDetailRevealHtml(candidate) {
    const detail = candidate.candidate_epistemic_detail_reveal && typeof candidate.candidate_epistemic_detail_reveal === "object"
      ? candidate.candidate_epistemic_detail_reveal
      : {};
    const claimItems = Array.isArray(detail.claim_items) ? detail.claim_items : [];
    if (!Object.keys(detail).length) {
      return "";
    }
    return `
      <details class="reasoning-block" data-epistemic-rendered="candidate-detail-reveal" data-epistemic-status="${escapeHtml(String(detail.status || "no_epistemic_objects"))}">
        <summary>Inspect epistemic detail</summary>
        ${
          detail.available
            ? `
              <div class="decision-primary-context">
                <span class="data-chip">Claims ${escapeHtml(String(detail.claim_count || 0))}</span>
                <span class="data-chip">Pending ${escapeHtml(String(detail.pending_experiment_count || 0))}</span>
                <span class="data-chip">Unresolved ${escapeHtml(String(detail.unresolved_count || 0))}</span>
                <span class="data-chip">Belief update ${detail.has_belief_update ? "yes" : "no"}</span>
              </div>
              ${
                claimItems.length
                  ? `<ul class="detail-list">${claimItems
                      .map(
                        (item) => `<li>${
                          escapeHtml(titleCase(String(item.claim_type || "unknown").replace(/_/g, " ")))
                        }: ${escapeHtml(item.claim_text || "Claim detail recorded.")} ${
                          item.pending_request_count ? `Pending ${escapeHtml(String(item.pending_request_count))}. ` : ""
                        }${
                          item.has_results ? "Result recorded. " : ""
                        }Belief ${escapeHtml(String(item.belief_state || "absent"))}. Unresolved state: ${escapeHtml(titleCase(String(item.unresolved_state || "unknown").replace(/_/g, " ")))}.</li>`
                      )
                      .join("")}</ul>`
                  : `<p class="helper-copy">No linked claim detail is available beyond the compact summary.</p>`
              }
            `
            : `
              <p>No canonical epistemic detail is available beyond the compact summary.</p>
              ${detail.absence_reason ? `<p class="helper-copy">Explicit absence: ${escapeHtml(titleCase(String(detail.absence_reason).replace(/_/g, " ")))}</p>` : ""}
            `
        }
      </details>
    `;
  }

  function focusedClaimInspectionHtml(candidate) {
    const claim = candidate.focused_claim_inspection && typeof candidate.focused_claim_inspection === "object"
      ? candidate.focused_claim_inspection
      : {};
    if (!Object.keys(claim).length) {
      return "";
    }
    const claimChoices = Array.isArray(claim.claim_choices) && claim.claim_choices.length
      ? claim.claim_choices
      : [{
          claim_id: claim.selected_claim_id,
          claim_type: claim.claim_type,
          claim_status: claim.claim_status,
          claim_scope: claim.claim_scope,
          candidate_label: claim.candidate_label,
          run_label: claim.run_label,
          claim_text: claim.claim_text,
          support_basis_summary: claim.support_basis_summary,
          experiment_request_count: claim.experiment_request_count,
          experiment_result_count: claim.experiment_result_count,
          pending_request_count: claim.pending_request_count,
          belief_update_count: claim.belief_update_count,
          belief_state: claim.belief_state,
          unresolved_state: claim.unresolved_state,
          selected: true,
        }];
    return `
      <details class="reasoning-block" data-epistemic-rendered="focused-claim-inspection" data-epistemic-status="${escapeHtml(String(claim.claim_status || "absent"))}" data-epistemic-focus-root data-epistemic-selection-key="candidate:${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}:claim">
        <summary>Inspect one claim</summary>
        ${
          claim.available
            ? `
              ${
                claim.multiple_available && claimChoices.length
                  ? `
                    <label class="panel-label" for="focused-claim-select-${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}">Claim selection</label>
                    <select
                      id="focused-claim-select-${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}"
                      class="input"
                      data-epistemic-rendered="focused-claim-selector"
                      data-epistemic-focus-select
                    >
                      ${claimChoices.map((choice) => `<option value="${escapeHtml(String(choice.claim_id || ""))}" ${choice.selected ? "selected" : ""}>${escapeHtml(String(choice.label || choice.claim_id || "Claim"))}</option>`).join("")}
                    </select>
                    <p class="helper-copy">Selection stays inside the focused claim layer and does not change recommendation or belief truth.</p>
                  `
                  : ""
              }
              ${claimChoices.map((choice) => `
                <div data-claim-choice-panel="${escapeHtml(String(choice.claim_id || ""))}" data-epistemic-focus-panel="${escapeHtml(String(choice.claim_id || ""))}" ${String(choice.claim_id || "") !== String(claim.selected_claim_id || "") ? "hidden" : ""}>
              <div class="decision-primary-context">
                <span class="data-chip">Claim ${escapeHtml(titleCase(String(choice.claim_type || "unknown").replace(/_/g, " ")))}</span>
                <span class="data-chip">Status ${escapeHtml(titleCase(String(choice.claim_status || "unknown").replace(/_/g, " ")))}</span>
                <span class="data-chip">Scope ${escapeHtml(titleCase(String(choice.claim_scope || "unknown").replace(/_/g, " ")))}</span>
                ${choice.candidate_label ? `<span class="data-chip">Candidate ${escapeHtml(choice.candidate_label)}</span>` : ""}
              </div>
              <p>${escapeHtml(choice.claim_text || "Claim detail recorded.")}</p>
              <p class="helper-copy">${escapeHtml(choice.support_basis_summary || "Canonical support basis not recorded.")}</p>
              <div class="decision-primary-context">
                <span class="data-chip">Requests ${escapeHtml(String(choice.experiment_request_count || 0))}</span>
                <span class="data-chip">Results ${escapeHtml(String(choice.experiment_result_count || 0))}</span>
                <span class="data-chip">Pending ${escapeHtml(String(choice.pending_request_count || 0))}</span>
                <span class="data-chip">Belief ${escapeHtml(String(choice.belief_state || "absent"))}</span>
                <span class="data-chip">Unresolved ${escapeHtml(titleCase(String(choice.unresolved_state || "unknown").replace(/_/g, " ")))}</span>
              </div>
                </div>
              `).join("")}
              ${
                claim.default_first_fallback_used
                  ? `<p class="helper-copy">Default-first focused claim fallback is active because no explicit claim selection was provided.</p>`
                  : ""
              }
            `
            : `
              <p>No focused claim is available for inspection.</p>
              ${claim.absence_reason ? `<p class="helper-copy">Explicit absence: ${escapeHtml(titleCase(String(claim.absence_reason).replace(/_/g, " ")))}</p>` : ""}
            `
        }
      </details>
    `;
  }

  function focusedExperimentInspectionHtml(candidate) {
    const experiment = candidate.focused_experiment_inspection && typeof candidate.focused_experiment_inspection === "object"
      ? candidate.focused_experiment_inspection
      : {};
    if (!Object.keys(experiment).length) {
      return "";
    }
    const experimentChoices = Array.isArray(experiment.experiment_choices) && experiment.experiment_choices.length
      ? experiment.experiment_choices
      : [{
          request_id: experiment.selected_request_id,
          status: experiment.status,
          claim_scope: experiment.claim_scope,
          linked_claim_id: experiment.linked_claim_id,
          candidate_label: experiment.candidate_label,
          run_label: experiment.run_label,
          objective_summary: experiment.objective_summary,
          rationale_summary: experiment.rationale_summary,
          result_status: experiment.result_status,
          has_belief_update: experiment.has_belief_update,
          belief_state: experiment.belief_state,
          unresolved_state: experiment.unresolved_state,
          result_summary: experiment.result_summary,
          belief_summary: experiment.belief_summary,
          selected: true,
        }];
    return `
      <details class="reasoning-block" data-epistemic-rendered="focused-experiment-inspection" data-epistemic-status="${escapeHtml(String(experiment.status || "absent"))}" data-epistemic-focus-root data-epistemic-selection-key="candidate:${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}:experiment">
        <summary>Inspect one experiment-linked state</summary>
        ${
          experiment.available
            ? `
              ${
                experiment.multiple_available && experimentChoices.length
                  ? `
                    <label class="panel-label" for="focused-experiment-select-${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}">Experiment selection</label>
                    <select
                      id="focused-experiment-select-${escapeHtml(String(candidate.candidate_id || candidate.canonical_smiles || "candidate"))}"
                      class="input"
                      data-epistemic-rendered="focused-experiment-selector"
                      data-epistemic-focus-select
                    >
                      ${experimentChoices.map((choice) => `<option value="${escapeHtml(String(choice.request_id || ""))}" ${choice.selected ? "selected" : ""}>${escapeHtml(String(choice.label || choice.request_id || "Experiment"))}</option>`).join("")}
                    </select>
                    <p class="helper-copy">Selection stays inside the focused experiment layer and does not imply scheduling or execution workflow.</p>
                  `
                  : ""
              }
              ${experimentChoices.map((choice) => `
                <div data-experiment-choice-panel="${escapeHtml(String(choice.request_id || ""))}" data-epistemic-focus-panel="${escapeHtml(String(choice.request_id || ""))}" ${String(choice.request_id || "") !== String(experiment.selected_request_id || "") ? "hidden" : ""}>
                  <div class="decision-primary-context">
                    <span class="data-chip">Status ${escapeHtml(titleCase(String(choice.status || "unknown").replace(/_/g, " ")))}</span>
                    <span class="data-chip">Scope ${escapeHtml(titleCase(String(choice.claim_scope || "unknown").replace(/_/g, " ")))}</span>
                    ${choice.linked_claim_id ? `<span class="data-chip">Claim ${escapeHtml(choice.linked_claim_id)}</span>` : ""}
                    ${choice.candidate_label ? `<span class="data-chip">Candidate ${escapeHtml(choice.candidate_label)}</span>` : ""}
                  </div>
                  <p>${escapeHtml(choice.objective_summary || "Experiment request recorded.")}</p>
                  ${choice.rationale_summary ? `<p class="helper-copy">${escapeHtml(choice.rationale_summary)}</p>` : ""}
                  <div class="decision-primary-context">
                    <span class="data-chip">Result ${escapeHtml(titleCase(String(choice.result_status || "absent").replace(/_/g, " ")))}</span>
                    <span class="data-chip">Belief update ${choice.has_belief_update ? "present" : "absent"}</span>
                    <span class="data-chip">Belief ${escapeHtml(String(choice.belief_state || "absent"))}</span>
                    <span class="data-chip">Unresolved ${escapeHtml(titleCase(String(choice.unresolved_state || "unknown").replace(/_/g, " ")))}</span>
                  </div>
                  <div class="mini-callout">
                    <span class="panel-label">Result summary</span>
                    <p>${escapeHtml(choice.result_summary || "No result recorded.")}</p>
                  </div>
                  <div class="mini-callout">
                    <span class="panel-label">Belief linkage</span>
                    <p>${escapeHtml(choice.belief_summary || "No belief update recorded.")}</p>
                  </div>
                </div>
              `).join("")}
              ${
                experiment.default_first_fallback_used
                  ? `<p class="helper-copy">Default-first focused experiment fallback is active because no explicit experiment selection was provided.</p>`
                  : ""
              }
            `
            : `
              <p>No focused experiment-linked state is available for inspection.</p>
              ${experiment.absence_reason ? `<p class="helper-copy">Explicit absence: ${escapeHtml(titleCase(String(experiment.absence_reason).replace(/_/g, " ")))}</p>` : ""}
            `
        }
      </details>
    `;
  }

  function compactScientificBlocksHtml(candidate) {
    const blocks = [
      { label: "Uploaded evidence and derived facts", ...candidateDataFacts(candidate) },
      { label: "Model output", ...candidateModelJudgment(candidate) },
      { label: "Support signals", ...candidateDomainAndNovelty(candidate) },
      { label: "Policy output and recommendation", ...candidateDecisionPolicy(candidate) },
    ];
    return `
      <section class="candidate-context-grid">
        ${blocks
          .map(
            (block) => `
              <article class="context-card">
                <span class="panel-label">${escapeHtml(block.label)}</span>
                <strong>${escapeHtml(block.title)}</strong>
                <p>${escapeHtml(block.summary)}</p>
              </article>
            `
          )
          .join("")}
      </section>
    `;
  }

  function detailedScientificBlocksHtml(candidate) {
    const blocks = [
      { label: "Observed or derived session facts", ...candidateDataFacts(candidate) },
      { label: "Model output", ...candidateModelJudgment(candidate) },
      { label: "Applicability and novelty signals", ...candidateDomainAndNovelty(candidate) },
      { label: "Decision policy and recommendation", ...candidateDecisionPolicy(candidate) },
    ];
    return `
      <section class="detail-section">
        <span class="panel-label">Scientific structure</span>
        <div class="detail-grid">
          ${blocks
            .map(
              (block) => `
                <article class="detail-item">
                  <span class="panel-label">${escapeHtml(block.label)}</span>
                  <strong>${escapeHtml(block.title)}</strong>
                  <p>${escapeHtml(block.summary)}</p>
                  ${bulletListHtml(block.bullets)}
                </article>
              `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function scoreBreakdownHtml(candidate) {
    const breakdown = Array.isArray(candidate.score_breakdown) ? candidate.score_breakdown : [];
    if (!breakdown.length) {
      return "<p class=\"helper-copy\">Score contributions are not available for this candidate.</p>";
    }
    return `
      <div class="score-breakdown-list">
        ${breakdown
          .map(
            (item) => `
              <article class="score-breakdown-item">
                <div class="score-breakdown-head">
                  <strong>${escapeHtml(item.label)}</strong>
                  <span>${escapeHtml(`${formatNumber(item.contribution)} contribution`)}</span>
                </div>
                <div class="score-breakdown-meta">
                  <span class="data-chip">Raw ${escapeHtml(formatNumber(item.raw_value))}</span>
                  <span class="data-chip">Weight ${escapeHtml(`${formatNumber((Number(item.weight || 0) * 100) / 100)} (${Number(item.weight_percent || 0).toFixed(1)}%)`)}</span>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    `;
  }

  function buildStatusSelect(candidate) {
    return `
      <select data-status-select="${escapeHtml(candidate.candidate_id)}">
        ${statusOptions
          .map((option) => {
            const selected = option === candidate.status ? " selected" : "";
            return `<option value="${escapeHtml(option)}"${selected}>${escapeHtml(titleCase(option))}</option>`;
          })
          .join("")}
      </select>
    `;
  }

  function selectedArray() {
    return state.candidates.filter((candidate) => state.selected.has(candidate.candidate_id));
  }

  function showFeedback(message, variant) {
    if (!statusBox) {
      return;
    }
    statusBox.textContent = message;
    statusBox.classList.remove("hidden", "muted", "error", "success");
    statusBox.classList.add(variant || "muted");
  }

  function clearFeedback() {
    if (!statusBox) {
      return;
    }
    statusBox.textContent = "";
    statusBox.classList.add("hidden");
    statusBox.classList.remove("error", "success", "muted");
  }

  function matchesRange(value, min, max) {
    return value >= min && value <= max;
  }

  function filteredCandidates() {
    return state.candidates.filter((candidate) => {
      const searchPass = !state.filters.search || candidate.search_text.includes(state.filters.search);
      const bucketPass = state.filters.bucket === "all" || candidate.bucket === state.filters.bucket;
      const riskPass = state.filters.risk === "all" || candidate.risk === state.filters.risk;
      const statusPass = state.filters.status === "all" || candidate.status === state.filters.status;
      const confidencePass = matchesRange(candidate.confidence, state.filters.confidenceMin, state.filters.confidenceMax);
      const uncertaintyPass = matchesRange(candidate.uncertainty, state.filters.uncertaintyMin, state.filters.uncertaintyMax);
      const noveltyPass = matchesRange(candidate.novelty, state.filters.noveltyMin, state.filters.noveltyMax);
      return searchPass && bucketPass && riskPass && statusPass && confidencePass && uncertaintyPass && noveltyPass;
    });
  }

  function sortCandidates(candidates) {
    const sorted = candidates.slice();
    sorted.sort((left, right) => {
      if (state.sortBy === "risk") {
        return (right.risk_rank ?? riskRank[right.risk] ?? 1) - (left.risk_rank ?? riskRank[left.risk] ?? 1);
      }
      if (state.sortBy === "latest") {
        return String(right.latest_sort_key || "").localeCompare(String(left.latest_sort_key || ""));
      }
      if (state.sortBy === "surfaced_order_score") {
        if (Boolean(right.surfaced_attention_active) !== Boolean(left.surfaced_attention_active)) {
          return Boolean(right.surfaced_attention_active) ? 1 : -1;
        }
      }
      return Number(right[state.sortBy] || 0) - Number(left[state.sortBy] || 0);
    });
    return sorted;
  }

  function buildTableView(candidates) {
    const rows = candidates
      .map((candidate) => {
        const checked = state.selected.has(candidate.candidate_id) ? " checked" : "";
        return `
          <tr data-candidate-id="${escapeHtml(candidate.candidate_id)}">
            <td><input class="candidate-select" type="checkbox" data-select-candidate="${escapeHtml(candidate.candidate_id)}"${checked} aria-label="Select ${escapeHtml(candidate.candidate_id)}" /></td>
            <td>
              <button class="link-button" type="button" data-view-details="${escapeHtml(candidate.candidate_id)}">${escapeHtml(candidate.candidate_id)}</button>
              <div class="table-subtle">Rank ${escapeHtml(candidate.rank)}</div>
              <div class="table-subtle">${escapeHtml(candidate.primary_score_label)} ${escapeHtml(formatNumber(candidate.primary_score_value))}</div>
            </td>
            <td>
              <button class="smiles-trigger" type="button" data-view-details="${escapeHtml(candidate.candidate_id)}" title="${escapeHtml(candidate.smiles)}">${escapeHtml(truncateSmiles(candidate.smiles, 32))}</button>
            </td>
            <td>
              ${badgeHtml("decision", candidate.decision_category)}
              ${candidate.trust_label ? badgeHtml("status", candidate.trust_label) : ""}
              <div class="table-subtle">${escapeHtml(candidate.suggested_next_action || candidate.decision_label)}</div>
              <div class="table-subtle">${escapeHtml((candidate.candidate_epistemic_context && candidate.candidate_epistemic_context.summary_line) || "No claim, experiment, or belief context recorded.")}</div>
            </td>
            <td>${metricHtml(signalLabel("confidence"), candidate.confidence, "confidence")}</td>
            <td>${metricHtml(signalLabel("uncertainty"), candidate.uncertainty, "uncertainty")}</td>
            <td>${metricHtml(signalLabel("novelty"), candidate.novelty, "novelty")}</td>
            <td>${metricHtml(signalLabel("priority_score"), candidate.priority_score, "priority")}</td>
            <td>${metricHtml(signalLabel("experiment_value"), candidate.experiment_value, "experiment")}</td>
            <td>${badgeHtml("domain", candidate.domain_status)}</td>
            <td>${badgeHtml("bucket", candidate.bucket)}</td>
            <td>${badgeHtml("risk", candidate.risk)}</td>
            <td>${badgeHtml("status", candidate.status)}</td>
            <td>
              ${escapeHtml(candidate.rationale_summary || candidate.explanation_short)}
              ${
                Array.isArray(candidate.rationale_session_context) && candidate.rationale_session_context.length
                  ? `<div class="table-subtle">${escapeHtml(candidate.rationale_session_context[0])}</div>`
                  : ""
              }
            </td>
            <td>
              <div>${escapeHtml(candidate.provenance_compact)}</div>
              <div class="table-subtle">${escapeHtml(candidate.reviewed_at_label)}</div>
            </td>
            <td>
              <div class="row-actions">
                <button class="inline-action" type="button" data-view-details="${escapeHtml(candidate.candidate_id)}">View rationale</button>
                <button class="inline-action primary" type="button" data-review-action="approve" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Shortlist</button>
                <button class="inline-action danger" type="button" data-review-action="reject" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Reject</button>
                <button class="inline-action" type="button" data-review-action="under_review" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Hold</button>
              </div>
            </td>
          </tr>
        `;
      })
      .join("");

    return `
      <div class="discovery-table-wrap">
        <table class="workbench-table">
          <thead>
            <tr>
              <th>Select</th>
              <th>Candidate ID</th>
              <th>SMILES</th>
              <th>Recommended Move</th>
              <th>${escapeHtml(signalLabel("confidence"))}</th>
              <th>${escapeHtml(signalLabel("uncertainty"))}</th>
              <th>${escapeHtml(signalLabel("novelty"))}</th>
              <th>${escapeHtml(signalLabel("priority_score"))}</th>
              <th>${escapeHtml(signalLabel("experiment_value"))}</th>
              <th>Domain</th>
              <th>Bucket</th>
              <th>Risk</th>
              <th>Status</th>
              <th>Why Now</th>
              <th>Provenance</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function buildCardView(candidates) {
    return `
      <div class="candidate-card-grid">
        ${candidates
          .map((candidate) => {
            const checked = state.selected.has(candidate.candidate_id) ? " checked" : "";
            return `
              <article class="workbench-card" data-candidate-id="${escapeHtml(candidate.candidate_id)}">
                <header class="workbench-card-head">
                  <div class="candidate-name">
                    <label>
                      <input class="candidate-select" type="checkbox" data-select-candidate="${escapeHtml(candidate.candidate_id)}"${checked} />
                      <span class="visually-hidden">Select ${escapeHtml(candidate.candidate_id)}</span>
                    </label>
                    <span class="panel-label">Candidate</span>
                    <strong>${escapeHtml(candidate.candidate_id)}</strong>
                  </div>
                  <div class="card-badge-row">
                    ${badgeHtml("decision", candidate.decision_category)}
                    ${badgeHtml("bucket", candidate.bucket)}
                    ${badgeHtml("risk", candidate.risk)}
                    ${badgeHtml("status", candidate.status)}
                    ${badgeHtml("domain", candidate.domain_status)}
                  </div>
                </header>

                <section class="card-smiles">
                  <span class="panel-label">Full SMILES</span>
                  <code>${escapeHtml(candidate.smiles)}</code>
                </section>

                <section class="candidate-context-grid">
                  <article class="context-card">
                    <span class="panel-label">Recommended move</span>
                    <strong>${escapeHtml(candidate.decision_label)}</strong>
                    <p>${escapeHtml(candidate.suggested_next_action || candidate.decision_summary)}</p>
                  </article>
                  <article class="context-card">
                    <span class="panel-label">Domain coverage</span>
                    <strong>${escapeHtml(candidate.domain_label || "Unavailable")}</strong>
                    <p>${escapeHtml(candidate.domain_summary || "Reference similarity was not available for this candidate.")}</p>
                  </article>
                  <article class="context-card">
                    <span class="panel-label">${escapeHtml(targetKind === "regression" ? "Predicted / observed value" : "Observed value")}</span>
                    <strong>${
                      targetKind === "regression" && candidate.predicted_value != null
                        ? `${escapeHtml(formatNumber(candidate.predicted_value))} predicted`
                        : escapeHtml(formatObservedValue(candidate.observed_value))
                    }</strong>
                    <p>${escapeHtml([candidate.assay, candidate.target].filter(Boolean).join(" / ") || "No assay or target context recorded.")}</p>
                  </article>
                </section>

                ${compactScientificBlocksHtml(candidate)}

                ${candidateEpistemicContextHtml(candidate)}
                ${candidateEpistemicDetailRevealHtml(candidate)}
                ${focusedClaimInspectionHtml(candidate)}
                ${candidate.focused_experiment_inspection?.available ? focusedExperimentInspectionHtml(candidate) : ""}

                <section class="decision-summary-block">
                  <span class="panel-label">Trust read</span>
                  <strong>${escapeHtml(candidate.trust_label || "Mixed trust")}</strong>
                  <p>${escapeHtml(candidate.trust_summary || candidate.rationale_summary || candidate.decision_summary)}</p>
                </section>

                <section class="decision-summary-block">
                  <span class="panel-label">Why this candidate</span>
                  <strong>${escapeHtml(candidate.primary_score_label || "Current shortlist logic")}</strong>
                  <p>${escapeHtml(candidate.normalized_explanation?.why_this_candidate || candidate.rationale_summary || candidate.decision_summary)}</p>
                </section>

                ${
                  Array.isArray(candidate.rationale_session_context) && candidate.rationale_session_context.length
                    ? `
                      <section class="reasoning-block">
                        <span class="panel-label">Within this run</span>
                        <ul>
                          ${candidate.rationale_session_context
                            .map((line) => `<li>${escapeHtml(line)}</li>`)
                            .join("")}
                        </ul>
                      </section>
                    `
                    : ""
                }

                <section class="score-grid">
                  ${metricCardHtml(signalLabel("confidence"), candidate.confidence, "confidence")}
                  ${metricCardHtml(signalLabel("uncertainty"), candidate.uncertainty, "uncertainty")}
                  ${metricCardHtml(signalLabel("novelty"), candidate.novelty, "novelty")}
                  ${metricCardHtml(signalLabel("priority_score"), candidate.priority_score, "priority")}
                  ${metricCardHtml(signalLabel("experiment_value"), candidate.experiment_value, "experiment")}
                </section>

                <section class="decision-summary-block">
                  <span class="panel-label">Recommended follow-up</span>
                  <strong>${escapeHtml(candidate.decision_label)}</strong>
                  <p>${escapeHtml(candidate.normalized_explanation?.recommended_followup || candidate.rationale_recommended_action || candidate.suggested_next_action || candidate.decision_summary)}</p>
                </section>

                <section class="reasoning-block">
                  <span class="panel-label">Why now</span>
                  <p>${escapeHtml(candidate.rationale_why_now || candidate.decision_summary)}</p>
                  <ul>
                    ${(Array.isArray(candidate.rationale_strengths) ? candidate.rationale_strengths : [])
                      .map((line) => `<li>${escapeHtml(line)}</li>`)
                      .join("")}
                  </ul>
                </section>

                <section class="reasoning-block">
                  <span class="panel-label">What supports it and what weakens it</span>
                  <ul>
                    ${(Array.isArray(candidate.rationale_evidence_lines) ? candidate.rationale_evidence_lines : candidate.explanation_lines)
                      .map((line) => `<li>${escapeHtml(line)}</li>`)
                      .join("")}
                  </ul>
                  ${
                    Array.isArray(candidate.rationale_cautions) && candidate.rationale_cautions.length
                      ? `<div class="warning-chip-row">${candidate.rationale_cautions
                          .map((line) => `<article class="warning-chip">${escapeHtml(line)}</article>`)
                          .join("")}</div>`
                      : ""
                  }
                </section>

                <section class="reasoning-block">
                  <span class="panel-label">Score contributions</span>
                  ${scoreBreakdownHtml(candidate)}
                </section>

                <section class="provenance-block">
                  <span class="panel-label">Provenance</span>
                  <div class="provenance-grid">
                    <article class="provenance-item">
                      <span class="panel-label">Source type</span>
                      <strong>${escapeHtml(titleCase(candidate.source_type))}</strong>
                    </article>
                    <article class="provenance-item">
                      <span class="panel-label">Parent molecule</span>
                      <strong>${escapeHtml(candidate.parent_molecule)}</strong>
                    </article>
                    <article class="provenance-item">
                      <span class="panel-label">Iteration</span>
                      <strong>${escapeHtml(candidate.iteration)}</strong>
                    </article>
                    <article class="provenance-item">
                      <span class="panel-label">Model / dataset</span>
                      <strong>${escapeHtml(candidate.model_version)} / ${escapeHtml(candidate.dataset_version)}</strong>
                    </article>
                  </div>
                </section>

                <section class="review-block">
                  <span class="panel-label">Review</span>
                  <label class="control-field">
                    <span>Reviewer</span>
                    <input type="text" value="${escapeHtml(candidate.reviewer || "unassigned")}" data-reviewer-input="${escapeHtml(candidate.candidate_id)}" />
                  </label>
                  <label class="control-field">
                    <span>Status</span>
                    ${buildStatusSelect(candidate)}
                  </label>
                  <label class="control-field">
                    <span>Reviewer note</span>
                    <textarea rows="3" data-note-input="${escapeHtml(candidate.candidate_id)}">${escapeHtml(candidate.review_note || "")}</textarea>
                  </label>
                  <div class="card-action-row">
                    <button class="inline-action" type="button" data-view-details="${escapeHtml(candidate.candidate_id)}">View rationale</button>
                    <button class="inline-action primary" type="button" data-review-action="approve" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Shortlist</button>
                    <button class="inline-action danger" type="button" data-review-action="reject" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Reject</button>
                    <button class="inline-action" type="button" data-review-action="under_review" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Hold</button>
                    <button class="inline-action" type="button" data-review-action="save_note" data-candidate-id="${escapeHtml(candidate.candidate_id)}">Save note</button>
                  </div>
                </section>
              </article>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderEmptyResults() {
    root.innerHTML = `
      <div class="empty-results">
        <h3>No candidates match the current filters.</h3>
        <p>Widen the filters to bring more of the saved shortlist back into view.</p>
      </div>
    `;
  }

  function updateReviewSummary() {
    const counts = { suggested: 0, "under review": 0, approved: 0, rejected: 0, tested: 0 };
    state.candidates.forEach((candidate) => {
      if (Object.prototype.hasOwnProperty.call(counts, candidate.status)) {
        counts[candidate.status] += 1;
      }
    });
    Object.entries(summaryNodes).forEach(([key, node]) => {
      if (node) {
        node.textContent = String(counts[key] || 0);
      }
    });
  }

  function updateCounterNodes(visible) {
    if (resultCountNode) {
      resultCountNode.textContent = String(visible);
    }
    if (selectedCountNode) {
      selectedCountNode.textContent = String(state.selected.size);
    }
  }

  function render() {
    const visible = sortCandidates(filteredCandidates());
    updateCounterNodes(visible.length);
    updateReviewSummary();

    if (!visible.length) {
      renderEmptyResults();
      return;
    }

    root.innerHTML = state.view === "table" ? buildTableView(visible) : buildCardView(visible);
    window.discoveryEpistemicFocus?.enhance(root);
  }

  function candidateById(candidateId) {
    return state.candidates.find((candidate) => candidate.candidate_id === candidateId);
  }

  function recordToLocalReview(review) {
    const candidate = candidateById(review.candidate_id);
    if (!candidate) {
      return;
    }
    const reviewedAt = review.reviewed_at || review.timestamp || "";
    const normalized = {
      action: review.action,
      status: review.status,
      note: review.note || "",
      reviewer: review.reviewer || "unassigned",
      reviewed_at: reviewedAt,
      reviewed_at_label: formatTimestamp(reviewedAt),
    };
    candidate.status = review.status || candidate.status;
    candidate.review_note = review.note || candidate.review_note;
    candidate.reviewer = review.reviewer || candidate.reviewer;
    candidate.reviewed_at = reviewedAt;
    candidate.reviewed_at_label = formatTimestamp(reviewedAt);
    candidate.latest_sort_key = reviewedAt || candidate.latest_sort_key;
    candidate.review_history = Array.isArray(candidate.review_history) ? candidate.review_history.concat([normalized]) : [normalized];
    candidate.review_history_count = candidate.review_history.length;
  }

  async function submitReviews(items) {
    const response = await fetch(config.reviewsEndpoint || "/api/reviews", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({
        session_id: config.sessionId || "",
        items,
      }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Could not save review action.");
    }

    return response.json();
  }

  function buildReviewPayload(candidate, action) {
    const status = action === "approve"
      ? "approved"
      : action === "reject"
        ? "rejected"
        : action === "under_review"
          ? "under review"
        : action === "tested"
          ? "tested"
          : (candidate.status || "under review");

    return {
      session_id: config.sessionId || "",
      candidate_id: candidate.candidate_id,
      smiles: candidate.smiles,
      action,
      status: action === "save_note" ? candidate.status : status,
      note: candidate.review_note || "",
      reviewer: candidate.reviewer || "unassigned",
    };
  }

  async function runReviewAction(candidateIds, action) {
    const items = candidateIds
      .map((candidateId) => candidateById(candidateId))
      .filter(Boolean)
      .map((candidate) => buildReviewPayload(candidate, action));

    if (!items.length) {
      showFeedback("Select at least one candidate first.", "error");
      return;
    }

    try {
      const body = await submitReviews(items);
      const reviews = Array.isArray(body.reviews) ? body.reviews : body.review ? [body.review] : [];
      reviews.forEach(recordToLocalReview);
      render();
      if (action !== "export") {
        showFeedback(`${reviews.length} review update${reviews.length === 1 ? "" : "s"} saved.`, "success");
      }
    } catch (error) {
      showFeedback(error.message || "Could not save review action.", "error");
    }
  }

  function exportSelected() {
    if (config.allowExport === false) {
      showFeedback("Export requires the Pro plan.", "error");
      return;
    }
    const rows = selectedArray();
    if (!rows.length) {
      showFeedback("Select candidates before exporting.", "error");
      return;
    }
    const headers = [
      "candidate_id",
      "smiles",
      "decision_label",
      "bucket",
      "risk",
      "status",
      "confidence",
      "uncertainty",
      "novelty",
      "priority_score",
      "experiment_value",
    ];
    const csv = [
      headers.join(","),
      ...rows.map((candidate) =>
        headers
          .map((key) => `"${String(candidate[key] ?? "").replace(/"/g, '""')}"`)
          .join(",")
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "selected_discovery_candidates.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showFeedback(`${rows.length} selected candidate${rows.length === 1 ? "" : "s"} exported.`, "success");
  }

  function ensureDrawer() {
    let drawer = document.getElementById("candidate-detail-drawer");
    if (drawer) {
      return drawer;
    }

    drawer = document.createElement("div");
    drawer.id = "candidate-detail-drawer";
    drawer.className = "drawer-shell hidden";
    drawer.innerHTML = `
      <div class="drawer-backdrop" data-close-drawer="true"></div>
      <aside class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div class="drawer-head">
          <div class="detail-title">
            <span class="panel-label">Candidate detail</span>
            <h2 id="drawer-title">Candidate</h2>
          </div>
          <button class="drawer-close" type="button" data-close-drawer="true" aria-label="Close detail panel">&times;</button>
        </div>
        <div class="drawer-content" id="drawer-content"></div>
      </aside>
    `;
    document.body.appendChild(drawer);

    drawer.addEventListener("click", (event) => {
      if (event.target instanceof HTMLElement && event.target.dataset.closeDrawer) {
        drawer.classList.add("hidden");
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        drawer.classList.add("hidden");
      }
    });

    return drawer;
  }

  function openDrawer(candidateId) {
    const candidate = candidateById(candidateId);
    if (!candidate) {
      return;
    }

    const drawer = ensureDrawer();
    const titleNode = drawer.querySelector("#drawer-title");
    const contentNode = drawer.querySelector("#drawer-content");
    if (!titleNode || !contentNode) {
      return;
    }

    titleNode.textContent = candidate.candidate_id;
    contentNode.innerHTML = `
      <section class="detail-section">
        <div class="detail-title">
          <span class="panel-label">Snapshot</span>
          <h3>${escapeHtml(candidate.candidate_id)}</h3>
        </div>
        <div class="card-badge-row">
          ${badgeHtml("decision", candidate.decision_category)}
          ${badgeHtml("bucket", candidate.bucket)}
          ${badgeHtml("risk", candidate.risk)}
          ${badgeHtml("status", candidate.status)}
          ${badgeHtml("domain", candidate.domain_status)}
        </div>
        <div class="card-smiles">
          <span class="panel-label">Full SMILES</span>
          <code>${escapeHtml(candidate.smiles)}</code>
        </div>
        <p>${escapeHtml(candidate.decision_summary)}</p>
      </section>

      <section class="detail-section">
        ${candidateEpistemicContextHtml(candidate)}
      </section>

      <section class="detail-section">
        ${candidateEpistemicDetailRevealHtml(candidate)}
      </section>

      <section class="detail-section">
        ${focusedClaimInspectionHtml(candidate)}
      </section>

      ${
        candidate.focused_experiment_inspection?.available
          ? `
            <section class="detail-section">
              ${focusedExperimentInspectionHtml(candidate)}
            </section>
          `
          : ""
      }

      <section class="detail-section">
        <span class="panel-label">Trust read</span>
        <div class="detail-grid">
          <article class="detail-item">
            <span class="panel-label">Trust label</span>
            <strong>${escapeHtml(candidate.trust_label || "Mixed trust")}</strong>
            <p>${escapeHtml(candidate.trust_summary || candidate.rationale_summary || candidate.decision_summary)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Why this candidate</span>
            <strong>${escapeHtml(candidate.primary_score_label || "Current shortlist logic")}</strong>
            <p>${escapeHtml(candidate.normalized_explanation?.why_this_candidate || candidate.rationale_summary || candidate.decision_summary)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Why now</span>
            <strong>${escapeHtml(candidate.rationale_why_now || candidate.primary_score_label)}</strong>
            <p>${escapeHtml(candidate.rationale_summary || candidate.decision_summary)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Recommended move</span>
            <strong>${escapeHtml(candidate.decision_label)}</strong>
            <p>${escapeHtml(candidate.normalized_explanation?.recommended_followup || candidate.rationale_recommended_action || candidate.suggested_next_action)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Primary driver</span>
            <strong>${escapeHtml(
              candidate.rationale_primary_driver === "confidence"
                ? signalLabel("confidence")
                : candidate.rationale_primary_driver === "uncertainty"
                  ? signalLabel("uncertainty")
                  : titleCase(candidate.rationale_primary_driver || candidate.primary_score_name || "priority_score")
            )}</strong>
            <p>${escapeHtml(candidate.decision_summary)}</p>
          </article>
        </div>
      </section>

      ${detailedScientificBlocksHtml(candidate)}

      ${
        Array.isArray(candidate.rationale_session_context) && candidate.rationale_session_context.length
          ? `
            <section class="detail-section">
              <span class="panel-label">Within this run</span>
              <ul class="detail-list">
                ${candidate.rationale_session_context
                  .map((line) => `<li>${escapeHtml(line)}</li>`)
                  .join("")}
              </ul>
            </section>
          `
          : ""
      }

      <section class="detail-section">
        <span class="panel-label">Signals behind the recommendation</span>
        <div class="detail-grid">
          <article class="detail-item">${metricHtml(signalLabel("confidence"), candidate.confidence, "confidence")}</article>
          <article class="detail-item">${metricHtml(signalLabel("uncertainty"), candidate.uncertainty, "uncertainty")}</article>
          <article class="detail-item">${metricHtml(signalLabel("novelty"), candidate.novelty, "novelty")}</article>
          <article class="detail-item">${metricHtml(signalLabel("priority_score"), candidate.priority_score, "priority")}</article>
          <article class="detail-item">${metricHtml(signalLabel("experiment_value"), candidate.experiment_value, "experiment")}</article>
        </div>
      </section>

      <section class="detail-section">
        <span class="panel-label">What to do with this candidate</span>
        <div class="detail-grid">
          <article class="detail-item">
            <span class="panel-label">Recommended action</span>
            <strong>${escapeHtml(candidate.decision_label)}</strong>
            <p>${escapeHtml(candidate.suggested_next_action)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Primary ranking signal</span>
            <strong>${escapeHtml(candidate.primary_score_label)} ${escapeHtml(formatNumber(candidate.primary_score_value))}</strong>
            <p>${escapeHtml(candidate.decision_summary)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Domain status</span>
            <strong>${escapeHtml(candidate.domain_label || "Unavailable")}</strong>
            <p>${escapeHtml(candidate.domain_summary || "Reference-similarity diagnostics are not available.")}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">${escapeHtml(targetKind === "regression" ? "Predicted / observed value" : "Observed value")}</span>
            <strong>${
              targetKind === "regression" && candidate.predicted_value != null
                ? `${escapeHtml(formatNumber(candidate.predicted_value))} predicted`
                : candidate.observed_value == null
                  ? "Not available"
                  : escapeHtml(formatNumber(candidate.observed_value))
            }</strong>
            <p>${escapeHtml([candidate.assay, candidate.target].filter(Boolean).join(" / ") || "No assay or target metadata recorded.")}</p>
          </article>
          ${
            trustContext.bridge_state_summary
              ? `
                <article class="detail-item">
                  <span class="panel-label">Bridge-state note</span>
                  <strong>${escapeHtml(trustContext.evidence_support_label || "Limited evidence support")}</strong>
                  <p>${escapeHtml(trustContext.bridge_state_summary)}</p>
                </article>
              `
              : ""
          }
        </div>
      </section>

      <section class="detail-section">
        <span class="panel-label">Score contributions</span>
        ${scoreBreakdownHtml(candidate)}
      </section>

      <section class="detail-section">
        <span class="panel-label">What supports it and what weakens it</span>
        <ul class="detail-list">
          ${(Array.isArray(candidate.rationale_evidence_lines) ? candidate.rationale_evidence_lines : candidate.explanation_lines)
            .map((line) => `<li>${escapeHtml(line)}</li>`)
            .join("")}
        </ul>
        ${
          Array.isArray(candidate.rationale_cautions) && candidate.rationale_cautions.length
            ? `<div class="warning-chip-row">${candidate.rationale_cautions
                .map((line) => `<article class="warning-chip">${escapeHtml(line)}</article>`)
                .join("")}</div>`
            : ""
        }
      </section>

      <section class="detail-section">
        <span class="panel-label">Saved session context</span>
        <div class="detail-grid">
          <article class="detail-item">
            <span class="panel-label">Source type</span>
            <strong>${escapeHtml(titleCase(candidate.source_type))}</strong>
          </article>
          <article class="detail-item">
            <span class="panel-label">Parent molecule</span>
            <strong>${escapeHtml(candidate.parent_molecule)}</strong>
          </article>
          <article class="detail-item">
            <span class="panel-label">Iteration</span>
            <strong>${escapeHtml(candidate.iteration)}</strong>
          </article>
          <article class="detail-item">
            <span class="panel-label">Model / dataset</span>
            <strong>${escapeHtml(candidate.model_version)} / ${escapeHtml(candidate.dataset_version)}</strong>
          </article>
        </div>
        <div class="detail-placeholder">${escapeHtml(candidate.provenance)}</div>
      </section>

      <section class="detail-section">
        <span class="panel-label">Prior workspace evidence</span>
        ${
          candidate.workspace_memory_count
            ? `
              <p>
                ${escapeHtml(String(candidate.workspace_memory_count))} prior review event${
                  candidate.workspace_memory_count === 1 ? "" : "s"
                } across ${escapeHtml(String(candidate.workspace_memory_session_count || 0))} earlier workspace session${
                  candidate.workspace_memory_session_count === 1 ? "" : "s"
                }.
              </p>
              <div class="history-list">
                ${(Array.isArray(candidate.workspace_memory_history) ? candidate.workspace_memory_history : [])
                  .map(
                    (item) => `
                      <article class="history-item">
                        <div class="history-meta">
                          ${badgeHtml("status", item.status)}
                          <span class="data-chip">${escapeHtml(item.session_label || item.session_id || "Session")}</span>
                          <span class="data-chip">${escapeHtml(item.action_label || titleCase(item.action || "review"))}</span>
                          <span class="data-chip">${escapeHtml(item.reviewer || "unassigned")}</span>
                          <span class="data-chip">${escapeHtml(item.reviewed_at_label || formatTimestamp(item.reviewed_at))}</span>
                        </div>
                        <p>${escapeHtml(item.note || "No reviewer note recorded.")}</p>
                      </article>
                    `
                  )
                  .join("")}
              </div>
            `
            : "<p>No earlier workspace feedback matched this molecule.</p>"
        }
      </section>

      <section class="detail-section">
        <span class="panel-label">Review history</span>
        ${
          candidate.review_history && candidate.review_history.length
            ? `<div class="history-list">
                ${candidate.review_history
                  .map(
                    (item) => `
                      <article class="history-item">
                        <div class="history-meta">
                          ${badgeHtml("status", item.status)}
                          <span class="data-chip">${escapeHtml(titleCase(item.action))}</span>
                          <span class="data-chip">${escapeHtml(item.reviewer || "unassigned")}</span>
                          <span class="data-chip">${escapeHtml(item.reviewed_at_label || formatTimestamp(item.reviewed_at))}</span>
                        </div>
                        <p>${escapeHtml(item.note || "No reviewer note recorded.")}</p>
                      </article>
                    `
                  )
                  .join("")}
              </div>`
            : "<p>No review history recorded yet.</p>"
        }
      </section>

    `;

    window.discoveryEpistemicFocus?.enhance(contentNode);
    drawer.classList.remove("hidden");
  }

  function bindControls() {
    const bindings = [
      ["filter-search", "search"],
      ["filter-bucket", "bucket"],
      ["filter-risk", "risk"],
      ["filter-status", "status"],
      ["sort-by", "sortBy"],
      ["filter-confidence-min", "confidenceMin"],
      ["filter-confidence-max", "confidenceMax"],
      ["filter-uncertainty-min", "uncertaintyMin"],
      ["filter-uncertainty-max", "uncertaintyMax"],
      ["filter-novelty-min", "noveltyMin"],
      ["filter-novelty-max", "noveltyMax"],
    ];

    bindings.forEach(([id, key]) => {
      const node = document.getElementById(id);
      if (!node) {
        return;
      }
      if (key === "sortBy" && node instanceof HTMLSelectElement) {
        node.value = state.sortBy;
      }
      const eventName = node.tagName === "SELECT" ? "change" : "input";
      node.addEventListener(eventName, () => {
        if (key === "sortBy") {
          state.sortBy = node.value;
        } else if (key === "search") {
          state.filters.search = node.value.trim().toLowerCase();
        } else if (key.endsWith("Min") || key.endsWith("Max")) {
          state.filters[key] = Math.max(0, Math.min(1, Number(node.value || 0)));
        } else {
          state.filters[key] = node.value;
        }
        render();
      });
    });

    document.querySelectorAll("[data-view-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.getAttribute("data-view-mode") || "table";
        document.querySelectorAll("[data-view-mode]").forEach((node) => node.classList.remove("is-active"));
        button.classList.add("is-active");
        render();
      });
    });

    document.querySelectorAll("[data-bulk-action]").forEach((button) => {
      button.addEventListener("click", async () => {
        const action = button.getAttribute("data-bulk-action");
        if (action === "export") {
          exportSelected();
          return;
        }
        await runReviewAction(Array.from(state.selected), action || "under_review");
      });
    });
  }

  root.addEventListener("click", async (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!target) {
      return;
    }

    const detailButton = target.closest("[data-view-details]");
    if (detailButton instanceof HTMLElement) {
      openDrawer(detailButton.dataset.viewDetails || "");
      return;
    }

    const actionButton = target.closest("[data-review-action]");
    if (actionButton instanceof HTMLElement) {
      await runReviewAction([actionButton.dataset.candidateId || ""], actionButton.dataset.reviewAction || "under_review");
    }
  });

  root.addEventListener("change", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!target) {
      return;
    }

    if (target.matches("[data-select-candidate]")) {
      const candidateId = target.getAttribute("data-select-candidate") || "";
      const input = target;
      if (input instanceof HTMLInputElement && input.checked) {
        state.selected.add(candidateId);
      } else {
        state.selected.delete(candidateId);
      }
      updateCounterNodes(filteredCandidates().length);
      return;
    }

    if (target.matches("[data-status-select]")) {
      const candidate = candidateById(target.getAttribute("data-status-select") || "");
      if (candidate && target instanceof HTMLSelectElement) {
        candidate.status = target.value;
        updateReviewSummary();
      }
    }
  });

  root.addEventListener("input", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!target) {
      return;
    }
    if (target.matches("[data-note-input]") && target instanceof HTMLTextAreaElement) {
      const candidate = candidateById(target.getAttribute("data-note-input") || "");
      if (candidate) {
        candidate.review_note = target.value;
      }
      return;
    }
    if (target.matches("[data-reviewer-input]") && target instanceof HTMLInputElement) {
      const candidate = candidateById(target.getAttribute("data-reviewer-input") || "");
      if (candidate) {
        candidate.reviewer = target.value;
      }
    }
  });

  bindControls();
  render();
})();
