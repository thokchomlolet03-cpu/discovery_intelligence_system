# Trusted Evidence, Promotion Gates, and Anti-Poisoning Architecture

## Purpose
Discovery Intelligence is intended to be a scientifically disciplined, truth-seeking system, not a mass-participation platform optimized for volume, engagement, or consensus by repetition.

Because the system may eventually allow users to upload data, and because some uploaded information may later influence broader reuse or future learning pipelines, the system must be designed from the beginning to resist epistemic capture.

This document defines the formal principles and target architecture for:

- separating local user value from shared system influence
- preventing low-quality or manipulative data from steering the core
- ensuring that broader reuse and future learning candidacy depend on evidence quality, provenance, contradiction survival, and explicit governance rather than volume
- preserving scientific integrity as the system scales

## Status
This document is a philosophy and target-architecture reference for Discovery Intelligence. It describes the direction the system should follow and the kinds of semantics the architecture should support over time.

It does not mean every mechanism described here is already fully implemented. Where the live product is still bridge-state, heuristic, or only partially wired, this document should be read as design intent rather than a statement of complete runtime behavior.

## Core Principle
Discovery Intelligence must follow this rule:

> Information does not gain influence because it is numerous.  
> Information gains influence only because it is credible, traceable, relevant, and survives scrutiny.

This principle is foundational.

The system must never behave like a social platform where repetition, visibility, coordination, or engagement can overwhelm truth-seeking logic.

## Non-Goals
Discovery Intelligence is not intended to be:

- a democratic voting system for evidence
- a popularity-ranked knowledge platform
- a social feed of scientific claims
- a system where repeated uploads imply stronger truth
- a passive aggregator of user opinions
- a mass-input platform where raw volume affects shared scientific state

The system should be resistant to these failure modes by design.

## Problem Statement
Any system that allows user-provided data to influence shared state is vulnerable to several kinds of corruption:

- low-quality uploads
- incorrect or fabricated measurements
- unverifiable provenance
- biased uploads
- coordinated uploads from a common source
- repeated uploads that appear independent but are not
- bot-generated or systematically manipulated inputs
- domain-incompatible evidence being treated as comparable
- noisy or weak evidence being over-promoted into broader reuse

If these risks are not addressed from the beginning, the system may drift away from scientific integrity and toward influence by accumulation.

That would undermine the system’s core identity.

## Architectural Principle: Separate Local Value from Core Influence
Discovery Intelligence must separate two different loops.

### 1. Local usefulness loop
A user uploads data.  
The system provides value locally by:

- analyzing the data
- producing claims
- generating experimental suggestions
- updating local session state
- supporting local reasoning

This is desirable and should be easy.

### 2. Core influence loop
A subset of uploaded evidence may later be considered for:

- broader governed reuse
- cross-claim reuse
- cross-target reuse
- future learning candidacy
- eventual promotion into stronger system-level influence

This is dangerous and must be difficult.

These two loops must remain separate.

Raw local uploads must never directly alter broader system truth or future learning state.

## Foundational Design Rule
All uploaded evidence is local-only by default.

This means:

- an upload can be useful for the user or workspace
- an upload can affect local claims, local results, and local belief state
- an upload must not automatically affect broader governed reuse
- an upload must not automatically affect future learning candidacy
- an upload must not automatically alter any shared or generalized system state

This default protects the system from immediate poisoning.

## Evidence Trust Model
Discovery Intelligence should treat evidence as belonging to trust classes rather than as undifferentiated rows.

### Trust Class A: Governed trusted evidence
Evidence that is:

- provenance-rich
- quality-assessed
- contradiction-checked
- context-compatible
- explicitly approved for stronger governed reuse

This is the highest-trust class.

### Trust Class B: Candidate evidence
Evidence that is:

- potentially useful
- possibly promotable
- not yet strongly trusted
- under review or awaiting further validation
- not yet allowed to shape broader system state strongly

This is the intermediate class.

### Trust Class C: Local-only evidence
Evidence that is:

- useful for a user, workspace, or session
- not sufficiently validated for broader influence
- allowed to shape local reasoning only
- blocked from shared or generalized influence

