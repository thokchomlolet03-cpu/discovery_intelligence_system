# LLM Role and Interaction Boundary in Discovery Intelligence

## Purpose
This document defines the role of large language models (LLMs) inside Discovery Intelligence.

It exists to prevent architectural confusion.

Discovery Intelligence is being built as a truth-seeking, scientific, state-grounded, governance-aware system. Because LLMs are powerful and flexible, there is always a temptation to let them do too much. If that happens, the system can become smoother on the surface while becoming weaker scientifically.

This document defines:

- what the LLM is for
- what the LLM must not do
- how the LLM should interact with the deterministic Discovery Intelligence core
- how natural-language interaction should work
- how ambiguity should be handled
- how the LLM should be constrained so that it improves usability without weakening epistemic integrity

The goal is to make the LLM useful without letting it become the scientific authority.

## Status
This is a forward-looking AI-interface and interaction-boundary specification for Discovery Intelligence.

It defines the intended architectural role of LLMs relative to the deterministic Discovery Intelligence core.

It does not mean the live product already implements the full clarification layer, grounded response layer, interaction ledger, or supported-action protocol described below. This document should be read as boundary-setting design intent and future implementation guidance.

# Core Position

In Discovery Intelligence, the LLM is not the scientific brain.

It is the language and interaction layer between:

- vague human intention
- explicit machine-usable Discovery Intelligence actions

and between:

- structured Discovery Intelligence outputs
- natural but bounded human-readable explanation

This means the LLM has two valid roles:

## Role A - Human -> System translation
The LLM helps convert natural, vague, incomplete human language into structured Discovery Intelligence requests.

## Role B - System -> Human explanation
The LLM helps translate structured Discovery Intelligence outputs into clear, natural, scientific language.

That is the correct role.

# The Fundamental Boundary

## Discovery Intelligence core owns:
- scientific state
- claim state
- experiment-request state
- experiment-result state
- belief-update state
- belief-state state
- support quality
- contradiction and degradation logic
- trust tiers
- source class and provenance confidence
- review posture
- effective governance posture
- broader carryover posture
- promotion boundaries
- scenario simulation
- ranking and prioritization logic
- scientific explanation of record

## The LLM owns:
- intent interpretation
- ambiguity detection
- missing-information detection
- clarification questioning
- structured request formation
- natural-language explanation of DI outputs
- grounded summarization
- grounded follow-up suggestion generation

This separation is not optional.
It is constitutional.

# The Main Doctrine

## The LLM may reduce ambiguity, but it may never hide ambiguity.

This is one of the most important rules in the whole system.

If the user says something vague such as:
- "Why is this weaker now?"
- "Can this move forward?"
- "What if I add these?"
- "Show me the important change."
- "Why is this blocked?"

the LLM must not:
- pretend it fully understands
- silently guess what "this" means
- infer scientific details that were not provided
- choose an interpretation without exposing ambiguity

Instead, the LLM must:
1. extract what is already clear
2. detect what is missing
3. ask focused follow-up questions
4. continue until DI has enough structured information to act

That is the correct behavior.

# Why Discovery Intelligence Should Use an LLM At All

Humans and computers do not naturally communicate in the same way.

Humans often communicate with:
- ambiguity
- incomplete references
- implied goals
- soft language
- unclear object references
- under-specified requests

Computers require:
- explicit state
- explicit entities
- explicit action type
- explicit boundaries
- explicit conditions
- explicit required inputs

The LLM exists to bridge this gap.

It should help:
- users speak naturally
- the system remain explicit
- interaction feel modern
- the scientific core remain disciplined

The LLM is therefore a translation and clarification layer, not a reasoning substitute.

# The LLM Must Not Be the Scientific Authority

The LLM must not be used to decide or invent:

- scientific truth
- claim validity
- support quality
- contradiction pressure
- trust posture
- review posture
- carryover posture
- promotion status
- scenario outcomes
- ranking outcomes
- what broader influence should be allowed
- what evidence is scientifically valid
- what state the system is "probably" in

These belong to Discovery Intelligence.

Even if an LLM sounds scientifically plausible, that is not enough.

A plausible explanation is not the same as:
- system truth
- structured state
- recorded review posture
- deterministic scenario outcome
- governed scientific judgment

# What the LLM May Do

The LLM has a real and important role, but it must be narrow and deliberate.

## 1. Intent parsing
Understand what the user is trying to do.

Examples:
- explain a claim
- explain a block reason
- compare sessions
- inspect trust posture
- inspect contradiction
- run a bounded scenario
- generate a visual view
- inspect derived vs manual posture
- inspect governance inbox item

