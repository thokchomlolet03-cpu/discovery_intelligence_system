# Governed Candidate and Evidence Exchange

## Purpose
This document defines the long-term design of the Discovery Intelligence public-facing publication and testing surface.

This page is not intended to be:
- a generic results feed
- a popularity board
- a leaderboard
- a social layer
- a place where visibility implies truth
- a place where engagement directly updates the core system

Instead, it is intended to be:

**a governed scientific candidate, testing, and evidence-exchange surface**

Its role is to:
- publish bounded, test-worthy candidates and claims
- make uncertainty and evidence visible
- invite structured scientific engagement
- allow scientists and labs to submit testing outcomes or relevant evidence
- feed new evidence into Discovery Intelligence in a governed way
- support belief updating and broader scientific state evolution
- avoid letting popularity, repetition, or casual activity act as epistemic strength

This document explains:
- why this page should exist
- what kinds of items belong on it
- what publication states should exist
- what users should be able to do
- what labs and scientists should be able to submit
- what role the LLM should play
- what should and should not update when new evidence arrives
- how this page contributes to long-term improvement without corrupting the system

## Status
This is a forward-looking publication-surface and governed-evidence-exchange specification for Discovery Intelligence.

It defines the intended long-term design boundary for how bounded scientific opportunities, external testing, and structured evidence intake should be exposed outside the internal workbench.

It does not mean the live product already implements a public candidate exchange, external testing intake flow, publication-state contract, or LLM-assisted publication screening layer. This document should be read as design intent and future implementation guidance.

# Core Position

Discovery Intelligence should include a separate page that exposes bounded scientific opportunities to external users, scientists, labs, and serious domain participants.

However, that page must not be designed as:
- a popularity-driven engagement surface
- a latest discoveries page in the sense of validated truth
- a direct self-learning update loop
- a mechanism where visibility or attention changes epistemic status

Instead, it should be designed as:

# **a governed candidate and evidence exchange**

This means:
- promising candidates can be published
- uncertainty remains visible
- contradiction remains visible
- labs can test or respond
- evidence can come back into the system
- the system's beliefs can update
- broader or deeper core influence must still go through explicit promotion rules

# Why This Page Should Exist

A serious discovery system should not remain closed.

If Discovery Intelligence only scores, ranks, and stores internal state but never reaches:
- scientists
- labs
- domain experts
- external testers
- real-world contradiction and replication

then the system will have less contact with reality than it should.

This page exists because high-quality engagement can provide:
- external validation
- external contradiction
- replication
- context correction
- assay-specific interpretation
- new structured evidence
- real-world feedback loops

These are valuable.

But they are valuable only if they are governed correctly.

# The Main Principle

# Engagement should increase evidence flow, not epistemic authority.

This is one of the most important principles of the entire page.

The page should absolutely help the system gather:
- more relevant testing
- more real-world evidence
- more lab outcomes
- more contradiction
- more context-sensitive correction

But the page must never assume that:
- views
- clicks
- comments
- repeated mentions
- popularity
- excitement
- activity volume

increase scientific trust.

This page exists to improve **contact with reality**, not to reward attention.

# What This Page Is

This page is:

- a publication surface for bounded scientific opportunities
- a testing invitation surface
- a structured evidence intake surface
- a candidate inspection surface
- a governed feedback loop
- a bridge between DI outputs and real-world testing

It is not:

- a final truth page
- a self-updating scientific authority
- a community forum where volume implies correctness
- a place where the LLM curates truth
- a page where published items automatically become core knowledge

# Naming and Identity

This page should not be framed as a simple Results page.

That language is too strong and too ambiguous.

The better long-term identity is:

# **Governed Candidate and Evidence Exchange**

Alternative acceptable names:
- Scientific Opportunity Board
- Governed Testing and Evidence Exchange
- Candidate Publication and Testing Exchange
- Governed Scientific Opportunity Exchange

The key reason for this naming is that the page should communicate:
- boundedness
- uncertainty
- opportunity
- testing
- evidence exchange
- governance

and not:
- finality
- authority
- validation
- certainty

# What Should Be Published

The page should publish items such as:

- bounded claims
- promising candidates
- test-worthy opportunities
- externally relevant signals
- context-limited but interesting findings
- externally testable hypotheses
- evidence-backed but not fully settled opportunities

Each published item should be treated as:
- worth seeing
- worth interrogating
- possibly worth testing

But not automatically:
- true
- promoted
- broadly reusable
- core-worthy

# Publication States

One of the most important parts of the page is explicit publication state.

Every item should visibly carry a publication and governance status.

