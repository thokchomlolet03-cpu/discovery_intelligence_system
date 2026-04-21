# HOW_TO_READ_DISCOVERY_INTELLIGENCE_FIRST_BATTLEFIELD_CANON

## Purpose

This is the guided reading system for the first battlefield of Discovery Intelligence.

It is not just a canon list.
It is the operational way to use that canon so it changes:

- how you think
- how you design the system
- how you model evidence and uncertainty
- how you build the polymer/material discovery battlefield

The battlefield remains:

**A goal-directed polymer/material discovery system that interprets user-specified material requirements, asks clarifying questions when critical scientific constraints are missing, searches and organizes evidence, returns the best-supported material answer when current evidence is sufficient, and only requests additional data or experiments when the evidence is insufficient.**

### Status

This document is a guided reading and doctrine-construction program for the first battlefield.
It does not claim that the current bridge-state Discovery Intelligence runtime already implements the full polymer/material discovery architecture described here.

The live system remains operationally centered on:

- upload
- analyze
- score
- rank
- review
- dashboard

But this guide exists to help build the first real battlefield systematically.

---

# GUIDED READING SYSTEM FOR DISCOVERY_INTELLIGENCE_FIRST_BATTLEFIELD_LIFETIME_CANON

## What this guide is for

You are not reading to finish books.

You are reading to build the first battlefield of Discovery Intelligence:

**a goal-directed polymer/material discovery system that interprets user-specified material requirements, asks clarifying questions when critical scientific constraints are missing, searches and organizes evidence, returns the best-supported material answer when current evidence is sufficient, and only requests additional data or experiments when the evidence is insufficient.**

So every resource must do one of four jobs:

1. shape your mind
2. shape the system
3. shape the domain understanding
4. solve the current bottleneck

---

# PART 1 — HOW TO READ

## Rule 1: Read in four modes

### 1. Foundation reading

For books that change how you think.

How to read:

- slow
- handwritten or high-quality notes
- few pages per session
- stop often and reflect

Use this for:

- Deutsch
- Popper
- Pearl
- Spiegelhalter

### 2. Operational reading

For books and docs that should immediately affect the codebase.

How to read:

- keep the code open
- read one section
- apply one thing
- write one DI note

Use this for:

- DDIA
- Fluent Python
- Architecture Patterns with Python
- FastAPI docs
- SQLAlchemy docs
- RDKit docs

### 3. Reference reading

For deeper technical works you revisit when the system reaches a specific problem.

How to read:

- do not force cover-to-cover first
- read targeted chapters
- return later

Use this for:

- Causality
- Jaynes
- Murphy
- Bayesian Data Analysis
- polymer textbooks

### 4. Live literature reading

For papers, standards, and current sources tied to the active bottleneck.

How to read:

- selective
- problem-driven
- tied to current implementation

Use this for:

- active learning papers
- materials informatics
- packaging science
- OECD standards
- RDKit examples
- retrieval papers

---

## Rule 2: Every reading session must produce a DI note

Use this template every time:

### Source

Book / chapter / paper / standard / doc

### Core idea

What is the main truth here?

### Why it matters for DI

What does this change in the first battlefield?

### DI implications

What changes in:

- goal intake
- clarification logic
- structured requirements
- evidence retrieval
- claim formation
- contradiction
- belief revision
- answer-if-sufficient logic
- unknown detection
- experiment request

### Immediate action

What should change now in:

- doctrine
- code
- schema
- prompt
- architecture
- reading priorities

### Open questions

What remains unclear?

Without this, reading stays passive.

---

## Rule 3: Never read the whole canon at once

At any given time, keep only these active:

- 1 epistemology/philosophy book
- 1 probability/statistics/ML book
- 1 architecture/software book
- 1 domain science source
- 1 live paper/standard stream

That is enough.

---

# PART 2 — THE PHASES

---

## PHASE A — BUILD THE MIND OF DISCOVERY

### Goal of this phase

Make sure DI never collapses into:

- ranking only
- prediction only
- dashboarding only
- answer generation without epistemic discipline

