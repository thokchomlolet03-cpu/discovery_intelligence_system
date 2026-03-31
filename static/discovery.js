(function () {
  const dataNode = document.getElementById("discovery-workbench-data");
  const root = document.getElementById("discovery-results-root");
  if (!dataNode || !root) {
    return;
  }

  const workbench = JSON.parse(dataNode.textContent || "{}");
  const config = window.discoveryWorkbenchConfig || {};
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
    sortBy: config.defaultSort || workbench?.ranking_policy?.primary_score || "experiment_value",
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
              <div class="table-subtle">${escapeHtml(candidate.suggested_next_action || candidate.decision_label)}</div>
            </td>
            <td>${metricHtml("Confidence", candidate.confidence, "confidence")}</td>
            <td>${metricHtml("Uncertainty", candidate.uncertainty, "uncertainty")}</td>
            <td>${metricHtml("Novelty", candidate.novelty, "novelty")}</td>
            <td>${metricHtml("Priority Score", candidate.priority_score, "priority")}</td>
            <td>${metricHtml("Experiment Value", candidate.experiment_value, "experiment")}</td>
            <td>${badgeHtml("domain", candidate.domain_status)}</td>
            <td>${badgeHtml("bucket", candidate.bucket)}</td>
            <td>${badgeHtml("risk", candidate.risk)}</td>
            <td>${badgeHtml("status", candidate.status)}</td>
            <td>${escapeHtml(candidate.explanation_short)}</td>
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
              <th>Confidence</th>
              <th>Uncertainty</th>
              <th>Novelty</th>
              <th>Priority Score</th>
              <th>Experiment Value</th>
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
                    <span class="panel-label">Observed value</span>
                    <strong>${escapeHtml(formatObservedValue(candidate.observed_value))}</strong>
                    <p>${escapeHtml([candidate.assay, candidate.target].filter(Boolean).join(" / ") || "No assay or target context recorded.")}</p>
                  </article>
                </section>

                <section class="score-grid">
                  ${metricCardHtml("Confidence", candidate.confidence, "confidence")}
                  ${metricCardHtml("Uncertainty", candidate.uncertainty, "uncertainty")}
                  ${metricCardHtml("Novelty", candidate.novelty, "novelty")}
                  ${metricCardHtml("Priority Score", candidate.priority_score, "priority")}
                  ${metricCardHtml("Experiment Value", candidate.experiment_value, "experiment")}
                </section>

                <section class="decision-summary-block">
                  <span class="panel-label">Decision guidance</span>
                  <strong>${escapeHtml(candidate.decision_label)}</strong>
                  <p>${escapeHtml(candidate.decision_summary)}</p>
                </section>

                <section class="reasoning-block">
                  <span class="panel-label">Why this was selected</span>
                  <ul>
                    ${candidate.explanation_lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
                  </ul>
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
        <span class="panel-label">Signals behind the recommendation</span>
        <div class="detail-grid">
          <article class="detail-item">${metricHtml("Confidence", candidate.confidence, "confidence")}</article>
          <article class="detail-item">${metricHtml("Uncertainty", candidate.uncertainty, "uncertainty")}</article>
          <article class="detail-item">${metricHtml("Novelty", candidate.novelty, "novelty")}</article>
          <article class="detail-item">${metricHtml("Priority score", candidate.priority_score, "priority")}</article>
          <article class="detail-item">${metricHtml("Experiment Value", candidate.experiment_value, "experiment")}</article>
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
            <span class="panel-label">Primary score</span>
            <strong>${escapeHtml(candidate.primary_score_label)} ${escapeHtml(formatNumber(candidate.primary_score_value))}</strong>
            <p>${escapeHtml(candidate.decision_summary)}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Domain status</span>
            <strong>${escapeHtml(candidate.domain_label || "Unavailable")}</strong>
            <p>${escapeHtml(candidate.domain_summary || "Reference-similarity diagnostics are not available.")}</p>
          </article>
          <article class="detail-item">
            <span class="panel-label">Observed value</span>
            <strong>${candidate.observed_value == null ? "Not available" : escapeHtml(formatNumber(candidate.observed_value))}</strong>
            <p>${escapeHtml([candidate.assay, candidate.target].filter(Boolean).join(" / ") || "No assay or target metadata recorded.")}</p>
          </article>
        </div>
      </section>

      <section class="detail-section">
        <span class="panel-label">Score contributions</span>
        ${scoreBreakdownHtml(candidate)}
      </section>

      <section class="detail-section">
        <span class="panel-label">Full explanation</span>
        <ul class="detail-list">
          ${candidate.explanation_lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
        </ul>
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
