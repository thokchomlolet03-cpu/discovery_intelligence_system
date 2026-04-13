# Dynamic Representation and Evaluation Architecture for Discovery Intelligence

## Purpose

This document defines how Discovery Intelligence should implement:

- dynamic representation selection
- representation evaluation
- iterative representation improvement
- controlled promotion of better representations
- representation-aware scoring and uncertainty
- representation-aware comparison across sessions and versions

This is not a proposal for uncontrolled adaptive learning.

It is a proposal for a **governed, versioned, task-aware representation system**.

The core idea is simple:

> Discovery Intelligence cannot represent all of reality.
> So it must choose representations deliberately, evaluate them scientifically, and improve them iteratively without losing comparability, auditability, or epistemic discipline.

## Status

This is a forward-looking architecture document for the scientific representation layer.

It describes how Discovery Intelligence should evolve beyond a single legacy-shaped representation path while still preserving reviewability, comparability, and explicit governance. It does not mean the live system already ships a full representation registry, router, builder, evaluation loop, or promotion workflow. The current runtime is still bridge-state: recommendations are real, but important code paths remain legacy-constrained by biodegradability-era assumptions, heuristic novelty/applicability logic, and partially completed measurement-first modeling.

This document should therefore be read as implementation direction and control logic, not as a claim that representation-aware runtime adaptation is already complete.

## Core Position

Discovery Intelligence should **not** use a single frozen representation forever.

It also should **not** create a new unconstrained representation every time a new input arrives.

Instead, it should use:

## **a governed family of representation profiles**

selected dynamically at runtime from an approved set,
and improved iteratively through evaluation and promotion.

This gives the system:

- flexibility
- task awareness
- input awareness
- safer fallback behavior
- versioned comparability
- scientific discipline

## Why This Is Needed

The system's scientific usefulness depends heavily on what it can "see."

If the representation is too weak:

- raw predictive signal stays weak
- ranking stays fragile
- heuristic dominance stays high
- uncertainty stays large
- candidate separation stays poor

If the representation is too complex or uncontrolled:

- evaluation becomes muddy
- version comparison becomes weak
- interpretability drops
- governance becomes harder
- the system may overfit or drift

So Discovery Intelligence needs a middle path:

## **dynamic but governed representation**

## Design Goals

The representation system should satisfy these goals.

### 3.1 Task-awareness

Different scientific tasks may need different representation emphasis.

Examples:

- candidate prioritization
- classification
- regression
- uncertainty-sensitive ranking
- session comparison
- contradiction analysis

### 3.2 Input-awareness

The system should respond differently when the input is:

- rich
- medium quality
- thin
- missing important fields
- structure-only
- structure-plus-context

### 3.3 Honest degradation

If representation support is weak, the system should:

- reduce confidence
- reduce ranking aggressiveness
- expose thinness explicitly
- avoid false precision

### 3.4 Comparability

Representation changes must remain:

- versioned
- inspectable
- comparable across runs where feasible

### 3.5 Governability

Representation must stay compatible with:

- score interpretation
- uncertainty summaries
- reviewer workflow
- predictive-path explanation
- downstream governance shell

## High-Level Architecture

The dynamic representation system should have five main parts:

### A. Representation Registry

Stores all approved representation profiles.

### B. Representation Router

Chooses the best profile at runtime based on task and input condition.

### C. Representation Builder

Constructs the actual feature set for the chosen profile.

### D. Representation Evaluation Layer

Measures how well each representation profile performs.

### E. Representation Promotion Layer

Decides when a new or updated representation profile becomes approved for production use.

## Representation Profile Concept

A **representation profile** is a named, versioned, explicitly defined representation strategy.

It is not just "a bag of features."

Each profile should define:

- profile name
- version
- supported tasks
- required inputs
- optional inputs
- feature families used
- fallback behavior
- known limitations
- expected uncertainty implications
- evaluation history summary

### Example profile names

- `structure_basic_v1`
- `structure_similarity_v1`
- `structure_contextual_v1`
- `thin_input_fallback_v1`
- `regression_contextual_v1`
- `classification_density_enhanced_v1`

These are examples only, not fixed names.

## Representation Registry

### Purpose

The registry is the canonical list of approved representation profiles.

### It should store for each profile:

