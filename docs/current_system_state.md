# Discovery Intelligence — Current System State

## Current System Identity

Discovery Intelligence today is a session-aware molecular decision-support workbench for choosing what to test next.

It is not just a modeling script, and it is not yet a mature autonomous discovery engine. It is a real product surface with durable sessions, controlled scientific state, candidate review, dashboard interpretation, and an explicit minimal epistemic layer for claims, experiments, and belief-state tracking.

The system is currently strongest as a governed workbench:

- upload, discovery, dashboard, and sessions behave like one connected flow
- recommendation output is persisted and reopenable
- current system state is increasingly explicit rather than hidden in artifact files
- the scientific core is more honest about bridge-state constraints than earlier versions

The system should therefore be understood as a serious technical workbench with a partially transitional scientific core, not as a finished discovery platform.

## What the System Does Today

Today the system can:

- ingest uploaded chemistry datasets into durable sessions
- derive target and evidence context from uploaded inputs
- run ranking and recommendation workflows for candidate prioritization
- persist canonical scientific, run-level, and candidate-level state
- surface trust, fallback, ranking, and comparison context in the product
- let users review and reopen sessions across Upload, Discovery, Dashboard, and Sessions
- carry forward workspace review memory across related sessions
- track a minimal epistemic layer with claims, experiment requests, experiment results, belief updates, and belief states
- render compact epistemic summaries in product-facing views
- support lightweight and focused epistemic inspection without turning the product into a workflow engine

What it does not do today:

- provide experimental truth automatically
- replace bench validation
- run a mature evidence-to-learning loop
- support a broad experiment workflow system
- claim that review decisions are the same as scientific belief truth

## Current Canonical Architecture

### 1. Scientific-State Substrate

The scientific-state substrate now persists core scientific objects as canonical records:

- `TargetDefinition`
- `EvidenceRecord`
- `ModelOutput`
- `RecommendationRecord`
- `CarryoverRecord`

This layer is the durable scientific session substrate rather than a transient report-only layer.

### 2. Run-Level Canonical Substrate

Run-level canonical state now exists for:

- `run_contract`
- `comparison_anchors`
- `ranking_policy`
- `ranking_diagnostics`
- trust and fallback summaries
- provenance markers

This lets the system surface what kind of run actually happened, not just what recommendation artifacts look like afterward.

### 3. Candidate-Level Canonical Substrate

Candidate-level canonical state now persists:

- identity context
- evidence summary
- predictive summary
- recommendation summary
- governance summary
- carryover summary
- trust summary
- provenance markers

This allows candidate rendering to rely less on ad hoc artifact reconstruction and more on explicit candidate state.

### 4. Minimal Epistemic Layer

The minimal epistemic layer is now canonical and persisted:

- `Claim`
- `ExperimentRequest`
- `ExperimentResult`
- `BeliefUpdate`
- `BeliefState`

This layer is intentionally small. It is not a full scientific knowledge graph or contradiction engine.

### 5. Controlled Read Surfaces

The canonical epistemic layer is now readable through controlled surfaces:

- compact belief-layer summaries
- claim-detail inspection
- experiment-lifecycle read surfaces
- explicit absent and unresolved states
- experiment-to-belief linkage visibility

### 6. Controlled UI-Facing Surfacing

The product now renders compact epistemic state through:

- compact session epistemic summaries
- compact candidate epistemic context
- lightweight entry-point metadata
- reusable session-level rendering partials
- Discovery, Dashboard, and Sessions integration
- client-side Discovery candidate rendering for compact epistemic context
- lightweight reveal blocks
- focused claim and experiment inspection surfaces

The result is that the epistemic layer is now visible, inspectable, and shaped, rather than remaining hidden in backend-only structures.

## Current Workflow

### Upload and Ingest

The practical workflow still begins with upload and ingestion:

- users upload chemistry datasets
- the system creates a durable session
- target and evidence context are derived or reconstructed
- session metadata and artifacts remain reopenable

### Discovery, Ranking, and Review

The Discovery surface then presents:

- ranked candidates
- recommendation summaries
- trust and caution language
- review controls
- candidate-level scientific and epistemic context

