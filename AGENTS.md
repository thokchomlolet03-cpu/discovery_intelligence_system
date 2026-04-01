# AGENTS

## Project Identity
Discovery Intelligence is a session-aware molecular decision-support workbench for choosing what to test next.

## Current Truth
The system is stronger as a product workbench than as a discovery engine. Upload, Discovery, Dashboard, and Sessions form one connected workflow. The scientific core is still bridge-state: recommendations are real, but the code still carries legacy biodegradability assumptions, heuristic novelty/applicability logic, and partially completed measurement-first modeling.

## Operating Rules
- Do not invent unsupported scientific capability.
- Preserve Upload -> Discovery -> Dashboard -> Sessions continuity.
- Prefer additive refactor plus compatibility adapters over hard replacement.
- Distinguish clearly between observed, computed, retrieved, derived, and predicted data.
- Be explicit when behavior is bridge-state, fallback-based, heuristic, or legacy-constrained.
- Do not widen product or scientific claims beyond the code truth.
- Preserve reviewability, provenance, and session reconstruction when changing internals.
- Keep target semantics truthful; do not present the system as target-agnostic if the code path is still legacy-shaped.

## Required Phase Report Format
After every implementation phase, report in this order:
1. What changed
2. What remains partial
3. What remains legacy-constrained
4. What remains intentionally unchanged
5. Verification
6. Risks or caveats
7. What should be done next