## 2. Entity extraction
Extract references such as:
- claim ID
- session ID
- result ID
- evidence ID
- carryover layer
- scenario target
- visualization type

## 3. Ambiguity detection
Recognize when the user has not provided enough information.

Examples:
- multiple possible claims are referenced
- "this" is ambiguous
- session not specified
- local vs broader effect not specified
- scenario mutation is unclear
- evidence being added is not identified

## 4. Clarification questioning
Ask minimal, focused, DI-relevant follow-up questions.

Examples:
- "Which session do you mean?"
- "Are you asking about local usefulness or broader carryover?"
- "Which claim should I inspect?"
- "Do you want to add evidence, compare sessions, or change review posture?"

## 5. Structured request formation
Convert clarified user intent into a machine-usable DI action.

## 6. Grounded natural-language explanation
Take structured DI outputs and present them in:
- clear
- natural
- bounded
- scientific language

## 7. Grounded summarization
Summarize DI results, diffs, or scenario outputs without adding new scientific content.

## 8. Grounded follow-up suggestions
Suggest the next valid system-supported questions or actions based on current DI state.

# What the LLM Must Not Do

The LLM must not:

## 1. Answer directly from its own memory in grounded DI mode
It must not use:
- general scientific memory
- prior unrelated conversation memory
- unsourced outside knowledge
- plausible interpolation

unless the system is explicitly in a different mode that allows external knowledge.

## 2. Fill scientific gaps silently
If information is missing, it must ask.
It must not invent:
- entity references
- scenario mutations
- evidence properties
- trust status
- carryover meaning
- governance rationale

## 3. Simulate outcomes by imagination
For any what-if question, the LLM must not directly guess the answer.
It must hand the structured hypothetical to the DI scenario engine.

## 4. Replace deterministic state with probabilistic prose
It must not translate:
- uncertain internal guesses

into

- authoritative natural language

## 5. Override DI
The LLM must never:
- change state directly
- substitute its own decision for DI logic
- choose the governing posture
- decide promotion or broader carryover
- silently reinterpret system state beyond what DI exposes

# The Two-Pass LLM Architecture

Discovery Intelligence should use the LLM in two distinct passes.

## Pass 1 - Pre-execution clarification layer
This happens before DI acts.

### Function
- read user message
- extract intent
- extract entities
- detect ambiguity
- ask for missing required information
- form structured DI request

### Output
A structured action request.

Example:

```json
{
  "intent": "explain_block_reason",
  "entity_type": "claim",
  "entity_id": "claim_42"
}
```

If the request is incomplete, the LLM should not produce final action JSON yet.
It should instead ask a clarification question.

---

## Pass 2 - Post-execution explanation layer

This happens after DI computes the answer.

### Function
- receive DI structured output
- explain it naturally
- summarize it clearly
- stay within DI facts
- avoid adding external scientific interpretation

### Output

A grounded natural-language explanation.

Example:

Claim 42 remains blocked because the current effective reviewed posture is manual block. The strongest reasons recorded in Discovery Intelligence are high contradiction pressure and weak provenance confidence. Local usefulness remains possible, but broader carryover is denied.

This is correct because it only restates DI output.

---

# Required Product Modes

The system should explicitly distinguish answer modes.

This helps users understand what kind of answer they are receiving.

## 1. Clarification mode

The LLM is still gathering the information DI needs.

Example:

I can help with that, but I need to know which session you mean.

## 2. Grounded DI answer mode

The answer is based only on current Discovery Intelligence state.

Example:

Grounded in current DI state: this session remains blocked for broader carryover because the effective reviewed posture is manual block and the continuity cluster remains contradiction-heavy.

## 3. Scenario result mode

The answer comes from the DI scenario engine after structured hypothetical simulation.

Example:

Scenario result from DI simulation: adding Result 18 strengthens local support, but broader carryover remains blocked because the session-family posture stays manually deferred.

## 4. Insufficient-state mode

The system cannot answer honestly from current DI state.

Example:

I do not have enough Discovery Intelligence context to answer that. Please specify which claim or session you want me to inspect.

These mode labels improve trust and reduce confusion.

---

# The Clarification Protocol

This protocol should be formalized.

For every user message, the LLM should conceptually produce:
- extracted intent
- extracted entities
- extracted scope
- confidence in interpretation
- missing required fields
- ambiguity flags
- next question if needed

This makes the LLM easier to:
- debug
- evaluate
- improve
- constrain

Example

User:

Why is this weaker now?

Possible internal interpretation result:

```json
{
  "intent_candidate": "explain_state_change",
  "entity_type": null,
  "entity_id": null,
  "scope": null,
  "interpretation_confidence": "low",
  "missing_required_fields": ["entity_type", "entity_id"],
  "ambiguity_flags": ["ambiguous_reference"],
  "next_question": "Are you asking about a claim, a session, a belief-state item, or broader carryover?"
}
```

This is much better than pretending to understand.

---

# Supported-Action Schema

The LLM should not assume the system can answer everything.

Discovery Intelligence should expose a finite set of supported actions.

Examples include:
- explain_claim
- explain_block_reason
- compare_sessions
- inspect_trust_path
- show_contradiction_summary
- show_derived_vs_manual_posture
- run_what_if
- generate_diagram
- summarize_governance_item
- inspect_carryover_posture
- list_next_actions

If a user asks for something outside the supported action set, the LLM should:
- clarify
- redirect
- say unsupported
- or route into a separate clearly labeled mode later

This prevents silent capability inflation.

---

# Natural Language Should Be Allowed, But Constrained

Users should be able to ask natural questions like:
- "Why is this blocked?"
- "What changed from the last session?"
- "If I add these results, what changes?"
- "Show me the contradiction here."
- "Can this move forward now?"
- "What is holding this back?"

This natural interaction is important because users are now used to interacting with systems conversationally.

However, the LLM should translate these into:
- supported intents
- structured inputs
- deterministic DI actions

The system should not become a free-form chatbot.

---

# Example Full Interaction Flow

User

Why is this session still blocked from broader carryover even though two claims look stronger?

LLM pre-execution role

Parses:
- intent: explain session carryover block
- target: session
- target ID: ask if not obvious
- scope: broader carryover

If needed, asks:

Which session do you mean?

DI execution

DI computes:
- derived posture
- manual posture
- effective posture
- contradiction and degradation context
- trust and provenance posture
- carryover effect summary

LLM post-execution role

Explains:

This session remains blocked from broader carryover because the current effective reviewed posture is manual block. The strongest reasons in current DI state are contradiction-heavy continuity and mixed provenance confidence. Two claims strengthened locally, but the higher-layer carryover boundary did not clear.

This is the ideal behavior.

---

# Bounded What-If Questions

The LLM should support what-if questions, but only through DI's deterministic scenario engine.

Allowed user behavior

The user may ask:
- "If I add these results, what changes?"
- "What if this evidence had stronger provenance?"
- "What if this claim were manually approved?"
- "What if broader carryover were blocked?"
- "What if we remove this contradictory result?"

Required system behavior

The LLM must:
1. extract the hypothetical mutation
2. detect missing fields
3. ask follow-up questions if required
4. pass a structured scenario request to DI
5. wait for DI simulation result
6. explain the DI diff naturally

Prohibited behavior

The LLM must not:
- guess scenario outcomes
- infer system changes from general intuition
- produce speculative simulation results on its own

---

# The "Nothing More, Nothing Less" Principle

This is one of the strongest principles for Discovery Intelligence.

When the LLM explains a DI result, it should answer:

nothing more, nothing less than what Discovery Intelligence state supports

That means:

It may include:
- DI-recorded reasons
- DI-recorded posture
- DI-computed diffs
- DI scenario output
- DI trust, review, and carryover fields
- DI grounded summaries

It must not include:
- external scientific facts unless separately sourced and labeled
- hidden model memory
- invented causal stories
- unsupported generalization
- extra interpretive claims not in DI state

This principle should be preserved everywhere.

---

# Good vs Bad LLM Behavior

Good

Claim 12 remains blocked because the current effective reviewed posture is manual block. Discovery Intelligence records contradiction-heavy support and weak provenance confidence as the strongest reasons.

Why good:
- grounded in DI
- explicit
- bounded
- scientific

Bad

Claim 12 is probably blocked because the science is not mature enough yet and the evidence may not generalize.

Why bad:
- "probably" is guessy
- "science is not mature enough" may not be a DI field
- "may not generalize" may be external inference
- too much added interpretation

---

# Required Refusal Behavior

The LLM must be allowed to refuse to answer when DI context is insufficient.

This is a sign of maturity, not weakness.

Examples:
- "I do not have enough Discovery Intelligence context to answer that."
- "That could refer to multiple claims. Please specify which one."
- "This hypothetical is too underspecified for DI to simulate."
- "Current DI state does not expose enough information for a grounded answer."

A system that refuses gracefully is better than one that hallucinates smoothly.

---

# Interaction Ledger

A strong addition to the architecture is an internal interaction ledger.

