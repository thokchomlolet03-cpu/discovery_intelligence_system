# Discovery Intelligence Interaction Model and Dynamic Workbench Specification

## Purpose
This document defines the intended interaction style for Discovery Intelligence.

The current product has a structured scientific state and governance architecture, but its long-term value will not come only from static summaries, tables, and dashboards. The system should evolve toward a dynamic scientific workbench where users can inspect, question, compare, stress-test, and act on the system's current state.

This document explains:

- why a static interface is not enough
- what kind of interaction model Discovery Intelligence should adopt
- what kinds of dynamic features belong in the product
- how these features should be grounded in the existing scientific state
- what should be implemented now versus later
- how this interaction layer fits into the broader roadmap

## Status
This is a forward-looking interaction and product-architecture specification for Discovery Intelligence.

It describes the intended long-term workbench style that should sit on top of the system's explicit scientific and governance state.

It does not mean the live product already implements the full dynamic interaction layer described below. The current runtime remains centered on structured pages such as Upload, Discovery, Dashboard, Sessions, and comparison. This document should be read as design intent and sequencing guidance rather than as a statement that the full interaction model is already shipped.

## Core Position
Discovery Intelligence should not remain only a static report-viewing application.

It should evolve into:

**a structured, dynamic, state-grounded scientific workbench**

This means the system should eventually allow users to:

- ask why a result appears the way it does
- inspect the evidence and logic behind a posture
- compare current and historical state
- explore contradictions
- understand what is blocking broader carryover
- test bounded what-if scenarios
- interact with diagrams, trust ladders, and evidence maps
- take review and governance actions where appropriate

However, Discovery Intelligence should **not** become a generic chatbot or a free-form speculative assistant. The interaction model must remain grounded in explicit scientific state and governance structure.

## Why a Static Interface Is Not Enough
A static interface is useful for:

- showing a current result
- presenting summary state
- rendering tables and charts
- surfacing claims, support, and review posture

But a static interface is weak for:

- follow-up questioning
- causal explanation
- contradiction exploration
- sensitivity analysis
- what-would-change-if reasoning
- understanding the difference between local usefulness and broader influence
- helping users decide what to do next

Scientific users do not only need to **see** a result.
They need to **interrogate** it.

A discovery system should therefore support:

- explanation
- exploration
- comparison
- simulation
- governed action

## Interaction Philosophy
The product should move away from:

> "Here are the results."

and toward:

> "Here is what the system currently believes, why it believes it, what is weak, what is blocked, what could change, and what should happen next."

This is a major difference.

Discovery Intelligence should feel less like:

- a dashboard
- a report generator
- a static analytics page

and more like:

- a scientific reasoning partner
- a structured evidence workbench
- a governed decision-support environment

## The Key Design Rule
The dynamic interaction layer must be:

**state-aware, evidence-aware, and governance-aware**

This means the interaction layer should not invent answers from empty space.

Every answer should be grounded in existing system state such as:

- claims
- experiment requests
- experiment results
- belief updates
- belief state
- support quality
- contradiction/degradation
- trust tier
- source class
- provenance confidence
- derived review posture
- manual review posture
- effective current posture
- continuity-cluster posture
- session-family carryover posture

The interaction layer should be a way of exploring the existing machine, not escaping it.

## What Discovery Intelligence Should Become
The long-term interaction model should be a hybrid scientific workbench made of four parts:

### 1. Structured state surface
The user still needs stable surfaces such as:

- Discovery
- Dashboard
- Sessions
- comparisons
- claim summaries
- trust and review summaries
- charts and tables

These remain the stable visual anchors.

### 2. Dynamic reasoning panel
A persistent interaction surface where the user can ask:

- why
- why not
- what changed
- what is blocking this
- what supports this
- what would strengthen this
- what should happen next

This should be grounded in explicit state, not generic free chat.

### 3. Interactive explanatory artifacts
The system should be able to generate interactive artifacts such as:

- trust ladders
- contradiction maps
- claim-support graphs
- carryover maps
- session drift views
- derived-vs-manual comparison views
- evidence lineage views

These should be connected to real system objects.