Recommended states include:

## 1. Internal only
The item exists inside DI but is not suitable for publication.

Possible reasons:
- too weak
- too incomplete
- too underdetermined
- too noisy
- duplicate-like
- not relevant enough
- missing required provenance or context

## 2. Publishable candidate
The item is suitable to appear on the page as a bounded candidate or test-worthy opportunity.

This does **not** mean:
- true
- validated
- promotable

It means:
- worth external visibility
- suitable for bounded scientific engagement

## 3. Published with caution
The item is visible, but the system wants to make clear that:
- support is weak
- contradiction exists
- provenance is incomplete
- representation is thin
- the item is fragile or context-limited

## 4. Externally unvalidated
The item is published, but no external lab or test confirmation has yet been received.

## 5. Externally tested
At least one structured external test submission has been received.

This should not automatically imply strong truth.
It simply means:
- external evidence now exists

## 6. Contradictory external feedback present
At least one external submission conflicts with the current support direction or interpretation.

Contradiction should be visible, not hidden.

## 7. Under governance review
The item has publication visibility but is also being actively reviewed at a governance layer.

## 8. Not eligible for broader promotion
The item may be visible and even useful locally, but it is not eligible for broader carryover or deeper promotion.

## 9. Candidate for governed promotion
The item is not yet promoted, but current evidence and review posture suggest it may deserve stronger governed consideration.

These states should be visible so users do not collapse:
- visible
- trusted
- core-worthy

# Publication Reason vs Promotion Reason

This distinction is essential.

The page should explicitly distinguish:

## Publication reason
Why is the item visible here?

Examples:
- test-worthy opportunity
- bounded but promising signal
- relevant to likely lab domains
- contradiction needs resolution
- externally useful to inspect

## Promotion reason
Why might or might not this item deserve broader governed influence?

Examples:
- stronger governed support
- repeated independent evidence
- contradiction resistance
- strong provenance
- governance approval
- not eligible due to weak provenance or conflict

A candidate can be publishable without being promotable.

This distinction must remain explicit.

# Local Relevance vs Broader Relevance

External participants may find something relevant in a very local context.

That is valuable, but it should not be confused with broad scientific generalization.

The page should support distinctions like:

- relevant in a narrow assay or context
- local domain relevance only
- broader relevance unknown
- broader relevance under review
- context-limited result
- broader carryover blocked
- broader carryover candidate

This allows the system to preserve useful domain-specific feedback without overstating generality.

# Contradiction Must Be Visible by Default

This is a crucial principle.

If a published candidate has:
- supporting evidence
- conflicting evidence
- contradictory external results
- mixed provenance
- uncertain context alignment

the page should show that.

The page should not act like a showcase of only clean optimism.

A scientific exchange surface should reveal:
- where uncertainty remains
- where contradiction exists
- where more testing is needed
- where support is fragile
- where context mismatch may exist

Contradiction is not a problem to hide.
It is part of the value of the page.

# What Every Published Item Should Show

Every item should include a compact but useful scientific summary.

Recommended fields:

- candidate ID
- bounded claim or candidate statement
- current publication state
- publication reason
- promotion reason, if relevant
- domain or scientific area
- why it is interesting
- what evidence supports it
- what remains weak
- contradiction pressure, if any
- trust and provenance posture
- whether it is externally validated or not
- what type of lab or test would help most
- local vs broader relevance posture
- current broader carryover posture
- whether broader promotion is blocked or under review

This makes the page genuinely useful and scientifically legible.

# Why This Is Published Block

This should be a first-class element of every item.

The page should answer:

# Why is this item visible?

This block may include:
- why the system surfaced it
- what kind of signal made it interesting
- whether it is an opportunity, contradiction, or fragile signal
- what domain it may matter to
- why external testing would help

This transforms the page from a passive feed into:
# an explicit invitation to interact with bounded uncertainty

# What Would Help Most Block

This is one of the highest-value features on the page.

Every published item should answer:

# What kind of external input would most reduce uncertainty here?

Examples:
- replication under the same assay
- contradiction resolution
- stronger provenance
- method clarification
- broader context testing
- missing metadata
- stronger measurement quality
- independent lab confirmation

This gives scientists and labs a very clear reason to engage constructively.

Instead of just saying:
- interesting result

the system says:
- this is the exact kind of evidence that would make this much more useful

That is excellent.

# Types of External Submission

Not all incoming material is the same.

The page should explicitly distinguish three different submission types.

## 1. New evidence submission
This is a new piece of evidence such as:
- lab result
- assay result
- measurement
- dataset-linked evidence
- publication-linked evidence
- structured experimental outcome

