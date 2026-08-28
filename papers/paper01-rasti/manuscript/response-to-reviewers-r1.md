# SIMULATED INTERNAL REVIEW RESPONSE — NOT JOURNAL CORRESPONDENCE

# Response to the Editor and Reviewers — Major Revision, Round 1

**Target journal:** *RAS Techniques and Instruments* (RASTI)
**Manuscript:** *An Auditable Bayesian Fusion Framework for Deep Mineral Exploration Under Cover: Formulation, Component-Level Synthetic Evidence, and a Failed Joint Pilot*

This is a simulated Stage 4 working response, not correspondence from RASTI. The scientific, governance and literature-comparison corrections described below have been applied through a hash-bound revision chain. Residual nearest-neighbour scores and score-dependent novelty arguments were withdrawn in favour of an identity-verified discovery inventory plus a location-specific full-text recoding protocol. The corresponding author has confirmed the Funding and CRediT statements. Formal release remains blocked until the new candidate commit passes the separate human-verification gate, so this response is not an upload-ready cover letter.

## Overall response

We thank the Editor and Reviewers for identifying a mismatch between the original manuscript's framework-level framing and its component-level evidence. We chose the formulation/protocol route. The revised title, abstract, contribution statement, limitations and conclusion now consistently state that the manuscript reports a formulation, component-level Synthetic-run evidence and a failed joint pilot. It makes no claim of validated assembled fusion, exercised multi-scale behaviour, field validity or production-scale practicality.

The diagnostics implementation was also corrected and replayed. Non-finite and degenerate channels now fail closed; the Blom plotting position is aligned with the contract; the curated release suite reports 57 passing tests; 65 historical joint-chain files preserve their source hashes and remain `Failed -> Failed`; and all 42 post-hoc gate-ledger rows are exactly reconstructible from hashed per-run inputs. The generic algorithm-correctness asset was separately replayed under the corrected formula, and its four conservatively rounded manuscript values are unchanged.

## Editor / journal-fit comments

### REV-EIC-1 — Submission-facing narrative and production annotations

**Response:** Addressed in the editorial view. Section 8.4 was compressed to a short scientific motivation for the governance design, and three repetitive internal-audit paragraphs were removed from the anchored revision. A deterministic final clean render removes 617 block markers, 212 ARS evidence-note spans and 95 reference-pipeline notes without semantic edits. The underlying anchored manuscript remains available for audit.

**Locations:** §8.4; `manuscript/manuscript-clean.md`; `provenance/clean-render-report.json`.

### REV-EIC-2 — Consistent article identity and claim strength

**Response:** Addressed by selecting the narrower formulation/protocol identity. The title, abstract, introduction, limitations and conclusion now use one evidence ceiling. The multi-scale mechanism is explicitly design-only in this paper, and the failed joint pilot is not represented as an evaluation of assembled behaviour.

**Locations:** Title, Abstract, §1, §8.5 and §9.

### REV-EIC-3 — Repository fact and external audit route

**Response:** Addressed at release-candidate scope. The manuscript identifies the public repository at `https://github.com/xiaopengcug/GeoDeepBayes1.0.1`; the curated candidate contains the manuscript, evidence registry, replay bundle, figures, supplement and adopter checklist. The candidate branch may be pushed for inspection, but no formal tag, GitHub Release or DOI is claimed until human verification and explicit release authorization bind a full candidate commit SHA.

**Locations:** §8.5; Code and data availability; reproducibility supplement; revision evidence bundle.

### REV-EIC-4 — Funding and CRediT declarations

**Response:** Addressed from author-owned facts. The corresponding author confirmed that no specific grant was received and approved the CRediT allocation. Li Xiao Peng's `Writing – original draft` role is reconciled with the AI disclosure: AI tools assisted under his direction and review, he made substantive revisions, and he accepts responsibility for the manuscript; AI tools are not authors.

**Locations:** Funding; Author contributions.

## Reviewer 1

### REV-R1-2 — Same-kernel and nested-misspecification scope

**Response:** Addressed through claim narrowing rather than a new validation arm. The joint asset is now described as an implementation baseline. Same-kernel generation/inference, the nested injection and the absence of an independent-forward or non-nested discrepancy arm are explicit. No general structural-error or field-like robustness claim is made.

**Locations:** §6.4 and §8.5.

### REV-R1-3 — Weight operationalisation

**Response:** Addressed at the manuscript-definition level. Equation (3.9) is now the sole canonical definition. The pilot's historical additive-floor form is preserved as non-canonical provenance, not a co-equal definition; no controlled comparison was run, so no weight-sensitivity or robustness conclusion is drawn. Any future weighted asset must freeze Eq. (3.9) and register a separate sensitivity design.

**Location:** §3.5.

### REV-R1-4 — Diagnostics contract, non-finite handling and replay

**Response:** Addressed in code, tests and read-only replay. The rank-normalisation denominator now uses $(r-3/8)/(N+1/4)$. Non-finite inputs, non-finite derived diagnostics and finite zero-range channels fail closed with structured reasons; aggregation no longer discards them. The curated release suite reports 57 passing tests. Read-only replay of 65 historical joint chain files preserved all source hashes and yielded `Failed -> Failed = 65`, with `nonfinite_diagnostic = 65`. Degenerate-channel counts were one in 57 files, two in 3 files and six in 5 files. A separate replay of EVD-ALGO-002 retained all four manuscript values after conservative rounding.