This is the default class for uploads.

## Evidence Weighting Principle
Discovery Intelligence must not treat evidence count as evidence strength.

Volume has zero or near-zero epistemic weight.

This means:

- 1,000 weak uploads do not outweigh 1 strong, well-characterized result
- repeated submissions do not imply independent support
- coordination cannot substitute for quality
- comments, reactions, or frequency do not count as scientific truth signals
- duplicated or near-duplicated evidence does not accumulate linearly

What matters instead is:

- provenance
- quality
- independence
- context compatibility
- contradiction survival
- governance status

## Promotion Philosophy
Promotion into broader reuse or future learning candidacy must be:

- explicit
- rare
- auditable
- reversible
- quality-gated
- contradiction-aware

The system should prefer false negatives over false promotions.

In other words:

It is better to fail to promote some useful evidence than to pollute the broader system with weak or manipulated evidence.

## Promotion Gate Requirements
No evidence should move from local-only or candidate status into stronger governed reuse unless it passes explicit promotion gates.

A promotion candidate should carry a structured dossier including the following.

### 1. Provenance
The system should know, as far as possible:

- who produced the evidence
- what organization, lab, or workflow produced it
- whether the source is identifiable
- whether the origin is direct observation, derived interpretation, or extracted summary
- whether the evidence was uploaded manually, ingested from a trusted dataset, or generated through another process

Weak provenance should sharply reduce promotability.

### 2. Measurement quality
The system should capture whether the evidence is:

- confirmatory
- screening
- provisional
- noisy
- incomplete
- context-limited
- unit-compatible
- method-compatible

Higher-quality measurement basis should count more than raw count.

### 3. Context compatibility
The system should evaluate whether the evidence is compatible with:

- the same target context
- a comparable assay context
- a comparable measurement basis
- relevant unit interpretation
- appropriate scientific scope

Context mismatch should reduce or block broader promotion.

### 4. Independence
The system should distinguish:

- many independent observations
- many repeated records of the same underlying source

Support must not be over-weighted when dependence is hidden.

### 5. Contradiction survival
Promotion candidacy should depend on whether evidence has:

- survived weakening evidence
- remained coherent under mixed evidence
- remained stable after contradiction pressure
- avoided degradation into historical-only or weakly reusable status

Contradiction-heavy or degraded histories should reduce candidacy sharply.

### 6. Governed reuse posture
Evidence should not only be assessed for local usefulness but also for whether it is:

- local-only
- context-only
- selectively reusable
- broader governed reuse candidate
- contradiction-limited
- historical-only
- not suitable for stronger future promotion yet

## Evidence Source Taxonomy
The system should classify source types explicitly.

Possible source classes include:

- trusted benchmark dataset
- peer-reviewed or externally validated scientific dataset
- internal experimental result
- partner-lab result
- user-uploaded uncontrolled source
- extracted free-text scientific note
- AI-derived interpretation
- imported structured data with unknown origin

This classification should influence promotion candidacy and reuse posture.

## Promotion Workflow
The system should follow this flow.

### Step 1: Upload
Evidence enters the system as local-only.

### Step 2: Local use
The system may:

- analyze it
- derive local claims
- create local experiment requests
- update local support
- produce local belief state
- support local decision-making

### Step 3: Candidate evaluation
The system may mark some evidence or continuity histories as:

- candidate for broader governed reuse
- selective reuse candidate
- contradiction-limited candidate
- local-only but interesting
- context-only continuity

### Step 4: Governed review
Promotion into stronger reuse must require explicit governed review or governed acceptance rules.

### Step 5: Promotion outcome
The result may be:

- remain local-only
- remain context-only
- selective broader reuse allowed
- broader governed reuse candidate accepted
- blocked due to contradiction, weak provenance, weak context, or weak quality

### Step 6: Reversibility
If later evidence undermines the promoted evidence, the system must be able to:

- degrade it
- supersede it
- quarantine it
- reduce reuse posture
- remove it from stronger promotion candidacy