- `profile_id`
- `profile_name`
- `profile_version`
- `supported_tasks`
- `required_fields`
- `optional_fields`
- `feature_families`
- `selection_rules`
- `fallback_policy`
- `known_limits`
- `status` (`experimental`, `approved`, `deprecated`)
- `created_at`
- `evaluation_summary`
- `replaced_by` if deprecated

### Why this matters

Without a registry:

- dynamic representation becomes implicit
- version comparison becomes weak
- runtime selection becomes opaque
- evaluation becomes harder to trust

## Representation Router

### Purpose

The router decides **which approved profile to use** for a given request.

### Inputs to routing

The router should inspect:

- task type
- input modality
- available structure
- available metadata/context
- missingness pattern
- representation support richness
- possibly data quality class

### Router output

The router should return:

- selected profile ID
- selection reason
- available input summary
- missingness summary
- representation support class
- caution flags

### Example routing logic

#### Example 1 - Structure only

Input:

- SMILES only
- no assay context
- no external metadata

Route to:

- `structure_similarity_v1`

#### Example 2 - Rich regression task

Input:

- structure
- numeric assay context
- target-specific measurement fields

Route to:

- `regression_contextual_v1`

#### Example 3 - Thin input

Input:

- incomplete structure or sparse fields
- weak context
- low support

Route to:

- `thin_input_fallback_v1`

### Important constraint

The router must choose only among:

## approved, versioned, explicit profiles

It must not invent a new representation at runtime.

## Representation Builder

### Purpose

Given a selected representation profile, build the actual feature matrix / feature object used by the predictive engine.

### Responsibilities

The builder should:

- gather required fields
- gather optional fields when present
- compute feature families
- apply missingness handling
- compute representation support metadata
- emit a feature package with traceable provenance

### Representation output should include:

- feature vector / feature frame
- feature family summary
- missingness summary
- representation support summary
- profile ID/version used
- build-time warnings

### Example feature families

Depending on profile:

- RDKit descriptors
- fingerprints
- similarity features
- local similarity-density features
- numeric context variables
- assay context variables
- support-density summaries
- missingness indicators

## Runtime Dynamic Representation Selection

This is the practical dynamic part.

### Allowed dynamic behavior

At runtime, Discovery Intelligence may:

- choose different profiles for different tasks
- choose different profiles for rich vs thin input
- choose safer fallback profiles under missingness
- attach representation support summaries to output

### Not allowed dynamic behavior

At runtime, Discovery Intelligence must not:

- invent a new feature family spontaneously
- silently change profile definitions
- create new latent semantics without versioning
- break comparability by uncontrolled adaptation

So:

## dynamic selection is allowed

## uncontrolled dynamic invention is not

## Representation Support Semantics

Representation quality should not be hidden.

Each candidate or run should carry a representation support summary.

### Suggested support states

- `strongly_supported`
- `moderately_supported`
- `thinly_supported`
- `context_limited`
- `fallback_profile_used`

### Representation support can be influenced by:

- feature completeness
- neighborhood density
- similarity support
- missing critical context
- profile fallback usage
- out-of-distribution signs where available

### Why this matters

The representation system should not only build features.
It should also tell the rest of DI how much trust to place in that representation.

## Representation-Aware Scoring

Representation should influence scoring behavior, not only explanation afterward.

### Allowed effects

Representation weakness may:

- reduce ranking aggressiveness
- increase uncertainty
- increase fragility warnings
- reduce separation confidence
- mark candidate as thinly supported
- downgrade strong-looking but weakly supported ordering

### Important principle

Representation-aware scoring should improve:

- honesty
- ranking behavior
- uncertainty handling

Not just:

- user-facing caution text

## Representation Evaluation

Representation should be evaluated scientifically, not chosen by taste.

### What evaluation should answer

For a given representation profile:

- does it improve candidate ranking?
- does it improve separation?
- does it reduce heuristic dominance?
- does it increase stability?
- does it improve uncertainty honesty?
- does it perform better on certain subsets?
- where does it fail?

### Evaluation levels

#### 12.1 Task-level evaluation

Check performance by task:

- classification
- regression
- candidate prioritization
- uncertainty-sensitive ranking

#### 12.2 Input-condition evaluation

Check performance under:

- rich input
- medium input
- thin input
- missing metadata
- structure-only cases

#### 12.3 Cohort-level evaluation

Check performance on subsets such as:

- representation-supported
- representation-limited
- signal-led
- heuristic-heavy
- fragile band
- top shortlist

#### 12.4 Cross-session evaluation

Check behavior across:

- related sessions
- similar evidence patterns
- repeated scoring contexts

#### 12.5 Version comparison

Compare profile version vs prior version:

- what improved
- what worsened
- which subsets changed most
- whether uncertainty changed honestly

## What Metrics Should Be Used

No single metric is enough.

Use multiple bounded diagnostics.

### Suggested evaluation categories

#### 13.1 Ranking usefulness

- top-k usefulness
- candidate separation
- shortlist quality structure

#### 13.2 Stability

- rank stability across mild variation
- fragile ordering diagnostics
- too-close-to-call frequency

#### 13.3 Dependence structure

- raw signal contribution
- heuristic dominance
- representation support dependence

#### 13.4 Uncertainty honesty

- thin-support caution rate
- fragile-signal detection
- weak-separation detection

#### 13.5 Cross-session robustness

- subset consistency
- cohort behavior across sessions
- representation-limited failure patterns

Metrics should remain bounded and honest.
Do not fabricate benchmark truth if it does not exist.

## Factors to Consider Beyond Evaluation

Evaluation is necessary, but not sufficient.

When deciding whether to adopt or update a representation, Discovery Intelligence should also consider:

### 14.1 Scientific plausibility

Does this representation make scientific sense?

### 14.2 Interpretability

Can the system and reviewers understand what the representation is doing?

### 14.3 Stability

Does it behave consistently, or only look good on narrow cases?

### 14.4 Data availability

Can the required inputs realistically be obtained often enough?

### 14.5 Missing-data behavior

Does it degrade honestly when data is incomplete?

### 14.6 Governance compatibility

Can downstream trust/review/carryover logic still operate clearly?

### 14.7 Comparability

Can this new representation still be compared against older versions?

### 14.8 Cost and complexity

Is the gain worth the implementation burden?

### 14.9 Failure-mode shape

Does it fail:

- loudly and honestly

or

- smoothly and deceptively?

The first is often safer for a scientific system.

## Iterative Representation Improvement

Representation should be updated iteratively.

But the update loop must be controlled.

### Correct loop

#### Step 1

Define or modify a candidate representation profile.

#### Step 2

Evaluate it against relevant tasks, subsets, and cohorts.

#### Step 3

Compare against currently approved profiles.

#### Step 4

Inspect:

- improvement
- failure modes
- uncertainty behavior
- heuristic dependence
- representation thinness patterns

#### Step 5

Decide:

- reject
- keep experimental
- approve for bounded use
- promote to preferred profile

#### Step 6

Version and document the change.

This is the right scientific loop.

### Wrong loop

- change representation
- rerun once
- looks better
- silently replace old one

That must be avoided.

## Representation Promotion Policy

A representation update should not become active just because it looks promising.

A new profile should be promoted only if it satisfies enough of the following:

- improves target task metrics
- improves relevant subsets/cohorts
- does not worsen critical stability too much
- keeps uncertainty honest
- remains explainable enough
- stays compatible with governance shell
- does not destroy comparability beyond acceptable limits

### Promotion states

A representation profile may be:

- `experimental`
- `approved_for_bounded_use`
- `preferred`
- `deprecated`

This is enough for the current stage.

## Stable Base + Conditional Enhancement Strategy

This is the recommended practical strategy.

### Layer A - Stable base representation

Always available.
Low risk.
Forms the default comparison anchor.

### Layer B - Conditional enhancement profiles

Activated only when:

- task needs them
- inputs support them
- evaluation shows benefit

### Layer C - Honest fallback profiles

Used when input is weak or incomplete.

This strategy gives:

- stability
- dynamic behavior
- fallback safety
- easier evaluation

## How This Fits into Discovery Intelligence Architecture

Dynamic representation should connect to existing DI components.

### Upstream

- upload parser
- session input inspection
- feature/data services
- candidate generation
- training/prediction services

### Midstream

- scoring semantics service
- predictive path service
- uncertainty / fragility logic
- run metadata service

### Downstream

- session report
- dashboard
- discovery workbench
- session comparison
- future LLM explanation layer
- future governed publication/testing surface

Representation is therefore not just a modeling detail.
It is part of the core predictive architecture.

## Suggested Services / Components to Add

These names are suggestions, not strict requirements.

### 19.1 `representation_registry_service.py`

Stores and loads profile definitions.

### 19.2 `representation_router_service.py`

Chooses the profile for a given task/input situation.