### 4. Controlled action layer
The system should allow bounded user action where appropriate, such as:

- manual review actions
- drill-down inspection
- review queue triage
- governance decisions
- bounded scenario testing
- note-taking or pinning
- filtering by trust or carryover posture

## What the System Should Not Become
Discovery Intelligence should **not** become:

- a generic chatbot layered on top of the product
- a free-form AI speculation engine
- a dashboard filled with decorative charts
- a visualization-heavy interface with weak epistemic grounding
- a chat-first interface that ignores explicit scientific state
- a system where user questions are answered by vague model improvisation

The interaction layer must remain disciplined.

## Core Interaction Modes
The intended interaction model can be divided into several modes.

### 1. Explanation mode
The user asks:

- Why is this claim blocked?
- Why is this local-only?
- Why is this not promotable?
- Why did this session lose broader carryover?
- What evidence is making this contested?

This mode should explain the current state.

### 2. Comparison mode
The user asks:

- What changed from the previous session?
- How is this different from that?
- Where is the stronger evidence?
- What changed in reviewed posture?

This mode should compare states.

### 3. Diagnostic mode
The user asks:

- What is weak here?
- What contradiction is holding this back?
- What is degraded?
- What is historical-only?
- What is missing?

This mode should reveal structural weaknesses.

### 4. Action mode
The user asks:

- What should we test next?
- What review action makes sense?
- What would strengthen this claim?
- What remains useful locally if broader carryover is blocked?

This mode should support decision-making.

### 5. Visualization mode
The user asks:

- Show me the contradiction map
- Show me the trust ladder
- Show me the evidence lineage
- Show me the carryover path
- Show me the derived vs reviewed split

This mode should render visual explanations.

### 6. Scenario mode
The user asks:

- What if this evidence is added?
- What if this result is confirmed?
- What if this trust tier changes?
- What if broader carryover is blocked?
- What if this contradictory result is removed?

This mode should run bounded hypothetical analysis.

## High-Value Features
The following features appear especially valuable for the intended users of Discovery Intelligence.

### A. Why-this / Why-not-this
Allow the user to ask:

- Why is this ranked high?
- Why is this blocked?
- Why is this not promotable?
- Why is this local-only?
- Why did this lose to another candidate?

This should be one of the first dynamic interaction features.

### B. Minimal-change trigger
Allow the system to answer:

- What is the smallest thing that would change this result?
- What evidence would move this from contested to useful?
- What would make this promotable?

This helps users understand leverage.

### C. Evidence sensitivity map
Show which evidence is doing the most work in the current posture:

- strongest support drivers
- strongest contradiction drivers
- weakest but influential evidence
- fragile dependence points

### D. Contradiction explorer
Provide a dedicated interaction mode for:

- what exactly is conflicting
- whether the conflict is real or context mismatch
- what would resolve it

### E. Derived vs reviewed comparison
Show:

- derived machine posture
- manual reviewed posture
- effective current posture
- supersession history

### F. Promotion path explorer
Show:

- which gate is failing
- what is blocking broader promotion
- what would need to improve
- whether the problem is trust, contradiction, context, or history

### G. Session drift view
Show how posture changed over time:

- what became stronger
- what weakened
- what moved to historical-only
- what was downgraded
- what broader carryover changed

### H. Missing-information detector
Show:

- what information is missing
- why the system cannot answer more strongly
- what experiment or metadata would help most

### I. Experiment impact planner
Help answer:

- which next experiment reduces uncertainty most
- which one tests the most important contradiction
- which one has the largest posture impact

### J. Bounded what-if analysis
Allow structured scenario exploration without guesswork.

This feature should be one of the long-term anchors of the system.

## Bounded What-If Analysis
This feature deserves explicit treatment.

The system should allow questions such as:

- If I include these additional results, what changes?
- If this evidence had stronger provenance, what changes?
- If this contradictory evidence were weak, what changes?
- If this continuity cluster were quarantined, what changes?
- If this claim were manually approved, what broader carryover would open up?

However, the system must not answer by guessing.

It should answer by:

1. converting the user's hypothetical into a structured state mutation
2. applying the mutation to a temporary hypothetical state
3. rerunning relevant reasoning and governance services
4. comparing the hypothetical state to the current state
5. reporting:
   - what changed
   - what did not change
   - what assumptions were used
   - what remains uncertain

This keeps the feature scientific instead of speculative.

## Interactive Visual Artifacts
The dynamic workbench should eventually support interactive visuals such as:

### 1. Claim-support graph
A graph showing:

- the claim
- supporting evidence
- contradictory evidence
- current vs historical support
- review posture

### 2. Continuity / carryover map
A view showing:

- local-only continuity
- candidate continuity
- blocked carryover
- approved bounded carryover
- downgraded or quarantined paths

### 3. Trust ladder
A visual view of evidence moving through:

- local-only
- review candidate
- governed evidence
- broader carryover candidate
- blocked / deferred / downgraded / quarantined

### 4. Derived vs reviewed posture split
A comparison view between:

- computed posture
- manual posture
- effective posture
- supersession history

### 5. Session drift map
A visual timeline or state-drift view showing:

- support changes
- trust changes
- carryover changes
- review changes

These visuals should be explanatory, not decorative.

## Implementation Principle
The interaction layer should not be implemented as add chat.

It should be implemented as:

**a state-grounded interaction layer on top of the existing scientific state machine**

This means it should have four technical layers.

### 1. Scientific state layer
The current source of truth:

- claims
- results
- updates
- trust
- review
- carryover
- session summaries

### 2. Interaction intent layer
A structured interpretation of user requests, such as:

- explain_claim
- explain_block_reason
- compare_sessions
- show_contradictions
- run_what_if
- generate_diagram
- list_next_actions

### 3. Reasoning / transformation layer
Backend services that:

- answer explanations
- compute diffs
- run bounded scenarios
- produce visual payloads
- expose governance decisions

### 4. Presentation layer
UI surfaces such as:

- reasoning panel
- diagram container
- scenario editor
- explanation cards
- governance inbox
- drill-down controls

This should remain grounded in structured state.

## LLM Position
Discovery Intelligence does not need LLMs to implement the first serious version of this interaction model.

A strong first version can be built deterministically using:

- current structured state
- explicit reasoning services
- explicit diff services
- explanation templates
- diagram payload builders
- bounded scenario simulation

LLMs may later help with:

- natural-language query translation
- explanation polishing
- scenario clarification
- summary generation

But the core interaction and scenario behavior should come from the Discovery Intelligence state machine itself, not from model improvisation.

## Readiness Assessment
The current system is ready for a first bounded interaction layer because it already has:

- explicit scientific objects
- support semantics
- contradiction and degradation logic
- trust tiers
- review posture
- carryover posture
- manual override logic
- multi-layer governance

This means the system is ready for:

- deterministic explanations
- interactive inspection
- interactive visuals
- bounded scenario analysis
- governance workflow support

It is not yet appropriate to replace the product with an unconstrained chatbot.

## Recommended Sequencing
The correct sequence is:

### Implement now as specification
Write and preserve the interaction model formally.
This document exists for that purpose.

### Optional early implementation
Implement one small high-value feature such as:

- Why-this / Why-not-this explanation panel

### Do not implement the full dynamic interaction layer immediately
The full workbench should not displace the current sequence before the core and governance roadmap are mature enough.

### Continue the planned roadmap
Follow the main architecture sequence.

### Return to this specification after the next major strengthening wave
The full workbench should be implemented when the system is ready to support it properly.

## Current Recommendation
Discovery Intelligence should **not** fully implement the dynamic interaction layer immediately.

Instead, it should:

1. preserve this interaction vision formally
2. optionally implement one small explanation slice early
3. continue the current strategic roadmap
4. return to the broader dynamic workbench once the next core-strengthening phase is in place

This prevents the interface shell from racing too far ahead of the scientific engine.

## One-Line Summary
Discovery Intelligence should evolve into a dynamic, state-grounded scientific workbench where users can explain, inspect, compare, simulate, and govern results, but this should be implemented as a structured interaction layer over explicit scientific state, not as a generic chatbot, and it should be sequenced carefully so the interaction shell does not outrun the scientific core.