## 2. Validation and contradiction submission
A lab or scientist says:
- we tested this and support it
- we tested this and obtained a conflicting result

This should be modeled separately because it has a direct relationship to a published item.

## 3. Commentary and interpretation submission
A domain expert may say:
- this is relevant to our domain
- this grouping may be wrong
- the assay context changes interpretation
- this contradiction may actually be context mismatch
- this should be bounded differently

This is useful, but it should not be treated as raw experimental evidence.

These types should not all use the same trust logic.

# Structured External Testing Intake

External submissions should not be only free-text comments.

That would be too weak, too noisy, and too hard to govern later.

The page should require structured fields such as:

- target published item or candidate ID
- submitting lab or organization identity
- submitter role or reviewer identity if appropriate
- evidence type
- method or assay type
- domain or context
- outcome type
- confidence or quality indicator
- provenance or linked artifact
- whether the result supports, weakens, or contradicts the current item
- optional narrative note

This structure is necessary for:
- comparability
- filtering
- contradiction analysis
- auditability
- future governed updates

# Anti-Popularity Doctrine

This page should explicitly reject the logic of social engagement as epistemic strength.

The product doctrine should include something like:

> Visibility, clicks, views, comments, repeated discussion, or submission volume do not increase scientific trust or promotion status.

This is a critical long-term rule.

Because once the page exists, there will be a temptation to treat:
- visible
- valuable
- true

That must be resisted at both:
- architectural level
- product language level

# Trust and Actionability Tiers for Publication

The page would benefit from bounded publication tiers.

For example:

## Tier A - Worth testing now
Characteristics:
- bounded enough
- useful enough
- test-worthy
- meaningful next evidence is clear

## Tier B - Interesting but fragile
Characteristics:
- weak or mixed support
- contradiction exists
- context-limited
- published with caution

## Tier C - Observational signal only
Characteristics:
- visible for awareness
- not ready for serious testing recommendation
- useful mainly as a possible weak signal

These are product-facing publication and actionability tiers, not deep truth tiers.

They help users understand what kind of item they are looking at.

# Non-Publication Path

The page should not imply that everything worth computing is worth publishing.

There must be a clear internal non-publication path.

Items may remain:
- local-only
- internal-only
- under review
- incomplete for publication
- duplicate-like
- too weak
- too underspecified
- too provenance-poor

This keeps the system disciplined.

The publication page should be a subset, not the whole world.

# The Role of Labs and Scientists

The page should allow serious external actors to do several things.

## 1. Inspect
They can inspect the current item, its support, weaknesses, and what is needed next.

## 2. Test
They can test a candidate if relevant to their lab, instruments, domain, or assay.

## 3. Submit structured outcomes
They can send back:
- support
- contradiction
- context-limited result
- null result
- stronger evidence
- new measurement

## 4. Offer interpretation
They can provide bounded commentary if they have useful contextual understanding.

## 5. Express testing interest
They may not yet have results, but can indicate:
- we can test this
- this fits our domain
- we want more details
- we want to follow this candidate

This last path can become valuable later, but it must remain clearly separate from evidence submission.

# Interested Lab and Test Request Workflow

This is an optional but highly valuable addition.

A lab may want to say:
- we are interested in this item
- we can test this in our environment
- we want more methodological detail
- we want to receive updates

This is different from submitting actual evidence.

It should be handled separately so the system does not confuse:
- intent to test
- evidence from testing

This can improve long-term engagement while preserving scientific discipline.

# How This Page Improves the System

This page can improve Discovery Intelligence in the long term, but only through the right loop.

The correct loop is:

# Publication -> Testing -> Feedback -> Governed Update

That means:

## Step 1
DI publishes a bounded candidate or opportunity.

## Step 2
Scientists and labs inspect it.

## Step 3
Some test it or respond with structured evidence.

## Step 4
New evidence comes back into DI.

## Step 5
The system's scientific state updates:
- claims
- belief updates
- belief state
- support posture
- contradiction state
- trust and review posture
- broader carryover posture where appropriate

## Step 6
Only under stronger conditions does broader or deeper system learning occur.

This is excellent.

The dangerous loop would be:
- publish
- get attention
- treat attention as improvement
- update the core directly

That must not happen.

# What Should Update When New Results Arrive

This is one of the most important distinctions.

## Working scientific memory should update
When trustworthy external results arrive, DI should update:
- claims
- belief updates
- belief state
- support posture
- contradiction pressure
- trust and review posture
- broader carryover posture where appropriate

