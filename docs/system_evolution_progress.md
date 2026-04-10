# System Evolution Progress

## Long-Term Goal
Help a small molecular R&D team choose better next experiments faster, with explanations they can trust and challenge.

## Current Truthful System Identity
Discovery Intelligence is a scientific decision-support workbench, not an autonomous discovery engine. Today it is a session-backed product for upload, scoring, review, comparison, and continuity across runs. It is not yet a true evidence-learning discovery system.

## Current Major Stage
Bridge-state workbench stabilization after the neutral-core cleanup, trust-surface pass, measurement-first honesty slice, the first explicit evidence/session-truth contract, canonical-first comparison adoption, selective evidence activation governance, future-learning eligibility definition, the narrow controlled-reuse activation slice, the Phase 3 scientific-loop scaffolding slices, the broader governed evidence-reuse semantics slice, the continuity-cluster promotion semantics slice, the governed promotion-boundary semantics slice, the trusted-evidence plus governed-review slice, and now the multi-layer governed-review extension slice. The product surface now exposes session identity, evidence basis, model/policy separation, bridge-state fallback, regression ranking semantics, canonical scientific session truth, explicit evidence-use activation boundaries, selective evidence use, controlled future-eligibility boundaries, limited recommendation/ranking-context reuse, first-class proposed claims, claim-linked proposed experiment requests, observed experiment-result records, bounded belief-update records, a target-scoped belief-state summary with more explicit proposed-vs-accepted governance, explicit belief-update acceptance/rejection actions, explicit supersede/history handling, bounded read-across alignment, lightweight cross-session claim continuity-vs-novelty surfacing weighted by prior governed support quality, a bounded broader-reuse layer that distinguishes local usefulness from broader governed carryover, a bounded continuity-cluster layer that distinguishes local-only/context-only continuity from selective or stronger promotion-candidate continuity, a bounded promotion-boundary layer that distinguishes not-a-candidate, blocked, selectively promotable, promotable, downgraded, and quarantined continuity under explicit governed rules, and now a persisted governed-review ledger plus explicit trust-tier, source-class, provenance-confidence, local-only-by-default, anti-poisoning posture surfacing, target-scoped belief-state review history, continuity-cluster review history, and session-family carryover review history. The scientific-core path now also uses result quality, assay-context alignment, and bounded numeric interpretation rules to make BeliefUpdate generation less flat, and it now carries an explicit support-quality layer that distinguishes decision-useful active support from active-but-limited, context-limited, and weak/unresolved support. It now also adds a governed-support-posture layer that distinguishes accepted posture-governing support from accepted-but-limited support, tentative active support, and historical-only support after supersession. The latest upgrades also add bounded contradiction/degradation semantics so multiple accepted or active updates no longer collapse into a single flat “current support exists” picture: current support can now be surfaced as coherent, contested, degraded, contested-and-degraded, or historically stronger than the present, governed reuse can now be surfaced as strongly reusable, selectively reusable, contradiction-limited, weakly reusable, or historical-only, broader governed reuse can now be surfaced as strong, selective, contradiction-limited, historical-only, or still only locally meaningful, continuity clusters can now be surfaced as local-only, context-only, selective, contradiction-limited, historical-heavy, or stronger promotion-candidate quality, promotion boundaries can now be surfaced through compact promotion stability, promotion gate, and promotion block-reason semantics, and governed review can now preserve approval, block, defer, downgrade, quarantine, and reversal history instead of letting those postures stay purely ephemeral. BeliefState, continuity-cluster posture, session-level decision summaries, claims, and session comparison now all roll up support quality, governed posture, coherence, local reuse, broader continuity, broader reuse, continuity-cluster posture, promotion-candidate posture, promotion stability, promotion-gate posture, promotion block reason, future reuse candidacy, compact trust/review posture, and multi-layer carryover guardrails so the product can say not just that support exists, but whether it is genuinely strong enough to govern present posture, still tentative, context-limited, mixed under contradiction pressure, materially degraded by newer evidence, mainly historical context after stronger support has been superseded, still too local for honest broader carryover, strong enough to be treated as a later governed promotion candidate, blocked at belief-state or continuity-cluster level, deferred at session-family level, or still useful locally while broader influence remains constrained by source class, provenance, contradiction, or higher-layer instability. The scientific core still needs stronger evidence-learning behavior.

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
- Evidence activation policy now also rolls up source-class semantics, provenance confidence, trust tier, governed review posture, explicit local-only-by-default wording, and an anti-poisoning note that repetition does not create broader influence.
- Limited selective evidence use is now operational for recommendation interpretation and ranking-context honesty, especially around workspace memory and review continuity, without changing model outputs or training.
- Controlled future-learning eligibility and recommendation-reuse eligibility are now persisted per evidence type, including stronger-validation requirements and permanently non-active boundaries for weak or indirect evidence classes.
- Controlled recommendation reuse and ranking-context reuse are now active in a small, explicit, user-visible form for continuity/prioritization framing, and canonical scientific session truth persists whether that reuse was active for a session.
- Claim now exists as a first-class DB-backed bounded scientific assertion derived from current session recommendations.
- ExperimentRequest now exists as a first-class DB-backed proposed next-experiment object derived from current Claims and linked into canonical scientific session truth.
- ExperimentResult now exists as a first-class DB-backed observed outcome record linked to ExperimentRequest / Claim context, ingested through an explicit human-entered flow, and summarized in canonical scientific session truth.
- BeliefUpdate now exists as a first-class DB-backed bounded support-change record linked to Claim plus ExperimentResult.
- BeliefState now exists as a first-class DB-backed target-scoped support summary, and it now surfaces mostly-proposed vs mostly-accepted governance, tentative vs stronger support language, bounded session-level read-across alignment, explicit dependence on governed belief-update status, explicit separation between current active support changes and superseded historical support records, compact current-vs-historical chronology summaries across the existing product surfaces, lightweight per-claim chronology grouping, lightweight cross-session claim continuity-vs-novelty summaries, bounded broader target reuse, broader continuity clustering, and future reuse candidacy.
- Claims now persist lightweight governed-review records that preserve source class, provenance confidence, trust tier, review posture, promotion gate, promotion block reason, and reversal history instead of relying only on ephemeral rollups.
- Belief-state, continuity-cluster, and session-family carryover postures now also persist lightweight governed-review records so broader influence above the individual claim layer is reviewable, reversible, and no longer only computed ephemerally.
- Discovery, Dashboard, Sessions, and comparison now surface multi-layer broader-review posture compactly, including belief-state review, continuity-cluster review, session-family carryover review, promotion-audit summaries, and anti-poisoning carryover guardrails.