**Locations:** §6.1 and §8.5; diagnostic replay evidence under `stage4-revision/evidence/`.

### REV-R1-5 — Post-hoc reconstruction provenance

**Response:** Addressed. The manuscript distinguishes post-hoc additive reconstruction from runtime-generated batch evidence. The lineage audit hashes metrics, run manifests and raw chains and exactly reconstructs 42/42 ledger rows, with no unbound run identifier. Future pilots must emit batch artefacts natively before endpoint evaluation.

**Location:** §7.5; `rev-r1-5-reconstruction-lineage.json`.

### REV-R1-6 — Coverage intervals

**Response:** Addressed. The revised text and Figure 5 map 358/400 to nominal 0.90 and 378/400 to nominal 0.95. Two-sided 95% Wilson intervals without continuity correction are [0.861, 0.921] and [0.918, 0.963]. Both include the corresponding nominal value. The text retains the same-truth frequentist, non-SBC boundary.

**Locations:** §7.2 and Figure 5.

## Reviewer 2

### REV-R2-1 — Full-text basis for the nearest-neighbour matrix

**Response:** Addressed through an explicitly authorised integrity-correction round. A post-apply scan found that the original roadmap had omitted the main score table and several score-dependent paragraphs, leaving them inconsistent with the `unknown` policy. Integrity patch r2 replaced all 36 identified blocks with one discovery-inventory and location-specific full-text recoding protocol. The §2.2 text now points to Table A.1, which assigns every unreviewed element cell `unknown`, computes no score or rank, and supports no closest-work, empty-combination, absence, priority or distinctiveness conclusion. The patch preserved 578/614 blocks byte-identically, changed no registered quantitative claim surface, and passed the continuous revision-bundle replay.

**Locations:** §2.2–§2.4, §8.3, limitations, self-reference disclosure and Appendix A; `integrity-correction-list-r2.json`; `integrity-patch-r2.apply-report.json`.

### REV-R2-2 — Chinese-language coverage

**Response:** Addressed as a targeted, auditable search rather than an exhaustive review. The audit records queries, date, source pages and unresolved records. It corrects the 2020 gravity–magnetic–MT record to Yan Zhengwen et al., 63(2):736–752, DOI 10.6038/cjg2020M0355; verifies related deterministic cross-gradient work; and records a relevant 2025 CSAMT–DC Bayesian application. A purported 2016 Bayesian MT–seismic record remains unresolved and is neither cited nor scored as negative evidence. The language-coverage limitation remains explicit.

**Locations:** §2 and §8.5; `analysis/chinese-literature-audit-r1.md`.

### REV-R2-4 — Mapping operators to the joint graph

**Response:** Addressed with Table 5a, immediately following Table 5. Each of the nine methods now has an observable and unit, property support, exercised/shared-latent status and evidence tier. Only gravity and magnetics exercised shared geometry and cross-gradient coupling in the failed joint pilot. Other shared nuisance and coupling combinations remain specification-only or `unknown`; petrophysical priors remain Hypothesis-tier.

**Location:** immediately after Table 4.

## Reviewer 3

### REV-R3-1 — Decision-interface workflow

**Response:** Addressed with a specification-only workflow table. It identifies the method lead, data steward, decision board and independent analyst; defines required inputs and outputs; and makes failed diagnostics, uncalibrated scores and missing provenance quarantine conditions. It contains no observed decision or resource claim.

**Location:** §5.

### REV-R3-2 — Environment baseline and compute boundary

**Response:** Addressed. The revision host is reported as Windows 10 Pro 10.0.19045, Intel Core i7-8850H, 31.8 GiB RAM, Python 3.11.9, NumPy 1.26.4, SciPy 1.17.1, pytest 9.0.3 and SimPEG 0.25.2. It is explicitly a reproducibility baseline, not a benchmark. No runtime, memory, acceleration, scaling or production-practicality value is claimed.

**Locations:** §8.5 and Code availability.

### REV-R3-4 — Adopter checklist and clean-environment replay

**Response:** Partially addressed. The supplement now provides minimum input/output/unit/provenance fields, component support boundaries, local regression and replay commands, expected statuses, licence boundaries and failure escalation. The local revision-host replay is complete. A clean-environment replay by an independent team has not been completed and is not claimed; it depends on an immutable paper-specific release.

**Locations:** Code and data availability; `supplement/reproducibility-and-adoption-checklist-r1.md`.

### REV-R3-5 — Field-transfer risk register

**Response:** Addressed. A four-domain register covers geology, survey, petrophysics and data governance, linking each gap to explicit entry evidence for EVD-FIELD-001. The Field-validated tier remains empty, and the text states that additional synthetic work cannot promote an asset into that tier.

**Location:** §8.6.

## Remaining author actions before submission

1. Supply and approve the Funding statement.
2. Supply and approve CRediT roles.
3. Decide and execute the paper-specific public release, or approve a final restricted-availability statement consistent with repository and licence facts.
4. If external reproducibility is to be claimed, complete a clean-environment replay against the immutable release and record its hashes and status.