## Anti-Poisoning Rules
Discovery Intelligence should implement these rules from the start.

### Rule 1: Local by default
Every upload is local-only until proven otherwise.

### Rule 2: No direct core updates
No raw upload may directly alter broader governed system state.

### Rule 3: Promotion is explicit
Promotion into broader reuse or future learning candidacy must be explicit and reviewable.

### Rule 4: Repetition is not strength
Repeated similar uploads do not imply stronger truth unless independence is established.

### Rule 5: Contradiction reduces promotability
Contested or degraded histories should reduce or block broader promotion.

### Rule 6: Historical support is context, not silent authority
Historical evidence may remain visible but should not silently dominate current promotion or reuse.

### Rule 7: Provenance matters more than volume
Evidence without traceable provenance should be capped in influence.

### Rule 8: Quality outranks quantity
One strong, well-characterized result may deserve more governed weight than many weak uploads.

### Rule 9: Promotion must be auditable
The system must be able to answer:

- why was this evidence allowed broader influence?
- what conditions were satisfied?
- what contradictions or weaknesses were observed?
- what trust class does it belong to now?

### Rule 10: Promotion must remain reversible
If evidence later weakens, the system must be able to reduce its broader role.

## Required System Semantics
To support this anti-poisoning architecture, the system should be able to represent at minimum:

- local-only evidence
- context-only continuity
- selective broader reuse
- broader governed reuse candidate
- contradiction-limited candidacy
- degraded present posture
- historical-only relevance
- future learning candidacy posture
- promotion approval status
- promotion denial or block reason
- provenance confidence
- source class

These do not all need to be user-facing at once, but they should exist formally in the architecture.

## Relationship to Existing Architecture
This trust-and-promotion layer should build on the existing Discovery Intelligence architecture rather than replace it.

It should integrate with:

- claims
- experiment requests
- experiment results
- belief updates
- belief state
- support quality
- governed posture
- contradiction and degradation semantics
- local reuse
- broader governed reuse
- continuity-cluster promotion semantics

The anti-poisoning layer is therefore not separate from the scientific architecture.  
It is a higher-order control layer over how scientific state earns broader influence.

## Why This Matters for Discovery Intelligence
Discovery Intelligence is not supposed to become a social knowledge platform.  
It is supposed to become a scientifically disciplined system.

That means it must differ fundamentally from mass platforms.

### Mass platform logic

- more visibility -> more influence
- more repetition -> more perceived truth
- more activity -> more ranking power

### Discovery Intelligence logic

- better provenance -> more trust
- better quality -> more weight
- better contradiction survival -> more reuse
- better context compatibility -> more promotability
- explicit review -> broader influence

This distinction is essential.

## Future-Proofing
This architecture is especially important because the system may later support:

- user uploads at greater scale
- collaboration across workspaces
- broader governed reuse
- future learning promotion
- integration with stronger external models
- AI-assisted extraction from messy scientific inputs

Without strong trust tiers and promotion gates, those future capabilities would create serious corruption risk.

With them, the system can scale without abandoning epistemic discipline.

## Limits
This architecture does not yet provide:

- a full scientific trust stack
- a complete provenance verification infrastructure
- independent source authentication
- a full target-family ontology
- automatic fraud detection
- live learning or retraining
- a full evidence marketplace or peer-review ecosystem

It is a bounded architecture for resisting epistemic corruption from the beginning.

## Implementation Direction
Implementation should prioritize:

1. explicit trust tiers
2. source-class and provenance fields
3. local-only by default behavior
4. broader reuse candidacy posture
5. promotion approval and block semantics
6. contradiction-aware promotion discounting
7. reversible promotion state
8. compact product surfacing where useful
9. audit-friendly summaries
10. compatibility with future local-vs-core learning separation

Implementation should be performed in a coordinated way and should remain additive and compatibility-safe.

## One-Line Summary
Discovery Intelligence should be designed so that user-uploaded evidence is useful locally by default but only influences broader system state when it has earned that influence through provenance, quality, context compatibility, contradiction survival, and explicit governed promotion, never through raw volume.