### 19.3 `representation_builder_service.py`

Builds features for a selected profile.

### 19.4 `representation_evaluation_service.py`

Evaluates profile behavior across tasks/subsets.

### 19.5 `representation_promotion_service.py`

Handles profile status changes and approval workflow.

### 19.6 Contract additions

Schema models for:

- representation profile
- representation selection summary
- representation support summary
- representation evaluation summary
- representation comparison summary

## Product Surfacing

The product should expose dynamic representation in a compact but meaningful way.

### At run/session level

Show:

- selected profile
- why it was selected
- representation support class
- key limitations

### At candidate level

Show:

- representation support
- thinness / fallback warnings
- effect on uncertainty or caution

### At comparison level

Show:

- profile differences across runs
- subset behavior
- whether a newer profile improved or worsened reusable cohorts

Do not build a giant representation dashboard.
Keep it compact and inspectable.

## Example Runtime Flow

### Example case

Task:

- rank candidates for what-to-test-next

Input:

- structure present
- some metadata present
- partial assay context
- moderate missingness

#### Flow

1. Router checks task and input richness.
2. Router selects `structure_contextual_v1`.
3. Builder computes descriptors, fingerprints, similarity-density, and available context fields.
4. Builder emits representation support = `moderately_supported`.
5. Predictive engine scores candidates using this representation.
6. Scoring layer reduces aggressiveness where support is thin.
7. Uncertainty layer reflects representation thinness.
8. Predictive path panel shows:

- selected profile
- support summary
- representation-limited subsets if relevant

That is the practical implementation target.

## Example Iterative Update Flow

### Current preferred profile

`structure_similarity_v1`

### Candidate new profile

`structure_similarity_density_v2`

#### Offline process

1. Evaluate v2 against v1 on:

- top shortlist
- representation-supported subset
- representation-limited subset
- signal-led subset
- fragile band

2. Compare:

- separation
- stability
- uncertainty honesty
- heuristic dominance

3. Inspect failure modes.
4. If v2 improves relevant targets without unacceptable regressions:

- mark `approved_for_bounded_use`
- optionally promote to `preferred`

5. Keep v1 for comparison history.

This is how iterative update should work.

## What This Should Not Become

The representation system should not become:

- uncontrolled auto-adaptation
- hidden dynamic behavior
- an opaque feature jungle
- a comparability-breaking mechanism
- a substitute for evaluation
- a substitute for scientific reasoning

It should remain:

- explicit
- versioned
- evaluable
- governed
- useful

## Relationship to Future LLM Layer

The LLM should not decide representation.

At most, later, it may help:

- explain which profile was selected
- explain why representation is thin
- ask users for missing fields that would unlock a richer profile

But:

- profile selection rules
- profile definitions
- promotion logic

must remain in DI, not in the LLM.

## Relationship to Future Governed Publication / Testing Page

Later, external evidence may reveal:

- which representation profiles are too weak
- which domains need richer context
- which subset failures matter most

That can inform future representation iteration.

But external engagement must not directly rewrite representation.
It should influence representation only through:

- evidence
- evaluation
- governed review
- versioned promotion

## Implementation Roadmap

### Phase 1 - Registry and routing

Implement:

- representation profile schema
- registry
- router
- runtime selection summary

### Phase 2 - Builder integration

Implement:

- feature construction per profile
- support summaries
- fallback handling

### Phase 3 - Evaluation integration

Implement:

- profile-level evaluation summaries
- version comparison
- subset/cohort diagnostics

### Phase 4 - Promotion workflow

Implement:

- experimental / approved / preferred states
- promotion rules
- deprecation flow

### Phase 5 - Product surfacing

Implement:

- compact profile visibility in workbench/reporting
- candidate-level support visibility
- comparison-level profile differences

This is the recommended order.

## Final Position

Dynamic representation is not only possible in Discovery Intelligence.
It is desirable.

But it must be implemented as:

## **a governed system of versioned representation profiles**

selected dynamically from an approved set based on task and input conditions,
evaluated scientifically across reusable subsets,
and updated iteratively through explicit promotion rules.

That is the practical way to make representation dynamic without making the system chaotic.

## One-Line Summary

Discovery Intelligence should implement dynamic representation as a **versioned family of approved representation profiles** chosen at runtime by a representation router based on task and input quality, evaluated across reusable subsets and cohorts, and updated iteratively through governed promotion rules rather than uncontrolled adaptation.