### Read in this order

#### A1. The Beginning of Infinity — David Deutsch

Verified link:
[Official site / book page](https://www.thebeginningofinfinity.com/)

Why first:

- explanation over prediction
- error correction
- progress through knowledge growth

What to extract:

- What counts as a good explanation in DI?
- Why DI must not become a mere recommender
- Why criticism is a growth mechanism

Output:

- `DI_EXPLANATION_DOCTRINE.md`

How to read:

- 10–20 pages per session
- after each session, write:
- one idea about explanation
- one idea about error correction
- one consequence for DI

#### A2. Conjectures and Refutations — Karl Popper

Verified link:
[Routledge book page](https://www.routledge.com/Conjectures-and-Refutations-The-Growth-of-Scientific-Knowledge/Popper/p/book/9780415285940)

Why second:

- claims
- criticism
- refutation
- scientific growth through challenge

What to extract:

- What is a claim in DI?
- Why contradiction is necessary
- Why criticism is not failure

Output:

- `DI_CLAIM_DOCTRINE.md`
- `DI_CONTRADICTION_DOCTRINE.md`

How to read:

- do not read as abstract philosophy
- map each chapter into:
- claim
- criticism
- refutation
- growth

#### A3. The Book of Why — Judea Pearl, Dana Mackenzie

Verified link:
[Pearl book page](https://bayes.cs.ucla.edu/WHY/)

Why third:

Your first battlefield is not just what material correlates with property X.
It is:

- what should be used
- under what conditions
- what is still unknown
- what next evidence matters

That requires moving beyond association.

What to extract:

- association vs intervention
- what DI can and cannot claim causally
- why experiments are not just data collection

Output:

- `DI_CAUSALITY_BOUNDARY.md`

How to read:

After each major section, ask:

- what kind of causal reasoning belongs in the first battlefield now?
- what must wait until later?

#### A4. The Art of Statistics — David Spiegelhalter

Use a legal publisher or library edition.

Why fourth:

- evidence
- uncertainty
- confidence boundaries
- best-supported answer vs weak evidence

What to extract:

- What does sufficient evidence mean?
- How should DI express uncertainty?
- What should never be hidden?

Output:

- `DI_UNCERTAINTY_DOCTRINE.md`

#### A5. The Logic of Scientific Discovery — Karl Popper

Use a legal publisher or library edition.

Why fifth:

- testability
- scientific risk
- falsifiability
- when DI should answer vs defer

Output:

- refine `DI_CLAIM_DOCTRINE.md`
- refine `DI_EXPERIMENT_DOCTRINE.md`

---

## PHASE B — BUILD UNCERTAINTY, INFERENCE, AND BELIEF

### Goal of this phase

Prevent DI from being naive about evidence and belief.

### Read in this order

#### B1. Introduction to Probability — Blitzstein & Hwang

Verified link:
[Harvard Stat 110 / book reference](https://projects.iq.harvard.edu/stat110)

Why first:

- uncertainty
- conditional reasoning
- dependence
- evidence effects

What to extract:

- what changes belief
- what does not
- what conditional dependence means for evidence

Output:

- `DI_PROBABILITY_INTUITION_NOTES.md`

#### B2. All of Statistics — Larry Wasserman

Use a legal edition.

Why second:

- weak evidence vs strong evidence
- uncertainty intervals
- inference logic
- data quality implications

Output:

- `DI_EVIDENCE_SUFFICIENCY_DOCTRINE.md`

#### B3. Statistical Rethinking — Richard McElreath

Use a legal edition.

Why third:

- model assumptions
- uncertainty overconfidence
- belief movement under ambiguity

Output:

- refine `DI_BELIEF_REVISION_DOCTRINE.md`

#### B4. Probability Theory: The Logic of Science — E. T. Jaynes

Use as reference, not as a first-pass linear read.

Why now:

This is for long-term epistemic architecture, not quick implementation.

Output:

- `DI_LONG_TERM_BELIEF_ARCHITECTURE.md`

#### B5. Bayesian Data Analysis — Gelman et al.

Later-stage reference.

Use when:

- belief revision becomes more formal
- uncertainty aggregation becomes a bottleneck

---

## PHASE C — BUILD THE COMPUTATIONAL CORE

### Goal of this phase

Understand what modeling can do for DI and where it must stop.

### Read in this order

#### C1. Pattern Recognition and Machine Learning — Christopher Bishop

Verified link:
[Springer book page](https://link.springer.com/book/10.1007/978-0-387-45528-0)

Why first:

- predictive models
- probabilistic modeling
- uncertainty in modeling
- model limitations

Output:

- `DI_MODELING_BOUNDARIES.md`

#### C2. Deep Learning — Goodfellow, Bengio, Courville

Verified link:
[Official free online book](https://www.deeplearningbook.org/)

Why second:

- representation learning
- when deep learning helps
- when it is overkill
- where DI should remain symbolic or structured

Output:

- `DI_NEURAL_BOUNDARY_DOCTRINE.md`

#### C3. Probabilistic Machine Learning: An Introduction — Kevin Murphy

Use a legal edition.

Why third:

- probability
- modeling
- decision ideas

Output:

- refine `DI_MODELING_BOUNDARIES.md`
- refine `DI_BELIEF_REVISION_DOCTRINE.md`

#### C4. Interpretable Machine Learning — Christoph Molnar

Verified link:
[Official online book](https://christophm.github.io/interpretable-ml-book/)

Why fourth:

DI must justify, not only output.

Output:

- `DI_MODEL_EXPLANATION_POLICY.md`

#### C5. Data Science for Business — Provost & Fawcett

Use as a cautionary bridge, not a final worldview.

Why:

This helps clarify what ordinary data systems do, so DI can go beyond them.

---

## PHASE D — BUILD SEARCH, EXPERIMENT SELECTION, AND ACTIVE DISCOVERY

### Goal of this phase

Turn DI from a static model system into a search-and-next-step system.

### Read in this order

#### D1. The Algorithm Design Manual — Steven Skiena

Use a legal edition.

What to extract:

- search-space thinking
- combinatorial discipline
- practical algorithmic reasoning

Output:

- `DI_SEARCH_SPACE_NOTES.md`

#### D2. Reinforcement Learning: An Introduction — Sutton & Barto

Use the official or author-hosted version if available legally.

What to extract:

- exploration vs exploitation
- sequential choice
- why next-step selection is hard

Output:

- `DI_EXPLORATION_EXPLOITATION_DOCTRINE.md`

#### D3. Burr Settles — Active Learning / survey

Verified link:
[Free survey PDF](https://burrsettles.com/pub/settles.activelearning.pdf)

Why this is critical:

Your first battlefield explicitly needs:

- answer if sufficient
- ask for more data or experiment only if insufficient

That is active-learning territory.

Output:

- `DI_ASK_FOR_MORE_ONLY_IF_NEEDED.md`

#### D4. Gaussian Processes / Bayesian Optimization resources

Use legal editions or tutorials.

What to extract:

- surrogate reasoning
- expensive-query selection
- uncertainty-aware experiment choice

Output:

- `DI_EXPERIMENT_SELECTION_LONG_TERM.md`

#### D5. Bandits and multi-objective optimization

Use later, when experiment choice becomes more mature.

---

## PHASE E — BUILD SCIENTIFIC MEMORY, RETRIEVAL, AND STRUCTURE

### Goal of this phase

Make DI a structured scientific memory, not a bag of outputs.

### Read in this order

#### E1. Introduction to Information Retrieval — Manning, Raghavan, Schütze

Verified link:
[Cambridge / Stanford reference page](https://nlp.stanford.edu/IR-book/)

What to extract:

- retrieval quality
- evidence lookup
- indexing
- ranking vs relevance
- search evaluation

Output:

- `DI_EVIDENCE_RETRIEVAL_DOCTRINE.md`

#### E2. Knowledge Graphs — Kejriwal, Knoblock, Szekely

Use a legal edition.

What to extract:

- graph-structured scientific memory
- explicit relations
- typed nodes and edges
- why scientific state should not be flattened

Output:

- `DI_SCIENTIFIC_MEMORY_GRAPH.md`

#### E3. Graph Representation Learning — William Hamilton

Use the author or publisher page or a legal edition.

What to extract:

- relational learning
- graph embeddings
- where graph learning might later help DI

Output:

- `DI_GRAPH_LEARNING_BOUNDARY.md`

#### E4. Ontology / logic / probabilistic graphical models

Reference phase.

What to build from this:

- claim ontology
- evidence ontology
- contradiction ontology
- belief-state precision

---

## PHASE F — BUILD THE SOFTWARE ARCHITECTURE

### Goal of this phase

Make DI durable enough to survive growth.

### Read in this order

#### F1. Designing Data-Intensive Applications — Martin Kleppmann

Verified link:
[Official book site](https://dataintensive.net/)

Why this is one of the most important:

DI is fundamentally a scientific-state system.

What to extract:

- truth boundaries
- storage
- consistency
- state transition discipline
- provenance implications

Output:

- `DI_DATA_AND_STATE_DOCTRINE.md`

#### F2. Architecture Patterns with Python — Percival & Gregory

Use a legal edition.

What to extract:

- repositories
- services
- domain objects
- boundaries

Output:

- `DI_DOMAIN_MODELING_NOTES.md`

#### F3. Fluent Python — Luciano Ramalho

Use a legal edition.

What to extract:

- Python depth
- language power
- implementation maturity

Output:

- `DI_PYTHON_IMPLEMENTATION_NOTES.md`

#### F4. Domain-Driven Design — Eric Evans

Use a legal edition.

What to extract:

- bounded contexts
- ubiquitous language
- domain object discipline

Output:

- refine `DI_DOMAIN_MODELING_NOTES.md`

#### F5. Refactoring — Martin Fowler

Use as continuous support, not a one-time read.

Output:

- `DI_REFACTORING_POLICY.md`

#### F6. FastAPI documentation

Verified link:
[Official FastAPI docs](https://fastapi.tiangolo.com/)

#### F7. RDKit documentation

Verified link:
[Official RDKit docs](https://www.rdkit.org/docs/)

Use both as operational reading, not passive reading.

---

## PHASE G — BUILD CONTACT WITH THE DOMAIN

### Goal of this phase

Make the first battlefield scientifically real.

### Read in this order

#### G1. RDKit docs and RDKit Book

Verified link:
[Official RDKit docs](https://www.rdkit.org/docs/)

What to extract:

- structure representation
- fingerprints
- descriptors
- substructures
- chemistry-aware operations

Output:

- `DI_MOLECULAR_REPRESENTATION_DOCTRINE.md`

#### G2. Polymer chemistry textbook

Legal edition.

What to extract:

- monomers
- copolymers
- polymer families
- network structures
- chemistry-to-property intuition

Output:

- `DI_POLYMER_CHEMISTRY_NOTES.md`

#### G3. Polymer physics textbook

Legal edition.

What to extract:

- chain behavior
- morphology
- glass transition
- swelling
- mechanical response
- diffusion

Output:

- `DI_POLYMER_PHYSICS_NOTES.md`

#### G4. Materials science foundational text

Legal edition.

What to extract:

- structure-property relationships
- transport
- interfaces
- durability
- failure modes

Output:

- `DI_MATERIALS_FOUNDATION_NOTES.md`

#### G5. Packaging materials science / transport / barrier behavior

Use papers and applied sources.

What to extract:

- wet-use constraints
- barrier requirements
- moisture behavior
- lifetime constraints
- application realism

Output:

- `DI_PACKAGING_AND_BARRIER_NOTES.md`

#### G6. Transient / stimuli-responsive / degradation literature

Use papers, reviews, and standards.

What to extract:

- trigger-dependent behavior
- transition under condition change
- functional lifetime
- what evidence counts

Output:

- `DI_TRANSIENT_MATERIALS_NOTES.md`

#### G7. OECD, PubChem, EPA CompTox, ECHA

Use as living evidence sources and standards.

Why:

These keep DI attached to real public scientific structure and assay reality.

Output:

- `DI_PUBLIC_EVIDENCE_SOURCES.md`

---

## PHASE H — BUILD THE INTERACTIVE LAYER CORRECTLY

### Goal of this phase

Make the LLM interface disciplined enough not to corrupt the scientific core.

### Read in this order

#### H1. Requirements elicitation / expert-system interaction

Use HCI and expert-system materials.

What to extract:

- how to ask precise questions
- how to detect missing information
- how to avoid vague interaction

Output:

- `DI_CLARIFYING_QUESTION_DOCTRINE.md`

#### H2. Dialogue design under uncertainty

Use HCI and dialogue-system materials.

What to extract:

- ask only what is necessary
- avoid conversational filler
- avoid hidden assumptions

Output:

- refine `DI_CLARIFYING_QUESTION_DOCTRINE.md`

#### H3. Structured extraction / tool orchestration / hallucination control

Use modern LLM engineering references and docs.

What to extract:

- LLM for orchestration only
- structured extraction
- no silent filling of critical scientific constraints

Output:

- `DI_SCIENTIFIC_CORE_VS_LLM_BOUNDARY.md`

---

# PART 3 — WEEKLY READING SYSTEM

## Daily structure

30 min — philosophy / epistemology

One of:

- Deutsch
- Popper
- Pearl
- Spiegelhalter

30 min — math / ML / uncertainty

One of:

- probability
- stats
- Bishop
- Murphy
- active learning

30 min — system / domain

One of:

- DDIA
- Python / architecture
- RDKit
- polymer/materials science
- standards

---

## Weekly structure

### 3 sessions

Normal reading plus DI notes

### 1 integration session

Ask:

- what changed in my understanding this week?
- what should change in DI because of it?
- what doctrine file needs an update?
- what implementation prompt becomes possible now?

### 1 battlefield reality session

Read:

- standards
- papers
- domain literature
- public datasets and sources

Purpose:

keep the system attached to the real battlefield

---

# PART 4 — WHAT TO READ NOW

If you want the best immediate stack, start with this exact set:

## Track 1 — worldview

- [The Beginning of Infinity](https://www.thebeginningofinfinity.com/)
- [Conjectures and Refutations](https://www.routledge.com/Conjectures-and-Refutations-The-Growth-of-Scientific-Knowledge/Popper/p/book/9780415285940)

## Track 2 — causality and evidence

- [The Book of Why](https://bayes.cs.ucla.edu/WHY/)
- The Art of Statistics

## Track 3 — uncertainty

- [Introduction to Probability](https://projects.iq.harvard.edu/stat110)

## Track 4 — systems

- [Designing Data-Intensive Applications](https://dataintensive.net/)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [RDKit docs](https://www.rdkit.org/docs/)

## Track 5 — modeling

- [Pattern Recognition and Machine Learning](https://link.springer.com/book/10.1007/978-0-387-45528-0)
- [Deep Learning](https://www.deeplearningbook.org/)

## Track 6 — experiment logic

- [Burr Settles’ active-learning survey](https://burrsettles.com/pub/settles.activelearning.pdf)

## Track 7 — domain

- RDKit docs again
- polymer and materials overview sources obtained legally
- OECD / PubChem / EPA / ECHA as ongoing sources

---

# PART 5 — THE GOLDEN RULE

At the end of every week, produce exactly these five outputs:

1. one DI doctrine update
2. one architecture insight
3. one domain insight
4. one open scientific question
5. one implementation consequence

If your reading does not produce those, you are reading too passively.

---

## Final doctrine

The canon should be read as a construction program, not as a bookshelf.

The correct sequence is:

- shape the mind
- shape uncertainty
- shape modeling
- shape search
- shape retrieval
- shape the architecture
- shape the domain grounding
- shape the interface discipline
- translate everything into DI doctrine and code

That is how to systematically read for the first battlefield.

If needed later, this guide can also be split into a separate operational reading document while keeping the main battlefield canon as the doctrinal reference.