For each user interaction, the system should be able to record:
- raw user message
- extracted intent
- extracted entities
- ambiguity flags
- clarification questions asked
- final structured DI request
- DI output object
- final answer mode
- final user-facing response

This would help:
- debugging
- evaluation
- improvement of the LLM layer
- auditability
- future product refinement

This ledger should be treated as system instrumentation, not as scientific truth.

---

# Suggestion Chips and Guided Interaction

To keep the user experience natural without letting the LLM wander, the system should generate guided next-step suggestions.

Examples:
- Why is this blocked?
- Show contradiction path
- Compare with previous session
- What would make this promotable?
- Show derived vs reviewed posture
- Run what-if analysis
- Show trust ladder

These suggestions should come primarily from:
- DI-supported actions
- current state
- relevant objects
- current mode

The LLM may help phrase the suggestions, but the suggestions should remain DI-grounded.

---

# The LLM Should Not Become the Psychological Center of the Product

This is an important product risk.

Even if the architecture is correct, users may start to feel:
- "the chatbot is the system"

This is dangerous, because it creates pressure to let the LLM do more than it should.

To prevent that, the UI should make it clear that the LLM is:
- an interface to Discovery Intelligence
not
- the scientific source of truth

Ways to reinforce this:
- show linked DI objects
- show answer mode labels
- show references to claims, sessions, and review posture
- keep inspectability visible
- let users open the underlying structured state easily

The user should experience:
- a natural interface
to
- a structured scientific machine

---

# Recommended Technical Architecture

The architecture should be:

User language

↓

LLM clarification and intent layer
- parse intent
- extract entities
- detect missing structure
- ask focused follow-up questions
- produce structured DI action

↓

Discovery Intelligence execution layer
- explanation services
- comparison services
- scenario services
- governance services
- visualization payload services

↓

LLM grounded explanation layer
- rewrite structured DI output
- summarize naturally
- stay within DI content

↓

User response plus visual artifacts plus next supported actions

This architecture must remain stable.

---

# LLM Safety Policy in DI-Grounded Mode

Allowed
- understand user question
- ask clarification questions
- identify missing fields
- classify intent
- extract entities
- structure requests
- rewrite grounded answers
- summarize grounded outputs
- propose next valid DI-supported questions

Not allowed
- invent evidence
- infer scientific state from memory
- answer without DI execution when DI state is required
- create unsupported scenario outcomes
- override trust, review, or carryover logic
- silently choose ambiguous meanings
- expand DI output with extra scientific claims

This should be enforced by prompt, architecture, and product design.

---

# Recommended Implementation Strategy

Phase 1

Build deterministic DI interaction features first:
- why-this and why-not-this
- inspect trust and review posture
- compare sessions
- contradiction exploration
- bounded what-if scenario engine
- diagrams and visual payloads

Phase 2

Add the LLM as a strict intent and clarification layer:
- parse user language
- ask follow-up questions
- produce structured DI actions

Phase 3

Add the LLM as a grounded explanation layer:
- rewrite DI outputs naturally
- summarize scenario diffs
- explain results in scientific but bounded language

Phase 4

Evaluate and refine:
- where ambiguity occurs
- where users get confused
- where unsupported questions are common
- how clarification prompts can improve

This sequence keeps the core protected.

---

# Recommended Local Model Role

For Discovery Intelligence, the first LLM does not need to be large.
Its job is not to reason scientifically at frontier level.
Its job is to:
- parse intent
- ask clarification questions
- phrase grounded outputs

That means a small local model is appropriate, especially during early testing.

This keeps:
- cost low
- control high
- architecture disciplined

The model should remain local or tightly controlled unless a later deployment reason justifies otherwise.

---

# Final Position

The best use of an LLM in Discovery Intelligence is not as a scientific decision engine, but as a clarification-first interaction boundary between humans and the deterministic DI core.

The LLM should:
- understand what the user is trying to ask
- detect ambiguity
- request missing information
- form explicit DI-ready actions
- explain DI outputs naturally and scientifically

The LLM should not:
- invent scientific state
- guess missing scientific facts
- replace DI reasoning
- simulate outcomes on its own
- become the source of truth

This boundary is what lets Discovery Intelligence feel natural and modern while preserving the explicit, governed, truth-seeking architecture that makes the system worth building.

---

# One-Line Summary

In Discovery Intelligence, the LLM should serve as a human-to-system clarification layer and a system-to-human grounded explanation layer, while all scientific state, scientific judgment, governance, and scenario outcomes remain fully owned by the deterministic Discovery Intelligence core.