This is correct and desirable.

## Broader governed memory may update
Under stricter conditions, the system may update:
- broader reusable structures
- continuity posture
- session-family carryover posture
- stronger governed memory

## Deep core learning should update only rarely
The deeper core should not update just because one result looks good.

It should only update under much stronger conditions such as:
- repeated evidence
- independent support
- strong provenance
- contradiction resistance
- governance approval
- evaluation-supported usefulness
- versioned promotion

This distinction must remain explicit.

# LLM Role on This Page

The page is one of the strongest places to use an LLM, but only in a bounded, governed way.

The LLM should be used for:

## 1. Intake parsing
Read messy submissions and extract:
- target item
- evidence type
- method
- domain
- outcome
- provenance fields
- relevance to DI schema

## 2. Missing-field detection
Detect what is incomplete and ask follow-up questions.

## 3. Clarification
Help users provide the exact information the system requires.

## 4. Normalization
Convert messy human descriptions into structured DI-ready submission objects.

## 5. Summarization
Create clean, bounded summaries of submissions.

## 6. Criteria-based screening recommendation
Against DI-defined publication criteria, the LLM may recommend:
- publishable candidate
- publishable with caution
- internal only
- needs clarification
- duplicate-like
- route to governance review

But this recommendation must be:
# derived from DI criteria
not
# free LLM intuition

# What the LLM Must Not Do on This Page

The LLM must not:
- decide scientific truth
- decide broader promotion on its own
- decide whether something becomes core knowledge
- merge contradiction away because it sounds weak
- rank scientific importance by intuition
- publish something because it sounds impressive
- treat popularity as trust
- substitute for governance review

So the correct model is:

# **LLM-assisted governed publication**
not
# **LLM-curated scientific truth**

# Publication Criteria Contract

Discovery Intelligence should expose a publication criteria contract that the page uses.

This contract should define things like:
- minimum required fields
- accepted source classes
- provenance expectations
- duplicate handling rules
- contradiction handling rules
- local-only vs publication-eligible rules
- publication-with-caution rules
- governance-review-required rules
- external testing submission requirements

Then the LLM's role is:

> Given this submission and these criteria, extract, clarify, normalize, and recommend.

That is the correct architecture.

# Relationship Between Visibility and Core Learning

This must be stated clearly.

## Visibility does not imply:
- truth
- trust
- promotion
- broader carryover
- core learning

## Visibility can imply:
- scientific interest
- test-worthiness
- bounded opportunity
- need for external evidence
- possible relevance to a domain or lab

This distinction is one of the most important protections in the whole design.

# Product Language Principles

The page should use language like:
- candidate
- bounded claim
- test-worthy
- published with caution
- externally unvalidated
- contradictory external feedback present
- not eligible for broader promotion
- candidate for governed review
- local relevance
- broader relevance unknown
- what would help most

It should avoid language like:
- validated discovery
- proven result
- confirmed scientific truth
- final breakthrough
- trustworthy because many engaged
- automatically promoted

# Minimum Useful First Version

The first serious version of the page does not need to be huge.

A strong first version should include:

- published candidate list
- publication state for each item
- why published
- what would help most
- contradiction visibility
- structured external testing submission
- publication reason vs promotion reason
- internal-only vs public split
- LLM-assisted intake normalization
- governance review path

That is enough to make the page meaningful and useful.

# Long-Term Identity

Long term, this page can become one of the strongest parts of Discovery Intelligence's identity.

Not because it creates engagement in the ordinary internet sense, but because it creates:

- contact with real scientific testers
- contact with external contradiction
- bounded publication of interesting opportunities
- governed inflow of external evidence
- a disciplined bridge between DI and the real world

That is exactly the kind of page that can help DI improve over time without losing epistemic discipline.

# Final Position

The separate page is a strong long-term idea, but only if it is designed as a governed scientific candidate, testing, and evidence-exchange surface.

Its job is not to increase popularity.
Its job is to increase:
- contact with reality
- quality of evidence flow
- structured testing
- contradiction visibility
- scientifically useful engagement

The page should make uncertainty visible, invite the right kind of interaction, and ensure that all incoming evidence passes through governed intake and promotion paths.

# One-Line Summary

The long-term publication page for Discovery Intelligence should be a **governed candidate and evidence exchange** where bounded, test-worthy items are published with explicit uncertainty and publication states, structured external testing and evidence can be submitted, contradiction remains visible, LLMs assist only with intake and normalization under DI criteria, and engagement improves the system only by increasing evidence flow, not by acting as a signal of truth or importance.