### Partial
- Measurement-first modeling is now surfaced more honestly in Discovery and Dashboard, but the broader scientific core still leans on compatibility-shaped ranking and heuristic signals.
- Explanation quality is materially better than before, and Discovery/Dashboard now surface evidence, model, policy, source class, trust tier, and fallback semantics more clearly, but trust-contract work is still partly rule-based and not yet manually governed end-to-end.
- Workspace memory is useful, but it is not yet the same thing as a model-improvement loop.
- Selective evidence governance is now explicit and partly operational, but it is still narrow: it affects interpretation/ranking context wording, continuity semantics, and limited reuse framing more than core recommendation mechanics.
- Future-learning eligibility is now explicit, but it still does not activate live learning or model updates.
- Candidate generation exists, but it is still narrow and heuristic.
- The Phase 3 ontology now exists end-to-end, and BeliefUpdate governance now has real human accept/reject/supersede actions with more readable claim-level chronology plus lightweight cross-session claim read-across weighted by prior governed support quality. BeliefUpdate generation now also uses bounded result-quality, assay-context, and derived-label-rule input where available. Experiment-request intent, observed-result interpretation, claim support usefulness, belief-state usefulness, and the compact session-level scientific decision picture are now more explicit across the existing pages, including whether support is decision-useful now, still limited, context-limited, or weak/unresolved. Governed support semantics are also stronger: accepted support can now be surfaced as posture-governing or only limited-weight, proposed support can remain explicitly tentative, superseded support is more clearly treated as historical-only, cross-session continuity can now be discounted when prior active support was only tentative or weak, mixed active/accepted updates can now surface contradiction pressure, degraded current posture, and contradiction-limited reuse instead of looking cleanly current just because records still exist, broader claim/target reuse can now be separated from local support so the system can say when a support picture is only locally meaningful, selectively reusable, contradiction-limited, historical-heavy, or a stronger candidate for later governed reuse, continuity clusters can now be kept explicitly separate as local-only, context-only, selective, contradiction-limited, historical-heavy, or stronger promotion-candidate quality, promotion boundaries can now be surfaced as stable, selectively stable, blocked, downgraded, quarantined, or promotable under bounded rules, and multi-layer governed-review history is now persisted rather than reconstructed only from the current summary state. Governance remains intentionally simple and there is still no live learning or model-updating behavior behind it.

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
- The evidence loop is now defined with explicit activation boundaries, a selective activation policy, controlled future-eligibility rules, limited controlled reuse, explicit source-class/provenance/trust posture, and a non-volume-weighted anti-poisoning boundary, but it is still not an active live-learning system.
- The claim -> experiment -> result -> belief loop now exists structurally, and BeliefUpdate governance plus session-level and claim-level support chronology are now explicit and more readable. Cross-session claim read-across is also now surfaced in a lightweight way and now distinguishes active governed continuity from historical-only or sparse prior context. BeliefUpdate generation now uses bounded result-quality, assay-context, and target-scoped numeric interpretation when the current target definition provides a clean target rule and enough matching context to use it honestly. BeliefState and session-level support summaries now also expose whether the current support picture is grounded mostly in observed labels, bounded numeric interpretation, or unresolved/weak-basis evidence, and they now add a compact support-quality layer saying whether active support is decision-useful now, still limited, context-limited, or weak/unresolved. Claim summaries now expose both the same support-basis composition and that support-quality picture at the per-claim level. Claim summaries now also derive bounded next-step guidance from current governed support, support-basis mix, and support-quality signals, and they now separate current active support grounding from historical-only context more explicitly so a user can see whether a claim is presently actionable because active support is decision-useful, merely limited despite being active, context-limited, only historically interesting, mixed current/historical and still needing clarification, or lacking active governed support altogether. The newest broader reuse upgrade now also lets the system say when broader reuse is strong versus selective, when broader continuity is coherent versus contested or historical-heavy, when degraded present posture should weaken broader target continuity, when contradiction-heavy histories should limit future reuse candidacy, when current support remains locally meaningful without being honest broader carryover, whether a continuity cluster should remain local-only/context-only or whether it is coherent enough to count as a later governed promotion candidate, and now whether that candidate is actually promotable, only selectively promotable, blocked, downgraded, or quarantined under bounded rules. Experiment requests now also reflect whether they are confirmatory, clarifying, fresh-evidence, or exploratory follow-up, observed-result summaries now expose stronger-vs-limited-vs-context-limited-vs-unresolved interpretation more directly, and a compact session-level scientific decision picture now ties those pieces together across Discovery, Dashboard, Sessions, and comparison without becoming an autonomous planner. The overall support picture still remains deliberately conservative and does not amount to autonomous scientific reasoning, deep evidence fusion, strong claim identity resolution, or live learning.
- No fully neutral target semantics across all core model and data paths.
- No scientifically strong novelty/applicability treatment beyond similarity-based heuristics.
- The canonical scientific session object now exists for new sessions and comparison now prefers it, but old sessions still need compatibility backfills and not every read path is fully canonical-first yet.
- Candidate generation is not yet a strong discovery mechanism.

## Next Recommended Phase
Phase 3 follow-on slice: add first-class manual review actions and override traces on top of the new multi-layer governed-review ledger, then tighten provenance-aware local-vs-core learning separation and broader carryover controls without adding live retraining yet.

## Notes for Codex
- Be conservative about scientific claims.
- Treat bridge-state behavior as important truth, not something to hide.
- Prefer compatibility layers and phased cleanup over abrupt rewrites.
- When reporting progress, separate runtime-live capability from partial wiring and backend-only scaffolding.
