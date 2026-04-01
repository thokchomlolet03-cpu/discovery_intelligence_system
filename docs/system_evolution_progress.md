# System Evolution Progress

## Long-Term Goal
Help a small molecular R&D team choose better next experiments faster, with explanations they can trust and challenge.

## Current Truthful System Identity
Discovery Intelligence is a scientific decision-support workbench, not an autonomous discovery engine. Today it is a session-backed product for upload, scoring, review, comparison, and continuity across runs. It is not yet a true evidence-learning discovery system.

## Current Major Stage
Bridge-state workbench stabilization after the neutral-core cleanup, trust-surface pass, and the first measurement-first honesty slice. The product surface now exposes session identity, evidence basis, model/policy separation, bridge-state fallback, and regression ranking semantics more explicitly, but the scientific core still needs stronger evidence-learning behavior and cleaner fallback handling.

## Current Snapshot
### Implemented
- Session-aware Upload -> Discovery -> Dashboard -> Sessions workflow.
- Auth, workspaces, billing, job tracking, artifact registry, and review persistence.
- Support for structure-only, labeled, and measurement-oriented uploads.
- Session comparison and workspace feedback continuity.
- Candidate ranking, rationale generation, and dashboard/session reconstruction from persisted artifacts.

### Partial
- Measurement-first modeling is now surfaced more honestly in Discovery and Dashboard, but the broader scientific core still leans on compatibility-shaped ranking and heuristic signals.
- Explanation quality is materially better than before, and Discovery/Dashboard now surface evidence, model, policy, and fallback semantics more clearly, but trust-contract work is not fully finished.
- Workspace memory is useful, but it is not yet the same thing as a model-improvement loop.
- Candidate generation exists, but it is still narrow and heuristic.

### Legacy-constrained
- Legacy adapters still preserve `biodegradable` for backward compatibility even though target-aware paths now prefer `target_label`.
- Some fallback modeling still relies on the older saved baseline classification bundle rather than session-specific target semantics.
- Novelty and applicability are still largely similarity heuristics.
- Scientific session truth is still reconstructed from split DB and filesystem sources.

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
- No fully defined evidence-to-learning loop.
- No fully neutral target semantics across all core model and data paths.
- No scientifically strong novelty/applicability treatment beyond similarity-based heuristics.
- No single canonical scientific session object cleanly unifying DB truth and artifact truth.
- Candidate generation is not yet a strong discovery mechanism.

## Next Recommended Phase
Evidence Loop Definition and Canonical Scientific Session Truth. Keep the workbench stable while defining what evidence should genuinely change future recommendations and reducing the remaining split between DB/session truth and artifact reconstruction.

## Notes for Codex
- Be conservative about scientific claims.
- Treat bridge-state behavior as important truth, not something to hide.
- Prefer compatibility layers and phased cleanup over abrupt rewrites.
- When reporting progress, separate runtime-live capability from partial wiring and backend-only scaffolding.