This is a prioritization and review surface, not an experimental truth surface.

### Claims, Experiments, and Belief-State Support

Where epistemic objects exist, the system now supports:

- compact session-level epistemic visibility
- candidate-linked epistemic context
- lightweight reveal inspection
- focused claim inspection
- focused experiment-linked inspection

These layers are canonical and deterministic, but still intentionally bounded.

### Session, Workbench, Dashboard, and Sessions Surfaces

The product now behaves as one connected workbench across:

- `Upload`
- `Discovery`
- `Dashboard`
- `Sessions`

This continuity is one of the strongest implemented parts of the system today.

## What Is Implemented

Major implemented capabilities now include:

- durable session-aware product flow
- canonical scientific-state persistence
- canonical run-level metadata persistence
- canonical candidate-state persistence
- minimal canonical epistemic persistence
- controlled epistemic read surfaces
- compact UI-facing epistemic rendering
- lightweight epistemic detail reveal
- focused claim inspection
- focused experiment-linked inspection
- session reopening and workbench continuity
- workspace review memory carryover
- explicit trust, fallback, and comparison surfacing

## What Remains Partial

Several important areas remain transitional or partial:

- the scientific core still relies heavily on random-forest-style scoring paths
- novelty and applicability remain partly heuristic
- the evidence-to-learning loop is not yet mature
- the epistemic layer is still minimal rather than deeply model-integrated
- focused inspection exists, but object selection remains narrow and lightweight
- some surfaces still depend on bridge-state composition between canonical state and artifact-era structures

These are not hidden limitations. They are part of the current system truth.

## What Remains Legacy-Constrained

The main legacy constraints today are:

- residual artifact-era reconstruction logic
- compatibility layers for older sessions and older output formats
- remaining fallback dependence in parts of the scientific path
- bridge-state semantics where canonical state and historical artifact paths still coexist

The system is much less dependent on purely artifact-era truth than before, but that transition is not yet complete.

## What Is Intentionally Unchanged

Several things have deliberately not been added yet:

- no broad workflow engine for experiment execution
- no contradiction engine
- no graph-database-centric epistemic system
- no LLM scientific authority layer
- no recommendation text treated as belief truth
- no review state treated as experimental truth
- no large navigation redesign around epistemic objects

These omissions are intentional because the goal is disciplined system growth, not apparent complexity.

## Current Bottlenecks

The main bottlenecks today are:

### 1. Scientific Core Maturity

The workbench surface is ahead of the underlying discovery engine maturity. The product is more coherent than the scientific core is complete.

### 2. Bridge-State Compatibility

Canonical persistence is now real, but some truth still passes through compatibility paths that were necessary to preserve older sessions and artifacts.

### 3. Learning Loop Depth

The system can carry forward review memory and experiment-linked epistemic state, but that is not yet the same as a strong evidence-to-model learning loop.

### 4. Inspection Depth

The product now supports compact and focused epistemic inspection, but not yet a richer multi-object inspection flow. That is appropriate for now, but it remains a constraint.

## What Should Come Next

The next architectural direction should remain disciplined.

The likely next steps are:

- reduce remaining fallback dependence in the scientific core
- strengthen evidence-to-learning semantics without overstating current capability
- further tighten canonical state as the primary source of product truth
- improve object selection for focused claim and experiment inspection without introducing workflow sprawl
- continue making bridge-state constraints explicit rather than hidden

What should not happen next:

- adding speculative ontology
- building a large workflow system prematurely
- increasing UI surface complexity faster than canonical truth improves

## Final Summary

Discovery Intelligence today is a serious, session-aware molecular decision-support workbench with a durable canonical architecture across scientific, run, candidate, and minimal epistemic layers.

It already supports real product continuity, canonical state persistence, compact and focused epistemic inspection, and increasingly honest rendering of trust, fallback, and bridge-state constraints.

It is not yet a mature discovery engine or a complete evidence-learning system. The right way to understand it is as a technically real and increasingly disciplined workbench whose product surface is strong, whose canonical architecture is now substantial, and whose remaining limits are transitional rather than hidden.
