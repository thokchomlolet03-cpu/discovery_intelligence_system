# System Evolution Progress

## Long-Term Goal
Help a small molecular R&D team choose better next experiments faster, with explanations they can trust and challenge.

## Current Truthful System Identity
Discovery Intelligence is a scientific decision-support workbench, not an autonomous discovery engine. Today it is a session-backed product for upload, scoring, review, comparison, and continuity across runs. It is not yet a true evidence-learning discovery system.

## Current Major Stage
Bridge-state workbench stabilization after the neutral-core cleanup, trust-surface pass, measurement-first honesty slice, the first explicit evidence/session-truth contract, canonical-first comparison adoption, selective evidence activation governance, future-learning eligibility definition, the narrow controlled-reuse activation slice, and the first claim/experiment-loop scaffolding slices. The product surface now exposes session identity, evidence basis, model/policy separation, bridge-state fallback, regression ranking semantics, canonical scientific session truth, explicit evidence-use activation boundaries, selective evidence use, controlled future-eligibility boundaries, limited recommendation/ranking-context reuse, first-class proposed claims, claim-linked proposed experiment requests, observed experiment-result records, bounded belief-update records, and a first target-scoped belief-state summary more directly, but the scientific core still needs stronger evidence-learning behavior.

## Current Snapshot
### Implemented
- Session-aware Upload -> Discovery -> Dashboard -> Sessions workflow.
- Auth, workspaces, billing, job tracking, artifact registry, and review persistence.
- Support for structure-only, labeled, and measurement-oriented uploads.
- Session comparison and workspace feedback continuity.
- Candidate ranking, rationale generation, and dashboard/session reconstruction from persisted artifacts.
- Formal evidence contract distinguishing observed, computed, retrieved, derived, predicted, reviewed, and memory-only evidence.
- Canonical scientific session truth persisted for new completed sessions and consumed by Discovery, Dashboard, and Sessions where available.
- Session comparison now prefers canonical scientific session truth when present and only falls back to compatibility reconstruction when needed.
- Evidence-loop summaries now persist explicit activation boundaries for active modeling, active ranking context, interpretation-only, memory-only, stored-not-active, and future activation candidates.
- Canonical scientific session truth now also persists a selective evidence activation policy stating what evidence may affect modeling, ranking context, interpretation, comparison, future learning eligibility, or stored-only state.
- Limited selective evidence use is now operational for recommendation interpretation and ranking-context honesty, especially around workspace memory and review continuity, without changing model outputs or training.
- Controlled future-learning eligibility and recommendation-reuse eligibility are now persisted per evidence type, including stronger-validation requirements and permanently non-active boundaries for weak or indirect evidence classes.
- Controlled recommendation reuse and ranking-context reuse are now active in a small, explicit, user-visible form for continuity/prioritization framing, and canonical scientific session truth persists whether that reuse was active for a session.
- Claim now exists as a first-class DB-backed bounded scientific assertion derived from current session recommendations.
- ExperimentRequest now exists as a first-class DB-backed proposed next-experiment object derived from current Claims and linked into canonical scientific session truth.
- ExperimentResult now exists as a first-class DB-backed observed outcome record linked to ExperimentRequest / Claim context, ingested through an explicit human-entered flow, and summarized in canonical scientific session truth.

### Partial
- Measurement-first modeling is now surfaced more honestly in Discovery and Dashboard, but the broader scientific core still leans on compatibility-shaped ranking and heuristic signals.
- Explanation quality is materially better than before, and Discovery/Dashboard now surface evidence, model, policy, and fallback semantics more clearly, but trust-contract work is not fully finished.
- Workspace memory is useful, but it is not yet the same thing as a model-improvement loop.
- Selective evidence governance is now explicit and partly operational, but it is still narrow: it affects interpretation/ranking context wording, continuity semantics, and limited reuse framing more than core recommendation mechanics.
- Future-learning eligibility is now explicit, but it still does not activate live learning or model updates.
- Candidate generation exists, but it is still narrow and heuristic.
- Claim, ExperimentRequest, and ExperimentResult now exist, but there is still no belief-update or belief-state loop behind them.

### Legacy-constrained
- Legacy adapters still preserve `biodegradable` for backward compatibility even though target-aware paths now prefer `target_label`.
- Some fallback modeling still relies on the older saved baseline classification bundle rather than session-specific target semantics.
- Novelty and applicability are still largely similarity heuristics.
- Scientific session truth is cleaner for new sessions, but older sessions still fall back to split DB and filesystem reconstruction.

### Intentionally unchanged
- Product continuity across the core routes remains the stability anchor.
- Backward compatibility for legacy sessions and artifacts is still important.
- Operational hardening is not the first priority until scientific and trust contracts are cleaner.

## Reusable Phase Tracker
### Goal
State the single phase objective in one or two sentences.

### Implemented
List the runtime-live changes that actually shipped.

### Partial
List what was started but is still incomplete, weakly surfaced, or only partly wired.

### Legacy-constrained
List the old assumptions or paths that still shape behavior after the phase.

### Intentionally unchanged
List the important areas left stable on purpose.

### Verification
List tests, manual checks, artifact checks, and unresolved verification limits.

### Next
State the next highest-leverage follow-up, not a long backlog.

## Current Known Truth Gaps
- The strongest product truth is session continuity and decision traceability, not autonomous scientific learning.
- The strongest scientific truth is still ranking support built on chemistry descriptors, random-forest models, and heuristic novelty/applicability signals.
- Review and workspace feedback memory are live, but the live web path does not yet clearly convert that evidence into future model improvement.
- UI trust language is closer to backend truth than before, but the deepest scientific rigor still lags the product surface.
- The legacy baseline bundle is now treated more explicitly as bridge-state behavior, but it still remains part of the live fallback path.

## Current Discovery Gaps
- The evidence loop is now defined with explicit activation boundaries, a selective activation policy, controlled future-eligibility rules, and limited controlled reuse, but it is still not an active live-learning system.
- The claim -> experiment -> result -> belief loop has started structurally, but only Claim, ExperimentRequest, and ExperimentResult exist so far.
- No fully neutral target semantics across all core model and data paths.
- No scientifically strong novelty/applicability treatment beyond similarity-based heuristics.
- The canonical scientific session object now exists for new sessions and comparison now prefers it, but old sessions still need compatibility backfills and not every read path is fully canonical-first yet.
- Candidate generation is not yet a strong discovery mechanism.

## Next Recommended Phase
Phase 3 follow-on slice: tighten BeliefState governance and add explicit accepted/proposed filtering plus richer target-scoped read-across, still without introducing live learning or model retraining.

## Notes for Codex
- Be conservative about scientific claims.
- Treat bridge-state behavior as important truth, not something to hide.
- Prefer compatibility layers and phased cleanup over abrupt rewrites.
- When reporting progress, separate runtime-live capability from partial wiring and backend-only scaffolding.
