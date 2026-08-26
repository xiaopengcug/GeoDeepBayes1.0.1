<!--block:B0001-->
# An Auditable Bayesian Fusion Framework for Deep Mineral Exploration Under Cover: Formulation, Component-Level Synthetic Evidence, and a Failed Joint Pilot

<!--block:B0653-->
**Li Xiao Peng¹\***, **Hu Xue Ping¹**, **Dong Jian¹**, **Chen Lei¹**, and **Ma Li Xin¹**

<!--block:B0654-->
¹ Shandong Provincial Geological Survey Institute

<!--block:B0655-->
\* Corresponding author: Li Xiao Peng, xiaopengcug@gmail.com; ORCID: https://orcid.org/0009-0002-1814-9447

<!--block:B0002-->
## Abstract

<!--block:B0003-->
Deep mineral exploration under cover requires evidence from geophysical methods that respond to different physical properties and may disagree. This paper specifies an auditable Bayesian fusion framework combining source-disciplined priors, a shared-error likelihood and pre-registered diagnostic governance over a multi-scale parameterisation. The assembled framework is not presented as a validated technique: the paper evaluates components separately. Nine forward operators pass a common synthetic protocol, a full-dimensional delayed-acceptance sampler satisfies its contract on a generic non-geophysical target, and reduced-order compatibility and open-data ingestion assets are reported with their registered limitations and failures. The gravity–magnetic joint synthetic pilot failed its diagnostics hard gate on every replicate, so its coupling endpoint has no valid evaluation point; the multi-scale mechanism was specified but not exercised. The contribution is therefore a formulation and protocol, component-level Synthetic-run evidence, and an auditable failed-pilot record. No assembled-performance, field-validity or production-scale claim is made.

<!--block:B0005-->
**Keywords:** Bayesian joint inversion; multi-physics data fusion; uncertainty quantification; mineral exploration under cover; pre-registered validation; reproducibility governance

<!--block:B0006-->
## 1 Introduction

<!--block:B0007-->
P1. Most of the mineral deposits that remain to be found in mature terrains do not reach the surface. They lie beneath transported cover (regolith, sediment, weathered rock) that carries no geochemical or geological expression of what is underneath it, and searching under that cover is the recognised frontier problem of the discipline (Dentith & Mudge, 2014; Malehmir et al., 2012; Korsch & Doublier, 2016). The difficulty is not that geophysics fails there but that no single method succeeds there: each responds to a different physical property, each is separately non-unique, and under cover the depth at which the target sits is precisely the depth at which each method's resolution is weakest (Dentith et al., 2018; Jiang et al., 2022; Wang et al., 2016). The practical consequence is that evidence about a covered target has to be assembled from several methods with discordant responses; no single method provides it directly.

<!--block:B0008-->
P2. The discipline's established answer is joint inversion: invert several data sets together under a coupling that ties their models to one another, either structurally (cross-gradient and cooperative formulations, and the Gramian branch) or petrophysically, through a rock-property relationship that links the models directly. It is mature and delivers what it promises: mutually consistent models instead of separately plausible ones. **Two things it does not deliver are what motivate the work reported here.** It reduces non-uniqueness without quantifying it: the output is a model, and the range of other models the data would have tolerated is not part of the answer. And the relative weight given to each data set (a decision that materially changes the result) is in practice set by manual trial, so the single most consequential analyst choice in the procedure is neither declared in advance nor recoverable afterwards (Moorkamp et al., 2011). The lineage itself is set out in §2.1.1 and is not repeated here. ⟦I-2/I-3 · [BIB] #18 Vozoff & Jupp 1975（校）/#20 Lines et al. 1988（校）/#19 Haber & Oldenburg 1997/#21/#22（校）/#23 Gallardo & Meju/#25 Lin & Zhdanov 2018/#31 Astic & Oldenburg 2019（校）；**权重人工试凑 = #24 Moorkamp et al. 2011（校，真实题名）**——本文预注册权重治理的直接对照；**谱系全录落 §2.1.1，本段只作动机**⟧

<!--block:B0009-->
P3. The Bayesian formulation supplies the first of those: posed as posterior inference, not minimisation, inversion returns the range of models the data tolerate instead of one member of it, and the geophysical lineage doing so is long established (Backus & Gilbert, 1967; Tarantola & Valette, 1982a, 1982b; Mosegaard & Tarantola, 1995; Sambridge & Mosegaard, 2002; Stuart, 2010). A trans-dimensional branch went further, letting the data determine how much structure a model should carry **and at which scales that structure is represented** (Green, 1995; Malinverno, 2002; Sambridge et al., 2006; Bodin & Sambridge, 2009; Minsley, 2011; Hawkins & Sambridge, 2015; Blatter et al., 2021). Between them these establish per-method uncertainty quantification and considerable freedom in how a model is parameterised. **What it has not established is a treatment of the second gap.** Error that is shared across methods (a systematic distortion common to several surveys, or an idealisation common to several forward operators) is not represented as an inferred object, so it cannot be estimated, reported, or used to decide how far any one method should be believed. Nor does the lineage carry a discipline over where its priors came from, or a governance layer that fixes the acceptance criteria before the run, not afterwards. §2.1.2 gives the lineage in full. ⟦I-4 · [BIB] #4 B&G 1967（校）/#2/#3 TV 1982a/b/#5 M&T 1995（校）/#6 S&M 2002/#8 Stuart 2010/#11 Green 1995/#12 Malinverno 2002（校）/#13 Sambridge et al. 2006（校，四人署名）/#14 Bodin & Sambridge 2009/#15 Minsley 2011（校）/#16 Hawkins & Sambridge 2015/#17 Blatter et al. 2021；**「缺什么」三项对应 §3 的三项构件**；谱系全录落 §2.1.2⟧

<!--block:B0010-->
P4. Two further considerations shape the design, and both concern evidence, not preference. The first is that misspecification is not a peripheral risk in this setting. Inference about physical parameters is biased when the model's inadequacy is not represented, and abundant data does not repair the bias (Brynjarsdóttir & O'Hagan, 2014); under misspecification, Bayesian updating can fail to concentrate on the best available approximation at all (Grünwald & van Ommen, 2017); and there is a principled framework for tempering a likelihood one does not fully trust (Bissiri et al., 2016; Miller & Dunson, 2019). Combining methods multiplies the opportunities for all of this, because every added method adds a forward operator that is wrong in its own way. The second is reproducibility, which computational science has treated as a first-order methodological concern for some time (National Academies of Sciences, Engineering, and Medicine, 2019; Stodden et al., 2016; Wilkinson et al., 2016) and which this work has had specific cause to take seriously: **the reference material assembled for this paper by an LLM-assisted workflow was found, on verification, to contain a register of fabricated and distorted bibliographic records, and all four entries that material named as the closest prior art failed verification and could not be cited as claimed.** The counts, their differing conventions and the fingerprints that identify such records are given in Appendix C and discussed in §8.4. **The boundary on that finding is stated with it and is not relaxed anywhere: it is the hygiene history of this project's own pool, and it is not evidence about the rate of such records in the published literature.** ⟦I-5/I-6/I-7 · [BIB] #56 Brynjarsdóttir & O'Hagan 2014/#53 Grünwald & van Ommen 2017/#51 Bissiri et al. 2016/#52 Miller & Dunson 2019/#94 NAS 2019/#93 Stodden et al. 2016/#92 Wilkinson et al. 2016（作者表括注见 `references.md` 著录说明）；池失真 = [LCM] §4（24 条唯一登记口径）+ [CCA] §1–§5 + [RR] §5.1/§5.2；**边界句 = [RR] §5.5「自家池卫生史、不外推」**；**三口径计数刻意不入本段**，理由见交付注记 4；禁令 3（禁语料「现有研究不足」叙事）与禁令 7（Zhao et al. 不引）已履行⟧

<!--block:B0011-->
Each ingredient of the framework has an established lineage. This paper integrates source-disciplined auditable priors, a shared-error fusion likelihood, and pre-registered diagnostic governance within one explicit probabilistic graph. The integration is presented as a framework-design contribution, not as a firstness claim or evidence that the assembled conjunction outperforms alternatives. The multi-scale parameterisation follows established work (Bunks et al., 1995; Dodwell et al., 2015; Hawkins & Sambridge, 2015; Peherstorfer et al., 2018; Blatter et al., 2021; Lykkegaard et al., 2023; Afonso, 2026), and this paper claims no novelty for it.

<!--block:B0012-->
The comparative positioning rests on a targeted, verification-first literature base, not an exhaustive systematic search, and the search demonstrably missed a close recent paper before targeted gap filling. The resulting comparison is therefore bounded to the verified set and does not support a firstness or literature-wide absence claim. Chinese-language candidates that could not be independently verified are excluded from the evidential comparison and final reference list; the resulting coverage limitation remains explicit.

<!--block:B0013-->
P5. The paper makes four bounded contributions. First, it provides a formulation: an auditable probabilistic graph over nine geophysical method families with explicit shared-error structure, source-disciplined priors and multi-scale change-of-support. Second, it specifies distinct roles for per-method sensitivity weights and pair-level posterior-tension checks. Third, it reports component-level Synthetic-run evidence: per-method forward-operator verification, one algorithm-correctness MCMC study, one reduced-order compatibility exercise with mandatory failure co-disclosure, and one open-data ingestion audit. Fourth, it supplies governance infrastructure: a hash-bound evidence registry, a single diagnostic-threshold contract, failure co-disclosure and fail-closed gate-item admission. These contributions do not demonstrate the behaviour of the assembled framework, the multi-scale joint endpoint, field transfer or production-scale practicality.

<!--block:B0015-->
Two boundaries apply to everything that follows. **All quantitative claims in this paper are bounded at the Synthetic-run tier; no field validity is claimed anywhere.** No result in this paper supports a statement about discovery rates, detection performance, computational speed-up, or resource quantities. And the graph being *formulated* over nine method families is a statement about the formulation, not about deployment: **this paper does not claim that nine methods are jointly operational in production.** The evidence reported here is per-method (§7.1); the only joint object is a registered synthetic asset, a co-platform gravity–magnetic design whose status is given in §6.4 and §7.5. ⟦I-10 · [ES]；[RR] §7.1 首段（证据天花板声明句 = 受保护文本，[OUTLINE] §0.5 第 3 项）；禁令 5；**末二句新增 = [BP] §1「What this paper explicitly is not」第 4 项（"a claim that five/nine methods are jointly operational in production"）**——见交付注记 9⟧

<!--block:B0016-->
P6. §2 positions the framework against five comparison traditions and states the bounded contribution and comparison rule. §3 gives the formulation, §4 the inference strategy, §5 the decision-layer interface, and §6 the validation design and evidence registry. §7 reports one registered asset per subsection; §8 sets the evidential limits, architectural position, limitations, and future work. The appendices contain the nearest-neighbour discovery inventory and full-text recoding protocol (Appendix A), the decision-layer illustration (Appendix B), the search and verification protocol (Appendix C), the pre-registration summary and run-history ledger (Appendix D), the notation index (Appendix E), and the analytic derivations (Appendix F). Three mandatory failure co-disclosures accompany the evidence. Each appears with the evidence it qualifies at §7.1, §7.3, and §8.5 instead of being collected at the end.

<!--block:B0017-->
## 2 Related Work and Novelty Positioning

<!--block:B0018-->
This section positions the formulation within five comparison traditions, states the bounded contribution and records the search limits. Comparators are retained as an identity-verified discovery set, not as an element-scored ranking. No absence, priority or distinctiveness claim is derived from a record without location-specific full-text evidence, and unresolved Chinese-language records remain outside any positive or negative count.

<!--block:B0019-->
### 2.1 Five comparison traditions

<!--block:B0020-->
#### 2.1.1 Deterministic joint inversion: structural and petrophysical coupling

<!--block:B0021-->
Structural coupling runs from Vozoff and Jupp (1975) through the cooperative formulation of Lines et al. (1988) and the variational treatment of Haber and Oldenburg (1997) to the cross-gradient trilogy of Gallardo and Meju (2003, 2004, 2007), reaching a three-dimensional three-method framework in Moorkamp et al. (2011); Lin and Zhdanov (2018) represent a gravity–magnetic application of Gramian constraints in the verified comparison set. This citation is not presented as the first proposal of the Gramian approach because the verified base used for this paper did not adjudicate that priority. Petrophysical coupling runs from Bosch et al. (2010) and Grana and Della Rossa (2010) through Sun and Li (2016) and Giraud et al. (2017) to the dynamic Gaussian mixture model prior of Astic and Oldenburg (2019). This framework takes the **mechanisms** of that tradition and not its estimation paradigm: the structural and petrophysical factors of §3.3 are the Bayesian counterparts of these penalties, entering the joint distribution as prior factors, not tuned regularisation terms. ⟦R-1 · [SYN] §1 传统 1；[LCM] §2 传统 1；[BIB] #18/#20/#19/#21/#22/#23/#24/#25/#27/#28/#29/#30/#31⟧ The nearest constructions are Astic and Oldenburg (2019), whose mixture parameters are estimated dynamically inside a deterministic inversion rather than sampled in a posterior and which carries no provenance discipline, and Moorkamp et al. (2011), whose data weights are set by manual trial — the pain point that motivates the pre-registered weight governance of §3.5. The controlled comparison against this tradition is pre-registered as the coupling-on/coupling-off contrast of EVD-JOINT-001 endpoint (i) (§6.4); **that endpoint has not yet been validly assessed**, its execution status is reported in §7.5, and nothing about its result is anticipated here. ⟦R-1；[SYN] §1 传统 1 最近邻；槽位纪律：本节不预写端点结局⟧

<!--block:B0022-->
#### 2.1.2 The Bayesian geophysical inversion lineage and its trans-dimensional branch

<!--block:B0023-->
The lineage runs from Tarantola and Valette (1982a, 1982b) and Backus and Gilbert (1967) through Mosegaard and Tarantola (1995), Sambridge and Mosegaard (2002), Kaipio and Somersalo (2005) and Stuart (2010); its trans-dimensional branch runs from Green (1995) through Malinverno (2002), Sambridge et al. (2006), Bodin and Sambridge (2009), Minsley (2011), Hawkins and Sambridge (2015) and Blatter et al. (2021). The probabilistic graph of §3.1 is an explicit extension of that lineage: what is added is not the posterior formulation but the shared-error structure of §3.2, the auditable prior stack of §3.3 and the diagnostic governance of §4.6. ⟦R-1 · [SYN] §1 传统 2；[BIB] #1/#2/#3/#4/#5/#6/#7/#8/#11/#12/#13/#14/#15/#16/#17⟧ On the multi-scale axis of this branch the nearest construction is **Afonso (2026)**, treated in §2.2; Hawkins and Sambridge (2015) and Blatter et al. (2021) stand next to it, both single-physics, with a scale structure obtained by data-adaptive partitioning rather than by a prior-driven parameterisation, and in Blatter et al. (2021) the Gaussian process is a parameterisation prior rather than a discrepancy layer. In the contemporary literature Lin et al. (2026) occupies the intersection of cover-sequence targets and trans-dimensional Bayesian joint inversion, using receiver functions and surface-wave dispersion over the buried Nawa Domain; this application context is therefore already active, and the difference from the present work does not lie in working under cover. ⟦R-2 · [BIB] #111（[LCM] Errata E-7 表行 4；占据度 0）；辖域：仅应用语境对照，非要素对照⟧

<!--block:B0024-->
#### 2.1.3 Multi-physics Bayesian fusion and its modular alternatives

<!--block:B0025-->
On the fusion side the tradition runs from Bosch (1999) through Bosch and McGaughey (2001) (the closest antecedent for the gravity–magnetic method pair used in the registered synthetic asset) to Afonso et al. (2013) and, in the contemporary literature, Manassero et al. (2024). On the alternative side stand Bayesian melding (Poole & Raftery, 2000), Markov melding (Goudie et al., 2019) and the cut/modular-posterior diagnosis of Jacob et al. (2017, preprint arXiv:1708.08719). These alternatives are stated as what they are: principled architectures with an explicit account of when modularisation is preferable, not deficient versions of a joint model. The framework's choice of a single probabilistic graph over melding or cut, and the reasons for it, are deferred to §8.2. On this axis too the nearest construction is **Afonso (2026)** (§2.2), which supersedes Afonso et al. (2013) as the same group's general-purpose MCMC fusion framework; the lithological latent-variable sub-axis of Bosch (1999) and Bosch and McGaughey (2001) is unaffected by that re-ranking. Within the multi-observable probabilistic line, Manassero et al. (2024) is the nearest contemporary construction and its boundary must be stated precisely: it performs a joint probabilistic inversion of three-dimensional magnetotelluric and seismic data and propagates their uncertainties within one probabilistic framework, but it **does not claim a cross-method shared-error structure** — there is no shared systematic nuisance term, no inferred physical-idealisation discrepancy layer, and no correlated Student-t observation layer with a restricted single-common-mode cross-method covariance.

<!--block:B0026-->
#### 2.1.4 Bayesian experimental design and value of information

<!--block:B0027-->
Design runs from Chaloner and Verdinelli (1995) through Nowak et al. (2010), Huan and Marzouk (2013) and Ryan et al. (2016) to Rainforth et al. (2024); value of information runs from Howard (1966) through Bratvold et al. (2009) to Eidsvik et al. (2015). **The framework claims no methodological novelty in this tradition.** It uses these sources only to fix definitions and to impose the terminology discipline of §5.3 — design expected information gain, realised information gain and leave-one-method-out forward divergence are three distinct contracts and are never combined. ⟦R-1 · [SYN] §1 传统 4；[BIB] #41/#42/#43/#44/#45/#46/#47/#48；[BP] §5⟧

<!--block:B0028-->
#### 2.1.5 Generalised and robust Bayes, model discrepancy, and computational diagnostics

<!--block:B0029-->
This tradition supplies the normative source of nearly every wording constraint the framework operates under. Generalised Bayesian updating (Bissiri et al., 2016), coarsening (Miller and Dunson, 2019) and the inconsistency result and learning-rate repair of Grünwald and van Ommen (2017) govern how a weighted likelihood target may be described; the model-discrepancy lineage of Kennedy and O'Hagan (2001), Arendt et al. (2012) and Brynjarsdóttir and O'Hagan (2014) supplies both the discrepancy layer and the identifiability caution attached to it; simulation-based calibration from Cook et al. (2006) through Talts et al. (2018, preprint arXiv:1804.06788) to Modrák et al. (2025), together with the convergence diagnostics of Vehtari et al. (2021), fixes what may and may not be called calibration; and the heavy-tailed likelihood line from Egbert and Booker (1986) through Sacchi and Ulrych (1995), Guitton and Symes (2003), and Brossier et al. (2010) locates the observation layer of §3.2. Alemie and Sacchi (2011) instead place a correlated trivariate Cauchy prior on three AVO reflection coefficients. ⟦R-1 · [SYN] §1 传统 5；[BIB] #51/#52/#53/#54/#55/#56/#57/#58/#59/#69/#60/#61/#62/#63/#64⟧ The nearest constructions are Miller and Dunson (2019), whose coarsening rewrites the target posterior globally where the present weights are per-method scalar likelihood powers registered as a diagnostic instrument, and Alemie and Sacchi (2011), whose trivariate Cauchy is a within-method prior over AVO reflection coefficients, not a per-method likelihood or a cross-method coupling factor. ⟦R-3⟧

<!--block:B0030-->
### 2.2 Nearest-neighbour coverage

<!--block:B0031-->
The discovery inventory below is retained only as a discovery inventory of the registered nearest-neighbour set. Its former element scores were based on titles, abstracts and metadata and are therefore withdrawn from decision use. A cell may receive a non-`unknown` value only when a full-text passage, page or section is recorded for that element; no unverified or inaccessible record is encoded as absence. The inventory cannot establish priority, novelty or a missing combination, and no contribution claim in this paper depends on an element count.

<!--block:B0032-->
Discovery inventory. Discovery inventory of the registered nearest-neighbour set. The four disciplinary-element fields are `unknown` pending full-text, location-specific recoding; the table has no novelty or difference-making role.

<!--block:B0033-->
| Nearest neighbour | Auditable priors | Shared-error likelihood | Multi-scale | Pre-registered governance | Decision use |
|---|---|---|---|---|---|
| Bosch (1999) | unknown | unknown | unknown | unknown | none |
| Bosch and McGaughey (2001) | unknown | unknown | unknown | unknown | none |
| Afonso et al. (2013) | unknown | unknown | unknown | unknown | none |
| Astic and Oldenburg (2019) | unknown | unknown | unknown | unknown | none |
| Moorkamp et al. (2011) | unknown | unknown | unknown | unknown | none |
| Hawkins and Sambridge (2015) | unknown | unknown | unknown | unknown | none |
| Blatter et al. (2021) | unknown | unknown | unknown | unknown | none |
| Alemie and Sacchi (2011) | unknown | unknown | unknown | unknown | none |
| Miller and Dunson (2019) | unknown | unknown | unknown | unknown | none |
| Jacob et al. (2017) | unknown | unknown | unknown | unknown | none |
| Afonso (2026) | unknown | unknown | unknown | unknown | none |

<!--block:B0034-->
No element count or score is computed from the discovery inventory. `unknown` means that the present revision did not complete a location-specific full-text evidence bundle for that cell; it is not an absence finding. The table therefore carries no argument about a closest work, a maximum overlap or an unoccupied combination.

<!--block:B0035-->
The earlier draft attached per-row mechanism differentiators to the element scores. Those differentiators are now treated as hypotheses for future full-text recoding, not findings. A future comparison must bind each claimed contrast to an identity-verified full text and a page, section or paragraph locator before it can be used in the manuscript; until then, the reported contribution rests on the formulation and evidence assets themselves.

<!--block:B0036-->
Amaya et al. (2024), Cui et al. (2024) and Lin et al. (2026) remain in the broader discovery record as contemporary candidates. This revision assigns none of them an element occupancy or nearest-neighbour rank because no location-specific full-text recoding bundle was completed.

<!--block:B0037-->
A targeted 2024-onward scan identified eleven bibliographically verified candidates and documented retrieval limitations across its search channels. It did not complete full-text element adjudication, so its former occupancy counts and claims of an empty combination are withdrawn. Enumeration volume, abstract screening and title-only records are discovery evidence, not negative evidence about what the full literature contains.

<!--block:B0038-->
### 2.3 Bounded contribution statement and search scope

<!--block:B0039-->
> This paper specifies and audits the conjunction of source-disciplined priors, a shared-error fusion likelihood, and pre-registered diagnostic governance within one probabilistic graph over a multi-scale parameterisation. It does not claim priority for the constituent mechanisms or demonstrate the performance of the assembled conjunction.

<!--block:B0040-->
> The multi-scale parameterisation used here follows an established lineage, for which we claim no novelty (Bunks et al., 1995; Dodwell et al., 2015; Hawkins & Sambridge, 2015; Peherstorfer et al., 2018; Blatter et al., 2021; Lykkegaard et al., 2023; Afonso, 2026).

<!--block:B0041-->
> Within the shared-error fusion likelihood, the registered joint synthetic asset of this work (EVD-JOINT-001, a co-platform gravity–magnetic design) **implements and registers** the shared position/altitude systematic term ξ_g, the physical-idealisation discrepancy layer δ, and the cross-method restricted single-common-mode covariance Ω of the correlated Student-t observation layer. The surrogate-error layer δ_surr and the systematic terms ξ_t and ξ_a (the latter two held fixed at 1 in that asset) are **specified in formulation but not exercised by that asset**; they are stated as construction only, with no evidential claim attached.

<!--block:B0042-->
⟦R-5 · [NCF] §1.1/§1.2/§1.3 逐字（三段须连排、不得拆散或调换次序）；[SYN] §3.3 条件 1 ①②③；受保护文本 [OUTLINE] §0.5⟧

<!--block:B0043-->
The third paragraph states the design boundary of a registered asset, not a demonstration status. Its implementation and pilot outcome are reported in §6.4 and §7.5, and “implements and registers” must not be read as “has been demonstrated”. Each constituent has antecedents, and no element-level or conjunction-level priority is claimed. The framework's provenance discipline is presented as a design choice; the contribution does not depend on showing that prior literature failed to request or contain it.

<!--block:B0044-->
The comparison is bounded to the registered, verification-first search set and is not an exhaustive Web of Science/Scopus systematic search. Its recall is demonstrably below 100%: Afonso (2026), published in a target journal shortly before the search, was found only during later gap filling. Probe searches then showed that relevance ranking and citation-index lag could miss the same paper, while per-journal enumeration recovered it over the eight enumerated journals. These observations justify a permanent search-scope limitation. They do not establish absence across the published literature, and this paper therefore makes no firstness claim.

<!--block:B0045-->
Chinese-language candidate records that could not be independently verified were excluded from the evidential comparison and from the final reference list. This fail-closed decision avoids assigning evidential weight to unresolved metadata, but it also leaves the comparison set incomplete. The paper therefore treats its comparative positioning as bounded to the verified set and does not infer priority from the missing coverage.

<!--block:B0046-->
### 2.4 Comparison criterion, update rule, and current boundary

<!--block:B0047-->
Before the comparison was run, the project registered a four-part criterion concerning auditable priors, shared-error fusion, sensitivity-weighted diagnostics and pre-registered governance. The present paper records that historical criterion for provenance but does not apply it as a scoring or novelty rule because location-specific full-text evidence was not completed for the comparator cells.

<!--block:B0048-->
The historical criterion contained no multi-scale conjunct because multi-scale parameterisation has an established design lineage. No current statement is made about whether any comparator meets that criterion: every discovery-inventory element cell remains `unknown` pending full-text recoding.

<!--block:B0049-->
The registered joint asset did not yield a valid coupling-increment endpoint because its pilot failed the diagnostics gate. Independently of any literature-comparison criterion, that absence limits this paper to formulation, component evidence and governance infrastructure. Literature references provide design context; they do not substitute for the missing endpoint or validate the usefulness of the assembled combination.

<!--block:B0050-->
The discovery inventory remains updateable. A newly verified record may be added by identity, but an element cell changes from `unknown` only after a full-text evidence bundle records the relevant locator and adjudication. The discovery inventory and Appendix A must then be regenerated from the same bundle; unresolved or inaccessible records never enter a negative count.

<!--block:B0051-->
## 3 The Fusion Framework: Formulation

<!--block:B0052-->
Everything in this section is a **formulation claim**: it states what the framework *is*, not what has been demonstrated. Evidence tiers for the components that have been exercised are declared separately in Sections 6 and 7, and the wording boundaries registered there govern any statement made here. ⟦F-14 · BP §2.4 / RR §6.6⟧

<!--block:B0053-->
Figure 1 presents the paper's two-layer framework–governance architecture. This section develops the framework layer; the governance components are specified in Section 6, and their empirical motivation is discussed in Section 8.4. ⟦图 1 挂钩 · P5 `sec1-p5-novelty-contributions.md` 第 3 段；§6；§8.4⟧

<!--block:B0054-->
**Figure 1.** The framework of this paper has two layers, and the design of the second is a methodological component, not an administrative wrapper around it. The framework layer states what may be inferred; the governance layer states what may be claimed, through a hash-bound evidence registry, a pre-registered diagnostics contract, a rule admitting a gate item only when a construction that makes it fail is registered with it, and mandatory co-disclosure of registered failures. The relation is a loop, not an annotation: the governance layer's outputs return as boundaries on the framework layer's claims. **The four governance components are named here and specified in §6; the empirical record that motivated them is in §8.4.**

<!--block:B0055-->
### 3.1 A single probability graph

<!--block:B0056-->
The framework conditions all inference on one joint decomposition. Writing $c$ for the model/dimension index, $z$ for within-model lithology labels, $m$ for the continuous property fields, $\xi$ for shared systematic nuisance, $\delta$ for model discrepancy, $\delta_{\rm surr}$ for surrogate error, $\lambda$ for the scalar precision mixing variable and $\Theta$ for hyperparameters, the model is ⟦F-1 · 02::2.3.1 Eq. 2.3-WP1-1；BP §2.1⟧

<!--block:B0057-->
$$
\begin{aligned}
p(d,c,m,z,\xi,\delta,\delta_{\rm surr},\lambda,\Theta \mid h, D_{\rm val})
={}& p(\Theta)\,p(c\mid\Theta)\,p(z\mid c,\Theta)\,p(m\mid z,c,\Theta)\,p(\xi\mid c,\Theta)\\
&\times p(\delta\mid c,\Theta)\,p(\delta_{\rm surr}\mid m,z,\xi,c,h,D_{\rm val},\Theta_{\rm surr})\,p(\lambda\mid\nu)\\
&\times p(d\mid m,z,\xi,\delta,\delta_{\rm surr},\lambda,c,\Theta,h).
\end{aligned}
\tag{3.1}
$$

<!--block:B0058-->
Here $h$ collects the frozen configuration (discretisation, source–receiver geometry, frequency bands or time gates, and the version of the realisation map) and $D_{\rm val}$ is a fixed high-fidelity validation set. Both are conditioned upon and never sampled. The full variable dictionary, with dimensions, parents, and the unique entry point of each node, is given in Table 1; the corresponding directed graph is Figure 2.

<!--block:B0059-->
**Figure 2.** The joint decomposition of §3.1 as a directed graph. Variable nodes are rounded; observation factors are square. The shared systematic nuisance ξ is a single node entering every method's observation factor — the structure that distinguishes this formulation from a per-method product. Trans-dimensional states are carried on a disjoint union over the model index c; full definitions of every symbol are in Table 1.

<!--block:B0060-->
**Table 1.** Variable dictionary for the nodes of Eq. (3.1). *Parents* and *entry point* are read directly from the factorisation; each node appears as the conditioned variable of exactly one factor, and that factor is its entry point. Symbols introduced elsewhere in the paper are indexed in Appendix E, which does not restate this table.

<!--block:B0061-->
| Symbol | Meaning | Support / dimension | Parents | Unique entry point |
|---|---|---|---|---|
| $\Theta$ | hyperparameters | block-structured global set; $\Theta_{\rm surr}\subset\Theta$ (§3.2), with further blocks introduced in §3.3; cardinality is configuration-dependent (see note b) | none | $p(\Theta)$ |
| $c$ | model / dimension index | $\mathcal{C}$, counting measure | $\Theta$ | $p(c\mid\Theta)$ |
| $z$ | within-model lithology labels | $\mathcal{Z}_c$, model-specific counting or product measure | $c,\ \Theta$ | $p(z\mid c,\Theta)$ |
| $m$ | continuous property fields | $\mathcal{M}_c$, $\mathrm{Leb}_{n_c}$; dimension $n_c$, model-specific | $z,\ c,\ \Theta$ | $p(m\mid z,c,\Theta)$ |
| $\xi=(\xi_g,\xi_a,\xi_t)$ | shared systematic nuisance: bounded geometry offset, positive gain, clock offset | three strictly typed components; units and bounds from the method contract | $c,\ \Theta$ | $p(\xi\mid c,\Theta)$ |
| $\delta$ | model discrepancy | function-valued: $\delta\sim\mathcal{GP}(0,K_\delta)$ | $c,\ \Theta$ | $p(\delta\mid c,\Theta)$ |
| $\delta_{\rm surr}$ | surrogate error | function-valued and input-dependent: $\mathcal{GP}\!\left(0,K_s(x,x';D_{\rm val},\Theta_{\rm surr})\right)$ with $x=(m,z,\xi,h)$ | $m,\ z,\ \xi,\ c,\ h,\ D_{\rm val},\ \Theta_{\rm surr}$ | $p(\delta_{\rm surr}\mid m,z,\xi,c,h,D_{\rm val},\Theta_{\rm surr})$ |
| $\lambda$ | scalar precision mixing variable of the Student-$t$ observation layer | scalar; $0<\nu_{\min}\le\nu\le\nu_{\max}<\infty$ | $\nu$ | $p(\lambda\mid\nu)$ |
| $d$ | observed data across methods | method-wise; per method contract | $m,\ z,\ \xi,\ \delta,\ \delta_{\rm surr},\ \lambda,\ c,\ \Theta,\ h$ | $p(d\mid m,z,\xi,\delta,\delta_{\rm surr},\lambda,c,\Theta,h)$ |
| $h$ | frozen configuration: discretisation, source–receiver geometry, frequency bands or time gates, realisation-map version | — | **conditioned upon, never sampled** | enters $p(\delta_{\rm surr}\mid\cdot)$ and $p(d\mid\cdot)$ |
| $D_{\rm val}$ | fixed high-fidelity validation set | — | **conditioned upon, never sampled** | enters $p(\delta_{\rm surr}\mid\cdot)$ |

<!--block:B0062-->
*(a)* Trans-dimensional states live on $\bigsqcup_c \{c\}\times\mathcal{Z}_c\times\mathcal{M}_c$; model-specific dimensions, supports and parameterisations are not shared across $c$. *(b)* $\Theta$ has no fixed cardinality: §3 declares its block structure, not its size, and the blocks in force follow the configuration and the method contracts. *(c)* $h$ and $D_{\rm val}$ are not nodes of the graph — they are listed because Eq. (3.1) conditions on them and a reader tracing an entry point will otherwise look for their factors. ⟦T1 · Eq. (3.1) 逐因子；§3.1 基准测度段（(a)）；§3.2 $\xi$ 严格分型句；§3.2 $\delta\sim\mathcal{GP}(0,K_\delta)$；§3.1 「Both are conditioned upon and never sampled」（(c)）；[BP] §2.1；**辖域 = `appendix-e-notation.md` §E.1 逐字**⟧

<!--block:B0063-->
Two properties of this construction carry most of the framework's discipline. First, **no second joint posterior is defined anywhere**. Any posterior that mentions only a subset of the nodes (for example a posterior over $(m,\Theta)$ alone) must be obtained by explicit integration of Eq. (3.1) over the remaining nodes, and the framework provides no shortcut product form for such marginals. ⟦F-1 · 02::2.3.1；02::2.3.3 首段⟧ Second, the density is defined with respect to a declared product of base measures: counting measure on $\mathcal{C}$, model-specific counting or product measure on $\mathcal{Z}_c$, and $\mathrm{Leb}_{n_c}$ on $\mathcal{M}_c$. Trans-dimensional states therefore live on the disjoint union $\bigsqcup_c \{c\}\times\mathcal{Z}_c\times\mathcal{M}_c$, and model-specific dimensions, supports and parameterisations must not be implicitly shared across $c$. ⟦F-1 · 02::2.3.1 基准测度段⟧

<!--block:B0064-->
The formulation sits in the Bayesian inverse-problem tradition (Tarantola & Valette, 1982b; Tarantola, 2005; Kaipio & Somersalo, 2005; Stuart, 2010), of which Eq. (3.1) is an explicit extension to the multi-physics joint setting. ⟦F-15 · [BIB] #3/#1/#7/#8⟧ Posteriors carried over a disjoint union of this kind are specified in Green (1995) and have been developed for geophysical problems by Sambridge et al. (2006), Hawkins and Sambridge (2015) and Blatter et al. (2021); the base-measure and support discipline stated above follows those specifications. ⟦F-16 · [BIB] #11/#13（校：四人署名）/#16/#17⟧

<!--block:B0065-->
Non-compact $\mathcal{M}_c$ is permitted. A sufficient condition for a proper posterior is stated at the level of the whole graph, not any single component: the joint prior — including the model prior, all hyperpriors, and the normalised product-of-experts prior of Section 3.3 — is proper; the mean function $\mu$ is measurable and finite for prior-almost-every state; the degrees of freedom satisfy $0<\nu_{\min}\le\nu\le\nu_{\max}<\infty$; the eigenvalues of the observation scale matrix lie in $[\epsilon_{\min},C]$ with $0<\epsilon_{\min}<C<\infty$; and each product-of-experts normalising constant satisfies $0<Z_c(z,\Theta)<\infty$. Under these conditions the normalised marginal Student-$t$ likelihood is uniformly bounded and strictly positive, so $0<p(d\mid h,D_{\rm val})<\infty$ and the posterior is proper. No single threshold on $\nu$, and no bound on any one component in isolation, constitutes a well-posedness proof. ⟦F-1 · 02::2.3.1 proper 充分条件段⟧

<!--block:B0066-->
Two inference paths are carried explicitly and must be labelled in any application. On the **Full Bayes** path, $p(\Theta)$ is retained and the hyperparameters are sampled or integrated jointly. On the **Empirical Bayes** path, $\widehat{\Theta}$ may be estimated only from pre-declared training data isolated from the evaluation set, after which inference is conditional on $\widehat{\Theta}$; the report must then state the point estimates, the risk that uncertainty is understated because hyperparameter uncertainty is not propagated, and the sensitivity of conclusions to the estimate. Optimisation stopping guarantees neither global convergence nor a fixed iteration count, and an Empirical Bayes output must not be described as Full Bayes. ⟦F-1 · 02::2.3.1 推断边界段；03::3.6.2 EB 备选路径⟧

<!--block:B0067-->
### 3.2 The observation layer and its shared-error structure

<!--block:B0068-->
The unified observation layer is

<!--block:B0069-->
$$
d_k = T_{h,k}\!\left(d_k^{\rm raw}\right) = F_k^h(m,z,\xi) + \delta_k + \delta_{{\rm surr},k} + \epsilon_k ,
\tag{3.2}
$$

<!--block:B0070-->
where $T_{h,k}$ is the **realisation contract** of method $k$: it fixes channel order, units, masks and inverse-transform metadata, and $n_d$ is the total length after realisation. ⟦F-5 · 02::2.3.1 观测实数化契约表；WP3 契约；BP §2.1⟧ The contract is method-specific and detailed — gravity anomaly channels in mGal or µGal with the correction version recorded; total-field or component magnetic channels in nT with field direction and diurnal correction; DC voltage or apparent-resistivity channels that may not be interleaved, with the ABMN geometry and array type; time-domain IP chargeability stacked over pre-registered integration windows, with waveform, turn-off instant and window edges; complex impedance or complex resistivity in a declared representation; time-domain electromagnetic receiver quantities stacked window by window, with transmitter waveform, loop moment and transmitter–receiver geometry; magnetotelluric and audio-magnetotelluric impedance tensors in a fixed component order, with the controlled-source geometry recorded for CSAMT; and wide-field electromagnetic complex response components under a frozen device and source specification. Chargeability is not treated as protocol-transferable: a windowed chargeability and a Cole–Cole parameterisation do not define the same $\eta_{\rm IP}$, and sharing across protocols requires an explicit petrophysical map $\Phi_k$ with independent calibration. ⟦F-5 · 02::2.3.1 极化率跨制式段⟧

<!--block:B0071-->
The shared nuisance vector is strictly typed: $\xi=(\xi_g,\xi_a,\xi_t)$ contains a bounded geometry offset, a positive gain and a clock offset, with units and bounds supplied by the method contracts. Processing errors belong to the method-specific $\delta_k$ or $\epsilon_k$, and petrophysical quantities belong to $m$, to $\Theta$, or to an explicit map $\Phi_k$ — none of them may be absorbed into $\xi$. This typing is what makes $\xi$ a *shared-error* vehicle, not a general-purpose residual sink. ⟦F-2 · 02::2.3.1 统一观测层段；BP §2.1⟧

<!--block:B0072-->
Discrepancy and surrogate error are separated by construction and by data. Model discrepancy is $\delta\sim\mathcal{GP}(0,K_\delta)$ with zero mean and proper bounded hyperpriors on scale and correlation length. Surrogate error is input-dependent, $\delta_{\rm surr}\mid m,z,\xi,h,D_{\rm val},\Theta_{\rm surr}\sim\mathcal{GP}\!\left(0,K_s(x,x';D_{\rm val},\Theta_{\rm surr})\right)$ with $x=(m,z,\xi,h)$, and its hyperparameters satisfy $\Theta_{\rm surr}\subset\Theta$ — a block of the global hyperparameter set, not an independent new symbol, so its prior is already contained in $p(\Theta)$ and is not counted twice in Eq. (3.1). The validation set $D_{\rm val}$ is source-id-exclusive with respect to both the inversion data and any field hold-out set; it conditions the surrogate-error model exactly once and never re-enters $p(d\mid\cdot)$. The three error terms are separated in practice by independent data splits, distinct correlation scales, zero-mean constraints and ablation sensitivity. ⟦F-2 · 02::2.3.1 差异项可辨识约束段；BP §2.1⟧ The discrepancy layer follows the model-discrepancy construction of Kennedy and O'Hagan (2001); the reason for carrying it rather than omitting it is the bias that its absence induces in the physical parameters (Brynjarsdóttir & O'Hagan, 2014), and the difficulty of separating it from those parameters is itself documented (Arendt et al., 2012). ⟦F-20 · [BIB] #54/#56/#55⟧

<!--block:B0073-->
The conditional-independence product across methods is licensed, not assumed. Writing the observation factors as a product over methods is permitted only when the cross-method covariance is zero, or after conditioning on the shared latent variables that generate all of the cross-method correlation. Otherwise the full joint likelihood must be retained. ⟦F-3/F-4 · 02::2.3.1 注段与 2.3.5.1；BP §2.1 禁令 9⟧

<!--block:B0074-->
This licensing condition is where the framework's architecture becomes visible against its alternatives. The modular family declines to form one joint posterior at all, combining sub-models instead through Bayesian melding (Poole & Raftery, 2000), Markov melding (Goudie et al., 2019), or cut and modularised posteriors that deliberately block feedback between components (Jacob et al., 2017, arXiv:1708.08719, preprint). The nearest single-posterior construction over shared latent variables is the multi-observable probabilistic inversion of Afonso et al. (2013). The framework described here takes the single-graph route and pays for it with the licensing condition above; the trade-off between the two architectures is deferred to the Discussion. ⟦F-22 · [BIB] #38（校 DOI）/#39（校 Bayesian Analysis 14(1):81–109）/#40（arXiv 预印本）/#36⟧

<!--block:B0075-->
The observation layer is heavy-tailed and correlated. A single scalar mixing variable $\lambda\sim\mathrm{Gamma}(\nu/2,\nu/2)$ (second parameter a rate) is combined with $d\mid\cdots,\lambda,h\sim\mathcal{N}(\mu,\Omega/\lambda)$, and integrating $\lambda$ gives $r=d-\mu\sim t_\nu(0,\Omega)$ with

<!--block:B0076-->
$$
\Omega = BB^\top + \operatorname{blockdiag}(\Omega_1,\ldots,\Omega_K) + \epsilon_{\rm spd} I ,
\qquad \epsilon_{\rm spd}\ge\epsilon_{\min}>0 .
\tag{3.3}
$$

<!--block:B0077-->
$\Omega$ is the Student-$t$ scale matrix and **not** a marginal covariance: for $0<\nu\le 2$ the marginal covariance does not exist, for $\nu>2$ it equals $\nu\Omega/(\nu-2)$, and conditional on $\lambda$ the covariance is $\Omega/\lambda$. A single $\nu$ governs the whole stacked residual vector; a collection of per-method independent Student-$t$ likelihoods with method-specific $\sigma_k,\nu_k$ is a different model and is not an implementation of Eq. (3.1). Implementations must pass an SPD gate (symmetry, Cholesky factorisability and eigenvalue bounds) before the likelihood is evaluated. Independent replicates $r_{\rm rep}$ may be generated for posterior-predictive checking but are not added to the posterior state. ⟦F-3 · 02::2.3.1；03::3.6.2 Eq. 3.6-1；BP §2.1⟧

<!--block:B0078-->
Robustness to outlying observations has two separate lineages in geophysical inversion, and the construction adopted here coincides with neither. On the data side, robust norms and robust estimators replace the quadratic misfit (Egbert & Booker, 1986; Guitton & Symes, 2003; Brossier et al., 2010). On the model and prior side, heavy-tailed distributions are placed over model or reflectivity parameters (Sacchi & Ulrych, 1995; Alemie & Sacchi, 2011). Eq. (3.3) instead places a single $\nu$ over the whole stacked, cross-method-correlated residual vector — a form distinct both from per-method independent robust norms and from per-method independent heavy tails. ⟦F-21 · 数据侧 [BIB] #61/#62/#63；模型/先验侧 #60/#64（校 DOI 10.1190/1.3554627）⟧

<!--block:B0079-->
Cross-method correlation uses a **restricted single-common-mode construction**. For methods $k$ and $l$,

<!--block:B0080-->
$$
(BB^\top)_{kl} = M_k K_u M_l^\top ,
\qquad
(BB^\top)_{kl,ij} = \rho_{kl}\,\sigma_{k,i}\,\sigma_{l,j},
\tag{3.4}
$$

<!--block:B0081-->
where $M_k,M_l$ are co-location or same-batch matching matrices mapping a shared latent kernel $K_u(\Delta x,\Delta t,\Delta f)$ into the observation index sets. Pairs of observations that are neither co-located, nor from the same batch, nor linked by a pre-registered space–time–frequency kernel are set to zero: the framework never fills the cross block by taking a general cross-correlation of arbitrary unmatched observations. Here $\rho_{kl}\in[-1,1]$ is the loading correlation of a *single* common mode, not a general point-pair correlation coefficient, and $\sigma_{k,i}$ is the noise standard deviation of observation $i$ of method $k$. When this parameterisation is adopted it *is* the corresponding block of $\Omega$ in Eq. (3.3) and must not be superimposed a second time as a separate cross term. The joint block must be symmetric and strictly SPD overall; requiring $|\rho_{kl}|\le 1$ is not sufficient. Parameters are estimated from repeat calibration and from co-located or same-batch residuals under a pre-registered hierarchical model. Under this restricted single-common-mode construction the latent kernel $K_u$ collapses to a scalar: one correlation $\rho_{kl}$ per method pair scaling the observation scales $\sigma_{k,i}\,\sigma_{l,j}$ — and it is this collapsed scalar form that the single shared nuisance of Section 6.4 generates. ⟦F-4 · 02::2.3.1 Eq. 2.3-1a/1b；BP §2.1⟧

<!--block:B0082-->
### 3.3 The auditable prior stack

<!--block:B0083-->
Conditional on the lithology labels, the property prior is a three-layer product of experts,

<!--block:B0084-->
$$
p(m\mid z,\Theta)=\frac{p_{\rm str}(m\mid z,\Theta)\,p_{\rm phy}(m\mid z,\Theta)\,p_{\rm geo}(m\mid z,\Theta)}{Z(z,\Theta)},
\qquad
Z(z,\Theta)=\int p_{\rm str}p_{\rm phy}p_{\rm geo}\,dm .
\tag{3.5}
$$

<!--block:B0085-->
The product form is used only where the three factors consume mutually exclusive sources and the product is jointly normalisable; $Z(z,\Theta)$ must enter inference, and where it cannot be computed reliably, model evidence must not be compared. Where conditional independence between $p_{\rm geo}$ and $p_{\rm phy}$ cannot be established, the product of experts is abandoned in favour of a single hierarchical conditional factor. ⟦F-6 · 02::2.3.3 Eq. 5；BP §2.3⟧

<!--block:B0086-->
What makes the stack **auditable** is the unique source-id rule that governs which factor may consume what. The consumption sets are declared disjoint,
$S_z=\{\texttt{interpretation:campaign:v1}\}$,
$S_m=\{\texttt{property-db:campaign:v1},\ \texttt{borehole-conditioning:campaign:v1}\}$,
$S_d=\{\texttt{geophysics-observation:campaign:v1}\}$,
with $S_z\cap S_m=S_z\cap S_d=S_m\cap S_d=\varnothing$; $p_{\rm str}$ consumes no external observational source, $p_{\rm phy}$ consumes only $S_m$, $p_{\rm geo}$ consumes only $S_z$, and none of the three may consume $S_d$. Crucially, disjointness is **not** decided by comparing current source-id strings. Every raw source registers an immutable `origin-id`, a content hash and an ancestor set; copying, slicing, interpolation, summarisation, renaming and version upgrades may only extend the lineage, never reset or delete it. Any two generative factors are declared overlapping (and rejected from the joint model) as soon as their consumed objects share an `origin-id`, share a content hash, or have intersecting ancestor sets. Information that genuinely must be shared across factors may enter only as a deterministic summary generated by an upstream random node, with that summary's parents and ancestors registered; it may not be re-presented as a new independent observational source. ⟦F-6 · 02::2.3.1 唯一 source-id 规则；BP §2.3⟧

<!--block:B0087-->
Boreholes enter through exactly one door. Lithological logs, wireline data and assays are admitted only via $p(m\mid z,\Theta)$, represented as observations **with measurement error, position error and finite support volume**, including point-to-segment and segment-to-block upscaling. Their derived products may not re-enter the observation likelihood, and the corresponding grid cells are never fixed to error-free hard values. Evaluation holes carry an exclusive `borehole-holdout:*` identifier, enter no generative factor, and their copies and derivatives inherit the same ancestor set and are excluded with them. ⟦F-6 · 02::2.3.1 钻孔段；03::3.2.3；BP §2.3⟧

<!--block:B0088-->
Structural coupling, $p_{\rm str}$. With registered property transforms $G_i$ (a logarithm for positive quantities) and frozen centres and scales $\mu_i, s_i>0$, so that $u_i=(G_i(m_i)-\mu_i)/s_i$ is dimensionless,

<!--block:B0089-->
$$
p_{\rm str}(m\mid\theta)\ \propto\
\exp\!\left(-\sum_{i<j}\lambda_{ij}\int_V q_{ij}(x)\,\bigl\|\nabla u_i\times\nabla u_j\bigr\|^2\,dV\right),
\qquad \lambda_{ij}\ge 0,\ q_{ij}(x)\in[0,1].
\tag{3.6}
$$

<!--block:B0090-->
The mechanism draws on a structural-coupling lineage that runs from the earliest joint inversions (Vozoff & Jupp, 1975) and cooperative inversion (Lines et al., 1988), through the structural approach of Haber and Oldenburg (1997), to the cross-gradient constraint introduced and developed by Gallardo and Meju (2003, 2004, 2007). Within the verified reference set, Lin and Zhdanov (2018) provide the nearest gravity–magnetic application of Gramian constraints, which this framework does not adopt. This paper does not assign first-proposal priority for the Gramian approach because that question was not adjudicated by the verified base. ⟦F-17 · [BIB] #18（校 DOI 补登）/#20（校 DOI 补登）/#19/#21/#22（校 JGR 109(B3)）/#23；F-18 · #25⟧ Here the mechanism is carried as a *switchable soft prior factor* inside Eq. (3.1) rather than as a deterministic penalty. Setting $\lambda_{ij}=0$ or $q_{ij}(x)=0$ turns the coupling off explicitly, and that **off-state is retained as an independent multi-method baseline that must enter the same-data comparison** — it is not merely a limiting case mentioned in passing. ⟦F-7 · 02::2.3.3 Eq. 6；BIB #22；BP §2.3⟧ For gradual contacts — alteration halos, transitional boundaries — a relaxed variant normalises the cross-gradient and multiplies it by a differentiable smooth gate $s_{ij}(\cdot;b_{ij},\tau_{ij})$ with a positive regulariser $\epsilon_{ij}$; $b_{ij}$, $\epsilon_{ij}$ and the gate width $\tau_{ij}$ are positive dimensionless project parameters whose sources, scales, priors and numerical implementation must be recorded, and no cross-property universal contact threshold exists. The relaxed form is a candidate to be tested: its benefit must be reported against the $\lambda_{ij}=0$ baseline, against unit-rescaling variants, and on independent hold-out prediction. ⟦F-7 · 02::2.3.3 Eq. 6a⟧

<!--block:B0091-->
Petrophysical coupling, $p_{\rm phy}$. Coupling geophysical properties through petrophysical statistics has a long lineage: lithologic tomography (Bosch, 1999; Bosch & McGaughey, 2001), reservoir-side estimation combining statistical rock physics with seismic inversion (Bosch et al., 2010; Grana & Della Rossa, 2010), clustering-guided joint inversion (Sun & Li, 2016), geologically constrained uncertainty reduction (Giraud et al., 2017), and the petrophysically and geologically guided inversion framework of Astic and Oldenburg (2019). The form taken here is that coupling expressed as a prior factor in a transformed latent space. ⟦F-19 · [BIB] #34/#35/#27（校 DOI 补登）/#28（校 年份 2010）/#29（校 年份·题名·DOI）/#30（校 全题名）/#31（校 题名 "…model prior"）⟧ This factor consumes `property-db:*` and `borehole-conditioning:*` only, and builds a multi-property Gaussian mixture in a transformed latent space in which each variable is unconstrained: $\log\rho_e$ for resistivity, $\operatorname{logit}\eta_{\rm IP}$ for chargeability, $\log\rho_{\rm abs}$ for absolute density with the contrast $\rho_d=\rho_{\rm abs}-\rho_{\rm ref}$ defined against a project-fixed reference, and $u_\kappa$ for susceptibility with $\kappa=-1+\exp(u_\kappa)>-1$. The sampled variable is $u_\kappa$; any density reported in the $\kappa$ domain must include the $1/(1+\kappa)$ Jacobian, and the same requirement applies to every other latent transform, together with boundary checks. ⟦F-8 · 03::3.3；BP §2.3⟧ These petrophysical priors are hypothesis-tier constructs within the framework; nothing in this paper presents them as validated. ⟦F-8 · BP §4.5；RR §7.1-5⟧

<!--block:B0092-->
Interpretation-driven structure, $p_{\rm geo}$. This factor consumes `interpretation:*` only. It may reference deterministic masks generated by $p_{\rm phy}$, but may not re-read boreholes, the property database or geophysical observations. It supplies an anisotropic Gaussian process with along-strike correlation, a three-level exploration-stage hierarchy (weak constraints at the regional reconnaissance stage, medium at target-area follow-up, strong at deep exploration), and a training-image trust mixture

<!--block:B0093-->
$$
c_{TI}\sim\mathrm{Beta}(a_c,b_c),
\qquad
m\mid c_{TI},z,\Theta \sim c_{TI}\,p_{TI}(m\mid z,\theta_{TI}) + (1-c_{TI})\,p_{\rm local}(m\mid z,\theta_{\rm local}),
\tag{3.7}
$$

<!--block:B0094-->
with $a_c,b_c>0$ and both components proper and normalised on a common support. Here $c_{TI}$ is the latent credibility that the training image applies to the present survey area — not an arbitrary weight traded off against the likelihood. Structural, lithological and petrophysical differences may serve as pre-registered covariates of the $c_{TI}$ hyperprior, but the current inversion data may not be used post hoc to strengthen the same prior. **The local-prior baseline near $c_{TI}\to 0$ is always retained**, which is what prevents a globally trained deposit template from overriding the specific geology of the area. If the data identify $c_{TI}$, it is inferred jointly on the Full Bayes path; if it is fixed from an independent training area, the result is labelled Empirical Bayes with hyperparameter sensitivity and unpropagated uncertainty reported. ⟦F-9 · 03::3.2.1–3.2.3 Eq. 3.2-1；BP §2.3⟧

<!--block:B0095-->
Three prior-discipline instruments are mandatory and all three are reported: **prior-predictive checks** against pre-declared, physically meaningful statistics and admissible ranges, reporting Monte Carlo error, tail behaviour and impossible events; **prior–data conflict diagnostics**, read with the explicit caveat that a conflict indicts the prior–forward–error-model triple, not the prior alone, and that agreement likewise proves nothing on its own; and **hyperparameter sensitivity** across several proper prior specifications. ⟦F-9 · 03::3.2.1；BP §2.3⟧

<!--block:B0096-->
### 3.4 Multi-scale parameterisation

<!--block:B0097-->
Three nested scale mechanisms are carried, and all three are **parameterisation design** (Figure 3). ⟦F-10/F-11/F-12 · BP §2.2；CP1 D2；RR §6.6⟧

<!--block:B0098-->
**Figure 3.** The multi-scale parameterisation: a depth-band organisation, per-scale reduced coordinates, and a change-of-support operator carrying a band's field onto the observation support. All three are parameterisation design. This paper claims no novelty for multi-scale parameterisation and reports no multi-scale demonstration.

<!--block:B0099-->
*Depth-band organisation.* Shallow, intermediate, deep and regional-long-wavelength bands provide candidate structure with **project-registered boundaries**, never fixed depth constants. The framework's capability matrix makes every method's effective constraint interval conditional on frequency band or time gate, background properties, offset and transmitter moment, topography, noise and target scale, to be determined per project by depth-of-investigation analysis, resolution analysis or synthetic recovery tests. A method name never implies a depth range, and potential-field methods, while free of electromagnetic skin-depth limits, still attenuate with source distance and retain strong depth non-uniqueness. ⟦F-10 · 02::2.1.1 能力矩阵；BP §2.2⟧

<!--block:B0100-->
*Change-of-support coupling.* Scale transfer connects **the same property in the same transform space** at two support volumes. With $u=G(\rho)$ and a block-averaging operator $A_{R\leftarrow L}$ from local to regional support,

<!--block:B0101-->
$$
p(u_L,u_R\mid\Theta_{cs}) = p(u_L\mid\Theta_{cs})\,p(u_R\mid u_L,\Theta_{cs}),
\qquad
u_R\mid u_L,\Theta_{cs}\sim\mathcal{N}\!\left(A_{R\leftarrow L}u_L,\ \Sigma_R(\gamma,h;\Theta_{cs})\right),
\tag{3.8}
$$

<!--block:B0102-->
with $p(u_L\mid\Theta_{cs})$ proper. The operator, the variogram-structured residual covariance $\Sigma_R$, the coordinate system, the units and both support volumes are frozen in the project configuration; the reverse conditional $p(u_L\mid u_R,\Theta_{cs})$ is *derived* from this single generative direction, and an independent reverse Gaussian factor must not be multiplied in. The experimental variogram $\gamma_u(h)=\tfrac{1}{2N(h)}\sum_i[u(x_i)-u(x_i+h)]^2$ describes the spatial variation of one variable only. Where different properties must be linked (density to resistivity, say) the link passes through a lithological or petrophysical latent, $p(\rho,\kappa,\eta_{\rm IP}\mid l,\Theta_{rp})$, with dimensions, support scales, provenance, calibration and competing explanations stated for every edge. **Dimensionless linear exchange between property types is excluded by construction**, and a variogram alone cannot license such a link. ⟦F-11 · 02::2.1.4 Eq. 2.1-4/2.1-5；02::2.3.8 Eq. 2.3-54/55；BP §2.2⟧

<!--block:B0103-->
*Per-scale reduced coordinates.* A proper orthogonal decomposition basis is built per depth band, and the framework carries an explicit boundary with it. At fixed total rank, on the same training snapshots and under the Frobenius norm, the globally truncated SVD is optimal by the Eckart–Young–Mirsky theorem. Consequently **a per-scale basis cannot claim to outperform a global basis of equal total rank**, and the corpus theorem that once asserted otherwise was withdrawn. What remains verifiable is narrower: once the block partition, the per-block ranks $r_k$ and a weighted block norm are fixed in advance, the total projection error decomposes by block, and whether the per-scale construction beats an engineering baseline is an empirical question to be settled on an isolated hold-out set with the failure cases reported. We carry this retraction as a property of the framework instead of repairing the claim. ⟦F-12 · 03::3.1.2.1；BP §2.2⟧

<!--block:B0104-->
Neither ingredient of this construction originates here. Organising geophysical inversion by a hierarchy of frequency band and resolution goes back to Bunks et al. (1995), and multi-scale unstructured discretisation carried across methods within a joint inversion for mineral exploration appears in Lelièvre et al. (2012); the basis construction itself comes from the turbulence literature (Sirovich, 1987; Berkooz et al., 1993). What this framework contributes at this point is the depth-band per-scale organisation and the retraction discipline just stated — neither the multi-scale idea nor the decomposition. ⟦F-23（第 2 次补正）· 地球物理多尺度本源 [BIB] #98 Bunks et al. 1995（A 级；原过渡记法 R6）/[BIB] #100 Lelièvre et al. 2012（校 年份 2012；原 R7）；POD 本源 [BIB] #75/#76（湍流领域，不单独承担地球物理多尺度归属）；著录权威 = [E2REG] §3（**2026-08-22 更正：[RR] §10 已同步，N = 111**；原「尚未同步」为 2026-08-20 状态，现已失效）⟧

<!--block:B0105-->
The "multi-scale" of the title refers to exactly these three parameterisation mechanisms.

<!--block:B0106-->
### 3.5 Robustness as a first-class component

<!--block:B0107-->
The framework registers a **generalised-Bayes sensitivity weighting** layer as a pre-registered, frozen component, not a tuning knob. With $J_k(m)=\partial f_k/\partial m$, a frozen observation whitening operator $L_k$ and a frozen parameter scaling $D_m$,

<!--block:B0108-->
$$
\widetilde{S}_k(m)=L_k J_k(m) D_m,
\qquad
s_k(m)=\bigl\|\widetilde{S}_k(m)\bigr\|_F^2,
\qquad
w_k(m)=\left[\frac{s_k(m)}{\sum_{j=1}^{K}s_j(m)+\epsilon}\right]^{\alpha},
\qquad
W_k(m)=w_k(m)\,I_{n_k},
\tag{3.9}
$$

<!--block:B0109-->
entering the weighted target

<!--block:B0110-->
$$
\pi_W(m\mid d)\ \propto\ p(m)\exp\!\left(-\tfrac12\sum_{k=1}^{K}\bigl(d_k-f_k(m)\bigr)^\top W_k(m)\,C_k^{-1}\bigl(d_k-f_k(m)\bigr)\right).
\tag{3.10}
$$

<!--block:B0111-->
The exponent $\alpha>0$, the regulariser $\epsilon>0$, the whitening operator and the parameter scaling are declared in the pre-registration manifest and held fixed for the entire production run; the framework offers no cross-project "typical" or "recommended" values. ⟦F-13 · 00::摘要（式 + WP5 注记）；BP §2.4⟧

<!--block:B0112-->
Equation (3.9) is the sole canonical weighting definition for this manuscript. The existing joint-pilot registration preserves a historical, non-canonical additive-floor form, $w_k=(\mathrm{share}_k+\epsilon_w)^\alpha$, with $\alpha=1.0$ and $\epsilon_w=0.01$, as provenance; it is not an alternative definition: it is not algebraically equivalent to Eq. (3.9). In that asset the main posterior remains unweighted, $w_k\equiv1$, and the historical weighted form appears only in the two endpoint-(ii) arms. No controlled comparison of the two parameterisations was run, so the pilot cannot support a sensitivity or robustness conclusion about the weight operationalisation. Any future weighted asset must cite Eq. (3.9), freeze its parameters and register a separate sensitivity design before execution.

<!--block:B0113-->
Its position in the framework is deliberately narrow. It is **not** the default posterior and **not** an ingredient of marginal likelihoods or Bayes factors; it is a diagnostic and robustness instrument, and the weighted target is a generalised-Bayes object that must be calibrated on its own terms. Objects of this kind are formalised as general belief updates by Bissiri et al. (2016); what motivates admitting them is the behaviour of standard Bayesian updating under misspecification, where the posterior can concentrate on a wrong answer (Grünwald & van Ommen, 2017) or be stabilised only by explicit coarsening (Miller & Dunson, 2019). The calibration obligation is inherited from that same literature. ⟦F-24 · [BIB] #51/#53/#52⟧ Two discipline points are carried unchanged from the specification:

<!--block:B0114-->
1. **The weight is a per-method scalar.** With `weight_shape = scalar_times_identity`, $w_k$ multiplies the entire likelihood power of method $k$ and contains no $(k,l)$ information whatsoever. It therefore **cannot, by construction, selectively detect pair-level shared-error misspecification**. Pair-level detection is assigned instead to posterior-discrepancy tension checks evaluated on the restricted cross-covariance blocks $(BB^\top)_{kl}$ of Eq. (3.4). These are two distinct instruments with two distinct jobs, and neither substitutes for the other. ⟦F-13/F-14 · BP §2.4；RR §6.6 权重边界⟧
2. **Frobenius normalisation guarantees very little.** It neither removes physical units nor guarantees numerical stability, posterior calibration, or fusion superiority. The exponent, the regulariser and the standardising scales require sensitivity analysis in pre-registered scenarios and comparison against a canonical generative-model baseline. ⟦F-13 · 00::摘要 告诫段⟧

<!--block:B0115-->
The framework's claim is scoped accordingly: it offers **fusion with pre-registered sensitivity diagnostics and misspecification warning**. A method whose weight or whose tension statistics move under misspecification is flagged and can be down-weighted; there is no quantitative rule in the specification that automatically excludes a data set, and none is claimed. If fusion degrades a particular method pair on synthetic scenarios, that is a reportable finding about the configuration, not a failure of the framework. ⟦F-13/F-14 · BP §2.4；RR §6.6⟧

<!--block:B0116-->
Finally, the operational meaning of frozen whitening is stated explicitly because it determines what the weight channel can respond to. The Cholesky whitening rule is frozen, while the covariance supplied to it is governed by a sampled noise-scale node. Under linear forward operators, increasing that noise scale reduces the normalised sensitivity share and therefore reduces the method weight. This licenses only a directional diagnostic claim: weight trajectories may respond to the registered injected misspecification in the predicted direction. It does not establish that weighting improves posterior robustness, because the noise-scale channel already absorbs part of the misspecification and no isolated weighted-versus-unweighted comparison has been completed.

<!--block:B0117-->
## 4 Inference and Computation

<!--block:B0118-->
### 4.0 Components and their evidence tiers

<!--block:B0119-->
The inference stack is designed and partially evidenced. Table 2 lists every component and its current evidence tier, and no statement in this section exceeds that tier. Two rows carry Synthetic-run support: delayed acceptance together with the diagnostics contract it exercises, and numerical safeguards through the WP8 per-method operator checks. The remaining rows are design. ⟦C-1 · BP §3 表⟧

<!--block:B0120-->
The inference route taken throughout is Markov chain Monte Carlo. Variational and invertible-network or normalising-flow routes to geophysical Bayesian inversion form an active alternative family (Zhang & Curtis, 2021; Wu et al., 2025); they are named here to locate the present route within the available options, and no comparison of accuracy, speed or computational envelope is made or implied. ⟦C-16 · [BIB] #9（校 DOI 10.1029/2021JB022320）/#10；§5(b) 约束 3 禁性能对照⟧

<!--block:B0121-->
**Table 2.** Inference components, their role, and the evidence tier registered for each.

<!--block:B0122-->
| Component | Role in the framework | Evidence tier |
|---|---|---|
| MAP anchoring (L-BFGS) | candidate initial states and proposal construction; not optimality claims | design; multi-start and modal caveat disclosed |
| Multi-scale POD reduced coordinates | rank selected from a frozen candidate set by an isolated tuning loss; pushforward posterior behind a normalisation gate | design |
| Delayed acceptance (surrogate-first Metropolis–Hastings) | cheap screening proposals with two-stage correction to the exact target | **Synthetic-run (EVD-ALGO-002)** |
| Parallel tempering | unique likelihood-tempering target, frozen ladder, log-domain swap acceptance | design |
| Reversible-jump MCMC | unique Green specification for trans-dimensional moves | design (no trans-dimensional run) |
| Diagnostics contract | single source of all acceptance criteria and thresholds | **EVD-ALGO-002 exercises the contract end-to-end** |
| Numerical safeguards | scale-aware normalisation, matrix-free derivatives, adjoint and Taylor-remainder checks | WP8 per-method operator checks |

<!--block:B0123-->
### 4.1 MAP anchoring

<!--block:B0124-->
Deterministic optimisation enters the framework as an *anchor generator*, not as a solution method. An L-BFGS pass minimises

<!--block:B0125-->
$$
J(m)=\bigl\|d-F(m)\bigr\|^2_{C_d^{-1}} + \lambda_{\rm prior}\bigl\|m-m_{\rm prior}\bigr\|^2_{C_m^{-1}},
\tag{4.1}
$$

<!--block:B0126-->
whose minimiser supplies candidate initial states for the chains and centres for proposal construction. The functional is the generalised least-squares criterion of Tarantola and Valette (1982a), in the deterministic regularised-inversion tradition set out by Tarantola (2005); the framework takes it as an anchor generator and makes no claim about it as a solution method. ⟦C-10 · [BIB] #2/#1⟧ The regularisation weight $\lambda_{\rm prior}$ is a statistical prior precision and is a distinct object from the shared Student-$t$ residual scale $\lambda$ of Section 3.2, from the structural coupling strengths $\lambda_{ij}$ of Section 3.3, and from numerical damping introduced only for linear-algebraic stability. On the Full Bayes path it receives a proper hyperprior and is inferred jointly; on the Empirical Bayes path it is estimated on an isolated training split and fixed. An L-curve may be used only for an explicitly labelled deterministic baseline and never to assert a Bayesian optimum. ⟦C-2 · 03::3.1.1（Eq. 3.1-1/3.1-2）；BP §3 行 1⟧

<!--block:B0127-->
Two caveats apply whenever this component is used. **No optimality is claimed**: a MAP point is a numerical starting point, it cannot substitute for the joint posterior or for depth-of-investigation evidence, and multi-start optimisation is required because a single trajectory may miss distant modes. Anchors built from method-specific inversions may be combined over overlapping depth intervals by a smooth weighting function, but the smoothing parameters, transition widths and admissible error norms are project-level quantities that must be pre-registered and calibrated; defaults are not accepted. ⟦C-2 · 03::3.1.1、03::3.1.1.1；BP §3 行 1⟧

<!--block:B0128-->
### 4.2 Multi-scale reduced coordinates

<!--block:B0129-->
Where reduced coordinates are used, the model is represented as $m\approx m_0+\Phi_r\alpha$ with an orthonormal basis $\Phi_r$ obtained from a centred training snapshot matrix. The rank is not chosen by an energy criterion. Training energy ratios may generate only a **candidate rank set** $\mathcal{R}$; the rank is then selected as $q^\ast\in\arg\min_{q\in\mathcal{R}}\widehat{L}_{\rm tune}(q)$ on a snapshot split that is completely isolated from basis construction, and the final independent test set is run exactly once and used only for reporting, never to reselect the rank. Snapshots must span prior-predictive draws, pre-registered multi-start optima and tempered-chain states, not only the neighbourhood of a single optimum, and training, tuning and test splits, seeds and leakage checks are stored with the run record. ⟦C-3 · 03::3.1.2（Eq. 3.1-6/3.1-7c/3.1-7d）、03::3.1.2.2；BP §3 行 2⟧ Reduced-basis inference of this kind draws on the proper orthogonal decomposition (Sirovich, 1987; Berkooz et al., 1993), its extension to parameter and state reduction for large-scale statistical inverse problems (Lieberman et al., 2010), and the wider multifidelity family (Peherstorfer et al., 2018); what is specified here is the rank-selection isolation and the gate below, not the reduction itself. ⟦C-11 · [BIB] #75/#76/#77（校 作者与题名）/#78（校 DOI 补登）⟧

<!--block:B0130-->
The reduced posterior is defined with an explicit gate. With $T_r(\alpha)=m_0+\Phi_r\alpha$ and a proper coefficient prior $p_\alpha$, the coefficient posterior $p_r(\alpha\mid d)$ has normalising constant $Z_r(d)$, and the necessary condition for a proper reduced-order posterior is $0<Z_r(d)<\infty$; implementations must verify numerically that the likelihood is non-negative and measurable, that the coefficient prior is proper, and that $Z_r(d)$ is finite and non-zero, and **a posterior that fails this gate is not published**. The induced model-space measure $\mu_r^m=(T_r)_\#\mu_r^\alpha$ is a pushforward supported on an embedded subspace and is generally singular with respect to full-space Lebesgue measure, so it must not be compared to a full-dimensional posterior by a full-space Kullback–Leibler divergence; comparison is made after fixing a common observation or decision map, or by introducing an orthogonal complement so that both measures share a support. ⟦C-3 · 03::3.1.2.1 Def. 3.1.4（Eq. 3.1-7e）；BP §3 行 2⟧

<!--block:B0131-->
### 4.3 Delayed acceptance

<!--block:B0132-->
Surrogates enter the framework only under correction. When a reduced-order, learned or multi-fidelity surrogate is used for screening, its error is either probabilised as the $\delta_{\rm surr}$ node of Section 3.2 and calibrated against the independent validation set, or (where that error cannot be reliably probabilised) handled by a **two-stage delayed-acceptance kernel whose invariant distribution corresponds to the original physical-model target posterior**. A cheap first stage screens proposals; a second stage evaluates the high-fidelity model and applies the correcting acceptance ratio. An output that has not been corrected in one of these two ways is called a surrogate posterior and is labelled as such. ⟦C-4 · 03::3.7.3；BP §3 行 3⟧

<!--block:B0133-->
The two-stage pattern (a cheap coarse screen followed by a correction that restores the exact target) has an established methodological line. Cui et al. (2011) develop an adaptive delayed-acceptance Metropolis–Hastings sampler and apply it to Bayesian calibration of a large-scale geothermal reservoir model, although their adaptivity is broader than anything permitted here, since the discipline of Section 4.7 confines adaptation to a declared warmup, requires diminishing adaptation and containment, freezes it before production sampling, and excludes outright any scheme that keeps modifying proposals, auxiliary densities or the target in response to an observed acceptance rate. Lykkegaard et al. (2023) merge the discretisation hierarchy with the fidelity hierarchy in multilevel delayed acceptance, extending the hierarchical multilevel construction of Dodwell et al. (2015), and Peherstorfer et al. (2018) survey the multifidelity family for uncertainty propagation and inference.

<!--block:B0134-->
Those works locate the lineage; they are not the provenance of what is implemented here. Three boundaries follow from that and are stated explicitly: this framework carries **no multilevel implementation**, so the hierarchical constructions cited above are context and not capability; the scale at which any of those studies was applied implies **nothing** about the scale at which this framework has been exercised, and no compute, runtime or speedup claim is made or implied; and the specification followed here is the framework's own operator specification together with the accompanying implementation, **not a reproduction of any of those constructions**. Finally, while the verified citation base underlying this paper now contains delayed-acceptance methodological canon, it still contains no paper in which the scheme is first proposed; under the grey-zone-fails rule no entry outside that base is cited. ⟦C-12（第 2 次补正）· [BIB] #99 Cui et al. 2011（原过渡记法 R9）/ [BIB] #101 Lykkegaard et al. 2023（校 年份 2023；原 R8）/[BIB] #80/#78（校 DOI 补登）；规格出处 = 语料 `03::3.7.3` + `src/geodeepbayes/sampling/delayed_acceptance.py`（C-4 行）；§5(b) 约束 4 双层表述；著录权威 = [E2REG] §3；**基座边界句 = Stage 2.5 可核查项**⟧

<!--block:B0135-->
This is the one component in this section with registered run evidence. A full-dimensional delayed-acceptance sampler, implemented in the accompanying package, has been exercised on a generic 48-dimensional bimodal target and meets the joint diagnostics contract of Section 4.6; the registered diagnostic values, together with the frequentist same-truth coverage study run on the same target, are reported in Section 7.2 under evidence identifier EVD-ALGO-002. The boundary registered with that asset governs every use made of it here: the target is a **generic, non-geophysical** one, and the result is not extrapolated to petrophysically guided inversion, to joint multi-method inversion, to DC or electromagnetic methods, to field data, to full-scale problems, or to any performance claim. Its role in this paper is to show that the delayed-acceptance mechanism is correctly implemented and that the diagnostics contract is operable — nothing more. ⟦C-4 · MAP03 EVD-ALGO-002；`validation/wp7/versions/synthetic-block-v6-20260724`；RR §7.1-1⟧

<!--block:B0136-->
### 4.4 Parallel tempering

<!--block:B0137-->
Where multimodality is expected, tempering uses a single, uniquely specified target,

<!--block:B0138-->
$$
\pi_{\beta_\ell}(x)=\frac{p(x)L(x)^{\beta_\ell}}{Z_{\beta_\ell}},
\qquad 1=\beta_1>\beta_2>\cdots>\beta_L\ge 0,
\tag{4.2}
$$

<!--block:B0139-->
in which $x$ is the complete state of Eq. (3.1) and every rung shares the same proper prior and support. Swaps between adjacent rungs are accepted with

<!--block:B0140-->
$$
\log A_{\rm swap}=\min\Bigl[0,\ (\beta_i-\beta_j)\bigl\{\log L(x_j)-\log L(x_i)\bigr\}\Bigr],
\tag{4.3}
$$

<!--block:B0141-->
so that the intractable $Z_\beta$ cancels. The computation is performed in the log domain and non-finite values are rejected under the contract, not silently repaired. Whole-posterior tempering is not used, and any alternative bridging family would have to be defined as a separate algorithmic contract. ⟦C-5 · 02::2.3.5.2；03::3.3.2；BP §3 行 4⟧

<!--block:B0142-->
The temperature ladder is a pre-registered candidate configuration; the framework asserts no transferable rule for the number of rungs or the temperature ratio, and the earlier spectral-gap bound and "optimal" temperature-ratio formula were withdrawn because such results depend on the target, the local kernel, the exchange graph and the energy barriers. Ladders that are geometric, uniform in inverse temperature, or adaptive must be compared under equal budget on time-to-accuracy; any change during a run must satisfy diminishing adaptation and containment, or else be frozen before production sampling. Every rung's $\beta$ and $\log L$, the proposed and accepted swaps, cold-chain round trips and cross-modal visits are stored. **Exchange diagnostics are read for mechanism only** — they describe whether the ladder is communicating, and they carry no calibration meaning and cannot on their own establish convergence. ⟦C-5 · 02::2.3.5.2、03::3.3.2；BP §3 行 4⟧ The tempering literature this construction draws on is well established (Earl & Deem, 2005; Sambridge, 2014; Vousden et al., 2016).

<!--block:B0143-->
### 4.5 Reversible-jump MCMC

<!--block:B0144-->
Trans-dimensional inference is specified once, in Green's form, and no simplified variant is written anywhere else in the framework. With state $x=(c,\vartheta_c)$ and target $\pi(c,\vartheta_c)\propto p(d,c,\vartheta_c\mid h,D_{\rm val})$ bound explicitly to Eq. (3.1), a move $\ell$ is chosen with probability $j_\ell(x)$, auxiliary variables are drawn as $u\sim q_\ell(u\mid x)$, and a differentiable bijection

<!--block:B0145-->
$$
(y,u')=T_\ell(x,u),\qquad \dim(x)+\dim(u)=\dim(y)+\dim(u'),
\tag{4.4}
$$

<!--block:B0146-->
gives the acceptance probability

<!--block:B0147-->
$$
A_\ell(x,u)=\min\left\{1,\ \frac{\pi(y)\,j_{\ell^\star}(y)\,q_{\ell^\star}(u'\mid y)}{\pi(x)\,j_\ell(x)\,q_\ell(u\mid x)}\ \bigl|\det DT_\ell(x,u)\bigr|\right\}.
\tag{4.5}
$$

<!--block:B0148-->
Move probabilities must be renormalised at model boundaries where some moves are unavailable, and auxiliary variables must use base measures consistent with their discrete or continuous nature. Label ordering, empty classes, coincident splits and non-unique inverse maps are all defined before implementation. Every move logs `move_type`, `reverse_move`, `log_target_ratio`, `log_move_ratio`, `log_aux_ratio`, `log_abs_jacobian` and `log_acceptance_ratio`, and Jacobians are cross-checked by finite differences — a Jacobian of unity does not excuse omitting the move-probability and auxiliary-density factors. Detailed balance follows from pointwise flux equality on the augmented space and does not by itself deliver irreducibility, aperiodicity or a finite mixing time. ⟦C-6 · 03::3.3.3（Eq. 3.3-1/3.3-2/3.3-3）、02::2.3.5.3；BP §3 行 5⟧ The specification follows Green (1995), with proposal construction and model-choice practice as discussed by Brooks et al. (2003) and Hastie and Green (2012).

<!--block:B0149-->
This component is presented at design tier only. No trans-dimensional run exists at any evidence tier in this work, and nothing in this section should be read as reporting one. ⟦C-6 · BP §3 行 5；大纲 §5(c)-3⟧ The contrast is worth making explicit, because trans-dimensional samplers do have a substantial operational record in geophysics — parsimonious trans-dimensional inversion (Malinverno, 2002), reversible-jump seismic tomography (Bodin & Sambridge, 2009), trans-dimensional model assessment (Minsley, 2011), trans-dimensional trees (Hawkins & Sambridge, 2015) and two-dimensional trans-dimensional magnetotelluric inversion (Blatter et al., 2021). That record is cited here so the reader can locate what this work has *not* done; it confers no operational capability on the component specified above. ⟦C-13 · [BIB] #12（校 DOI …01847.x）/#14/#15（校 DOI 撞车已校）/#16/#17；§5(b) 约束 2 反衬功能不得反向使用⟧

<!--block:B0150-->
### 4.6 The diagnostics contract

<!--block:B0151-->
All acceptance criteria come from a single machine-readable source, `validation/wp2-toy/diagnostic-contract.json`. Its required fields are rank-normalised and folded split-$\widehat{R}$, bulk and tail effective sample size, relative Monte Carlo standard error, per-chain modal access (the field exercised by the registered `mode_visits` disclosure of the joint asset, Section 6.4), and the failed-replication rate, evaluated over the declared diagnostic domain of state parameters, reported functionals and the log density. **Thresholds are read at run time from the contract; this paper does not reproduce any threshold value as a source, and cites only the identity of the contract.** ⟦C-7 · 02::2.3.5.7、03::3.6.3；`validation/wp2-toy/diagnostic-contract.json`；BP §3 行 6⟧ The improved rank-normalised diagnostic follows Vehtari et al. (2021).

<!--block:B0152-->
The contract is enforceable through three rules. First, it is a **hard gate**: a run is successful only if every required field passes, and a run that fails any of them is archived as Failed under an immutable record and may only be superseded by a new run identifier after the proposal design has been revised — the gate itself is never relaxed. Second, **acceptance rate is a debugging quantity only**; neither it nor an aggregate effective sample size is admissible as convergence evidence, and neither "the parameters barely moved" nor "the posterior-predictive checks look stable" constitutes a convergence proof. Third, kernel-specific quantities such as divergences, boundary hits, tree depth or energy statistics are separately pre-registered additional diagnostics that remain explicitly unvalidated, because the contract supplies no general thresholds for them. ⟦C-7 · 03::3.6.3、03::3.3 统一诊断规范段、02::2.3.5.7；BP §3 行 6⟧

<!--block:B0153-->
Simulation-based calibration is specified as a validation instrument in Section 6, not a sampler diagnostic here; its contract, including the treatment of ordered scalar ranks, categorical events and the sensitivity of conclusions to the choice of test quantity, follows Cook et al. (2006), Talts et al. (2018, arXiv:1804.06788, preprint) and Modrák et al. (2025). ⟦C-7 · 06::6.3.1；BIB #57/#58/#59⟧

<!--block:B0154-->
### 4.7 Numerical safeguards and adaptation discipline

<!--block:B0155-->
Forward operators are required to expose matrix-free directional derivatives. Explicit Jacobians are not treated as routine assets at scale; each operator implements $Jv$ and $J^\top v$ by discrete adjoint or by verified automatic differentiation, and every implementation is checked by the adjoint dot test $\langle Jv,w\rangle\approx\langle v,J^\top w\rangle$, by a Taylor-remainder convergence-order test, and by a small-scale finite-difference comparison. The per-method `jvp_*` and `taylor_remainder_order` checks that carry this requirement are part of the nine-check synthetic verification matrix reported in Section 7.1. Matrix-free adjoint derivatives and operator-level verification of them are established practice in open geophysical and inverse-problem frameworks (Cockett et al., 2015; Rücker et al., 2017; Villa et al., 2021); the requirement stated here is of that same kind, and is not a statement that this implementation depends on or reproduces any of those packages. ⟦C-14 · [BIB] #89（校 DOI 补登）/#90（校 DOI 补登）/#97；§5(b) 约束 5 不得读作依赖声明；代码包身份归 §11.4⟧ Complexity is accounted separately by physics — direct integration or FFT for potential fields, an elliptic PDE solve per source for DC, a per-source time march for time-domain electromagnetics, and a per-source per-frequency Maxwell solve for frequency-domain methods — and is never collapsed into a single order estimate. ⟦C-9 · 附录 7 §2.1（正锚）；语料 `03::3.7.3`（佐证）；WP8 `wp8-synthetic-completion-v1.json`；BP §3 行 7⟧

<!--block:B0156-->
Normalisation is scale-aware and frozen. Gradients are normalised against a task-scaled denominator in which the reference scale and the absolute and relative protection terms are all fixed before the run, and the implementation is exercised against scale changes, zero-sensitivity inputs, non-finite values and automatic-differentiation cross-checks; the construction is not claimed to suit every gradient algorithm. Compensated summation is registered as a *candidate* safeguard for accumulation-dominated kernels, not a rule, and no uniform error bound is asserted for it — whether to adopt it, or mixed precision, is settled per task by forward error, backward error, throughput, memory and failure rate. For ill-conditioned problems the framework carries no fixed condition-number threshold and no fixed retained-energy rule: regularisation, truncation rank and preconditioner are chosen jointly from problem scale, the error model, hold-out prediction, the reliability of the condition-number estimate and the error budget. ⟦C-9 · 附录 7 §2.1（正锚）；BP §3 行 7⟧

<!--block:B0157-->
Adaptation is confined by contract. Proposal adaptation occurs **only inside a declared warmup phase**, must satisfy diminishing adaptation and containment, and is frozen before production sampling begins; the standard step-size conditions and a single Lyapunov drift inequality are not on their own sufficient to establish geometric ergodicity, and where the additional conditions have not been verified the adaptive scheme is treated as an implementation heuristic, not a guarantee. Any scheme that would continue to modify move probabilities, auxiliary densities or the target on the basis of an observed acceptance rate is excluded from production sampling for the same reason — acceptance rate is not a transferable target across algorithms, and release is decided by the joint check of Section 4.6; no single statistic decides release. ⟦C-8 · 附录 7 §2.3（正锚）；语料 `02::2.3.5.5`、`03::3.3.3` 末段（佐证）；BP §3 适配纪律段⟧ The adaptive-MCMC constructions and their ergodicity conditions are those of Haario et al. (2001), Roberts and Rosenthal (2007) and Andrieu and Thoms (2008). Tuning-free adaptive samplers have also been applied directly to geophysical Bayesian inverse problems (Arabpour et al., 2025); the discipline adopted here is the more restrictive of the two, confining adaptation to a declared warmup and freezing it before production rather than allowing it to continue through sampling. ⟦C-15 · [BIB] #68（校 DOI 10.1007/s12145-024-01599-7，池内原 DOI 系模板化伪造）⟧

<!--block:B0158-->
## 5 Decision-Layer Interface Specification

<!--block:B0646-->
**Specification-only workflow; no observed decision result.**

<!--block:B0647-->
| Stage | Owner | Required inputs | Output / consumer | Quarantine or escalation |
|---|---|---|---|---|
| Evidence admission | Method lead and data steward | Gate-passing posterior asset; units, provenance, licence and diagnostic-contract hash | Admitted evidence record / decision board | Any failed gate or missing contract field is quarantined |
| Scenario definition | Designated exploration decision board | Frozen actions, scenarios, loss definitions and calibrated probabilities | Versioned action–scenario table / audit record | Uncalibrated scores remain descriptive and cannot rank actions |
| Decision computation | Independent analyst appointed by the board | Admitted evidence and frozen action–loss table | Reproducible comparison or `no-decision` / board | Sensitivity conflict or unsupported extrapolation returns to method lead |
| Approval and follow-up | Decision board | Comparison, limitations and dissent record | Approved action or `no-decision` / field-program owner | Field use requires independent validation and the EVD-FIELD-001 entry gate |

<!--block:B0159-->
The framework terminates in a decision layer, but this section specifies its interface and workflow only. The workflow assigns ownership, inputs, quarantine rules, outputs and escalation paths so that a posterior cannot be converted silently into an operational recommendation. It reports no observed decision, calibrated utility, resource estimate or field outcome.

<!--block:B0160-->
### 5.1 Per-draw target-volume scenarios

<!--block:B0161-->
Within each complete joint posterior draw, the mineralisation indicator, voxel volume, density, grade, recovery and the dilution and loss corrections are taken **from that same draw** to compute volume, tonnage, in-situ content and recovered metal. Draws are never broken apart, and these quantities are never reconstructed independently from marginal probabilities, because doing so discards exactly the joint structure the inference was run to obtain. Quantiles are taken only over the set of per-draw totals, and the reporting convention is fixed: $P90=q_{0.10}$, $P50=q_{0.50}$, $P10=q_{0.90}$. The outputs are labelled **geophysics-constrained scenarios**. They are not a resource classification, they do not substitute for one under any reporting code, and no tonnage or grade figure derived from them appears in this paper. ⟦D-1 · 语料 `03::3.4.3` Step 1；WP4 契约；[BP] §5⟧

<!--block:B0162-->
### 5.2 Calibrated event probabilities

<!--block:B0163-->
An event probability (that a hole misses its target, for instance) requires a **frozen event definition** together with isolated training and calibration data; test holes and blind holes are used for evaluation only. An uncalibrated weighted quantity is a **score**, and the specification forbids promoting one to a probability by clipping, rescaling or renaming. This distinction is carried in the field names of the interface, not merely in prose. ⟦D-2 · 语料 `03::3.4.3` Step 2；[BP] §5⟧

<!--block:B0164-->
### 5.3 Three information contracts, kept separate

<!--block:B0165-->
Information gain is recorded under exactly one of three types, separated by time point and conditioning set:

<!--block:B0166-->
$$
\operatorname{EIG}(a)=\mathbb{E}_{p(y\mid a,D_0)}\,D_{\mathrm{KL}}\!\left[p(\psi\mid y,a,D_0)\,\Vert\,p(\psi\mid D_0)\right],
\tag{5.1}
$$
$$
\operatorname{RIG}(y_{\mathrm{obs}};a)=D_{\mathrm{KL}}\!\left[p(\psi\mid y_{\mathrm{obs}},a,D_0)\,\Vert\,p(\psi\mid D_0)\right],
\qquad
L_k^{\rightarrow}=D_{\mathrm{KL}}\!\left[p(\psi\mid D)\,\Vert\,p(\psi\mid D_{-k})\right].
\tag{5.2}
$$

<!--block:B0167-->
The first is a design quantity evaluated before $y$ is observed; the second is realised gain after observation; the third is a leave-one-method-out forward divergence. Every record fixes the target $\psi$, the baseline and conditioning set, the direction of the divergence, the common support, the estimator, the replication count and the Monte Carlo standard error, and nested estimators additionally report outer design-sampling error, inner evidence-estimation error and failure rate. **The three are not additive.** They may not be summed, they may not be normalised into "contribution rates", and they do not constitute a ranking of method importance; reverse-direction leave-one-method-out is a different quantity and is recorded separately. The design-theoretic framing follows Chaloner and Verdinelli (1995) and its modern treatment by Rainforth et al. (2024); the framework claims no methodological novelty in this area and uses these sources to fix definitions. ⟦D-3 · 语料 `03::3.4.2`（Eq. 3.4-1/2/3）；[BP] §5；D-5 · [BIB] #41/#45（校 DOI 10.1214/23-STS915，页码 100–114）⟧

<!--block:B0168-->
### 5.4 Decision-theoretic contract

<!--block:B0169-->
Under a single state–action–cash-flow contract, cash flows are constructed per draw over a fixed action set, itemising survey and implementation cost, failure loss, capital and operating cost, price, tax, recovery and salvage. Net present value and its expectation follow, together with the expected value of perfect information and of sample information, with **survey cost deducted exactly once** in net-EVSI. Risk preference enters as an explicit frozen input,

<!--block:B0170-->
$$
\mathrm{ENPV}_\gamma=\mathrm{ENPV}-\gamma\,\sigma(\mathrm{NPV}),\qquad \gamma\ge 0,
\tag{5.3}
$$

<!--block:B0171-->
a mean–standard-deviation criterion in which $\gamma$ carries whatever units make $\gamma\sigma(\mathrm{NPV})$ commensurate with ENPV. There is no cross-project typical range for $\gamma$, and the criterion does not license labelling a decision-maker risk-averse or risk-seeking; where $\gamma$ has not been elicited and calibrated, only a scenario analysis over a $\gamma$ grid is reported. Decision thresholds are endogenous, following from equality of expected loss between actions; no fixed cut-off is used. The value-of-information framing follows Howard (1966), with the earth-science and petroleum treatments of Eidsvik et al. (2015) and Bratvold et al. (2009); here too the contribution is interface specification, not method. ⟦D-4 · 语料 `03::3.5.2`（Eq. 3.5-1/3.5-2）；[BP] §5；D-5 · [BIB] #46/#48（校 DOI 10.1017/CBO9781139628785）/#47⟧

<!--block:B0172-->
### 5.5 Quarantine

<!--block:B0173-->
No quantity defined in this section is reported as a result. No expected-information-gain or expected-value-of-sample-information number is stated, and no resource, reserve, tonnage or investment figure is stated or implied. Failed diagnostics, uncalibrated scores, and records missing units, provenance or licence terms remain quarantined and cannot enter an action comparison. The illustrative values in Appendix B are labelled "synthetic placeholder, not evidence". The interface is specified and uncalibrated; it was not exercised in this work.

<!--block:B0174-->
## 6 Validation Design and Registered Evidence

<!--block:B0175-->
This section states what would count as evidence in this work before any of it is reported. It has two jobs. The first is bookkeeping: to fix the tier system, to enumerate exactly which registered assets the paper is permitted to draw on, and to state the protocol that was pre-registered for the validation the framework prescribes. The second is less usual and is the reason the section is placed before the Results: a pre-registered diagnostics regime is one of the four ingredients whose conjunction this paper claims, and a claim of that kind is only worth as much as the evidence that the regime does something. That evidence is supplied here, in the form of results this regime produced about itself — results that are derivable from definitions, that hold independently of any run we performed, and that are stated in a form other groups can apply to their own gates. ⟦V-1 · [ES]；[MAP03]；[BP] §4.1；本节主张形态 = 治理（甲类落点，见交付注记 3）⟧

<!--block:B0176-->
### 6.1 Evidence tiers and the registration regime

<!--block:B0177-->
Every quantitative statement in this paper is bound to a row of a hash-bound evidence registry, and every row carries a tier. Five tiers are used. **Design-assumption** covers quantities fixed by declaration (discretisations, geometries, noise floors, thresholds) which constrain what may be computed but assert nothing about the world. **Hypothesis** covers constructs that are specified and implemented but not validated, among them the petrophysical priors of Section 3.3. **Synthetic-run** covers quantities produced by a completed, registered run on synthetic data under a frozen configuration. **Open-data-run** covers audits performed on published data holdings. **Field-validated** is defined so that the register can record its absence: **no row of this work's registry carries it, and no claim in this paper is made at that tier.** ⟦V-1 · [ES]；[RR] §7.1 首段（证据天花板声明句 = 受保护文本，[OUTLINE] §0.5 第 3 项）；[BP] §4.1⟧

<!--block:B0178-->
The registry is enforceable through three disciplines. Registration precedes reporting: an asset acquires a tier only when a completed run, its manifest, its input and code hashes and its diagnostics record are all present, and design approval is explicitly not a status upgrade. Failure is archived, never overwritten: a run that fails the diagnostics gate is retained immutably as `Failed`, with its outputs and its provenance intact, and may be superseded only by a new run identifier after the design has been revised — the precedent that fixed this rule, and the failure package it preserved, are reported in Section 7.3. And amendment is versioned: any change to a frozen design requires a new version number, a revision record and re-approval, so that the state of the instrument at the time of any run is recoverable. The AI-agent provenance of this pipeline, including the parts of it that produced the governance record itself, is disclosed in the Declarations, under AI-use disclosure; the two disclosures are cross-referenced so that readers can audit the provenance of the governance record itself. ⟦V-1 · [ES]；[PREREG] 冻结纪律段 + §6 失败纪律；[WP] §4.1 落点（C-1 交叉引用一句）；[BP] §4.1⟧

<!--block:B0179-->
A gate item must be able to fail, and this has to be demonstrated explicitly. The regime described above governs *whether* a criterion is applied and *when* it may be changed; it says nothing about whether the criterion discriminates. That gap is not hypothetical, and this work found one instance of it in its own instrument. One item of the joint diagnostics gate is an operationalised substitute: the diagnostics contract requires a per-chain modal-access field whose literal specification presupposes a multimodal target, whereas the synthetic asset of Section 6.4 is registered as a unimodal design, so the pre-registration replaced the field with a surrogate (each chain's post-warmup mean log-density must lie within $k$ pooled standard deviations of the grand mean) and made disclosure of that substitution, and of its reason, a condition of approval. ⟦V-8/V-9 · [PREREG] §5 D-E1 与其批准条件 2（逐字：run-manifest 与论文披露该字段的操作化替代及理由）；实现 `src/geodeepbayes/benchmarks/joint_block.py` L551–566 与其 docstring；契约身份 `validation/wp2-toy/diagnostic-contract.json`⟧

<!--block:B0180-->
That surrogate has a closed-form ceiling. For $M$ chains of $n$ post-warmup draws, with the pooled standard deviation taken over the flattened sample, the criterion's own statistic is bounded by a quantity that depends on the configuration alone:

<!--block:B0181-->
$$
\max_i\ \frac{\bigl|\bar{x}_i-\bar{x}\bigr|}{s}
\ \le\ R^{*}(M,n)=\sqrt{\frac{(M-1)(Mn-1)}{Mn}}\ \xrightarrow[n\to\infty]{}\ \sqrt{M-1},
\tag{6.1}
$$

<!--block:B0182-->
and the bound is attained, not merely approached, at the configuration in which the within-chain variances vanish and the chain means are maximally spread. The limiting form $\sqrt{M-1}$ is a supremum that finite $n$ never reaches; the finite-$n$ value is the one that decides the question. With $k=3$ and $M=4$ (the frozen chain count of this work) the bound is $\sqrt{3}\approx1.7321$, which is $0.5774$ of the threshold, a constant margin of $1.7321\times$ that no data can consume. Setting $R^{*}(M,n)>k$ and clearing denominators gives $(M-1)(Mn-1)>k^{2}nM$, which at $k=3$ holds if and only if $M\ge11$, **and this threshold is independent of $n$**. The chain length is not a lever on it: at $M=4$, doubling the post-warmup length from $4000$ to $8000$ draws moves the bound from $1.731997$ to $1.732024$ (a change in the fifth decimal place, against a threshold of $3$) and no length whatever brings the two together. **The independence is exact, not asymptotic**: at $M=11$ the bound already exceeds the threshold at the shortest chain there is, $R^{*}(11,1)=3.0151>3$, so a system adopting a criterion of this form can settle the question once from its chain count alone and need not recheck it when the chain length changes. At $M=10$ the finite-$n$ bound is $2.99996<3$, so the item passes strictly and the conclusion does not turn on whether the comparison is written $\le$ or $<$. **The item therefore cannot fail in this configuration, and no property of the sampler, the target or the data can make it fail.** One qualification belongs with the result and is not a detail: the argument assumes the log-density values are finite. A single non-finite value makes the pooled standard deviation undefined, every comparison false, and the item fail — so the domain in which "cannot fail" holds is $M\le10$ *together with* finite inputs, and both conditions must be declared, not just the first. **The two conditions are not of the same kind, and the difference is the point taken up below**: the chain count decides whether the item can fail at all, whereas the finiteness of the inputs decides which way it fails. ⟦V-1 · 甲类 A-1；判据形态 = `joint_block.py` L551–566（逐字：`in_domain = np.abs(chain_means - grand) <= 3.0 * pooled_sd`）、L588 `all(v == 1 …)`；`N_CHAINS = 4` 同件 L76；推导与数值见**附录 F**；有限性条件 = `v13-hard-gate-clauses-draft.md` §5-HG(7) E-2⟧

<!--block:B0183-->
The correction is not that the gate misjudged anything. It never did: the item returned the right answer on every input it ever saw, and a reader auditing the runs would find nothing wrong, because there was nothing wrong to find. What was wrong was the impression — a conjunctive gate that reports five satisfied conditions invites the reading that five things were checked. **A defect of this kind is invisible to any pass/fail audit, precisely because the verdicts are correct.** The rule it forced us to write is the one we propose for reuse:

<!--block:B0184-->
> **Gate-item admission.** A gate item is registered with a configuration in which it can fail. If no such construction can be exhibited, it is retained only as disclosure; failure to construct is not proof of impossibility. The archived construction records the criterion, threshold source, admissible domain and configuration because discriminating power is a property of both the criterion and that configuration. Non-finite input, a non-finite derived diagnostic, or a finite degenerate channel is outside the admissible passing domain and triggers a structured fail-closed stop; no aggregation may discard that channel. Each run records admitted-channel counts and the stop reason, and no endpoint is interpreted after a diagnostic stop.

<!--block:B0185-->
Three properties of this rule are worth separating from the case that produced it. It is falsifiable in the direction that matters — a group applying it either can exhibit the failing input or cannot. It is configuration-relative, which means it must be re-adjudicated when a configuration changes; it cannot be inherited as a settled verdict. And it applies to the instruments that check compliance, not only to the gate items they check: a detector whose sensitivity has never been established returns negatives that are indistinguishable from absence, which is the same mechanism one level up. This pipeline therefore requires every checking script to carry a positive control (an input known to trigger it) before any negative result from it is treated as evidence. **We applied that requirement to the compliance checks used on this section and it caught one probe that could not match its target and had been returning clean**; the diagnosis is recorded with the section's own verification record. None of these three properties depends on anything specific to this work. ⟦V-1 · 治理构件 M-GATE-1 的自指施用；扫描纪律出处 = [WP] §3.3 逐字「检查脚本须带阳性对照（对已确认命中的字段断言），防空跑假绿」；同族第三实例（扫描的阴性结论）= `v13-hard-gate-clauses-draft.md` §7.1 表第 3 行；本文只述规则与「已抓到一处」，实例细节留过程注记⟧

<!--block:B0186-->
A related edge case concerns a channel that is exactly constant across draws and chains. For such a channel the within-sub-chain variance and the between-sub-chain variance are both zero in exact arithmetic. The usual split-$\widehat{R}$ ratio is therefore undefined; it is not equal to $\sqrt{(n-1)/n}$.

<!--block:B0188-->
A numerical implementation may omit the channel or may return a near-unit value if ranking, averaging, or floating-point arithmetic introduces a tiny non-zero within-chain variance. That behaviour is implementation-dependent and cannot be promoted to a universal analytic identity. For this paper, no convergence conclusion is drawn from $\widehat{R}$ on a zero-variation channel; an explicit movement or variance check is required to distinguish convergence from non-movement. Appendix F.4 states this boundary.

<!--block:B0189-->
The regime also has to say **when a pre-registered criterion may be amended at all**, and the same case supplies the answer in an unusually clean form. Removing an always-true conjunct from a conjunctive gate changes no verdict (not one already recorded, and not one that will be recorded later) so the amendment is, in its effect on decisions, exactly nothing. The constraint on it is therefore purely temporal: **it must land before the first pass appears.** Once a run has passed, the fact that the criterion was touched afterwards contaminates that pass regardless of whether the change loosened or tightened anything, because the objection is not to the change's substance but to its position in time. This is the operational boundary of the registration regime, and it is worth stating in the general form: *a criterion may be amended freely while no result depends on it, and the window closes at the first result, not at the first material change.* ⟦V-1 · 甲类 A-9（布尔代数 + 时序约束）；`v13-hard-gate-clauses-draft.md` §4 逐字「故本条的约束力来自时序，不来自改动的实质」；[PREREG] 冻结纪律段（新版本号 + 修订记录 + 重新批准）⟧

<!--block:B0190-->
### 6.2 The registered evidence this paper may use

<!--block:B0191-->
Four assets are registered at a tier that permits quantitative statements, and the paper draws on those four and no others. Assets that exist in the wider governance record but are not registered at a reportable tier (the petrophysical, benchmarking and cost-model lines among them) are excluded from this paper entirely, including from illustrative use. Table 3 reproduces the allowance, and its fourth column is not commentary: **it is the wording boundary each row is registered with, and a statement outside it is outside the evidence.** ⟦V-2 · [BP] §4.1（四行限额表，逐字）；[RR] §7.1；禁令 6（限额表外注册证据禁止入文）⟧

<!--block:B0192-->
**Table 3.** Registered evidence and the wording boundary attached to each row.

<!--block:B0193-->
| Claim the paper can make | evidence_id | Tier | Allowed wording boundary |
|---|---|---|---|
| All nine method forward operators and their adjoints pass a pre-registered synthetic verification protocol (nine checks, including reference agreement, adjoint consistency, Taylor-remainder order, three-level convergence, an adversarial suite, and within-method SBC with at least 400 replicates) | WP8 (`validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json`) | Synthetic-run | Per-method only; `field_validated=false` for all nine; TEM scoped to 1D-layered; must co-disclose the WP8-0 formal field feasibility result of 6/9 and the 2026-07-26 completion-policy renegotiation |
| Full-dimensional delayed-acceptance MCMC on a 48-dimensional bimodal target meets the joint diagnostics contract (registered values in §7.2) | EVD-ALGO-002 (`validation/wp7/versions/synthetic-block-v6-20260724`, `src/geodeepbayes`) | Synthetic-run | Generic, non-geophysical target; the 400-replicate same-target coverage study is frequentist same-truth coverage, **not** SBC; point estimates below nominal, reported as statistically consistent with nominal, slightly under |
| DO-27 reduced-order single-physics (gravity and magnetic) modern-API compatibility runs with GCV/LSQR | EVD-SYNTH-001 (`validation/wp7/versions/do27-v4-20260724`) | Synthetic-run (limited compatibility) | Mandatory co-disclosure: v2 failure package immutable; low RMS is an overfit warning; magnetic model recovery FAILED; not PGI, not joint, not Bayesian, not a notebook reproduction |
| Open geophysical data ingestion and integrity audit (a 184-file geophysics manifest and a 421-file MT manifest, SHA-256 and format checks) | EVD-OPEN-001 (`validation/runs/open-data-20260717-03`) | Open-data-run | Data-governance boundary only; never upgrades to field validity |

<!--block:B0194-->
Three of the four boundaries carry a mandatory co-disclosure or a mandatory negation, and they are discharged where the corresponding evidence is reported; this section does not repeat them: the verbatim disclosure statements are in Sections 7.1 and 7.3 and are collected in Section 8.5. This section registers the obligation; it does not restate the statements, and it does not summarise them. ⟦V-2 · [BP] §4.1；[WP] §5.1/§5.2/§5.3（逐字句唯一权威落点）；[OUTLINE] §0.6 落点分工；三项共披露汇总落 §8.5，本节不挤占⟧

<!--block:B0195-->
### 6.3 The pre-registered validation protocol

<!--block:B0196-->
What follows is the protocol the framework prescribes. **It is a design, not a report**: nothing in this subsection has an execution status attached, and no quantity defined here is given a value anywhere in this paper except where Section 7 reports a registered run. ⟦V-3 · 语料 `06::6.0` 首部证据状态声明；[BP] §4.2；禁令 2（禁止把协议呈现为已执行结果）⟧

<!--block:B0197-->
Forward-operator regression. Each method is regressed against an independent reference: a closed-form four-electrode potential difference for DC over a half-space; impedance recursion or a half-space closed form for 1D layered MT; an independent step or finite-ramp reference for TEM over a half-space, with waveform convolution; a tightened integral or high-accuracy reference for the CSAMT finite source; and DC end-member closed forms together with complex response references for the WFEM axial array. The oracle and the operator under test may share neither a numerical integration kernel nor a filter table, and results carry the label `Synthetic-run/Reference-regression` and no other. ⟦V-3 · 语料 `06::6.0` 矩阵五行 + oracle 独立性句；[BP] §4.2⟧

<!--block:B0198-->
The unit of statistical replication is the geological scene. Independent scenes drawn from a pre-registered scene-generating distribution are the top-level unit; noise realisations are nested within a scene and algorithm seeds within a scene–dataset–method cell, and neither may inflate the independent sample size. Comparisons are made as within-scene paired differences against a frozen baseline on identical data, and each difference is reported as a point estimate with an interval and compared against a pre-registered minimum important difference $\delta_{\rm MID}$ fixed before unblinding. Confirmatory endpoints declare their family and their multiplicity procedure in advance. **There is no p-value theatre**: intervals and effect sizes are reported in their original units, a failure to reach significance is never reported as equivalence, and no endpoint is reduced to a binary verdict. The scene count for method comparison and the replicate count for calibration diagnostics are budgeted separately and may not be substituted for one another. ⟦V-4 · 语料 `06::6.1` 多场景统计重复设计段、`06::6.3.2` 估计目标/层次配对/效应量/多重性四段；[BP] §4.2；禁令 1（禁 p 值戏台）⟧

<!--block:B0199-->
Four instruments, four contracts, kept apart. Simulation-based calibration randomises ranks only over frozen ordered scalar parameters or permutation-invariant scalar functionals, resolves ties by an explicit discrete-uniform draw, and handles categorical and trans-dimensional targets through frozen semantic events scored by reliability and Brier or log score; arbitrary label indices are not ranked; label switching, empty classes and unmatched states are recorded as failures and retained. Empirical interval coverage is computed separately from SBC ranks: each independent scene contributes exactly one hit indicator per functional and nominal level, the denominator is all pre-registered scenes, and **abnormal termination, non-finite posteriors and missing intervals all count as misses and are never re-drawn**; hits are reported with the difference from nominal and a Wilson or pre-registered hierarchical interval. Posterior-predictive checking freezes its discrepancy, grouping and replication mechanism before unblinding, reports the position of the observed discrepancy within the replicate distribution, and **sets no pass threshold and is never read as parameter coverage**. Continuous-score comparison aggregates nested noise and seeds within a scene before forming scene-level paired CRPS differences, pre-registers the direction and the minimum important difference, and reports paired differences with intervals without declaring a winner. ⟦V-5 · 语料 `06::6.3.1` SBC 合同 / 经验区间覆盖合同 / PPC / CRPS 比较合同四段；[BP] §4.2；文献锚 [BIB] #57 Cook et al. 2006 / #58 Talts et al. 2018（arXiv:1804.06788, preprint）/ #59 Modrák et al. 2025⟧

<!--block:B0200-->
Two adversarial scenarios are pre-registered before any selection. The first reduces the property contrast between target and host rock by 80%, so that the target is one conventional methods would not resolve; the second draws cover thickness, resistivity, lateral heterogeneity and noise covariance from a pre-registered distribution and requires the shared cover error to enter the joint error model, with a calibration ablation against the incorrect conditionally-independent model. Both fix the contrast, noise and target scale before running, both report failure cases, and neither permits a directional conclusion to be written in advance. ⟦V-6 · 语料 `06::6.4`、`06::6.5`；[BP] §4.2⟧

<!--block:B0201-->
### 6.4 EVD-JOINT-001: pre-registered design and registration status

<!--block:B0202-->
The framework's one joint asset is a co-platform gravity–magnetic synthetic experiment, pre-registered and frozen as v1.1 before implementation began. Its purpose is narrow and stated as such: to give the word *fusion* an evidential meaning at the Synthetic-run tier, through three endpoints each of which is capable of returning a negative answer. ⟦V-7 · [PREREG] §1；[BP] §4.4 Option A；[RR] §6.2⟧

<!--block:B0203-->
Scene and observation design. A three-dimensional $10\times10\times5$ tensor mesh with 50 m cells carries density contrast and susceptibility. Independently drawn scenes contain a $200\times200\times100$ m target block with its top between 50 and 100 m depth and a non-overlapping susceptibility-only decoy lens in the upper 50 m. Gravity and magnetic observations share one $6\times6$ nominal station grid; the true positions include a shared latent geometry offset $\xi_g$ with horizontal components over $\pm15$ m and a vertical component over $\pm3$ m, while inference sees only nominal positions. Noise follows the frozen 2% relative-plus-floor model. Generation and inference use the same WP8-verified operator pair. This is therefore an implementation baseline for the registered coupling and shared-nuisance path, not structural-error evidence: the same-kernel reservation applies to every statement from the asset, and no independent-forward or field-like discrepancy arm was run.

<!--block:B0204-->
**Figure 4.** The registered scene and observation design of EVD-JOINT-001: the target block, the susceptibility-only decoy lens, the shared station grid, and the shared station-location systematic term $\xi_g$. Only gravity and magnetic observations belong to this registered asset; no electrical observation channel is part of the design. Dimensions and station spacing are as frozen in the pre-registration. The figure presents a design, not an endpoint result.

<!--block:B0205-->
State, priors and the coupling switch. The state carries both property fields, the shared offset and two noise-scale multipliers. Property priors are proper Gaussian Markov random fields; the structural coupling is the cross-gradient factor of Eq. (3.6) instantiated with frozen dimensionless scales, and **its off-state $\lambda_{gm}=0$ is retained as an independent arm of the comparison, not mentioned as a limiting case**. The coupling strength is not sampled (the cross-gradient factor's normalising constant is intractable, and sampling it would target a biased posterior) so it is frozen by a pre-registered selection rule on a pilot scene family disjoint from the registered scenes, and this is registered as an empirical-Bayes-style freeze with its under-coverage risk disclosed. **Every endpoint conclusion is conditional on the frozen value**, and the guardrail behind that value covers one functional only, so no statement of the form *cross-gradient coupling is safe* is licensed by it. ⟦V-7 · [PREREG] §3（状态 / 先验 / 结构耦合 / λ* 冻结程序 + EB 式冻结披露 + 措辞纪律）；禁令 4（禁 λ*-非条件化结论）⟧

<!--block:B0206-->
Three endpoints, pre-registered in quantitative form. Endpoint (i) compares coupling-on against coupling-off on identical scenes, data and noise realisations — deliberately not joint-against-single-method, which would test only that Bayesian updating works. Three named held-out functionals are fixed in advance (total anomalous mass; the target block's mean susceptibility; its depth to top), each with its own $\delta_{\rm MID}$ justified on physical grounds, not statistical convention, and both the error family and the interval-width family are judged against the same threshold. Endpoint (ii) injects a named misspecification (the shared-geometry block set wrongly to zero) with the response direction and the minimum detectable magnitude pre-registered, and with the pre-registered ranking to be disclosed alongside the observed one if the two disagree. Endpoint (iii) reports scene-replicated empirical interval coverage against a Wilson interval at each nominal level. Table 4 gives the skeleton.

<!--block:B0207-->
**Table 4.** Pre-registered endpoint skeleton. Every threshold is fixed before unblinding; no cell is filled from data.

<!--block:B0208-->
| Endpoint | Reported quantity | Minimum important difference | Decision rule |
|---|---|---|---|
| (i) Coupling increment — F1, total anomalous mass | Per-scene paired difference of errors and 90% interval width between coupling-on and coupling-off | 0.10 × the scene's true value | Interval wholly above $+\delta_{\rm MID}$: important improvement; wholly within $\pm\delta_{\rm MID}$: no practically important increment; otherwise indeterminate. Holm adjustment across three functionals; $N=100$ scenes |
| (i) — F2, mean susceptibility of the target block | As above | 0.20 × the scene's true value | As above |
| (i) — F3, depth to top of the target block | As above | 50 m, one cell height | As above |
| (ii) Misspecification response | Paired displacement of the per-method weight trajectory and pair-level tension statistic | Pre-registered minimum detectable amplitude; injected-amplitude-ratio design target at least 2 | The registered direction is a falling weight for the misspecified method and a rising pair-level tension statistic; a mismatch is reported as a negative result |
| (iii) Joint empirical coverage | Per-level hit rate over independent scenes and the joint indicator across all three functionals | No minimum threshold | Nominal level inside the Wilson 95% interval is described as consistent with nominal; otherwise the direction and interval are reported. Abnormal exit, non-finite posterior, or gate failure counts as a miss |

<!--block:B0645-->
Endpoint (ii) is limited to the registered nested injection and is optimistic relative to unstructured real-world misspecification. Endpoint (iii) is scene-replicated frequentist coverage over the registered scene-generating distribution; it is neither simulation-based calibration nor the same-truth coverage study reported for EVD-ALGO-002.

<!--block:B0209-->
The metric form of endpoint (i), and why both forms are disclosed. Endpoint (i)'s decision quantity is a paired difference of *absolute* errors against the held-out truth. Write $b$ for the uncoupled arm's signed error and $\delta$ for the displacement the coupling produces. Then for $b\neq0$,

<!--block:B0210-->
$$

<!--block:B0211-->
|b+\delta|-|b| \;=\; \operatorname{sign}(b)\,\delta \;+\; 2\max\!\bigl(0,\ -\operatorname{sign}(b)\,\delta-|b|\bigr),

<!--block:B0212-->
\tag{6.2}
$$

<!--block:B0213-->
an identity whose first term depends only on the displacement and whose second is non-negative and vanishes unless the displacement carries the error across zero. Three consequences follow and are stated because they bound how the endpoint may be read. First, the second term's sign gives a one-directional containment: **the absolute form can never be more permissive than the signed form, only stricter.** This is a bound on the two forms, not a statement about how they behave on any particular dataset, and no such comparison is claimed here. Second, the endpoint's own question (did coupling land closer to the truth) is answered affirmatively exactly when $\delta$ lies strictly between $0$ and $-2b$, so there are two ways for the quantity to stop being informative about coupling: if $|b|\le|\delta|/2$ the window collapses and *beneficial* becomes unreachable, and if $|\delta|>2|b|$ the displacement overshoots and a move toward the truth is scored as harmful. Both are statements about the relative size of $b$ and $\delta$, not about coupling; **we do not assert that this work's scenes fall inside or outside that window.** Third, at $b=0$ the two forms are both empty of information and fail in opposite directions — the absolute form reduces to $\overline{|\delta|}\le0$ and admits nothing, the signed form reduces to $0\le0$ and admits everything. **That is precisely why neither form replaces the other.** The absolute form is retained as the decision quantity because it is the one that answers the endpoint's question; the signed form is disclosed beside it because it answers a different question (the direction and size of the displacement) and because the truth cancels from it exactly, making it immune to the choice of truth convention for the functional. Parallel disclosure costs one column and no additional run. The algebra is in Appendix F. ⟦V-7 · 甲类 A-2 / A-3 / A-8 / A-4，A-5 一行推论（代数落附录）；[PREREG] §4 端点(i) 报告形式（Δ_e 误差族）与 §3 λ* 护栏（同款绝对式）；A-3 配对纪律的处置见自查表与交付注记 5⟧

<!--block:B0214-->
Blinding, failure discipline and diagnostics. Blinding is enforced by hashes under a single operator working in separated roles: the scene generator freezes truths, noise and seeds and emits a hash; the inference executor sees only observations and nominal positions; the evaluator unblinds the truths and computes the pre-registered metrics; the auditor reconciles seeds, failed replicates and the evidence manifest. All acceptance thresholds are read at run time from the diagnostics contract of Section 4.6, which this section does not reproduce. The gate is conjunctive and hard (a run succeeds only if every required field passes) and a run that fails any field is archived immutably as `Failed` and may be superseded only by a new run identifier after the proposal design has been revised. **The gate is not relaxed to admit a run.** ⟦V-8 · [PREREG] §5（采样器与诊断）、§6（盲态程序、失败纪律）；[RR] §6.4；§4.6 契约身份单源⟧

<!--block:B0215-->
Registration status. The following is the state of the asset as this paper reports it; the quantities are in Section 7.5 and are not duplicated here. The registered pilot was conducted under v1.1; v1.3 became the approved frozen design on 2026-08-22. The implementation is delivered and tested, and one implementation defect was found by a calibration probe, pinned analytically and statistically, fixed, covered by new regression tests, and archived with its pre-fix probe retained as `Failed` and its posterior quantities voided. The registered pilot then **failed the diagnostics hard gate on every replicate**, which is the pre-registered failure path, not an anomaly, and the binding constraint was the effective-sample-size field. Because every input run to the coupling-strength selection rule failed the gate, the rule's eligible candidate set was **empty**, and the pre-committed empty-set branch was executed as written: the pilot was registered as a negative result, the mechanically selected value was recorded as a diagnostic reading only, the full-scale production run was suspended, and the outcome was returned to the user for decision. A redesign was ruled; its execution remains staged. **Consequently EVD-JOINT-001 remains registered as `Planned`, no endpoint result is reported anywhere in this paper, and every endpoint statement in this section is a description of a design.** ⟦V-9 · [PREREG-v1.3] §0.10、§5.3、§§10.1–10.3（现行冻结身份、分阶段执行与 Planned 边界）；[M1] §1–§6；[M2] §1–§3 + v2 章（历史 pilot）；[M2.5] 首部（历史裁定）；**与 §7.5「现状可写块」共用同一份状态文本源，读数单源落 §7.5**；Diagnostic 探针读数按 §7.5 禁令 10 不入文⟧

<!--block:B0216-->
Two of this section's own results bear on that outcome and are stated plainly, because reporting them as contributions while omitting that they are defects would be the wrong reading, and reporting them only as defects would be equally wrong. The gate that has not been passed is a conjunction whose *other* items are the ones that fail; the item analysed in Section 6.1 is the one item that has never failed and, in the frozen configuration, cannot. **The instrument was weaker than its own report form suggested, and we established that analytically without running it.** That is a limitation of the instrument and a result about instruments of that shape, and both readings are correct at once. The same holds for the metric-form analysis of endpoint (i): it identifies conditions under which the endpoint's decision quantity stops carrying information about coupling, and it is the reason the endpoint now discloses two quantities where it previously disclosed one. Neither finding was produced by a run, and neither depends on one. ⟦V-1/V-9 · 甲类 A-1 / A-2–A-8 的地位陈述；`analytic-findings-round2.md` §4 第 (3) 条分寸论证；本段不与 §8.5 三项强制共披露并列计数（见 §0.4 相邻风险）⟧

<!--block:B0217-->
Under v1.3, the pre-registered co-platform gravity–magnetic synthetic scenes, observation geometry, noise model, and same-kernel designation, including the inverse-crime caveat, remain unchanged. ⟦V-7/V-9 · [PREREG-v1.3] §0.10；§5.2⟧

<!--block:B0218-->
Execution is staged. ⟦V-9 · [PREREG-v1.3] §§10.1–10.2⟧ A Diagnostic-only attainability screen uses the registered baseline as a scaling reference and evaluates pCN and MALA on s02 at λ = 1000 under the registered draw-scaling schedule; qualifying arms receive the conditional s00 pressure control, which neither enters scaling extrapolation nor overturns the s02 decision. ⟦V-9 · [PREREG-v1.3] §10.1（R1）⟧ R2 may begin only if the pre-registered screen is passed; otherwise, any dimensional reduction or gate/contract change must be escalated rather than introduced silently. ⟦V-9 · [PREREG-v1.3] §§10.2–10.3⟧

<!--block:B0219-->
The formal 42-run re-pilot comprises 30 λ-grid runs (s00–s04 × λ ∈ {0, 1, 10, 100, 1000, 10000}), two adaptive-Metropolis arms, and ten weighted arms. Each run uses four chains, and `n_draws` follows the empirical R1 scaling slope. ⟦V-9 · [PREREG-v1.3] §10.2（R2）；§10.1-A⟧

<!--block:B0220-->
A run clears the convergence hard gate only if `rhat`, `bulk_ess`, `tail_ess`, and `relative_mcse` jointly satisfy the registered contract on all 1,009 channels: 1,005 state parameters, F1–F3, and log density. ⟦V-8/V-9 · [PREREG-v1.3] §5-HG(1)；§5.2⟧

<!--block:B0221-->
If any channel is excluded as non-finite (`n_channels_nonfinite > 0`), the separate guard marks all four diagnostic readings unusable, bars their use in any decision, early-exit criterion, or scaling extrapolation, and requires fail-closed termination and escalation. ⟦V-8/V-9 · [PREREG-v1.3] §5-HG(3)-bis⟧

<!--block:B0222-->
For the analytic reason registered in pre-registration Appendix E.1, `mode_visits` remains a mandatory run-level disclosure, including its operational fields, the surrogate rationale, and the analytic upper-bound-to-threshold ratio at the registered chain count. ⟦V-8/V-9 · [PREREG-v1.3] 附录 E.1；§5-HG(2)–(3)⟧

<!--block:B0223-->
The run identifier, criteria, frozen input manifest, and `environment_hash` must be frozen before execution so that their temporal precedence over run output is auditable and outcome-conditioned specification is prohibited. ⟦V-8/V-9 · [PREREG-v1.3] §5.3；§§10.1-E、10.4⟧

<!--block:B0224-->
EVD-JOINT-001 remains `Planned`; this paragraph records registered design obligations, not run or endpoint results. ⟦V-9 · [PREREG-v1.3] §0.10；§5.3⟧

<!--block:B0226-->
## 7 Results

<!--block:B0227-->
This section reports the registered evidence and nothing else. **Every quantitative statement below is bounded at the Synthetic-run tier, and no field validity is claimed anywhere**; the tier system and the registry that enforces it are described in §6.1, and the four rows of registered evidence this paper is permitted to draw on are listed in §6.2, Table 3. ⟦[ES]；[RR] §7.1 首段（**受保护文本**，[OUTLINE] §0.5 第 3 项）；§6.1/§6.2 指针⟧

<!--block:B0228-->
The section is organised by evidence identifier, not theme, one subsection per registered asset, and **each subsection carries its own wording boundary** — the boundary registered with that asset, not a general disclaimer applied at the end. A reader checking a claim against its permitted scope will find the two adjacent. Two of the four assets carry a mandatory failure co-disclosure; those are reported in full within their own subsections, at §7.1 and §7.3, and are collected again in §8.5. ⟦大纲 §8.0 逐字（「按 evidence_id 分节；每节自带措辞边界」）；[BP] §4.1；[WP] §5.1/§5.2 落点分工⟧

<!--block:B0229-->
One asset is reported without results. The joint synthetic experiment of §6.4 has been designed, implemented and piloted, and the pilot returned a registered negative result; no endpoint outcome exists. §7.5 reports that status. **Nothing in this section should be read as a demonstration of fusion behaviour.** ⟦[PREREG] 首部状态机（`Planned`）；[CP1] D2 绑定；**回填前不得含 Fusion 演示措辞**⟧

<!--block:B0230-->
### 7.1 Per-method forward-operator verification (WP8)

<!--block:B0231-->
The framework's forward operators were verified method by method against a pre-registered synthetic protocol before any of them was used in a joint setting. Nine method families were covered (gravity, magnetic, DC resistivity, time-domain IP, spectral and frequency-domain IP, transient electromagnetics, magnetotellurics and audio-magnetotellurics, controlled-source audio-magnetotellurics, and wide-field electromagnetics) and each was required to pass the same set of nine checks. The checks combine agreement against an independent reference prediction, a misspecification-detection case, two derivative checks (a finite-difference comparison of the directional derivative, and the adjoint dot test relating $Jv$ to $J^\top v$), a Taylor-remainder convergence-order test, a three-level discretisation-convergence test, a per-method adversarial suite, within-method simulation-based calibration at no fewer than 400 replicates, and a within-method performance case on a fixed small grid. All nine methods carry the same nine checks and the same recorded outcome. Tables 5 and 5a give the conservative joint-graph mapping and the per-method matrix, respectively. ⟦7.1-1 · `wp8-synthetic-completion-v1.json`（九方法名与九检查名逐字读自 `methods[].method` 与 `methods[].required_checks`；`required_checks` 九方法完全一致，已机核）；[BP] §4.1 行 1⟧

<!--block:B0232-->
The two views below separate interface scope from test breadth.

<!--block:B0648-->
**Table 5. Conservative mapping from verified method components to the joint-graph interface.**

<!--block:B0649-->
| Method | Observable and unit | Property support | Exercised shared nuisance / coupling | Evidence tier |
|---|---|---|---|---|
| Gravity | anomaly, mGal | 3-D cell density contrast, g cm^-3 | shared geometry $\xi_g$ and cross-gradient only in failed gravity–magnetic pilot | Synthetic-run component |
| Magnetic | total-field anomaly, nT | 3-D cell susceptibility, SI | shared geometry $\xi_g$ and cross-gradient only in failed gravity–magnetic pilot | Synthetic-run component |
| DC | voltage, V | 3-D cell log-conductivity, S m^-1 | none exercised jointly; specification-only | Synthetic-run component |
| TDIP | secondary voltage, V | 3-D cell chargeability | none exercised jointly; specification-only | Synthetic-run component |
| SIP/FDIP | complex voltage, V | Cole–Cole parameters on verified 1-D or 2-D/2.5-D variant | none exercised jointly; specification-only | Synthetic-run component |
| TEM | vertical dB/dt, T s^-1 | 1-D layered log-conductivity, S m^-1 | none exercised jointly; 3-D path unverified | Synthetic-run component |
| MT/AMT | impedance, V A^-1; tipper dimensionless in 3-D | layered or cell log-conductivity, S m^-1 | none exercised jointly; specification-only | Synthetic-run component |
| CSAMT | Ex, V m^-1; Hy, A m^-1 | 3-D cell log-conductivity, S m^-1 | none exercised jointly; specification-only | Synthetic-run component |
| WFEM | Ex/Ey, V m^-1 | 3-D cell log-conductivity, S m^-1 | none exercised jointly; specification-only | Synthetic-run component |

<!--block:B0650-->
Private noise parameters remain method-specific unless a named asset states otherwise. Petrophysical cross-property links remain Hypothesis-tier, and unexercised shared nuisance terms are `unknown` rather than inferred from the graph.

<!--block:B0233-->
**Table 5a.** Per-method synthetic verification. All nine methods carry all nine checks; no method carries field validation.

| Method family | Checks required | Recorded status | `field_validated` |
|---|---|---|---|
| Gravity | 9 | Synthetic-validated | false |
| Magnetic | 9 | Synthetic-validated | false |
| DC resistivity | 9 | Synthetic-validated | false |
| Time-domain IP | 9 | Synthetic-validated | false |
| Spectral / frequency-domain IP | 9 | Synthetic-validated | false |
| Transient electromagnetics | 9 | Synthetic-validated | false |
| Magnetotellurics / AMT | 9 | Synthetic-validated | false |
| Controlled-source AMT | 9 | Synthetic-validated | false |
| Wide-field electromagnetics | 9 | Synthetic-validated | false |

<!--block:B0234-->
The two matrices have different roles. Table 5 maps each component conservatively into the joint-graph vocabulary, while Table 5a reports per-method breadth. Each verification row remains Synthetic-run evidence for an operator in isolation; `field_validated` is false for all nine, TEM is limited to the verified one-dimensional layered path, and petrophysical priors remain Hypothesis-tier. Only the gravity–magnetic pilot exercised a shared geometry nuisance and cross-gradient coupling, and that pilot failed its diagnostics gate. Every other shared nuisance or cross-method coupling entry is specification-only or `unknown`, not an inferred joint capability.

<!--block:B0235-->
Mandatory co-disclosure. Two facts are registered with this asset and are reported here in full. From the specification's revision record: *the user changed the WP8 completion policy to synthetic-validation completion, explicitly forbidding a block on the grounds of absent field data; the field 6/9 result remains a non-blocking audit fact; once the nine synthetic gates pass, WP8 completion and WP9 start are permitted, while labelling that result `Field-validated` is permanently forbidden.* The 6/9 figure is an audit fact that has not been eliminated, and the policy change is a user-authorised governance event rather than a technical pass. The completion of this work package is therefore a decision taken under a stated policy, not a threshold that was met; a reader who wants to discount the matrix on that basis has been given what they need to do so. ⟦7.1-3 · **披露 2 逐字**——英译**逐字复用** `sec8-5-limitations.md` 现有副本（**字符级比对已执行，结果见自查**）；中文正典 [WP] §5.2；出处 = 同 JSON 的 `formal_field_feasibility` 字段（`passed_methods: 6` / `total_methods: 9` / `wp8_1_allowed: false`，实测）+ `spec-wp8-…md:133` + `wp8&wp9执行计划.md:10`；[SYN] §5-2；禁令 2⟧

<!--block:B0236-->
### 7.2 Algorithm-correctness study (EVD-ALGO-002)

<!--block:B0237-->
The delayed-acceptance sampler specified in §4.3 was exercised in full dimension on a **generic, non-geophysical** 48-dimensional bimodal target, and it meets the joint diagnostics contract of §4.6. The registered values are a maximum rank-normalised $\widehat{R}$ of 1.00374, a minimum bulk effective sample size of 2496, a minimum tail effective sample size of 1963, and a maximum relative Monte Carlo standard error of 0.0202. **These are the only diagnostic values reported anywhere in this paper for this asset**; §4.3 and §4.6 point here and do not restate them. Figure 5 summarises their distribution. **These four are reported under a conservative rounding rule: a minimum is rounded down and a maximum is rounded up, so that the reported value is never better than the measured one.** Full-precision values are in the registered run record. ⟦**取整规则单源落点 = 此处正文**（不在注记里，团队 2026-08-22 明令）；实测全精度 `max_rhat` 1.0037398 / `min_bulk_ess` 2496.4620 / `min_tail_ess` 1963.6081 / `max_relative_mcse` 0.0201222 → 报 1.00374 / 2496 / **1963** / **0.0202**；**理由**：这四值的读者用途是核门，**四舍五入会让一半取整朝「看起来更容易过门」偏**；**改前原文逐字存档于 `stage2-writing/_rounding-fix-archive-2026-08-22/`**⟧ ⟦7.2-1 · [MAP03] EVD-ALGO-002；`validation/wp7/versions/synthetic-block-v6-20260724`；[RR] §7.1-1；**单源化裁定（team lead 2026-08-20）：四值唯一落点 = 本节**；图 5 挂钩点⟧

<!--block:B0238-->
**Figure 5.** Convergence and effective-sample-size diagnostics for the algorithm-correctness study, together with frequentist same-truth coverage at nominal levels 0.90 and 0.95. Coverage counts are 358/400 and 378/400. Error bars are two-sided 95% Wilson score intervals without continuity correction: [0.861, 0.921] and [0.918, 0.963], respectively. This is not simulation-based calibration. Diagnostic thresholds are read from the bound contract at run time and are not redefined in the caption.

<!--block:B0239-->
A companion coverage study was run on the same target with 400 replications, giving hit rates of 0.895 and 0.945 at the two nominal levels. The first value is 358/400 at nominal coverage 0.90 and the second is 378/400 at nominal coverage 0.95. Two-sided 95% Wilson score intervals without continuity correction are [0.861, 0.921] and [0.918, 0.963], so each nominal value lies within its corresponding interval. The registered interpretation is statistically consistent with nominal, with point estimates slightly below. This is frequentist same-truth coverage, not simulation-based calibration or demonstrated calibration.

<!--block:B0240-->
What this asset does and does not support. It supports two things: that the delayed-acceptance mechanism is correctly implemented at full dimension, and that the diagnostics contract of §4.6 is operable end to end. It supports nothing else. In particular the target is **generic and non-geophysical**, and the result is not extrapolated to petrophysically guided inversion, to joint multi-method inversion, to DC or electromagnetic methods, to field data, to full-scale problems, or to any performance claim. ⟦7.2-3 · [BP] §4.1 行 2（通用目标性质披露）；[RR] §7.1-1 禁止外推清单**逐项复述**；与 `sec4-inference.md` §4.3 末段同款边界⟧

<!--block:B0241-->
### 7.3 DO-27 modern-API compatibility runs, and the failure package retained with them

<!--block:B0242-->
The third registered asset is a compatibility exercise, not a scientific result, and its value to this paper lies as much in what it failed at as in what it completed. A published open synthetic dataset (the DO-27 kimberlite gravity and magnetic case) was read, forward-modelled and inverted on a reduced grid through a current version of the open-source geophysical stack, with the regularisation weight selected by generalised cross-validation and the linear system solved by LSQR. Gravity and magnetic data were treated **separately, as two single-physics problems**, and the run is registered at the Synthetic-run tier with a limited-compatibility qualification. ⟦7.3-1 · `do27-v4-20260724/run-manifest.json`（`evidence_id: EVD-SYNTH-001`、`status: Synthetic-run` 实测）；`do27-v3-config.json`（GCV 选参规则与 LSQR）；[BP] §4.1 行 3⟧

<!--block:B0243-->
The claim boundary is registered with the asset and is reproduced here because it is narrower than a reader would assume. The run demonstrates that the same-source DO-27 data can be read, forward-modelled, GCV-selected and LSQR-solved as two reduced-order single-physics problems on a modern API. **It does not demonstrate model recovery, and it is not petrophysically guided inversion, not joint inversion, not Bayesian inference, and not a reproduction of the original notebook.** The acceptance criterion was correspondingly narrow: a hard gate on solver convergence together with a ceiling on the weighted data misfit, with the overfitting warning and the model-recovery comparison against a zero model both recorded as **non-gate** quantities — that is, reported but not permitted to decide acceptance. ⟦7.3-1 · `do27-v3-config.json` 的 `claim_boundary` 逐字（中文原文：「仅证明DO-27同源数据在现代SimPEG API上的降阶双单物理读取、正演、GCV选参和LSQR运行兼容；不证明模型恢复、PGI、联合、贝叶斯或原notebook复现」）；`hard_gates` 与 `reported_non_gates` 字段的**结构**（阈值数值按 §4.6 单源纪律不复制）；[RR] §7.1-2；禁令 3⟧

<!--block:B0244-->
Mandatory co-disclosure: the v2 failure package. An earlier run under a superseded protocol failed, and it is retained. From the three-role sign-off record: *the v2 magnetic `model_rmse` is 4.3 times that of the zero model → `Failed`; v3 `recovery=false` is reported as non-gate; the `claim_boundary` states explicitly that model recovery is not demonstrated.* From the QA review of the same record: *the failed v2 is retained as it stands — `do27-v2` is self-consistent across three evidence layers (stdout `accepted:false` → run-manifest `Failed` → evidence `failed/claims:[]`), neither deleted nor overwritten.* The failure package is immutable; a low RMS is an overfitting warning rather than a success; magnetic model recovery FAILED; and EVD-SYNTH-001 is a modern-API reduced-order single-physics compatibility run — not PGI, not joint, not Bayesian, not a reproduction of the original notebook. ⟦7.3-2 · **披露 1 逐字**——英译**逐字复用** `sec8-5-limitations.md` 现有副本（**字符级比对已执行，见自查**）；中文正典 [WP] §5.1；出处 `validation/wp7/signoff.json`（三角色 AI 审查）与 `do27-v3-config.json`；[SYN] §5-1；禁令 1⟧

<!--block:B0245-->
Two consequences of that disclosure are worth making explicit, because they are easy to lose. **A low residual is not a success criterion here** — it is the direction in which this particular asset is known to mislead, which is why the overfitting condition is recorded as a warning, not a gate. And **the magnetic model-recovery failure is a property of the retained record, not a resolved defect**: the later run does not overturn it, it operates under a claim boundary that never asserted recovery in the first place. ⟦7.3-2 · [WP] §5.1 披露要点第 2/3 句；`reported_non_gates` 的 non-gate 语义；禁令 2（禁模型恢复措辞）⟧

<!--block:B0246-->
Provenance of the sign-off. The acceptance decision on this asset was taken by three independently prompted AI reviewer roles, all recording approval, and the record carries its own scope limitations: an AI technical sign-off, not a natural-person signature; confined to the specified small-scale delayed-acceptance study and the DO-27 modern-API reduced-order single-physics compatibility; asserting nothing about petrophysically guided, joint, Bayesian, model-recovery, field, resource or production capability; and with local evidence that was not required to carry remote attestation. ⟦7.3-1 · `signoff.json` 的 `roles[]`（三角色 `identity_type: ai`、`decision: Approved` 实测）与 `scope_limitations` 四条逐条英译；与 Declarations 的 AI 出身披露互指；[RR] §7.1-2⟧

<!--block:B0247-->
### 7.4 Open-data ingestion and integrity audit (EVD-OPEN-001)

<!--block:B0248-->
Two published open geophysical data holdings were ingested and audited for integrity: a geophysics manifest of 184 files and a magnetotelluric manifest of 421 files, each checked for content hash and format conformance. The audit establishes that these holdings can be ingested reproducibly and that their contents match their recorded hashes. ⟦7.4-1 · `validation/runs/open-data-20260717-03`；[BP] §4.1 行 4；[RR] §7.1-3⟧

<!--block:B0249-->
The boundary on this asset is one sentence and it is absolute. This is a **data-governance** result and nothing more: it states that files were read and verified, not that anything was inverted, recovered or located. It carries no implication about inversion accuracy, and **it never upgrades to field validity**. Its role here is as the empirical wing of the governance contribution — a claim about reproducible data handling, supported by an audit of exactly that, and by nothing wider. ⟦7.4-1 · [BP] §4.1 行 4 措辞边界**逐字**（"Data-governance boundary only; never upgrades to field validity"）；[RR] §7.1-3；禁令 1⟧

<!--block:B0250-->
### 7.5 The joint synthetic asset: implementation, pilot outcome, and current status

<!--block:B0251-->
The joint synthetic asset is the one place in this work where the framework's components were assembled into a single posterior. This section reports what was built, what the pilot returned, and where the asset stands; **it reports no endpoint result, because none has been validly obtained.** The design and its pre-registration are described in §6.4 and are not repeated here. ⟦7.5-1 · [PREREG] v1.1-frozen；大纲 §8.5(a) 第 1 项（「一句指向 §6.4，不重复展开」）⟧

<!--block:B0252-->
Implementation and its test evidence. The new code required by the design (the coupling prior, the joint-posterior assembly and the scene producer) was delivered with 28 acceptance tests, all passing, two of which are regression tests added by the defect repair described below. The wider regression suite recorded 3 failures, 119 passes and 1 skip; **the three failures are a pre-existing environment mismatch** (an electromagnetic call path requires a newer array-library API than the pinned environment provides) and are unrelated to this asset — the gravity and magnetic forward tests, which are the two operators this asset actually uses, pass in full. ⟦7.5-1/7.5-2 · [M1] §3.1/§3.2（2026-08-20 现行版）；[RR] §6.5⟧

<!--block:B0253-->
A defect the governance machinery caught. A calibration probe returned a catastrophic diagnostics failure, and tracing it exposed a sign inversion in the log-ratio of an independent-proposal kernel — a defect that had passed unit testing. It was pinned twice over, analytically and statistically, repaired in two lines, and covered by new regression tests. **The probe that exposed it was archived as `Failed` under the immutable-failure rule and was not deleted, its posterior quantities were voided, and the pre-repair and post-repair scripts remain distinguishable by content hash.** We report this because a governance claim is worth what its interceptions are worth, and this is one. ⟦7.5-3 · [M2] §3；[M1] §5；[RR] §6.5；与 §8.5 的过程出身段互指⟧

<!--block:B0254-->
The pilot returned a negative result, and it is registered as one. All 42 pilot runs failed the diagnostics hard gate. **This is the pre-registered failure path, not an anomaly**: the design's risk register anticipated insufficient mixing for a state of this dimension and specified in advance what would happen if it occurred. *(The risk carries the label R1 in the pre-registration; that label denotes the registered risk item, and is unrelated to any later sampling batch that may share the name.)* The binding constraint was the minimum bulk effective sample size, short of its threshold by about two orders of magnitude across the board, and the failed-replicate rate reached unity in all five pilot scenes against a contracted ceiling of 0.02. All 42 failed runs are immutably archived. The repair described above did take effect and the evidence for that is positive and separable: the first-stage acceptance rate moved from 12.34% to the interval [28.7%, 34.7%]. **Every quantity in this paragraph is a property of a gate-failing batch; none of them is used, here or anywhere, to support an endpoint conclusion, and the effective sample sizes behind them are of order five, which is the contamination that makes them unusable for that purpose.** ⟦7.5-4/7.5-5 · [M2] §V2.3（`pilot/evaluation/m2-gate-ledger.json`）；**禁令 1 已履行——ESS≈5 污染声明随句**；R1 歧义消歧句为本节新增，理由见交付注记 3⟧

<!--block:B0255-->
The pilot driver did not run to completion, and the evaluation layer is a deterministic post-hoc reconstruction, not runtime-generated batch evidence. The driver stopped before its multi-start and summary stages, so the pilot summary, run contract, batch-level run manifest and versioned evidence record were not emitted. Per-run metrics, raw chains and manifests remain available for all 42 runs. The published reconstruction script hashes each input and reproduces all 42 gate-ledger rows exactly from the per-run metrics (42/42 exact matches, no unbound run identifier); it also binds the predecessor ledger and aggregation hashes. These reconstructed records retain a distinct status and are not represented as artefacts emitted by the driver. A future pilot must generate its batch artefacts natively before any endpoint is evaluated.

<!--block:B0256-->
Some pilot evidence does not depend on the sampler, and it survives the gate failure. Three quantities were obtained deterministically or analytically, independently of the chains: the injected-misspecification amplitude ratio was computed in closed form from the frozen kernels and fell in [5.2, 16.3], meeting the design target of at least 2 in all five pilot scenes, with the total-field magnetic channel dominating — which is the physical basis of the pre-registered response direction; an exact marginal argument settled the treatment of one nuisance parameter in all five; and a bistability in one proposal block was attributed quantitatively by its decay fingerprint. Separately, 37 of the 42 maximum-a-posteriori searches hit the iteration ceiling without converging. ⟦7.5-6/7.5-7/7.5-8/7.5-9 · [M2] §5.3（`probe-m2-deterministic/`）、§5.2、§V2.5、§V2.8⟧

<!--block:B0257-->
The coupling-strength selection rule returned an empty set, and the pre-committed branch was executed as written. Every run feeding the selection rule had failed the gate, so no candidate was eligible; the mechanically selected value is retained as a diagnostic reading only and is not a frozen coupling strength. The pre-committed consequences followed without further decision: the pilot was registered as a negative result, the full-scale production campaign was suspended, and the outcome was returned to the user. **This is what a pre-commitment is for — the branch was chosen before the data, and executing it required no judgement after the data.** ⟦7.5-10 · [M2] §V2.4（`pilot/evaluation/m2-posthoc-aggregation.json`）；[RR] §6.6 λ\* 段；**禁令 7 已履行——无任何 λ\*-非条件化结论**⟧

<!--block:B0258-->
One diagnostic question remains suspended. An early-warning signal of near-degenerate dual optima appeared in one scenario family and a threshold-adjacent drift in another; both are indicative only. The formal criterion that would have settled unimodality is **left open pending the redesign**, and the modal-access field's operationalised substitute passing on all 42 runs is **not** evidence of unimodality — at effective sample sizes of order five the chains had no opportunity to cross between modes even had modes existed. ⟦7.5-11 · [M2] §V2.9；与 §6.1 的判据分析互指（**该项的可失败性分析落 §6.1，本节不复述**）⟧

<!--block:B0259-->
Status as of 22 August 2026. The user ruled that the asset be redesigned and re-piloted, and that work is in progress; a revision package to the pre-registration is pre-authorised, with its final approval to accompany the redesign proposal. **EVD-JOINT-001 therefore remains registered as `Planned`.** No endpoint result appears in this paper, and the wording of every endpoint statement in §6.4 is a description of a design rather than a report of an outcome. Work carried out during the redesign is diagnostic-tier process and is not evidence. Appendix D reports only execution states and conclusion-type labels for that process; this paper reports no redesign-round numerical reading or endpoint result. ⟦7.5-12 · [M2.5] 首部（用户 M3 前置裁定 2026-08-20）；[PREREG] 首部状态机措辞；**截止时点与 §8.5 开篇对齐（同为 2026-08-22）**；**禁令 10 已履行——M2.5 读数零出现，其在文身份仅为「在途过程」**⟧

<!--block:B0261-->
## 8 Discussion

<!--block:B0262-->
### 8.1 What the registered evidence supports, and what it does not

<!--block:B0263-->
Section 7 reported what each registered asset returned. This section states what each of them licenses and what it does not, asset by asset, because a result and a permission are different objects and the second is the one a reader needs in order to check a claim. **No reading from §7 is repeated here.** The boundaries below are the ones registered with each asset before it was run, not qualifications added afterwards, and each is stated in a form that a reader can act on: it names a specific reading of the evidence and rules that reading out. ⟦8-1 · [RR] §7.1 禁止外推清单六条；[ES]；大纲 §9(a) 首项（「按 evidence_id 逐条复述『支持/不支持』边界」）；**团队 2026-08-22 明令：本节复述边界不复述读数**⟧

<!--block:B0264-->
The per-method verification matrix (WP8). *It supports three things.* Each of the nine forward operators, taken on its own, passes the same pre-registered synthetic protocol; the protocol is identical across the nine, so the rows are comparable to one another rather than nine differently-graded exercises; and the framework's forward layer is therefore established at operator level across the full method set rather than for a favourable pair. *It does not support three things.* It carries no information about joint or coupled behaviour — nine operators verified in isolation are not a nine-method capability, and no aggregation of the rows produces one. It carries no field capability, and the disclosure registered with it fixes that permanently: *labelling that result `Field-validated` is permanently forbidden.* And the completion of the work package is *a user-authorised governance event rather than a technical pass*, so a reader may not treat the matrix's completeness as evidence that a field bar was reached; the field-feasibility shortfall behind that policy, and the policy change itself, are stated in full at §7.1 and collected again in §8.5. The transient-electromagnetic row additionally supports nothing outside one-dimensional layered media. ⟦8-1 · §7.1 落点；**两处斜体串为披露 2 的逐字提取**（源 = `sec7-1-wp8-matrix.md`，字符级比对见自查）；[RR] §7.1-1 边界行；禁令 1/6⟧

<!--block:B0265-->
The algorithm-correctness study (EVD-ALGO-002). *It supports two things.* The delayed-acceptance mechanism is correctly implemented at full dimension, and the diagnostics contract of §4.6 is operable end to end — an instrument that runs, exercised on a target where the answer is known independently of it. *It does not support three things.* It transfers to nothing geophysical: the target is generic and non-geophysical, so the result reaches neither petrophysically guided inversion, nor joint inversion, nor direct-current or electromagnetic methods, nor field data, nor full-scale problems, nor any performance claim. Its companion coverage study does not support a calibration claim — it is frequentist same-truth coverage and not simulation-based calibration, and a reader who reads the two as interchangeable is reading something this asset does not say. And it does not support the expectation that the same sampler will meet the same contract on the joint target: §7.5 is the direct evidence that it did not, and the two facts sit in this paper side by side rather than one qualifying the other away. ⟦8-1 · §7.2 落点（**读数留在 §7.2，本节零复述**）；[RR] §7.1-1 禁止外推六项**逐项否定**；[BP] §4.1 行 2 通用目标性质；禁令 1⟧

<!--block:B0266-->
The DO-27 compatibility runs (EVD-SYNTH-001). *It supports two things.* A published open dataset can be read, forward-modelled, weight-selected and solved on a current version of the open-source stack as two reduced-order single-physics problems; and the failure package produced under the superseded protocol is retained, immutable and self-consistent across its three evidence layers — which is a fact about the process, not about the physics, and is registered as such. *It does not support three things.* Its registered boundary is a list of negations and they are load-bearing: *not PGI, not joint, not Bayesian, not a reproduction of the original notebook.* It does not support any inference from a small residual, because *a low RMS is an overfitting warning rather than a success* — this is the one asset in the paper whose known failure direction is to look better than it is. And it does not support any claim about magnetic model recovery: that failure is a property of the retained record and the later run does not overturn it, having operated under a boundary that never asserted recovery in the first place. The disclosure in full is at §7.3 and again at §8.5. ⟦8-1 · §7.3 落点；**两处斜体串为披露 1 的逐字提取**（源 = `sec7-3-do27-compatibility.md`，比对见自查）；[RR] §7.1-2；禁令 1/6⟧

<!--block:B0267-->
The open-data ingestion audit (EVD-OPEN-001). *It supports two things.* Two published open holdings can be ingested reproducibly, and their contents match their recorded hashes. That is the empirical wing of the governance contribution: a claim about reproducible data handling, supported by an audit of exactly that. *It does not support two things.* It says nothing about inversion accuracy, because nothing in it was inverted. And it never upgrades to field validity — that real data were read is not that any method worked on real data, and the distance between those two statements is the whole of what this asset is not. ⟦8-1 · §7.4 落点；[RR] §7.1-3（「数据治理边界绝不升级为现场有效」）；[BP] §4.1 行 4 措辞边界；禁令 1⟧

<!--block:B0268-->
The joint synthetic asset (EVD-JOINT-001). This is the asset the paper's fusion claim would rest on, and it is the one that returned no result. *It supports three things.* The design exists and was frozen before execution; the components it specifies were implemented and tested; and the pre-registered failure path executed as written, which is a fact about the pre-commitment rather than about the model. It also supports one governance claim with a concrete referent: the machinery intercepted a real defect that unit testing had passed, and the interception is on record with its own failure archive. *It does not support three things, and the third is the one most likely to be got wrong.* It supports no fusion behaviour of any kind — no endpoint result exists, so there is nothing to be cautious about interpreting; there is nothing to interpret. Its gate-failing readings support nothing, not weakly and not directionally, and this paper does not use them as evidence anywhere. **And its negative result does not support the converse claim either.** A diagnostics gate failure is a statement about whether the sampler mixed, not about whether the model is right; a reader who takes the registered negative result as evidence that fusion of this kind does not work is drawing a conclusion the asset cannot carry, in the same way and for the same reason that a positive result would not have carried the opposite one. ⟦8-1 · §7.5 落点；[PREREG] 首部状态机；[RR] §7.1-6（EVD-JOINT-001 自带边界，[RR] §6.6 全录）；**「负结果也不支持反向结论」为本节新增的对称边界，理由见交付注记 3**；禁令 5⟧

<!--block:B0269-->
The current state of the fusion evidence, stated without anticipation. The design is frozen, its components are implemented and tested, the pilot is registered as a negative result, and a redesign is in progress. Those four facts are the whole of the fusion evidence at the time of writing. **We do not know how the redesigned experiment will come out, and nothing in this paper is written so as to read better under one outcome than under another** — the endpoint wording for each of the pre-registered branches was fixed in advance and only the branch that occurs will be written. Until then the paper's substantive contributions are the framework's formulation, the per-component verification bounded as above, and the governance apparatus argued in §8.4. ⟦8-1 · 大纲 §9(a) 8.1 末句（「诚实状态陈述，**不预热结局**」）；[PREREG] §4 分支预注册；[SYN] §3.3 回落条款；禁令 5（**(i) 臂未决时禁写「组合有用性已证」类总结**）⟧

<!--block:B0270-->
### 8.2 Detection over isolation: the architectural position and what it costs

<!--block:B0271-->
When several physical methods are combined and any of them may be misspecified relative to the others, an architecture has to take a position before the data arrive. It can isolate the suspect component by construction, severing the feedback through which a bad likelihood would contaminate the rest of the posterior; or it can admit every component to a single joint posterior and instrument it, so that a component behaving badly becomes visible rather than being pre-emptively quarantined. **This framework takes the second position, and this section argues for it and states what it costs.** ⟦8-2 · [SYN] §1 传统 3「flip test 的正面战场」；大纲 §9(a) 8.2⟧

<!--block:B0272-->
The alternatives are principled, and this paper does not treat them otherwise. Bayesian melding (Poole and Raftery, 2000) and Markov melding (Goudie et al., 2019) join submodels around a shared quantity while keeping the submodels' own inferences intact; the cut and modular-posterior analysis of Jacob et al. (2017, preprint, arXiv:1708.08719) supplies a diagnosis of *when* suppressing feedback is the right choice, which is precisely what an architecture needs in order to make the choice defensibly. §2 states their positions and their nearest-neighbour status; the argument here is not that they are deficient joint models but that they answer a different question, and that on the question this framework asks the trade runs the other way. ⟦8-2 · [BIB] #38 Poole & Raftery 2000（校）/#39 Goudie et al. 2019（校）/#40 Jacob et al. 2017（arXiv 版本标注见 §2）；[SYN] §1 传统 3 谱系行；**禁令：不得把替代架构写成缺陷版本**⟧

<!--block:B0273-->
The reason for the position is that the isolation decision has to be made before the evidence that would justify it. A cut is a modelling decision taken in advance: it presumes that the analyst can name which module is the suspect one and which direction of feedback should be severed. In multi-physics joint inversion the misspecification most likely to matter is a *shared* one (a systematic error common to several surveys, or an idealisation error common to several forward operators) and a shared error has no single module to quarantine. Cutting one method's feedback does not remove a shared error; it removes the evidence that the error is shared. **The framework's response is to keep the components in one posterior and to make the shared structure an inferred object, so that misspecification appears as a movement in a quantity that is reported rather than as a discrepancy nobody measured.** ⟦8-2 · §3.1 联合分解（$\xi$ 共享系统 nuisance、$\delta$ 模型差异）；[SYN] §1 传统 3「与论文的关系」行（「理由须落在共享潜变量的跨模块全联合后验与预注册诊断的可审计性上」）⟧

<!--block:B0274-->
The instrumentation is two devices with two different jobs, and this matters more than it first appears. The per-method weight $w_k$ is a scalar likelihood power. With the registered weight shape it multiplies method $k$'s entire likelihood and **contains no $(k,l)$ information whatsoever**, so it cannot, by construction, detect a pair-level shared-error misspecification — no amount of weight movement localises the problem to a pair. Pair-level detection is assigned instead to tension checks evaluated on the restricted cross-covariance blocks $(BB^\top)_{kl}$ of Eq. (3.4). **Neither instrument substitutes for the other**, and a framework offering only one of them would be claiming a detection capability it does not have. This is why the position is "detection *and* down-weighting *with tension reported*" rather than detection alone. ⟦8-2 · §3.4 Eq.(3.4) 与双仪器分工段（`sec3-framework.md` §178 行，F-13/F-14）；[BP] §2.4；[RR] §6.6 权重边界⟧

<!--block:B0275-->
What the framework does not do is decide. A cut is a rule that removes a data set; the diagnostics here are instruments that report. There is no quantitative rule in the specification that automatically excludes a survey, and none is claimed: a method whose weight or whose tension statistics move under misspecification is flagged and *can* be down-weighted, by a person, with the movement on record. If fusion degrades a particular method pair on a synthetic scenario, that is a reportable finding about the configuration rather than a failure of the framework — and equally, it is not an automatic exclusion. Readers who want the automatic version should read the modular architectures, which supply it. ⟦8-2 · §3.5 主张辖域段（「fusion with pre-registered sensitivity diagnostics and misspecification warning」）；[RR] §6.6；**禁令：无 "refusal mechanism" 措辞**⟧

<!--block:B0276-->
The cost of this position is real and it is the one Jacob et al. identify. Admitting a possibly-misspecified likelihood to the joint posterior means its errors propagate to every other node; that is the phenomenon the cut is designed to prevent, and nothing in this framework repeals it. The framework's answer is not that contamination does not occur but that it should be *visible when it occurs*, and visibility is an empirical property of a configuration, not a theorem. **Whether the two instruments are in fact sensitive enough on any given problem is exactly what the registered joint asset was designed to measure, and it has not yet measured it** (§7.5). The position argued here is therefore a design rationale with a pre-registered test attached, not a result. ⟦8-2 · [BIB] #40 Jacob et al. 2017（误设传染分析）；§7.5 状态；**禁令 5：(i) 臂未决时不得预写「组合有用性已证」类总结**⟧

<!--block:B0277-->
The weight instrument requires one qualification and is stated here rather than left to the reader. Under the registered operationalisation the whitening *rule* is frozen while the covariance used in whitening is the sampled noise-scale node, so with linear forward operators the weight response is mediated entirely through that node: misspecification inflates the noise-scale posterior, which reduces the method's share, which down-weights it. **The noise-scale channel therefore already absorbs part of the misspecification on its own, and the weight channel is a second-order effect relative to that generating channel.** The claim this permits is that *weight trajectories respond to the injected misspecification as theory predicts*; the claim it does not permit (and which this paper does not make anywhere) is that weighting improves posterior robustness, because establishing that would require weighted and unweighted paired arms that isolate the weight channel from the generating channel. That experiment is registered as future work under a separate evidence identifier (§8.6). ⟦8-2 · [BP] §2.4 D-E2 操作化注记（**英文原件逐字**：permitted claim 与 NOT permitted 两串）；[RR] §6.6 D-E2 主张上限；**禁令 6（大纲 §8.5(c)）：「加权提升后验稳健性」+ s_k 生成通道吸收声明必随**⟧

<!--block:B0278-->
### 8.3 Historical comparison criterion and the current evidence boundary

<!--block:B0279-->
Section 2.3 states the contribution boundary. This section records the historical two-arm comparison criterion and explains why neither the literature inventory nor the failed joint endpoint supports a stronger statement in the current revision.

<!--block:B0280-->
Several cited traditions motivate individual design choices: manual data-weight practice motivates explicit weight governance; misspecification research motivates discrepancy and down-weighting mechanisms; and reproducibility research motivates provenance and diagnostic controls. These citations provide context for the formulation. They are not used to assert that the assembled combination was requested by, absent from or distinctive within the literature.

<!--block:B0281-->
An earlier draft classified some elements as having no prior literature request and used later retrievals to adjust that classification. Those classifications are withdrawn from decision use because they were not supported by a complete full-text evidence bundle. The provenance history remains in the governance archive, while the manuscript makes no request-absence claim.

<!--block:B0282-->
Citation-identity defects in inherited project material motivated stronger verification controls, but they are not evidence that a neighbouring body of work is empty. Failed or fabricated candidate records reveal defects in those records only; they cannot support a literature-absence, closest-work or novelty conclusion.

<!--block:B0283-->
The former sensitivity argument about removing one comparator depended on the element-scored matrix and is therefore withdrawn. Individual architectural contrasts may be discussed only when bound to full-text evidence, and no such contrast is needed for the formulation and component-evidence contribution claimed here.

<!--block:B0284-->
The second arm is not available, so the pre-committed evidence boundary applies. The coupling-increment arm would be supplied by the registered joint asset's first endpoint; that endpoint has not been validly assessed, for the reasons reported in §7.5, and no reading from that asset is used here. **The pre-registered consequence is stated rather than deferred: without a valid coupling-increment result, the paper is limited to formulation, component evidence, and governance infrastructure.** That branch was written before the data and is not open to revision now.

<!--block:B0286-->
### 8.4 Research-record motivation for the governance design

<!--block:B0287-->
The governance apparatus in §6 was motivated by citation-identity and provenance defects found in the project's inherited reference material. Those defects were corrected or quarantined before use; unresolved records were excluded from evidential comparisons, and the manuscript's contribution statement does not depend on them. The detailed row-level audit, counting conventions and correction history are retained in the supplementary governance record rather than repeated in the scientific narrative.

<!--block:B0291-->
The boundary on all of the above is narrow and it is not negotiable. The pool is the output of this project's own LLM-assisted workflow. Every rate quoted here estimates the hygiene history of *that* pool, and **it must not be extrapolated to a contamination rate for the published literature at large**. What this record supports is that contamination occurred in this paper's own material and was intercepted before it reached the argument; what it does not support is any figure for how often this happens anywhere else. The one contemporary source that describes the corpus-scale phenomenon is itself an unverified entry from inside the same pool, and is therefore used here as motivation only — it is not cited as evidence and does not appear in the reference list. ⟦8-6/8-7 · [RR] §5.5 边界句逐条；[RR] §5.3 末段边界声明（Zhao et al. 只作动机叙述、不入参考文献）；**禁令 3：禁池污染率外推**⟧

<!--block:B0292-->
The bounded gap observation. Within the geophysical-methods records examined in the registered search, the comparison did not identify a paper that treated verification of its own bibliographic record as a methodological contribution. This is an observation about the searched set, not a literature-wide absence claim; scientometrics and citation-integrity research lies outside the search scope. The contribution made here is therefore stated operationally: the paper documents practices adopted after bibliographic failures occurred in its own source pool and preserves the interception record.

<!--block:B0293-->
### 8.5 Limitations

<!--block:B0294-->
This section is an inventory, and an inventory is only meaningful relative to a stated cut-off. **Everything below is the state of this work as of 22 August 2026.** Two things follow from saying so. First, the claim of completeness is a claim about that date and not about the manuscript's eventual state; items may be added, and the discipline of this project is that they are added rather than substituted. Second, a limitation is not the same thing as an open question: the list of items still under adjudication at the cut-off is given at the end of this section, and **those items are not substitutes for limitations — they are things not yet known to be limitations.** Nothing in the pending list is offered as mitigation for anything in the inventory. ⟦8-8 · 截止时点 + 待决项分离，team lead 2026-08-22 明令；[BP] §7⟧

<!--block:B0295-->
#### The evidence ceiling

<!--block:B0296-->
All quantitative claims in this paper are bounded at the Synthetic-run tier, and no field validity is claimed anywhere. No row of this work's evidence registry carries the Field-validated tier; the tier exists in the register so that its emptiness is recorded rather than implied. Consequently no statement here supports a claim about discovery rates, detection performance, localisation accuracy, computational speed-up, or resource quantities. ⟦8-8 · [ES]；[RR] §7.1 首段（受保护文本，[OUTLINE] §0.5 第 3 项）⟧

<!--block:B0297-->
The per-method evidence carries strict scope limits. The nine-method matrix is component breadth rather than joint capability; `field_validated=false` for all nine, and TEM is limited to the verified 1-D layered path. The DO-27 exercises are reduced-order and single-physics, petrophysical priors remain Hypothesis-tier, and the decision layer is specified but uncalibrated. The revision environment is reported only as a reproducibility baseline. No registered benchmark supports runtime, memory, acceleration, scaling or production-practicality claims.

<!--block:B0298-->
Finally, a boundary on what the framework claims to do at all: **it does not claim to eliminate model misspecification — only to detect it and to bound parts of it.** A method whose weight or whose tension statistics move under misspecification is flagged and may be down-weighted; no rule in the specification automatically excludes a dataset, and none is claimed. ⟦8-8 · [BP] §7；[RR] §6.6 权重边界⟧

<!--block:B0299-->
#### The three mandatory failure co-disclosures

<!--block:B0300-->
These three are reproduced verbatim. Two of them are stated in full where their evidence is reported and are repeated here so that the inventory is complete; the third has this section as its primary location.

<!--block:B0301-->
Disclosure 1 — the DO-27 v2 failure package (co-disclosure of EVD-SYNTH-001; stated in full in §7.3). From the three-role sign-off record: *the v2 magnetic `model_rmse` is 4.3 times that of the zero model → `Failed`; v3 `recovery=false` is reported as non-gate; the `claim_boundary` states explicitly that model recovery is not demonstrated.* From the QA review of the same record: *the failed v2 is retained as it stands — `do27-v2` is self-consistent across three evidence layers (stdout `accepted:false` → run-manifest `Failed` → evidence `failed/claims:[]`), neither deleted nor overwritten.* The failure package is immutable; a low RMS is an overfitting warning rather than a success; magnetic model recovery FAILED; and EVD-SYNTH-001 is a modern-API reduced-order single-physics compatibility run — not PGI, not joint, not Bayesian, not a reproduction of the original notebook. ⟦8-8 · [WP] §5.1 中文正典逐字英译；`validation/wp7/signoff.json`；`do27-v3-config.json`；主落点 §7.3；禁令 6⟧

<!--block:B0302-->
Disclosure 2 — WP8-0 formal field feasibility 6/9 and the completion-policy renegotiation of 26 July 2026 (co-disclosure of the WP8 matrix; stated in full in §7.1). From the specification's revision record: *the user changed the WP8 completion policy to synthetic-validation completion, explicitly forbidding a block on the grounds of absent field data; the field 6/9 result remains a non-blocking audit fact; once the nine synthetic gates pass, WP8 completion and WP9 start are permitted, while labelling that result `Field-validated` is permanently forbidden.* The 6/9 figure is an audit fact that has not been eliminated, and the policy change is a user-authorised governance event rather than a technical pass. ⟦8-8 · [WP] §5.2 中文正典逐字英译；`wp8-synthetic-completion-v1.json`；主落点 §7.1；禁令 6⟧

<!--block:B0303-->
Disclosure 3 — the WP9 four-specialist re-review (provenance of the governance evidence; **this section is its primary location**, carried in parallel with Disclosure 2). The four specialist reviews on record are **4/4 Approved**; they are a single-generator automated AI evidence review (`identity_type=automated-ai-specialist-evidence-review`); they are not four independent human experts or four independent toolchains, and not a field, resource, regulatory or production certification. The associated remediation ledger of sixty items was closed as a **locally audited evidence audit**, with no Git or remote proof of closure claimed. The persuasiveness of a governance contribution depends on registering exactly this kind of provenance. ⟦8-9 · [WP] §5.3 中文正典逐字英译；`validate_wp9.py`；**与 Declarations（AI-use disclosure）的简短承载须逐字一致**——比对结果见自查；禁令 6⟧

<!--block:B0304-->
#### What the registered joint asset does and does not carry

<!--block:B0305-->
The following boundaries apply to EVD-JOINT-001. The asset is an implementation baseline, not a general validation arm. The multi-scale mechanism is not exercised: change-of-support transfers a single property, whereas gravity and magnetics use different properties and any cross-property link would pass through Hypothesis-tier petrophysical latents. The surrogate-error term is absent, clock offset has no physical role for static potential fields, and gain is fixed. Generation and inference use the same operator pair, so the same-kernel reservation applies throughout. No assembled-performance, structural-misspecification or multi-scale-demonstration claim is licensed.

<!--block:B0306-->
The misspecification endpoint addresses only one registered, known and nested injection that lies inside the well-specified arm's model class. It cannot support a general claim about detecting unstructured or field-like misspecification, and no independent-forward or non-nested discrepancy arm was added in this revision. The per-method scalar weight contains no pair-level information; pair-level detection belongs to tension diagnostics. Because the noise-scale channel can absorb part of the injection, even a directional response of the weight trajectory would not establish improved posterior robustness. A stronger claim requires a separately pre-registered validation asset.

<!--block:B0307-->
#### What the instrument has not established about itself

<!--block:B0308-->
This is the part of the inventory that concerns the validation apparatus rather than the framework.

<!--block:B0309-->
The diagnostics hard gate has not been passed under any registered mechanism, and the failure of the four remaining criteria is a settled fact, not a pending one. No run of the joint asset has satisfied the gate; the binding constraint has been the effective-sample-size field. The status of the asset is reported in §7.5 and it remains registered as Planned.

<!--block:B0310-->
The coupling endpoint's two-arm comparison has never been measured under gate-passing conditions, and the gap has two different shapes that must not be merged. For two of the three registered functionals a set of displacement measurements exists, but it was produced under conditions that the pre-registration itself excludes from evidential use, so those numbers are not evidence for or against anything. For the third functional, and for the later sampling batch, **there is no measurement at all**. "Excluded from use" and "does not exist" are different states, and a reader entitled to know which one applies to which functional is not served by a single sentence covering both.

<!--block:B0311-->
For the coupling-direction parameter the design, in its present form, cannot separate three mutually compatible explanations. The chain may not yet have reached the relevant region of the posterior; the posterior may itself lie away from the generating value, as it would if that parameter were close to unidentifiable under these data; or the model may be misspecified, so that even a correct posterior would not cover the generating value. **These three produce the same observable appearance**, and the evidence that would separate them (a chain meeting the diagnostic standard, a characterisation of the posterior obtained without sampling, and coverage statistics across scenarios) **is outside the scope of this round's design**. **No conclusion in the coupling endpoint that depends on where that parameter's posterior sits is therefore offered until the three have been separated.** ⟦8-8 · **形态 α，源 `xi-true-third-finding-workitem.md` §4.2**；**证据层级 = 乙类的命题半**（§4.1：命题可引用、例证不可）——**绑定类型「设计/治理」，不走定量类，故不需 `evidence_id`**；**红线全部已避**：不写「链未收敛故未覆盖」(1)、不写「后验不覆盖真值」(2)、不写「模型有偏」(3)、不写「不可辨识」为结论(4)、不写「改进采样即可解决」(5)、**不与三项共披露并列计数或称「第四项」(6)**、**整段承载不缩写为「结果从略」(7)**；**位置关系（丙-i）零出现**——本段只承载「本设计不能区分三种成因」这一可推导命题。**⚠ 现盘 α 自检证据**：`stage2-writing/_sec8_alpha_selfcheck.py` 以稳定起始串 `For the coupling-direction parameter` 到同一行首个 `⟦` 之前提取正文，过程锚不入域；当前边界为 **134 个 ASCII 词 / 136 个空白词**。14 条英文散文泄漏探针正文合计 **0 命中**；14 条各以自己的内存注入逐条由 **0→1，14/14 PASS**；域存活阳性与锚排除对照均 PASS。**旧证据不可复跑**：`sec8-5-limitations.r1-preAlphaSelfcheckRefresh.md:45` 与 `cross-wave-lessons.md:620-624` 两处均未给可执行脚本路径或完整14探针，因此仅凭这两处记录不可复跑旧结果。新脚本建立后以其为现盘证据。⟧ ⟦8-8 · [PREREG] §4 端点(i)；R-A4 前置条件；**两种缺口形态不得并句 —— team lead 2026-08-22 明令**⟧

<!--block:B0312-->
The endpoint's decision quantity is a difference of absolute errors, and that form makes the criterion depend on the size of the deviation being measured, not only on the coupling. Writing $b$ for the uncoupled arm's signed error and $\delta$ for the displacement the coupling produces, the quantity is positive exactly when $\delta$ lies strictly between $0$ and $-2b$. Two failure modes follow: if $\lvert b\rvert\le\lvert\delta\rvert/2$ the window collapses and a beneficial verdict is unreachable; if $\lvert\delta\rvert>2\lvert b\rvert$ the displacement overshoots and a movement towards the true value is scored as harmful. **We do not know, and do not claim, whether this work's scenarios fall inside or outside that window.** The identity underlying both statements is in Appendix F, and the design response (reporting the signed difference alongside the absolute one rather than replacing it) is described in §6.4. ⟦8-8 · 甲类 A-2/A-4；附录 F.2；**红线：不得写成「绝对误差是错的度量」，不得断言本项目落在窗内或窗外**⟧

<!--block:B0313-->
The diagnostic implementation now fails closed on non-finite or degenerate channels. Input arrays are rejected if any value is non-finite; non-finite derived diagnostics and finite zero-range channels produce a structured `Failed` stop; and aggregation no longer uses functions that silently discard non-finite entries. Regression tests cover NaN, positive and negative infinity, the exact plotting-position contract and finite constant channels. The revision-host selection completed with 24 tests passed and one slow test deselected. Endpoint interpretation remains prohibited after any diagnostic stop.

<!--block:B0314-->
The rank-normalisation implementation has been aligned with its contract. Both now use the Blom plotting position $(r-3/8)/(N+1/4)$; the former implementation's $N-1/4$ denominator has been removed. A hash-bound replay read all 65 historical raw-chain files without mutating them: all 65 retained the transition `Failed` to `Failed`, and all now carry the explicit `nonfinite_diagnostic` reason. Degenerate-channel counts were one in 57 files, two in 3 files and six in 5 files. The replay changes failure attribution, not any historical endpoint verdict, and it does not turn a failed pilot into an evaluation of coupling behaviour.

<!--block:B0315-->
The count of channels dropped from a criterion is a biased lower bound on the number of degenerate channels, not a measurement of it. A channel is dropped from the tail-based criterion only when *both* of its tail indicator variables degenerate; a channel that has degenerated in one tail only is still counted as participating. The count therefore covers only the channels that have degenerated furthest, and the true number of degenerate channels is at least as large. **This is stated as a proportionality, not a quantity**: the readings that would give it a magnitude are diagnostic-tier and are not reported in this paper, and this observation is a second view of the same underlying phenomenon as the effective-sample-size shortfall already described — not independent corroboration of it. ⟦8-8 · 乙类（team lead 2026-08-22 判定：机理可由 `ess.py` 逐行推出 ⇒ 命题可入文；具体计数为丙-i 不入文）；**不得当新证据用**⟧

<!--block:B0316-->
The convergence statistic we report is aggregated over channels that include degenerate ones, and we neither excluded nor flagged them. The diagnostic domain declared for this asset spans every state parameter together with the reported functionals and the log density, and at least one of those channels is frozen — its value does not vary across draws or across chains. For a channel of that kind the potential-scale-reduction statistic carries **no information about convergence** (the reason is stated in §6.1 and derived in Appendix F, and is not repeated here). The consequence for this work's own numbers is narrow and specific: **the reported statistic is an aggregate taken over a channel set that includes at least one channel for which the statistic is uninformative, and neither the aggregate nor the accompanying record marks which channels those are.** The four criteria do not treat such a channel alike (one drops it, this one returns a passing value, and the others do not pass) so the aggregate is not even internally consistent about it. **What a reader cannot currently do is recover, from what we report, how much of the diagnostic domain was in that condition.** ⟦8-8 · **对象 = 本工作自己的读数，不是 $\widehat{R}$ 这一统计量**（后者是 §6.1 的结果，此处**只作交叉指针、不复述推导**——team lead 2026-08-22 换对象裁定）；诊断域构成 = [PREREG] §5（全部状态参数 + F1/F2/F3 + log-density）；冻结通道存在性 = §7.5 登记状态（**本节不给任何读数，丙-i**）；**不得写成「所以其余读数仍然可靠」**⟧

<!--block:B0317-->
One further property of the gate (that one of its items could not fail under the frozen chain count) is **not listed here as a limitation**. It was analysed, the analysis produced a reusable rule, and the item's disposition is described in §6.1; repeating it in this inventory would dilute a list whose weight comes from every entry being a real limitation. ⟦8-8 · **交叉指针，不复述** —— team lead 2026-08-22 分寸明令：已修复且数学上零风险的构件不进限制清单；§6.1 为其唯一落点⟧

<!--block:B0318-->
#### The literature base

<!--block:B0319-->
The comparative positioning uses a targeted, verification-first literature search rather than an exhaustive systematic review. Later gap filling added Afonso (2026), and the Stage 4 Chinese-language audit identified verified deterministic cross-gradient studies and a directly relevant CSAMT–DC Bayesian application. Because recall remains unknown, the paper claims neither search completeness nor priority for the assembled conjunction. The former element-scoring matrix has been removed from decision use; contribution statements rest on the reported formulation and evidence assets, not on an absence count in the literature.

<!--block:B0320-->
The Chinese-language audit records its queries, date, identity checks and unresolved items. It corrects the metadata of a 2020 gravity–magnetic–MT record and verifies related multi-geophysical cross-gradient work. The corrected record remains part of the audit history and is not used here as a supporting citation. A purported 2016 three-dimensional Bayesian MT–seismic record could not be independently bound and remains `unresolved`; it is neither cited nor treated as negative evidence. This targeted audit reduces a metadata error but does not close the language-coverage gap.

<!--block:B0321-->
The historical comparison criterion was conjunctive and fixed before its original scoring exercise. That provenance fact is retained, but the current manuscript draws no conclusion from an absent matching row because the comparator cells have not undergone location-specific full-text recoding. A pre-registered quantifier does not compensate for an incomplete evidence base.

<!--block:B0322-->
The former nearest-neighbour scores were based on titles, abstracts and metadata and are withdrawn; all current element cells are `unknown`. The earlier English matrix was also a restricted translation of a Chinese table whose semantic-equivalence check was incomplete, retraction status was not verified entry by entry, and two candidates were preprints. These facts reinforce the decision to retain only an identity-verified discovery inventory until full-text recoding is completed.

<!--block:B0323-->
#### Provenance of this work's own process

<!--block:B0324-->
Three production limitations remain. First, blinding of the joint synthetic experiment used hashes and separated roles within one operator rather than institutionally independent parties. Second, a synthesis-phase process-integrity event was detected when reported deliverables were absent on disk; those adjudications were voided and rebuilt from verified inputs. Detection demonstrates that one control fired, not that all remaining records are correct. Third, the paper-specific public release is maintained by the authors and has undergone an author-managed clean-environment replay, but no independent-team reproduction has been completed. AI involvement is disclosed separately in the Declarations.

<!--block:B0325-->
Each of the artefacts underlying this paper carries its own register of items its authors could not verify, and those registers are retained rather than resolved by assertion. A consistency audit across the drafted sections was performed at the cut-off and found the sections mutually consistent on the facts it checked; **that audit verified agreement between sections, not correctness against sources, so the sections may be consistent and wrong together.** ⟦8-8 · 各件自陈未核实项汇总；`cross-section-consistency-audit.md` §7-3 逐字「八节可能在同一个错误上一致」——**本节新增，理由见交付注记 4**⟧

<!--block:B0326-->
#### Items still under adjudication at the cut-off

<!--block:B0327-->
The following matters remained open on 22 August 2026 and are listed to make the evidence boundary visible. They are not offered in mitigation of the limitations above. One verification run of the joint asset remained to be executed, and the reference-list and appendix materials still required finalisation. The exact title-and-abstract screening-exclusion count was not reconstructed at record level; the former value 294 was a closure residual and is withdrawn rather than reported as a measured count. Appendix C.6 records this accounting boundary.

<!--block:B0328-->
### 8.6 Future work

<!--block:B0329-->
Five pieces of work are registered as outstanding rather than left as aspirations. Each names a quantity to be measured, the identifier under which the measurement would be registered, and the condition that currently prevents it. ⟦大纲 §9(a) 8.6；**准入判准 = §8.5 编写口径的未来工作形态**⟧

<!--block:B0330-->
Paired weighted and unweighted arms. The claim ceiling stated in §8.2 (that weight trajectories may be reported as responding to injected misspecification, but that weighting may not be said to improve posterior robustness) is not a permanent limit on the framework; it is a limit on what a single-armed experiment can establish. Lifting it requires running the same scenarios with and without the weight instrument active, so that the weight channel is isolated from the noise-scale channel that already absorbs part of the misspecification. **That experiment is registered as future work under its own evidence identifier**, separate from the joint asset, because it answers a different question and should not inherit that asset's status. ⟦[BP] §2.4 D-E2 操作化注记末句（"requires weighted-vs-unweighted paired arms — future work, separate evidence ID"）；[RR] §6.6 D-E2 上限；与 §8.2 末段互指⟧

<!--block:B0331-->
The redesigned pilot, and the full campaign behind it. The joint asset's pilot returned a registered negative result and a redesign is in progress (§7.5). Two things follow that belong in future work rather than in this paper's results. The redesign must produce a pilot that passes the diagnostics gate before any endpoint quantity is meaningful, and the full-scale campaign (suspended when the coupling-strength selection returned an empty set) resumes only after a user checkpoint that was pre-registered as a condition, not added afterwards. **No result from either is anticipated here, and no quantity from either appears anywhere in this paper.** ⟦[RR] §9.3-1（M3 manifest 冻结 + 全量运行前用户再确认，时序约束在案）；§7.5 状态；**大纲 §8.5(c) 禁令 2：禁预写 M4/重设计任何数字**⟧

<!--block:B0332-->
A trans-dimensional run. The framework specifies a model-dimension index and carries its posterior over a disjoint union, with the reversible-jump machinery specified accordingly; **no trans-dimensional run exists at any evidence tier in this work**, and §4.5 says so in those terms. Executing one is the step that would move that component from the design tier to the Synthetic-run tier — a change of evidential status, not a refinement of the specification. The specification is written; what is missing is a run. ⟦`sec4-inference.md` §4.5 末段（"No trans-dimensional run exists at any evidence tier"，**受保护的整段声明**）；§3.1 disjoint union 基准测度段；[BP] §3 行 5⟧

<!--block:B0333-->
Environment baseline, not compute evidence. The revision host used Windows 10 Pro 10.0.19045 (64-bit), an Intel Core i7-8850H with 12 logical processors, 31.8 GiB RAM, Python 3.11.9, NumPy 1.26.4, SciPy 1.17.1, pytest 9.0.3 and SimPEG 0.25.2. These facts allow the local revision environment to be reconstructed but do not measure runtime, memory growth or scaling. Production-scale practicality remains open and requires a separately registered benchmark across state sizes.

<!--block:B0334-->
Field-transfer risk register. The Field-validated tier remains empty and EVD-FIELD-001 remains `Planned`.

<!--block:B0651-->
| Risk domain | Current evidence gap | Entry evidence required for EVD-FIELD-001 |
|---|---|---|
| Geology | No independently held field target or structural truth is bound | Frozen geological hypotheses, target definition and blind or spatio-temporal hold-out |
| Survey | No field acquisition geometry, calibration or error audit has passed admission | Licensed observations, coordinate and unit audit, instrument/calibration records and survey-error model |
| Petrophysics | Cross-property priors remain Hypothesis-tier | Traceable measurements, support/upscaling statement and held-out predictive check |
| Data governance | No release-ready field licence and provenance chain is registered | Licence, consent/access conditions where applicable, immutable manifest, hashes and redistribution decision |

<!--block:B0652-->
No field-validity conclusion follows from this register, and no amount of additional synthetic work promotes an asset into the Field-validated tier.

<!--block:B0335-->
These five are ordered by what they would change, not by difficulty. The first two decide whether the paper's fusion claim is supportable at the Synthetic-run tier at all; the third and fourth extend the range over which the specification has actually been exercised; the fifth is the only one that changes the tier at which anything here may be claimed. ⟦大纲 §9(a) 8.6 五项；[ES] 层级语义⟧

<!--block:B0336-->
## 9 Conclusions

<!--block:B0337-->
This paper has set out a framework and the evidence that may be claimed for it, and has been careful throughout to keep those two things apart.

<!--block:B0338-->
The formulation contribution is an auditable probabilistic graph combining source-disciplined priors, a shared-error fusion likelihood and pre-registered diagnostic governance over a multi-scale parameterisation. The graph is a design and protocol; the paper neither claims novelty for multi-scale parameterisation nor reports the graph as exercised end to end.

<!--block:B0339-->
The evidence contribution is component-level and tier-bounded. Nine forward operators pass a common synthetic protocol one at a time; a delayed-acceptance sampler meets its contract on a generic non-geophysical target; a published dataset is exercised as two reduced-order single-physics compatibility problems with its failure package retained; and two open-data holdings are ingested and hash-audited. These are isolated component statements. They do not establish assembled fusion, multi-scale endpoint, field-transfer or production-scale performance.

<!--block:B0341-->
The paper reports no behaviour of the assembled framework. The gravity–magnetic joint asset was designed, registered, implemented and piloted, but every pilot run failed the diagnostics hard gate. Its coupling endpoint therefore has no valid evaluation point. This is a measurement limitation, not evidence for or against the framework: no assembled-performance conclusion is drawn in either direction.

<!--block:B0342-->
The contribution of governance is the one this paper can most fully support, and it comes with its own boundary. A hash-bound evidence registry, mandatory co-disclosure of registered failures, a pre-registered diagnostics contract, and a rule admitting a gate criterion only when a construction that makes it fail is registered alongside it — these were adopted because the failures they guard against occurred in this project's own material, and the record of that is in §8.4. **The boundary on everything above is the one stated at the outset.** All quantitative claims in this paper are bounded at the Synthetic-run tier; no field validity is claimed anywhere. Three mandatory failure co-disclosures accompany this evidence and are reported in full at §7.1, §7.3 and §8.5 rather than summarised here. ⟦9-4 · [ES]；[RR] §7.1 首段（**天花板声明句 = 受保护文本，逐字提取自 `sec1-p5` 权威副本，比对见自查**）；[BP] §1-4 四构件；三项共披露落点 = 大纲 §0.6⟧

<!--block:B0343-->
## Declarations

<!--block:B0344-->
### AI-use disclosure

<!--block:B0345-->
This study was produced by an AI-agent research pipeline. We disclose the scope of that involvement in full rather than in summary.

<!--block:B0346-->
AI-assisted stages. AI agents supported scoping and the methodological blueprint (Phase 1), literature search, screening and verification (Phase 2), cross-source synthesis and novelty adjudication (Phase 3), report compilation (Phase 4), and initial manuscript text generation (Stage 2). This initial text was generated under Li Xiao Peng's conceptual and methodological direction and item-by-item review. Li Xiao Peng made substantive revisions and accepts responsibility for the manuscript. Literature verification used two separately instantiated verification agents. ⟦[RR] §2.1/§2.5/§8；[WP] §4.1-1⟧

<!--block:B0347-->
Two process deviations are disclosed rather than smoothed over. The Phase 1 blueprint was written by the pipeline orchestrator standing in for a research-architect agent whose session was lost and whose reading state could not be recovered. In Phase 3, a synthesis agent reported three deliverables that did not exist on disk; the fabricated delivery was detected by on-disk verification, all of its adjudications were voided, and the three products were rebuilt from the on-disk Phase 1 and Phase 2 files. We report both because a pipeline that claims auditability cannot present a curated version of its own record. ⟦[CP1] 过程偏差披露 #1；[SYN] §6⟧

<!--block:B0348-->
Independent adversarial review. Each Devil's Advocate checkpoint was a separate AI agent instance rather than the drafting agent reviewing its own work. The second-pass instance was rebuilt from its role template after a cross-session agent-registry failure; both its report and the first-pass report are retained. ⟦[WP] §4.1-2；[CP1] 过程偏差披露 #2⟧

<!--block:B0349-->
Provenance of the governance evidence. The WP7 sign-off was produced by three AI reviewer roles. The four specialist reviews on record are **4/4 Approved**; they are a single-generator automated AI evidence review (`identity_type=automated-ai-specialist-evidence-review`); they are not four independent human experts or four independent toolchains, and not a field, resource, regulatory or production certification. The persuasiveness of a governance contribution depends on registering exactly this kind of provenance; the same statement is carried as a mandatory companion disclosure in the Discussion (§8.5). ⟦[WP] §4.1-3 与 §5.3 互指⟧

<!--block:B0350-->
Human oversight points. Human decisions were taken at the following points and are recorded with dates in the governance archive: the Phase 1 checkpoint decisions D1 (disposition of the fusion-evidence gap), D2 (title) and D3 (venue plan), 2026-08-19; M0, approval to freeze the pre-registered design of the joint synthetic experiment, 2026-08-19; M3, a required user re-confirmation before any full-scale run campaign; the renegotiation of the WP8 completion policy on 2026-07-26, recorded as a user-authorised governance event and not as a technical pass; the 2026-08-21 rulings that fixed the wording of the novelty claim; and the 2026-08-22 approval of frozen design v1.3 and ruling to redesign and re-pilot EVD-JOINT-001. The archive carries the latter approval states as dated second-hand reports in the documents that act on them, rather than as separate first-hand decision records (Appendix D.4). ⟦[WP] §4.1-4；末项为清单外补登，见交付注记 D-2⟧

<!--block:B0351-->
Policy conformance. This disclosure is written to COPE guidance on AI use in research and publication and to the AI policies of the target journals. ⟦[WP] §4.1-5；COPE 无在册书目条目，未加编号引用——见交付注记 D-3⟧

<!--block:B0352-->
Authorship and responsibility. AI systems are not listed as authors. The CRediT role `Writing – original draft` records Li Xiao Peng's direction, substantive revision, item-by-item approval, and responsibility for the AI-assisted initial text; it does not attribute autonomous authorship to an AI system. ⟦[WP] §4.1-6；[ETH] AI Disclosure Verification⟧

<!--block:B0353-->
### Competing interests

<!--block:B0354-->
The authors declare the following structural interests. These interests are **not** removed by the measures listed below, and we do not claim that they are: the measures are what make the interests auditable by a reader who does not trust us.

<!--block:B0355-->
Self-reference, in three respects. (i) The authors produced the governance archive and the registered evidence assets used by this paper. (ii) The authors selected and interpreted the discovery inventory, so any future comparator adjudication requires transparent full-text locators and remains subject to independent re-scoring. (iii) The joint synthetic experiment was designed, implemented and adjudicated within one pipeline; no independent party replicated its endpoint.

<!--block:B0356-->
Countermeasures in place. The experimental design and failure boundary were pre-registered; generation and inference artefacts are hash-bound; failed runs are retained; and adversarial review occurred at three checkpoints. For literature comparison, unsupported ✓/◐/✗ scores and element counts have been withdrawn. The discovery inventory and Appendix A now expose `unknown` cells and the full-text evidence requirements for any future recoding rather than inviting readers to reproduce an under-supported score.

<!--block:B0357-->
These mechanisms have intercepted defects in this work, not merely been declared. A sign inversion in an independent-proposal kernel passed unit testing and was exposed by a calibration probe; the fabricated Phase 3 delivery described in the AI-use disclosure above was caught by on-disk verification; and a zero-margin defect in a pass threshold was caught by adversarial review. We report this as evidence that the mechanisms operate, **not** as evidence that the conclusions are correct — an intercepted defect bounds neither the number nor the severity of defects not intercepted. ⟦上游提供的可选实证，采用；边界句按上游明令写死⟧

<!--block:B0358-->
### Funding

<!--block:B0359-->
This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors.

<!--block:B0360-->
### Code and data availability

<!--block:B0361-->
The framework is implemented in the `geodeepbayes` package at `https://github.com/xiaopengcug/GeoDeepBayes1.0.1`. The paper-specific materials are distributed as the curated release `paper01-rasti-v1.0.0`; its release record carries the full commit identifier and archive DOI. The release binds the diagnostic contract, evidence registry, per-evidence hashes, joint-pilot registration and failure records. The Supplement provides the observed Windows/Python environment, minimum input/output/unit contract, clean-environment test and replay commands, supported component boundaries and failure-escalation rules. The replay was author-managed; an independent-team replay has not been completed, and the reported environment is not a performance benchmark.

<!--block:B0362-->
The manuscript reports Synthetic-run and data-ingestion evidence but no Field-validated result. Public-data source records and redistribution terms must accompany every released artefact; vendor DLLs and licence-bound SDKs are not distributed. The curated GitHub release binds code, data manifests, replay scripts, expected statuses, licence and access statements to an exact revision. This availability supports inspection and author-managed replay; it does not establish independent reproduction.

<!--block:B0363-->
### Author contributions

<!--block:B0364-->
Li Xiao Peng: Writing – original draft, Conceptualization, Methodology, Software, Validation, and Formal analysis. Hu Xue Ping: Writing – review & editing. Dong Jian: Writing – review & editing. Chen Lei: Formal analysis. Ma Li Xin: Data curation.

<!--block:B0365-->
## Appendix A. Nearest-neighbour discovery inventory and full-text recoding protocol

<!--block:B0366-->
This appendix records how an identity-verified candidate may be recoded from `unknown` using location-specific full-text evidence. It does not publish a current coverage score or rank. The protocol is included because the framework authors also selected the comparator inventory, and transparent evidence locators are required for independent reassessment.

<!--block:B0367-->
### A.1 Status vocabulary

<!--block:B0368-->
- **unknown** — no identity-verified, location-specific full-text evidence bundle has adjudicated the cell.
- **supported** — the full text explicitly exhibits the defined element, with a page, section or paragraph locator recorded.
- **not supported in the reviewed full text** — a documented, prespecified full-text review assessed the element and found no qualifying construction; this is limited to that reviewed work and is not a literature-absence claim.

<!--block:B0369-->
Every current discovery-inventory element cell is `unknown`. The former ✓/◐/✗ grades and their counts are historical working records only and carry no manuscript decision role.

<!--block:B0370-->
### A.2 Full-text evidence requirement

<!--block:B0371-->
Each element is adjudicated separately. A record must identify the exact work, full-text version, evidence locator, element definition, adjudicator and date. Title, abstract, metadata, citation context and inability to obtain a full text cannot establish that an element is absent.

<!--block:B0372-->
> For each element, what exact full-text passage shows that the work does or does not implement the defined construction, and where is that passage located?

<!--block:B0373-->
The evidence bundle must preserve the quoted or faithfully paraphrased passage within copyright limits, its page/section/paragraph locator, the identity-verification record and the adjudication rationale. If any required field is missing, the cell remains `unknown`. Provenance discipline and physical-property content are recorded as separate fields rather than collapsed into a single grade.

<!--block:B0374-->
The earlier draft's prior-content contrast and its claim that ten row scores were unchanged are withdrawn from the manuscript evidence. They may be reconsidered only through the full-text protocol above and cannot be recovered from the former marks themselves.

<!--block:B0375-->
### A.3 Evidence-neutral wording discipline

<!--block:B0376-->
A cell description must distinguish an observed full-text construction from an unreviewed possibility. Phrases such as “lacks”, “absent”, “none” or “off-axis” require a completed full-text adjudication and its locator; otherwise the only admissible status is `unknown`.

<!--block:B0377-->
This rule applies to all four element fields. It prevents incomplete retrieval, abstract silence or an inaccessible record from being rewritten as evidence of absence. It also prevents a mechanism description from silently becoming a rank or nearest-neighbour conclusion.

<!--block:B0378-->
### A.4 Evidence bundle and regeneration rule

<!--block:B0379-->
The inventory separates bibliographic discovery from element adjudication. A non-`unknown` cell requires a full-text quotation or paraphrase with page, section or paragraph locator and an identity-verified source. No title, abstract, metadata record or inaccessible candidate is scored as absence. Rows may be recoded only by updating the evidence bundle and regenerating both the discovery inventory and this appendix; unresolved records remain outside any count.

<!--block:B0380-->
### A.5 Full-text recoding queue

<!--block:B0381-->
**Table A.1. Full-text recoding queue for the registered nearest-neighbour inventory.** `unknown` means that no location-specific full-text evidence bundle was completed in this revision; it is not a negative score.

<!--block:B0382-->
| Nearest neighbour | Auditable priors | Shared-error likelihood | Multi-scale | Pre-registered governance | Decision use |
|---|---|---|---|---|---|
| Bosch (1999) | unknown | unknown | unknown | unknown | none |
| Bosch and McGaughey (2001) | unknown | unknown | unknown | unknown | none |
| Afonso et al. (2013) | unknown | unknown | unknown | unknown | none |
| Astic and Oldenburg (2019) | unknown | unknown | unknown | unknown | none |
| Moorkamp et al. (2011) | unknown | unknown | unknown | unknown | none |
| Hawkins and Sambridge (2015) | unknown | unknown | unknown | unknown | none |
| Blatter et al. (2021) | unknown | unknown | unknown | unknown | none |
| Alemie and Sacchi (2011) | unknown | unknown | unknown | unknown | none |
| Miller and Dunson (2019) | unknown | unknown | unknown | unknown | none |
| Jacob et al. (2017) | unknown | unknown | unknown | unknown | none |
| Afonso (2026) | unknown | unknown | unknown | unknown | none |

<!--block:B0383-->
⟦R-2 · [SYN] §3.2 表（十行）+ 2026-08-20 修订记录增列 Afonso 2026 行；(d) 单元格取 2026-08-21 核改后正典⟧

<!--block:B0384-->
## Appendix B. Decision-layer numerical illustration

<!--block:B0385-->
Section 5 defers its numerical illustrations to this appendix. Every value printed below carries the label **"synthetic placeholder, not evidence"**. It was invented for exposition, it is not the output of any run, model or data set used in this work, and no statement anywhere in this paper rests on it. ⟦大纲 §6(a) 5.5 隔离声明 + §6(c) 禁令 5 标签逐字；[BP] §5（DA Checkpoint 1 Major #3）⟧

<!--block:B0386-->
The illustrations are included because three of the interface's contracts are prohibitions, and a prohibition is easier to enforce once the mistake it forbids has been shown at least once. All quantities are dimensionless: they are ratios, standardised units or scores. No quantity here is expressed in a physical, monetary or tonnage unit, and none is a resource or reserve figure. ⟦大纲 §6(c) 禁令 2；[RR] §7.1-4；§5.5 的绝对措辞（本附录据其收窄）⟧

<!--block:B0387-->
### B.1 Why draws may not be broken apart

<!--block:B0388-->
Section 5.1 requires that every component of a per-draw total be taken from the same draw, and that quantiles be taken only over the set of per-draw totals. Table B.1 shows why the requirement is not a formality. Eleven synthetic draws carry two dimensionless factors, $a$ and $b$, whose per-draw product $Q=ab$ is the quantity of interest. The eleven draws are ordered arbitrarily; the factors are negatively associated within draws, which is the ordinary situation when two properties are constrained by the same observations.

<!--block:B0389-->
**Table B.1.** Values are "synthetic placeholder, not evidence". Eleven per-draw records and their per-draw totals.

<!--block:B0390-->
| Draw | $a$ | $b$ | $Q=ab$ |
|---|---|---|---|
| 1 | 0.5 | 2.0 | 1.00 |
| 2 | 0.6 | 1.8 | 1.08 |
| 3 | 0.7 | 1.7 | 1.19 |
| 4 | 0.8 | 1.5 | 1.20 |
| 5 | 0.9 | 1.4 | 1.26 |
| 6 | 1.0 | 1.3 | 1.30 |
| 7 | 1.1 | 1.1 | 1.21 |
| 8 | 1.2 | 1.0 | 1.20 |
| 9 | 1.3 | 0.9 | 1.17 |
| 10 | 1.5 | 0.8 | 1.20 |
| 11 | 1.8 | 0.6 | 1.08 |

<!--block:B0391-->
With eleven draws the order statistics are exact and no interpolation convention is needed: the $p$-quantile is the $(10p+1)$-th value of the sorted sample. Applying the fixed convention of Section 5.1, $P90=q_{0.10}$, $P50=q_{0.50}$ and $P10=q_{0.90}$, to the sorted per-draw totals gives $P90=1.08$, $P50=1.20$ and $P10=1.26$. ⟦D-1 · 语料 `03::3.4.3` Step 1；WP4 契约；[BP] §5⟧

<!--block:B0392-->
Now reconstruct the same three summaries the way the specification forbids: take each factor's own marginal quantile and multiply. The marginal quantiles are $q_{0.10}(a)=0.6$, $q_{0.50}(a)=1.0$, $q_{0.90}(a)=1.5$ and $q_{0.10}(b)=0.8$, $q_{0.50}(b)=1.3$, $q_{0.90}(b)=1.8$. The recombined summaries are $0.6\times0.8=0.48$, $1.0\times1.3=1.30$ and $1.5\times1.8=2.70$.

<!--block:B0393-->
**Table B.2.** Values are "synthetic placeholder, not evidence". The two aggregations compared.

<!--block:B0394-->
| Summary | Quantile of per-draw totals (specified) | Product of marginal quantiles (forbidden) |
|---|---|---|
| $P90$ | 1.08 | 0.48 |
| $P50$ | 1.20 | 1.30 |
| $P10$ | 1.26 | 2.70 |

<!--block:B0395-->
The specified interval spans a factor of about 1.17 from $P90$ to $P10$; the recombined one spans a factor of about 5.6. The recombination has not made the answer more conservative in any useful sense — it has manufactured a spread that no draw exhibits, by pairing each factor's low value with the other's low value although no draw contains that pair. It also moves the central summary, so the error is not confined to the tails. This is the concrete content of the rule that draws are never broken apart and that these quantities are never reconstructed from marginals. ⟦D-1 · 语料 `03::3.4.3` Step 1 逐 draw 纪律；本表为该纪律的算例，不引入新契约⟧

<!--block:B0396-->
### B.2 A score is not a probability

<!--block:B0397-->
Section 5.2 reserves the word probability for an output produced under a frozen event definition with isolated calibration data, and calls anything else a score. Table B.3 makes the distinction concrete. Five targets carry an uncalibrated weighted score; against a frozen event definition and an isolated calibration set, the observed frequency of the event in each score band is also shown.

<!--block:B0398-->
**Table B.3.** Values are "synthetic placeholder, not evidence". Uncalibrated scores against observed frequencies under a frozen event definition.

<!--block:B0399-->
| Target | Uncalibrated score | Observed frequency in band |
|---|---|---|
| T1 | 0.20 | 0.05 |
| T2 | 0.35 | 0.11 |
| T3 | 0.50 | 0.18 |
| T4 | 0.65 | 0.30 |
| T5 | 0.80 | 0.55 |

<!--block:B0400-->
The scores rank the five targets in the same order as the frequencies, and they already lie in $[0,1]$. Neither fact makes them probabilities: the score of T3 is 0.50 while the event occurs in that band with frequency 0.18, and no clipping, rescaling or renaming closes that gap, because the gap is not an artefact of range but the absence of a calibration map. A monotone relabelling would reproduce the frequencies here and would still carry no guarantee at a sixth target outside the calibration set. This is why the distinction is carried in the field names of the interface rather than in prose alone. ⟦D-2 · 语料 `03::3.4.3` Step 2；[BP] §5；大纲 §6(c) 禁令 3⟧

<!--block:B0401-->
### B.3 The information record, with its value slots empty

<!--block:B0402-->
Section 5.3 fixes what every information-gain record must declare. Table B.4 shows the record as the interface requires it to be filled. The value column is **deliberately empty**, and the reason is a commitment made in Section 5.5: this paper states no expected-information-gain and no expected-value-of-sample-information number, in this appendix or anywhere else. What the interface specifies is the record; what the paper declines to supply is its value. ⟦D-3 · 语料 `03::3.4.2`；大纲 §6(c) 禁令 1（禁 EIG/EVSI 数值主张）；§5.5 绝对措辞⟧

<!--block:B0403-->
**Table B.4.** Values are "synthetic placeholder, not evidence". Required fields of one information record.

<!--block:B0404-->
| Field | Required entry | Value |
|---|---|---|
| `information_type` | one of design-EIG, realised gain, leave-one-method-out forward divergence | — |
| target $\psi$ | the named functional the gain is about | — |
| baseline and conditioning set | the distribution the divergence is taken against | — |
| divergence direction | which argument is the first | — |
| common support | the set on which both densities are positive | — |
| estimator | the named estimator and its nesting structure | — |
| replication count | number of outer draws | — |
| Monte Carlo standard error | reported, not omitted | — |
| nested-estimator errors | outer design-sampling error, inner evidence-estimation error, failure rate | — |

<!--block:B0405-->
Three such records are three different quantities even when they name the same $\psi$; their separation and the operations that are not permitted on them are stated in Section 5.3 and are not restated here. ⟦D-3 · §5.3 单源；本附录不复制其禁令句⟧

<!--block:B0406-->
### B.4 Risk preference as an explicit input

<!--block:B0407-->
Section 5.4 makes risk preference an explicit frozen input through $\mathrm{ENPV}_\gamma=\mathrm{ENPV}-\gamma\,\sigma(\mathrm{NPV})$ and states that where $\gamma$ has not been elicited and calibrated, only a scenario analysis over a $\gamma$ grid is reported. Table B.5 is such a grid. Two actions are compared, with every quantity expressed in units of a common reference scale $\sigma_0$, so that no monetary figure appears: action A1 has $\mathrm{ENPV}=1.00\,\sigma_0$ with $\sigma(\mathrm{NPV})=1.00\,\sigma_0$, and action A2 has $\mathrm{ENPV}=1.20\,\sigma_0$ with $\sigma(\mathrm{NPV})=1.80\,\sigma_0$.

<!--block:B0408-->
**Table B.5.** Values are "synthetic placeholder, not evidence". $\mathrm{ENPV}_\gamma$ in units of $\sigma_0$ over a grid of $\gamma$.

<!--block:B0409-->
| $\gamma$ | A1 | A2 | Preferred |
|---|---|---|---|
| 0.00 | 1.00 | 1.20 | A2 |
| 0.25 | 0.75 | 0.75 | indifferent |
| 0.50 | 0.50 | 0.30 | A1 |
| 0.75 | 0.25 | $-0.15$ | A1 |
| 1.00 | 0.00 | $-0.60$ | A1 |

<!--block:B0410-->
The preferred action changes at $\gamma=0.25$, and that indifference point is not a threshold anyone chose: it follows from equality of the criterion between the two actions, which is what Section 5.4 means by decision thresholds being endogenous. The grid also shows why $\gamma$ cannot be left implicit or carried over from another project — the recommendation over this pair is not a property of the posterior alone, and reporting a single preferred action without stating $\gamma$ would conceal that the answer changes within a narrow span of a quantity that has no cross-project typical value. ⟦D-4 · 语料 `03::3.5.2`（Eq. 3.5-1 及其量纲/标签边界）；[BP] §5；阈值内生性见 §5.4 末⟧

<!--block:B0411-->
### B.5 What this appendix does not license

<!--block:B0412-->
Nothing in this appendix is exercised, calibrated or evidenced. The tables above are arithmetic on invented inputs, and their only function is to fix the meaning of four contracts. In particular, no number here supports any claim about a deposit, an action, an information gain or a decision, and none may be quoted outside this appendix. ⟦大纲 §6(a) 5.5 隔离；[RR] §7.1-4/-5；§5.5「specified and uncalibrated; it is not exercised in this work」⟧

<!--block:B0413-->
## Appendix C. Literature search and verification protocol

<!--block:B0414-->
Every entry cited in this paper passed the protocol described here, and no claim is made about literature outside the set it produced. The protocol is published in full so that the source discipline claimed by this paper can itself be audited. ⟦[SYN] §1；[LCM] §2；§2.1 前向引用点（"the four-channel verification protocol of Appendix C"）⟧

<!--block:B0415-->
### C.1 The four channels

<!--block:B0416-->
Each candidate record was checked against four independent bibliographic services, each of which plays a different role.

<!--block:B0417-->
**Table C.1.** Verification channels and their roles.

<!--block:B0418-->
| Channel | Role | Check applied |
|---|---|---|
| Crossref REST API | primary registration authority for journals and books | direct resolution of the claimed identifier, plus bibliographic title search; title, authors, container, year, volume, issue and pages compared field by field |
| DataCite API | registration authority for preprints and data sets | resolution of preprint identifiers; a journal identifier returning nothing here is an **expected negative**, since the two registries are disjoint |
| OpenAlex | first independent index | direct resolution and field comparison, together with the retraction flag |
| Semantic Scholar Graph API | second independent index | direct resolution and field comparison; also used to supply volume, issue and page fields absent elsewhere |

<!--block:B0419-->
A candidate passes only if all three substantive channels resolve it, if the three normalised titles are identical after case and punctuation are stripped, if every field conflict is resolved by registry evidence rather than by judging the records close enough, and if the retraction flag is false. ⟦[E2REG] §1.1 四通道语义 / §1.2 PASS 判据；[RR] §2.3⟧

<!--block:B0420-->
Two operational rules apply to the channels. First, where none of the four carries page ranges (which occurs for several statistics journals) pages were supplied from the publisher's own article page together with independent citation records, and the supplement is recorded as such rather than folded into a channel result. Second, and more consequentially, **a transport failure is never recorded as a registry negative**: rate limiting, timeouts and transport errors are logged separately from a genuine absence and retried under backoff. Collapsing the two would let a single episode of rate limiting manufacture a false absence verdict, which is the one failure mode capable of inverting the discipline described next. ⟦[RR] §2.3 页码补证；[E2REG] §1.3 逐字纪律⟧

<!--block:B0421-->
### C.2 The verdict vocabulary

<!--block:B0422-->
Three verdicts are used, and they are not degrees of confidence.

<!--block:B0423-->
- **VERIFIED** — the work exists and every declared field agrees with the registry record, typographic differences of case and hyphenation excepted.
- **MISMATCH** — the work exists but the declared metadata do not match. This includes the case in which a declared identifier resolves to a different paper, which is treated as the strongest single indicator of a record that was never checked against a registry.
- **NOT_FOUND** — the work cannot be retrieved under the combination of author, title and year declared for it.

<!--block:B0424-->
Over these three sits one rule, applied without exception: **a record that has not been confirmed by reproducible registry evidence is not citable.** There is no intermediate status in which an unconfirmed record is retained because it is probably correct. In particular NOT_FOUND is treated as disqualifying rather than as an invitation to search further, and a record whose verification channel is unavailable falls into the same category as one that failed. ⟦[RR] §2.3 判定口径 + 灰区 = FAIL 铁律；`verification-ch0207.md` 判定口径三条逐字⟧

<!--block:B0425-->
The rule is deliberately costly. It excluded records that may be genuine but that this pipeline could not confirm, including Chinese-language candidates not independently verified through the four channels. Those records are absent from the evidential comparison and final reference list and carry no argument. The resulting coverage loss is accepted and disclosed because a status meaning probably fine is precisely the status under which unverified records propagate.

<!--block:B0426-->
### C.3 Controls, and why an all-green result is not evidence

<!--block:B0427-->
A verification pipeline that returns a pass for everything it is given may be working, or may not be running at all, and the two are indistinguishable from the output. Every verification batch therefore carried both a positive and a negative control.

<!--block:B0428-->
**Table C.2.** Controls carried with each batch.

<!--block:B0429-->
| Control | Purpose | Expected outcome |
|---|---|---|
| Positive, journal identifier | show that the resolution path works | all three substantive channels resolve it |
| Positive, preprint identifier | show that the preprint registry is not failing wholesale, so that its other empty responses can be read as registry disjointness rather than as breakage | the preprint registry resolves it |
| Negative | show that the pipeline can produce a negative at all | a record already adjudicated absent is returned absent by all four channels |

<!--block:B0430-->
The negative control is the one that carries the weight. Without it, a batch reporting that every candidate passed would be consistent with a pipeline that cannot fail anything, and the pass verdicts would be an artefact of the instrument rather than a measurement. The negative control used here reproduced an absence verdict reached independently in an earlier batch, which is what licenses reading the passes as measurements. ⟦[E2REG] §1.4 三组对照实测 + 「没有 NEGCTRL 的全绿扫描不构成证据」；[WP] §3.3 扫描纪律⟧

<!--block:B0431-->
### C.4 What the protocol returned

<!--block:B0432-->
Two verification agents, working independently of the search that produced the candidates and of each other, returned **62 verdicts** across two batches (30 and 32 respectively) comprising 30 VERIFIED, 27 MISMATCH and 5 NOT_FOUND. Where a verdict overlapped an included entry, confirmed field values were adopted and mismatched records were either corrected against the registry or excluded; no conflict between the two agents was left unresolved. ⟦[RR] §2.3 62 条判决逐条分布；`verification-ch0104.md`（30 条：14/14/2）；`verification-ch0207.md`（32 条：16/13/3）；[LCM] §5⟧

<!--block:B0433-->
The mismatches were not scattered. They concentrated in the most recent additions to the internal pool and shared a recognisable set of signatures: identifiers resolving to unrelated real papers rather than to nothing, the same record carrying different identifier variants in different versions of the same source file, body text and reference list disagreeing on author and year for the same entry, and volume, issue or page fields colliding between entries. Identifiers that resolve to real but unrelated work are the signature that distinguishes a record composed from memory from a record mistyped, since a mistyped identifier ordinarily resolves to nothing. ⟦[CCA] §3 四指纹；[LCM] §4 池级三特征；[BIB] §1.2⟧

<!--block:B0434-->
Two verified counts describe the bibliographic-failure finding and are not interchangeable. The distortion registry contains 24 individually identifiable entries. Separately, 23 of 41 English-language entries selected for focused re-checking were distorted; that ratio describes only the defined subset and is not a pool-wide rate. Earlier workflow notes also counted verification events, including records later corrected, but those event counts are not used as a publication-flow statistic here.

<!--block:B0435-->
The pattern is consistent with a corpus-scale contamination phenomenon described in the recent literature. That description is used here as motivation only: the record describing it is itself outside the verified set, so under the rule of Section C.2 it is not cited, does not appear in the reference list, and carries no evidential weight. The evidence for contamination in this work is the pipeline's own verdicts and registry, not an external claim about the phenomenon. ⟦[RR] §5.3 边界声明逐字（仅动机叙述、不进参考文献、不作证据引用）；大纲 §12 附录 C 行「Zhao et al. 仅动机叙述不入参考文献」；[ETH] A-4⟧

<!--block:B0436-->
Entries retained in the registered search archive but not cited in the manuscript are not reproduced in the final reference list. Accordingly, the search-base counts in this appendix describe the research audit and are not the number of references cited by the paper.

<!--block:B0437-->
### C.5 The targeted forward scan

<!--block:B0438-->
The verified base was later extended twice under the same protocol, each extension registered as an erratum against the matrices rather than folded silently into the original counts. The first extension added English-language entries where the original search had left a coverage floor unmet. The second was a forward scan of literature published from 2024 onward, run against the four elements of the comparison claim after a closer neighbour was found by accident during the first. Its results are reported in Section 2.2 and are not repeated here; what belongs in a protocol appendix is how the scan was run and what it revealed about the channels themselves.

<!--block:B0439-->
Three retrieval routes were planned (keyword search, forward-citation traversal from anchor entries, and enumeration of the reference lists of the closest neighbour) and each was given a positive control: an entry already known to occupy the relevant space had to be returned by the route. **Two of the three routes failed their positive control.** Keyword search failed because relevance ranking buried the known entry below the retrieved depth, and forward-citation traversal failed because citation-graph ingestion lags recent publication, so a paper published a few months earlier had not yet accumulated retrievable citing records. A fourth route added in response (full enumeration of the candidate journals over the period) returned the known entry and was the only route whose sensitivity was established. ⟦[E3] §3.1/§3.2/§3.3 逐条失效机理与实测⟧

<!--block:B0440-->
This is reported rather than quietly repaired because it bears on how the scan's negative half may be read. A search route that cannot return an entry it is known to contain provides no evidence of absence, and the absence findings of that scan rest on the enumeration route alone. The scan is not exhaustive: its effective negative evidence covers the enumerated journals over the stated period, occupancy was judged from abstracts, and the discovery that prompted it was itself accidental — which is direct evidence that the original recall was below unity and is the reason the search-scope qualification attached to the comparative positioning is retained rather than relaxed.

<!--block:B0441-->
### C.6 Search-accounting boundary

<!--block:B0442-->
The archive records 458 identified records, 23 duplicate or placeholder removals, and 97 entries retained in the registered search base. It does not contain a replayable record-level derivation of the exact number excluded at title-and-abstract screening. The former value 294 was obtained as an arithmetic closure residual and is therefore withdrawn. No PRISMA-style flow or exact screening-exclusion total is claimed.

<!--block:B0446-->
Of the 97, the 41 internal entries are those that survived verification or were corrected against a registry; no internal record was carried on the strength of its own pool listing. The base was subsequently extended by registered errata to **111** entries. ⟦[BIB] §2 标题实测 N = 111（97 + 9 + 1 + 4）；[RR] §10 已同步⟧

<!--block:B0447-->
## Appendix D. Pre-registration summary and run-history ledger (EVD-JOINT-001)

<!--block:B0448-->
### D.1 What this appendix is, and what it is not

<!--block:B0449-->
This appendix summarises the pre-registration governing the joint synthetic asset and records the sequence of nodes through which that asset has passed. **It is a summary and a ledger, not an authority.** The pre-registration document itself is the authoritative text; where this summary and that document differ, the document governs, and the summary is the thing that is wrong. The distinction matters here more than it usually would, because the pre-registration is under active revision and a summary of a moving document goes stale silently. ⟦D-1 · 大纲 §12 D 行；**team lead 2026-08-22 要求 4 逐字：「写明它是摘要不是权威副本，权威在预注册件本身」**⟧

<!--block:B0450-->
The archive discipline under which the ledger is kept. Every run listed below is retained as it was produced. Runs that failed are archived as failures under their own identifiers rather than deleted or re-run over; pre-repair and post-repair executions remain distinguishable by content hash; and evaluation artefacts produced after the fact are marked as additive and modify no run artefact. A ledger whose failed entries can be removed is not a ledger, and the value of this one rests entirely on that property. ⟦D-1 · [M2] §V2.2 与 §V2.12 不可变归档纪律；大纲 §12 D 行「不可变归档纪律陈述」⟧

<!--block:B0451-->
Recording that a run happened is not reporting its result. The redesign-round entries below are diagnostic-tier process. They are listed so that the sequence of decisions is auditable, and each carries the type of conclusion it reached — not the values it produced. **No reading from any of them appears in this paper**, and none of them supports any claim in it; §7.5 remains the status statement for the asset. ⟦D-1 · 大纲 §12 D 行「M2.5 读数不入」；[M2.5] 定位行（Diagnostic 级、不进入登记册、不支撑端点结论）；与 §7.5 末段互指⟧

<!--block:B0452-->
### D.2 The pre-registration, as at 22 August 2026

<!--block:B0453-->
The design was frozen as **v1.1** before any run of the asset was executed, following an independent design review that returned approval with conditions; every condition was written into the frozen text rather than tracked separately. A second version, **v1.2**, was issued and frozen after the pilot, carrying the revisions that the pilot's outcome required. A third version, **v1.3, has since been issued as a document in its own right**, assembled from the frozen v1.2 text and the reviewed clause drafts by a generator that embeds the earlier text byte-for-byte rather than re-typing it, with a machine check pinning that property. It carries an explicit boundary section distinguishing the clauses that fell inside the approval it received from those appended after it — **stated that way rather than smoothed over**. Two changes are deliberately excluded from it and assigned to a further version, so that they are not read as having been approved alongside the rest. **The versioning rule is that any change requires a new version number, a revision record and a fresh approval, and that revision identifiers already published are frozen and may be added to but not altered.** ⟦D-2 · [PREREG] v1.1-frozen；`design-preregistration-v1.2.md`（**磁盘现存最高冻结版本**，§5.1 继承声明与末段冻结纪律逐字）；`v13-approval-package.md` §D「批准的直接后果」；**v1.3 未签发 = 本人 2026-08-22 磁盘枚举实测，见注记 4**⟧

<!--block:B0454-->
What a reader should take from the version history is its shape rather than its contents. Each version was frozen before the runs it governs, revisions were issued as additions with their own identifiers instead of edits to existing text, and the count of clauses has grown at every revision. The current version carries **nine families and sixty-five clauses, as at the incorporation of the last family and excluding the appendices appended after approval**. **That figure is stated with its cut-off and its enumeration scope because it is meaningless without them** — the same list has carried four different totals during its assembly, **of which two were counting errors that were subsequently declared and corrected by the assembling party, and two are the same enumeration at two points in its growth**. We report the distinction rather than the total alone, because a total that has moved is uninformative unless a reader can tell which movements were corrections and which were growth. **We state the figure as of the date above and not as a property of the design.** ⟦D-2 · `v13-approval-package.md` §2 逐族清单（**9 族 65 节**，2026-08-22 12:08；族小节字母 A–I 实测）；**范围限定 = team lead 2026-08-22 转达口径**（截至族 I 并入；不含批准后追加的附录 D–J，它们从未进入任何族编制）；**「计数须与截止时点 + 枚举范围一同给出」= §10.5-40**；**四个总数的传播链**（19→30→40→51→65 的同一清单不同时点）见 `v13-approval-package.md` §8.1 ①⟧ ⟦D-2 · `v13-approval-package.md` §2 逐族清单（**呈批件自陈 9 族 65 节，2026-08-22 12:08**）；**注记 3 登记其与载体清单「8 族 51 节」的并存不一致**；**不把计数写成设计的属性 = 本件判断**⟧

<!--block:B0455-->
### D.3 Run-history ledger

<!--block:B0456-->
Registered nodes — the spine of the asset, reported in §6.4 and §7.5.

<!--block:B0457-->
| Node | Purpose | Executed | Conclusion type |
|---|---|---|---|
| Design freeze (v1.1) | Fix the design and its endpoints before any run | Yes | *Frozen; conditions incorporated* |
| Calibration probe | Check the sampler's operating point before the pilot | Yes | *Failed; defect exposed* |
| Defect repair (F-M2-1) | Correct a sign inversion in an independent-proposal kernel | Yes | *Repaired; regression tests added* |
| Formal pilot | Measure whether the diagnostics gate is attainable across the registered scenario families | Yes | *Gate not attained; pre-registered failure path* |
| Coupling-strength selection | Select the guardrail value from eligible runs | Yes | *Eligible set empty; pre-committed branch executed* |
| Redesign ruling | Decide the asset's disposition after the negative pilot | Yes | *Redesign ordered; production suspended* |

<!--block:B0458-->
Redesign-round nodes — **diagnostic tier, not endpoint evidence. The ledger records execution states and conclusion-type labels, but no numerical reading from these nodes appears in this paper.**

<!--block:B0459-->
| Node | Question it was posed to answer | Executed | Conclusion type |
|---|---|---|---|
| Gate-attainability probe | Whether the registered gate is reachable at all under alternative proposal kernels | Yes | *Not attainable under the registered gate; escalated for adjudication* |
| Baseline arm | Provide the unmodified comparison point for the round | Yes | *Baseline established* |
| Stage-one arm | Whether an early exit from the round is triggered | Yes | *Early exit not triggered; stage two indicated* |
| Stage-two arms (three, plus an uncoupled control) | Whether the round's local hypothesis holds | Yes | *Local hypothesis refuted under the frozen decision table* |
| Mediation arm | Whether one nuisance channel mediates the effect | Yes | *Not evaluated — a frozen precondition failed, so the arm does not bear on the hypothesis* |
| Discriminating arm | Whether the mediation runs through the channel's value or its movement | Yes | *Negative half established; positive half not separable from a competing mechanism* |
| Placebo arm | Whether the effect is specific to the channel or general to the clamping operation | Yes | *Specific to the channel; both competing paths excluded* |
| Pinned-value round | Whether the surrogate's pinned constant should be changed | **Executed** | *— (executed; formal adjudication not yet issued)* |

<!--block:B0460-->
The last row carries a state, not a blank, and the states are three rather than two. A node that was never planned, a node approved but not yet executed, and a node executed but not yet adjudicated are three different things, and a ledger that renders any of them as absence has destroyed a distinction a reader needs. This row has passed through the second state into the third: it is recorded as executed, and its conclusion is withheld because the reading has not been issued — **not because there is nothing to report**. ⟦D-3 · `pin-value-precommitment.md` / `pin-value-round-design.md` / **`pin-value-results.md`（9,441 B / 2026-08-22 19:06:46，本人实测落盘）**；**team lead 2026-08-22 要求 3 逐字：「『已批准未执行』与『未曾计划』是不同状态，须可区分」**；**结论暂不落笔的依据 = team lead 2026-08-22「正式判读未到，不要据此写任何结论」**⟧

<!--block:B0461-->
### D.4 The ledger's own limits

<!--block:B0462-->
This appendix has four limits. **The conclusion types are types, not summaries**: an entry reading *not separable from a competing mechanism* records that the run reached that state, and a reader who wants to know which mechanisms, or by how much, will not find it here or anywhere else in this paper. **The redesign round is unfinished**: the ledger's last row is open, the pre-registration's next version is unissued, and both will change. The date at the head of §D.2 is the date at which every statement in this appendix was true. ⟦D-4 · [ES]；§7.5 状态；**截止时点三处对齐锁见头注**⟧

<!--block:B0463-->
The cut-off is a date, and the state it describes moved within that date. Two of the statements above changed on the day this appendix was written: a version was issued and a round was executed, both after the text describing them had been drafted. A date-granularity cut-off cannot express intra-day change, and a reader who assumes the appendix describes the end of the stated day will sometimes be reading a description of its morning. The remedy is not a finer cut-off — it is that every statement here names the artefact it rests on, so that a reader can check the artefact rather than trust the date. ⟦D-4 · **本人 2026-08-22 19:1x 实测：`design-preregistration-v1.3.md` 19:10:18 落盘、`pin-value-results.md` 19:06:46 落盘，二者均晚于本件初稿**；**⇒ 该限度是本件自身经历的，不是设想的**⟧

<!--block:B0464-->
And the approval states recorded here rest on second-hand records. Where a row reports that a decision was approved, what the project archive holds is the decision as reported within the documents that act on it, not a separate first-hand record of the decision itself. The decisions are not in doubt; **what is absent is an independent trace of them**, and a governance appendix that did not say so would be claiming a stronger provenance than it has. ⟦D-4 · **本人 2026-08-22 实测：仓内各处「用户裁定」均为转述，一手记录不在本仓**；**team lead 2026-08-22 裁定「这是一条真限度，且它现在才被指出来」并要求写入本件**；处置另路进行⟧

<!--block:B0465-->
## Appendix E. Notation and variable dictionary

<!--block:B0466-->
### E.1 Scope of this index

<!--block:B0467-->
This appendix is a symbol index for the whole paper. It lists each symbol, what it denotes, and the section in which it is defined; it does not define anything, and no symbol appears here that is not introduced in the body.

<!--block:B0468-->
It does **not** duplicate Table 1. Table 1 is the variable dictionary for the nodes of the joint decomposition of Eq. (3.1) and carries their dimensions, their parents, and the single point at which each enters the model; that table remains authoritative for those three properties, and where the two disagree Table 1 governs. What this appendix adds is coverage (the observation contracts, the prior stack, the scale mechanisms, the samplers and the validation quantities all introduce symbols that are not nodes of the graph) together with Section E.3, which resolves the symbols that carry more than one meaning. ⟦[OUTLINE] §12 附录 E 行「与 §4.1 变量字典表一致」；§13 表 1 行；单源纪律：三列归表 1，本附录只给意义与定义位⟧

<!--block:B0469-->
No numerical value appears in this appendix. Frozen constants, thresholds and registered readings are given where they are used and are not repeated here.

<!--block:B0470-->
### E.2 Symbols by role

<!--block:B0471-->
**Table E.1.** Notation index. Section numbers give the defining occurrence.

<!--block:B0472-->
| Symbol | Meaning | Defined in |
|---|---|---|
| **State and graph** | | |
| $c$ | model or dimension index; indexes the components of the disjoint union | 3.1 |
| $z$ | within-model lithology labels | 3.1 |
| $m$ | continuous property fields | 3.1 |
| $m_i$ | the $i$-th property field | 3.3 |
| $\xi=(\xi_g,\xi_a,\xi_t)$ | shared systematic nuisance: bounded geometry offset, positive gain, clock offset | 3.2 |
| $\delta$ | model discrepancy | 3.1 |
| $\delta_{\rm surr}$ | surrogate error | 3.1 |
| $\lambda$ | scalar precision mixing variable of the Student-$t$ observation layer | 3.1 |
| $\nu$ | degrees of freedom of the Student-$t$ observation layer | 3.1 |
| $\Theta$ | hyperparameters | 3.1 |
| $\Theta_{\rm surr}$ | the block of $\Theta$ governing surrogate error | 3.2 |
| $h$ | frozen configuration: discretisation, geometry, bands or gates, realisation-map version | 3.1 |
| $D_{\rm val}$ | fixed high-fidelity validation set, source-id-exclusive | 3.1 |
| $\mathcal{C},\ \mathcal{Z}_c,\ \mathcal{M}_c$ | model index set, label space, property space of model $c$ | 3.1 |
| $n_c$ | dimension of $\mathcal{M}_c$ | 3.1 |
| **Observation layer** | | |
| $d_k,\ d_k^{\rm raw}$ | realised and raw observations of method $k$ | 3.2 |
| $T_{h,k}$ | realisation contract of method $k$: channel order, units, masks, inverse-transform metadata | 3.2 |
| $F_k^h$ | forward map of method $k$ under configuration $h$ | 3.2 |
| $\epsilon_k$ | method-specific observation noise | 3.2 |
| $n_d,\ n_k$ | total realised data length; length for method $k$ | 3.2 |
| $K$ | number of methods | 3.2 |
| $\mu$ | mean function of the observation layer | 3.1 |
| $r$ | residual $d-\mu$ | 3.2 |
| $\Omega$ | Student-$t$ **scale** matrix, not a marginal covariance | 3.2 |
| $\Omega_k$ | within-method block of $\Omega$ | 3.2 |
| $B,\ K_u$ | common-mode loading matrix; shared latent kernel over space, time and frequency | 3.2 |
| $M_k$ | co-location or same-batch matching matrix of method $k$ | 3.2 |
| $\rho_{kl}$ | loading correlation of the single common mode between methods $k$ and $l$ | 3.2 |
| $\sigma_{k,i}$ | noise standard deviation of observation $i$ of method $k$ | 3.2 |
| $\epsilon_{\rm spd}$ | positive ridge enforcing strict positive definiteness | 3.2 |
| $K_\delta,\ K_s$ | covariance kernels of discrepancy and of surrogate error | 3.2 |
| $\Phi_k$ | explicit petrophysical map required before a quantity is shared across protocols | 3.2 |
| **Prior stack** | | |
| $p_{\rm str},\ p_{\rm phy},\ p_{\rm geo}$ | structural, petrophysical and interpretation-driven factors of the product of experts | 3.3 |
| $Z(z,\Theta)$ | normalising constant of the product of experts | 3.3 |
| $S_z,\ S_m,\ S_d$ | mutually exclusive source-identifier consumption sets | 3.3 |
| $\lambda_{ij}$ | structural coupling strength between properties $i$ and $j$; zero is the retained off-state | 3.3 |
| $q_{ij}(x)$ | spatial mask of the coupling, valued in $[0,1]$ | 3.3 |
| $G_i,\ \mu_i,\ s_i,\ u_i$ | registered property transform, frozen centre and scale, resulting dimensionless variable | 3.3 |
| $s_{ij},\ b_{ij},\ \tau_{ij},\ \epsilon_{ij}$ | smooth gate of the relaxed coupling, its location, its width, its regulariser | 3.3 |
| $\rho_e,\ \eta_{\rm IP},\ \rho_{\rm abs},\ \rho_d,\ \rho_{\rm ref},\ \kappa$ | resistivity, chargeability, absolute density, density contrast, project reference density, susceptibility | 3.3 |
| $u_\kappa$ | unconstrained latent for susceptibility; the sampled variable | 3.3 |
| $c_{TI},\ a_c,\ b_c$ | training-image credibility and its Beta hyperparameters | 3.3 |
| $p_{TI},\ p_{\rm local}$ | training-image component and retained local-prior baseline | 3.3 |
| **Scale mechanisms** | | |
| $u_L,\ u_R$ | the same transformed property at local and regional support | 3.4 |
| $A_{R\leftarrow L}$ | block-averaging operator from local to regional support | 3.4 |
| $\Sigma_R$ | variogram-structured residual covariance of the transfer | 3.4 |
| $\gamma_u(h)$ | experimental variogram of one variable; $h$ here is the lag | 3.4 |
| $\Theta_{cs}$ | frozen change-of-support configuration | 3.4 |
| $m_0,\ \Phi_r,\ \alpha$ | snapshot mean, orthonormal reduced basis, reduced coordinates | 4.2 |
| $\mathcal{R},\ q^\ast,\ \widehat{L}_{\rm tune}$ | candidate rank set, selected rank, isolated tuning loss | 4.2 |
| $T_r,\ p_\alpha,\ Z_r,\ \mu_r$ | reconstruction map, coefficient prior, reduced normalising constant, pushforward measure | 4.2 |
| **Robustness layer** | | |
| $J_k$ | Jacobian of method $k$ | 3.5 |
| $L_k,\ D_m$ | frozen observation whitening operator; frozen parameter scaling | 3.5 |
| $\widetilde{S}_k,\ s_k$ | scaled sensitivity matrix; its squared Frobenius norm | 3.5 |
| $\mathrm{share}_k$ | normalised sensitivity share | 3.5 |
| $w_k,\ W_k$ | per-method scalar weight; the corresponding $w_k I_{n_k}$ | 3.5 |
| $\alpha,\ \epsilon,\ \epsilon_w$ | weight exponent; denominator regulariser; additive floor of the registered instantiation | 3.5 |
| $\pi_W$ | the weighted, generalised-Bayes target | 3.5 |
| $C_k$ | observation covariance of method $k$, a sampled node | 3.5 |
| **Inference** | | |
| $J(m)$ | anchor-generating least-squares functional | 4.1 |
| $C_d,\ C_m,\ m_{\rm prior}$ | data covariance, model covariance, prior mean of that functional | 4.1 |
| $\lambda_{\rm prior}$ | prior precision weight of that functional | 4.1 |
| $L(x)$ | likelihood at state $x$ | 4.4 |
| $\beta_\ell,\ \pi_{\beta_\ell},\ Z_{\beta_\ell}$ | inverse temperature of rung $\ell$, its target, its normalising constant | 4.4 |
| $A_{\rm swap}$ | swap acceptance probability between adjacent rungs | 4.4 |
| $x=(c,\vartheta_c)$ | trans-dimensional state and its within-model parameters | 4.5 |
| $j_\ell,\ q_\ell,\ u,\ T_\ell,\ A_\ell$ | move probability, auxiliary density, auxiliary variables, bijection, acceptance probability | 4.5 |
| $\widehat{R}$ | rank-normalised and folded split convergence statistic | 4.6 |
| **Decision interface** | | |
| $\psi$ | the target quantity an information record is about | 5.3 |
| $a,\ y,\ D_0$ | action, observation, conditioning set of an information record | 5.3 |
| $\gamma$ | risk-preference coefficient, an explicit frozen input | 5.4 |
| **Validation** | | |
| $\xi_g$ | shared geometry offset; the single latent generating the cross-method block in the registered asset | 6.4 |
| $\lambda_{gm}$ | gravity-to-magnetic structural coupling strength; its zero is the baseline arm | 6.4 |
| F1, F2, F3 | the three held-out functionals: total anomalous mass, mean susceptibility of the target block, depth to its top | 6.4 |
| $\delta_{\rm MID}$ | pre-registered minimum important difference of a functional | 6.4 |
| $N$ | number of independent scenes | 6.4 |
| $b,\ \delta$ | signed error of the uncoupled arm; displacement produced by the coupling — **local to Eq. (6.2)** | 6.4 |
| $M,\ n,\ k$ | number of chains; draws per chain; dispersion coefficient of the criterion | 6.1, F.1 |
| $R^{*}(M,n)$ | attainable upper bound of that criterion | F.1 |

<!--block:B0473-->
### E.3 Symbols carrying more than one meaning

<!--block:B0474-->
Eight symbols are reused. Each reuse is standard in its own literature, and none is an error, but the paper states the distinctions rather than relying on context.

<!--block:B0475-->
**Table E.2.** Reused symbols and their disambiguation.

<!--block:B0476-->
| Symbol | Meanings and where each holds |
|---|---|
| $\lambda$ | Four distinct objects. Unsubscripted $\lambda$ is the Student-$t$ precision mixing variable (3.1, 3.2). $\lambda_{ij}$ is a structural coupling strength between two properties (3.3), of which $\lambda_{gm}$ is the instance used in the registered asset (6.4). $\lambda_{\rm prior}$ is the prior precision weight of the anchor functional (4.1). Numerical damping introduced only for linear-algebraic stability is a fourth object and is never written $\lambda$. |
| $\alpha$ | The weight exponent of the robustness layer (3.5) and the vector of reduced coordinates (4.2). The two never appear in the same equation. |
| $M$ | The matching matrix $M_k$ of a method (3.2) and the number of chains (6.1, F.1). The first is always subscripted by a method index; the second never is. |
| $\delta$ | The model-discrepancy node of the graph (3.1, 3.2) and, **within Eq. (6.2) only**, the displacement that coupling produces in a functional's error. The second usage is local to that identity and to Appendix F. |
| $\epsilon$ | Four objects. $\epsilon_k$ is the additive observation noise of the observation equation in Section 3.2; $\epsilon_{\rm spd}$ is the SPD regulariser added to $\Omega$ in the same section; unsubscripted $\epsilon>0$ is the normalisation regulariser of the sensitivity weight in Section 3.5; and $\epsilon_{ij}$ is the positive gate regulariser of the relaxed cross-gradient coupling in Section 3.3. |
| $d$ | The observed data across methods (Table 1, Section 3.2) and, within Appendix F.1 only, the worst spread of chain means, $d=\max_i\lvert\bar{x}_i-\bar{x}\rvert$, a statistic of a proof rather than a data object. |
| $b$ | Within Eq. (6.2) and Appendix F, the uncoupled arm's signed error against the held-out truth; in Appendix B, a per-draw component of the illustration's product total ($Q=ab$, Table B.1). The two never appear in the same section. |
| $G_i$ | The registered property transform of the structural coupling (3.3), acting on a physical property to produce a dimensionless registration variable. It is not the forward map: $F_k^h$ (Section 3.2) maps the model state to an observable, and the two act on different objects. |

<!--block:B0477-->
Two conventions apply throughout and are stated once. Subscript $k$ ranges over methods and subscript $i$ or $j$ over properties or over observations within a method, as the surrounding equation makes explicit. Quantities written with a hat are estimated from a sample; quantities written with a tilde have been scaled by a frozen operator. ⟦记号约定取自 §3.2/§3.5 用法实测，非新增规范⟧

<!--block:B0478-->
## Appendix F. Analytic derivations

<!--block:B0479-->
Every result in this appendix is a consequence of a definition. None of them requires access to a run, a dataset, or an archive of this project: each can be re-derived on paper, and each is stated so that a reader can reproduce its numerical values in a few lines of code from the definitions given here. Where a result is used to say something about *this* work, the frozen constant that instantiates it is named explicitly, so that the analytic half and the project-specific half can be checked separately. ⟦F-A 总纲 · 甲类判别两问法：命题与数值均不依赖任何 run；「适用于本项目」这一半单独给冻结落点（`analytic-findings-round2.md` §0.2 边界 1 的要求）⟧

<!--block:B0480-->
### F.1 The attainable bound of a chain-mean dispersion criterion

<!--block:B0481-->
Referenced from §6.1, Eq. (6.1).

<!--block:B0482-->
Consider a criterion of the form: *each chain's mean lies within $k$ pooled standard deviations of the grand mean.* Let there be $M$ chains of $n$ draws each, write $x_{ij}$ for draw $j$ of chain $i$, $\bar{x}_i$ for the chain means, $\bar{x}$ for the mean of the chain means, and let

<!--block:B0483-->
$$
s^{2}=\frac{1}{Mn-1}\sum_{i=1}^{M}\sum_{j=1}^{n}\bigl(x_{ij}-\bar{x}\bigr)^{2}
\tag{F.1}
$$

<!--block:B0484-->
be the sample variance over the flattened sample. The quantity the criterion thresholds is $T=\max_i\lvert\bar{x}_i-\bar{x}\rvert/s$.

<!--block:B0485-->
Step 1 — the within-chain variance only enlarges the denominator. Decompose the total sum of squares by chain,

<!--block:B0486-->
$$
\sum_{i,j}\bigl(x_{ij}-\bar{x}\bigr)^{2}
=\sum_{i}\Bigl[\underbrace{\textstyle\sum_j (x_{ij}-\bar{x}_i)^2}_{=\,n W_i\ \ge\ 0}
+\;n\bigl(\bar{x}_i-\bar{x}\bigr)^{2}\Bigr],
\tag{F.2}
$$

<!--block:B0487-->
where $W_i\ge0$ is the (biased) within-chain variance. Since $W_i$ enters only the denominator of $T$ and never the numerator, $T$ is maximised at $W_i\equiv0$ — that is, when every chain is constant. This gives a bound that no data can exceed.

<!--block:B0488-->
Step 2 — the worst spread of chain means. Fix $d=\max_i\lvert\bar{x}_i-\bar{x}\rvert$. Because the deviations $\bar{x}_i-\bar{x}$ sum to zero, minimising $\sum_i(\bar{x}_i-\bar{x})^2$ at fixed $d$ puts one chain at $+d$ and distributes $-d/(M-1)$ over the remaining $M-1$, giving

<!--block:B0489-->
$$
\sum_{i}\bigl(\bar{x}_i-\bar{x}\bigr)^{2}=d^{2}\Bigl(1+\tfrac{1}{M-1}\Bigr)=\frac{M}{M-1}\,d^{2}.
\tag{F.3}
$$

<!--block:B0490-->
Step 3 — the bound. Substituting (F.3) into (F.1) with $W_i\equiv0$ gives $s^{2}=n d^{2}M/\bigl[(M-1)(Mn-1)\bigr]$, hence

<!--block:B0491-->
$$
T\ \le\ R^{*}(M,n)=\sqrt{\frac{(M-1)(Mn-1)}{Mn}}\ ,
\qquad
R^{*}(M,n)\ \xrightarrow[n\to\infty]{}\ \sqrt{M-1}.
\tag{F.4}
$$

<!--block:B0492-->
The bound is **attained**, not merely approached: the configuration of Steps 1–2 is admissible, so $R^{*}(M,n)$ is the maximum of $T$ over all data, not a supremum that data merely approaches. The limiting form $\sqrt{M-1}$, by contrast, is a supremum that no finite $n$ reaches, and $R^{*}(M,n)<\sqrt{M-1}$ strictly for every finite $n$. **The distinction matters at $M=10$**, where the limit equals $3$ exactly while the finite-$n$ value does not.

<!--block:B0493-->
Step 4 — when the criterion can fail. The criterion can fail for some data if and only if $R^{*}(M,n)>k$, i.e.

<!--block:B0494-->
$$
(M-1)(Mn-1)>k^{2}nM .
\tag{F.5}
$$

<!--block:B0495-->
At $k=3$, write (F.5) as $(M-1)(Mn-1)>9nM$. For $M\le10$ the left side is at most $9(Mn-1)=9Mn-9<9Mn$, so (F.5) **fails for every $n\ge1$**. For $M=11$ it reduces to $10(11n-1)>99n$, i.e. $11n>10$, which **holds for every $n\ge1$**. Hence

<!--block:B0496-->
> **at $k=3$ the criterion is capable of failing if and only if $M\ge11$, and the threshold does not depend on the chain length $n$.**

<!--block:B0497-->
Instantiation for this work. The frozen configuration uses $k=3$ and $M=4$ (the coefficient and the chain count are fixed in the implementation of the criterion; see §6.1 for the code reference). Then $R^{*}(4,n)<\sqrt{3}=1.7320508076$ for all $n$, which is $0.5773502692$ of the threshold — a margin of $1.7320508076\times$ that no data can consume. The insensitivity to chain length is worth a number: at $M=4$, going from $n=4000$ to $n=8000$ moves the bound from $1.731997$ to $1.732024$, a change in the fifth decimal place against a threshold of $3$. ⟦F-A1 · 甲类 A-1；判据形态与 `N_CHAINS = 4` 的冻结落点见 §6.1 绑定锚，本附录不复制代码行号（单源）⟧

<!--block:B0498-->
This result has two caveats. First, the derivation assumes the values entering (F.1) are finite; a single non-finite value makes $s$ undefined, every comparison false, and the criterion fail — so *cannot fail* holds on the domain $M\le10$ **together with** finite inputs. Second, (F.4) is a property of this criterion's algebraic form; changing the definition of the pooled standard deviation (its degrees-of-freedom convention, whether it is pooled or per-chain, whether it is taken before or after warmup) requires redoing Steps 1–3.

<!--block:B0499-->
### F.2 An exact decomposition of a difference of absolute errors

<!--block:B0500-->
Referenced from §6.4, Eq. (6.2) and the paragraph following it.

<!--block:B0501-->
Let $b\ne0$ be a signed error and $\delta$ a displacement applied to it. Then

<!--block:B0502-->
$$
\lvert b+\delta\rvert-\lvert b\rvert
=\operatorname{sign}(b)\,\delta
+2\max\bigl(0,\ -\operatorname{sign}(b)\,\delta-\lvert b\rvert\bigr).
\tag{F.6}
$$

<!--block:B0503-->
Proof. Both sides are invariant under $(b,\delta)\mapsto(-b,-\delta)$, so it suffices to take $b>0$, where $\operatorname{sign}(b)=1$ and $\lvert b\rvert=b$. Two cases exhaust the possibilities.

<!--block:B0504-->
*Case 1: $b+\delta\ge0$*, equivalently $\delta\ge-b$. The left side is $(b+\delta)-b=\delta$. On the right, $-\delta-b\le0$, so the $\max$ is $0$ and the right side is $\delta$. The two agree.

<!--block:B0505-->
*Case 2: $b+\delta<0$*, equivalently $\delta<-b$. The left side is $-(b+\delta)-b=-\delta-2b$. On the right, $-\delta-b>0$, so the $\max$ is $-\delta-b$ and the right side is $\delta+2(-\delta-b)=-\delta-2b$. The two agree. $\blacksquare$

<!--block:B0506-->
Because the case split is on the sign of $b$ and on whether $b+\delta$ retains that sign, the four sign combinations of $(b,\ b+\delta)$ are covered by the two cases above and their images under the symmetry.

<!--block:B0507-->
Three consequences.

<!--block:B0508-->
(a) The penalty term is non-negative and vanishes unless the error crosses zero. By construction $2\max(0,\cdot)\ge0$, and it is strictly positive exactly when $-\operatorname{sign}(b)\delta>\lvert b\rvert$, i.e. exactly when $b$ and $b+\delta$ have opposite signs. So the first term of (F.6) is a *pure displacement* term, depending on $\delta$ and on the sign of $b$ but not on its magnitude, while the second depends on $\lvert b\rvert$ and is active only across a sign change.

<!--block:B0509-->
(b) A one-directional containment. Since the penalty is non-negative, $\lvert b+\delta\rvert-\lvert b\rvert\ \ge\ \operatorname{sign}(b)\,\delta$ for all $b\ne0$ and all $\delta$. Consequently a decision rule that thresholds the absolute-error difference is never more permissive than the same rule applied to the signed difference; it can only be equally permissive or stricter. This is a bound relating the two forms; it says nothing about whether the two differ on any particular dataset, and no such comparison is claimed here.

<!--block:B0510-->
(c) The window in which the displacement reduces the absolute error. Writing $\Delta=\lvert b\rvert-\lvert b+\delta\rvert$, we have $\Delta>0$ if and only if $\lvert b+\delta\rvert<\lvert b\rvert$, i.e. $-\lvert b\rvert<b+\delta<\lvert b\rvert$, which for $b<0$ reads $0<\delta<2\lvert b\rvert$ and for $b>0$ reads $-2\lvert b\rvert<\delta<0$. In both cases $\delta$ must lie strictly between $0$ and $-2b$. Two ways of leaving that window follow immediately: if $\lvert b\rvert\le\lvert\delta\rvert/2$ the window is too narrow to contain $\delta$, and it is empty at $b=0$; and if $\lvert\delta\rvert>2\lvert b\rvert$ the displacement overshoots, so that a movement *towards* the true value is scored as an increase in absolute error. Both are statements about the relative size of $b$ and $\delta$, not about the mechanism that produced $\delta$.

<!--block:B0511-->
(d) The degenerate point. At $b=0$ the two forms carry no information and fail in opposite directions: a rule requiring $\overline{\lvert\delta\rvert}\le0$ admits only $\delta\equiv0$, whereas $\operatorname{sign}(0)=0$ turns the signed form into $0\le0$, which admits everything. This is why neither form is a substitute for the other, and why both are reported. ⟦F-A2 · 甲类 A-2/A-3/A-4/A-8；报告形式的冻结落点 = [PREREG] §4 端点(i)（误差族配对差），本附录只给代数⟧

<!--block:B0512-->
### F.3 Exact cancellation of the reference value in a signed difference

<!--block:B0513-->
Referenced from §6.4, the closing sentence of the Eq. (6.2) paragraph.

<!--block:B0514-->
Let $\theta$ be the held-out reference value of a functional and let $\hat{\mu}_{\rm off}$, $\hat{\mu}_{\rm on}$ be the two arms' posterior means of that functional. The signed difference of signed errors is

<!--block:B0515-->
$$
\bigl(\hat{\mu}_{\rm off}-\theta\bigr)-\bigl(\hat{\mu}_{\rm on}-\theta\bigr)
=\hat{\mu}_{\rm off}-\hat{\mu}_{\rm on}.
\tag{F.7}
$$

<!--block:B0516-->
The reference value cancels identically. The quantity is therefore reconstructible from the two posterior means alone and is invariant to the choice of convention by which $\theta$ is defined — a property the absolute-error form does not share, since $\lvert\hat{\mu}-\theta\rvert$ depends on $\theta$ at every point. This is the sense in which disclosing the signed difference alongside the absolute one costs nothing: it requires no additional run and no additional quantity beyond what the two arms already report.

<!--block:B0517-->
Two boundaries. The cancellation is *algebraic*; in floating-point arithmetic the two sides can differ in the last bits when $\lvert\theta\rvert$ is large relative to the difference, so (F.7) should not be used as a bitwise identity test. And the invariance is to the choice of convention for $\theta$ only — it is not a claim that the reference value is unnecessary, since the absolute-error form still requires it. ⟦F-A3 · 甲类 A-5；红线：不得由「真值免疫」推出「带符号式更好」——本节只陈述「并列披露零成本」⟧

<!--block:B0518-->
### F.4 Degenerate constant channels and split-$\widehat{R}$

<!--block:B0519-->
Referenced from §6.1, the constant-channel criterion following Eq. (6.1).

<!--block:B0520-->
Call a channel exactly constant when every post-warmup draw in every chain has the same value. After splitting and rank normalisation, each sub-chain is still constant. Writing $\bar{y}_m$ and $s_m^2$ for the mean and unbiased variance of sub-chain $m$, the standard construction is

<!--block:B0521-->
$$
W=\frac{1}{M'}\sum_{m} s_m^{2},
\qquad
B=n\cdot\operatorname{var}_{\text{unb}}\bigl(\bar{y}_1,\ldots,\bar{y}_{M'}\bigr),
\qquad
\widehat{V}=\frac{n-1}{n}\,W+\frac{B}{n},
\qquad
\widehat{R}=\sqrt{\widehat{V}/W}.
\tag{F.8}
$$

<!--block:B0522-->
For an exactly constant channel, every $s_m^2=0$ and every sub-chain mean is identical, so $W=0$ and $B=0$. The ratio $\widehat{V}/W$ is therefore $0/0$ and $\widehat{R}$ is undefined. The split sub-chain length $n$ does not change this degeneracy.

<!--block:B0531-->
Boundary. Near-unit values observed for nominally frozen channels are implementation-dependent consequences of finite-precision arithmetic or explicit degenerate-channel handling. They do not establish a universal value below one. A zero-variation channel must be reported as undefined or not applicable for $\widehat{R}$ and assessed with a separate movement or variance check.

<!--block:B0532-->
## References

<!--block:B0533-->
> **著录说明**：当前投稿参考文献表含 94 条经核验或校正后保留的条目，并逐条保留 [LIT:n] 映射与质量级。注册搜索基座曾含 111 条候选，但该数字不是最终参考文献表规模；未完成独立核验的中文候选、ghost-reference 候选及其他被撤回条目均未保留。强制校正值与可复现 API 证据见 `source-quality-matrix.md`、`verification-ch0104.md`、`verification-ch0207.md` 和 `phase2-investigation\search-logs\`。卷期页仅采用可验证记录实际返回的字段；arXiv 条目标明预印本版本，作者字段不作推测性补全。

<!--block:B0534-->
Afonso, J. C. (2026). A multiscale MCMC approach to joint geophysical inversion: Tackling dimensionality, solver integration and multiscale data fusion. *Geophysical Journal International, 246*(2). https://doi.org/10.1093/gji/ggag216 `[LIT:18 · B]`（书目 #107；APA 7 单作者条目排在同首作者多作者条目之前，故位于下一条 #36 之前；**页码 Crossref 返回 `null`，从略且不得由记忆补填**；题名冒号后 Crossref 实返为小写 `tackling`，此处按 APA 7 句式大写化为 `Tackling`，下游串比对须先归一化大小写）

<!--block:B0535-->
Afonso, J. C., Fullea, J., Griffin, W. L., Yang, Y., Jones, A. G., & Connolly, J. A. D. (2013). 3-D multiobservable probabilistic inversion for the compositional and thermal structure of the lithosphere and upper mantle. I: A priori petrological information and geophysical observables. *Journal of Geophysical Research: Solid Earth, 118*(5), 2586–2617. https://doi.org/10.1002/jgrb.50124 `[LIT:5 · B]`（书目 #36；作者表按核验记录实载前六位，记录原作 "et al."，完整作者表未逐位著录——见著录说明）

<!--block:B0536-->
Alemie, W., & Sacchi, M. D. (2011). High-resolution three-term AVO inversion by means of a trivariate Cauchy probability distribution. *Geophysics, 76*(3), R43–R55. https://doi.org/10.1190/1.3554627 `[LIT:16 · B · 校]`（书目 #64；DOI 校正值，池内原尾号 …4629）

<!--block:B0537-->
Amaya, M., Meles, G., Marelli, S., & Linde, N. (2024). Multifidelity adaptive sequential Monte Carlo for geophysical inversion. *Geophysical Journal International, 237*(2), 788–804. https://doi.org/10.1093/gji/ggae040 `[LIT:13, 18 · B]`（书目 #108）

<!--block:B0538-->
Andrieu, C., & Thoms, J. (2008). A tutorial on adaptive MCMC. *Statistics and Computing, 18*(4), 343–373. https://doi.org/10.1007/s11222-008-9110-y `[LIT:9 · C]`（书目 #67）

<!--block:B0539-->
Arabpour, A., Hamidzadeh Moghadam, R., & Emami Niri, M. (2025). Geophysical Bayesian inverse problem solving with tuning-free adaptive MCMC sampler. *Earth Science Informatics, 18*(2), Article 186. https://doi.org/10.1007/s12145-024-01599-7 `[LIT:9 · B · 校]`（书目 #68；池内原 DOI 为模板化伪造，经标题检索找回真实记录）

<!--block:B0540-->
Arendt, P. D., Apley, D. W., & Chen, W. (2012). Quantification of model uncertainty: Calibration, model discrepancy, and identifiability. *Journal of Mechanical Design, 134*(10), 100908. https://doi.org/10.1115/1.4007390 `[LIT:8 · B]`（书目 #55）

<!--block:B0541-->
Astic, T., & Oldenburg, D. W. (2019). A framework for petrophysically and geologically guided geophysical inversion using a dynamic Gaussian mixture model prior. *Geophysical Journal International, 219*(3), 1989–2012. https://doi.org/10.1093/gji/ggz389 `[LIT:3 · B · 校]`（书目 #31；题名以 "…model prior" 结尾，声明漏词尾已校正）

<!--block:B0542-->
Backus, G. E., & Gilbert, J. F. (1967). Numerical applications of a formalism for geophysical inverse problems. *Geophysical Journal of the Royal Astronomical Society, 13*(1–3), 247–276. https://doi.org/10.1111/j.1365-246X.1967.tb02159.x `[LIT:1 · A · 校]`（书目 #4；DOI 补登）

<!--block:B0543-->
Berkooz, G., Holmes, P., & Lumley, J. L. (1993). The proper orthogonal decomposition in the analysis of turbulent flows. *Annual Review of Fluid Mechanics, 25*(1), 539–575. https://doi.org/10.1146/annurev.fl.25.010193.002543 `[LIT:13 · C]`（书目 #76）

<!--block:B0544-->
Bissiri, P. G., Holmes, C. C., & Walker, S. G. (2016). A general framework for updating belief distributions. *Journal of the Royal Statistical Society: Series B (Statistical Methodology), 78*(5), 1103–1130. https://doi.org/10.1111/rssb.12158 `[LIT:7 · A]`（书目 #51）

<!--block:B0545-->
Blatter, D., Ray, A., & Key, K. (2021). Two-dimensional Bayesian inversion of magnetotelluric data using trans-dimensional Gaussian processes. *Geophysical Journal International, 226*(1), 548–563. https://doi.org/10.1093/gji/ggab110 `[LIT:4 · B]`（书目 #17）

<!--block:B0546-->
Bodin, T., & Sambridge, M. (2009). Seismic tomography with the reversible jump algorithm. *Geophysical Journal International, 178*(3), 1411–1436. https://doi.org/10.1111/j.1365-246X.2009.04226.x `[LIT:4 · A]`（书目 #14）

<!--block:B0547-->
Bosch, M. (1999). Lithologic tomography: From plural geophysical data to lithology estimation. *Journal of Geophysical Research: Solid Earth, 104*(B1), 749–766. https://doi.org/10.1029/1998JB900014 `[LIT:5 · A]`（书目 #34）

<!--block:B0548-->
Bosch, M., & McGaughey, J. (2001). Joint inversion of gravity and magnetic data under lithologic constraints. *The Leading Edge, 20*(8), 877–881. https://doi.org/10.1190/1.1487299 `[LIT:3, 5 · B]`（书目 #35）

<!--block:B0549-->
Bosch, M., Mukerji, T., & Gonzalez, E. F. (2010). Seismic inversion for reservoir properties combining statistical rock physics and geostatistics: A review. *Geophysics, 75*(5), 75A165–75A176. https://doi.org/10.1190/1.3478209 `[LIT:3 · C · 校]`（书目 #27；DOI 补登）

<!--block:B0550-->
Bratvold, R. B., Bickel, J. E., & Lohne, H. P. (2009). Value of information in the oil and gas industry: Past, present, and future. *SPE Reservoir Evaluation & Engineering, 12*(4), 630–638. https://doi.org/10.2118/110378-PA `[LIT:15 · B]`（书目 #47；替代池内失真条目 [231] 的真实记录）

<!--block:B0551-->
Brooks, S. P., Giudici, P., & Roberts, G. O. (2003). Efficient construction of reversible jump Markov chain Monte Carlo proposal distributions. *Journal of the Royal Statistical Society: Series B (Statistical Methodology), 65*(1), 3–39. https://doi.org/10.1111/1467-9868.03711 `[LIT:11 · A · 校]`（书目 #73；DOI 校正值，声明 …00381 撞车他文）

<!--block:B0552-->
Brossier, R., Operto, S., & Virieux, J. (2010). Which data residual norm for robust elastic frequency-domain full waveform inversion? *Geophysics, 75*(3), R37–R46. https://doi.org/10.1190/1.3379323 `[LIT:16 · B]`（书目 #63）

<!--block:B0553-->
Brynjarsdóttir, J., & O'Hagan, A. (2014). Learning about physical parameters: The importance of model discrepancy. *Inverse Problems, 30*(11), 114007. https://doi.org/10.1088/0266-5611/30/11/114007 `[LIT:8 · B]`（书目 #56）

<!--block:B0554-->
Bunks, C., Saleck, F. M., Zaleski, S., & Chavent, G. (1995). Multiscale seismic waveform inversion. *Geophysics, 60*(5), 1457–1473. https://doi.org/10.1190/1.1443880 `[LIT:18 · A]`（书目 #98）

<!--block:B0555-->
Chaloner, K., & Verdinelli, I. (1995). Bayesian experimental design: A review. *Statistical Science, 10*(3), 273–304. https://doi.org/10.1214/ss/1177009939 `[LIT:6 · C]`（书目 #41）

<!--block:B0556-->
Cockett, R., Kang, S., Heagy, L. J., Pidlisecky, A., & Oldenburg, D. W. (2015). SimPEG: An open source framework for simulation and gradient based parameter estimation in geophysical applications. *Computers & Geosciences, 85*, 142–154. https://doi.org/10.1016/j.cageo.2015.09.015 `[LIT:17, 20 · B · 校]`（书目 #89；DOI 补登）

<!--block:B0557-->
Cook, S. R., Gelman, A., & Rubin, D. B. (2006). Validation of software for Bayesian models using posterior quantiles. *Journal of Computational and Graphical Statistics, 15*(3), 675–692. https://doi.org/10.1198/106186006X136976 `[LIT:12 · A]`（书目 #57）

<!--block:B0558-->
Cui, T., Detommaso, G., & Scheichl, R. (2024). Multilevel dimension-independent likelihood-informed MCMC for large-scale inverse problems. *Inverse Problems, 40*(3), 035005. https://doi.org/10.1088/1361-6420/ad1e2c `[LIT:18 · B]`（书目 #109；**跨通道年份冲突已登记**：Semantic Scholar 记 2019 对 Crossref/OpenAlex 2024，按**可归因异常值、非校正值**处置，**年份取 2024**；**该冲突成因未经核实，不得表述为「预印本年归并」**——形态相似不等于成因已知）

<!--block:B0559-->
Cui, T., Fox, C., & O'Sullivan, M. J. (2011). Bayesian calibration of a large-scale geothermal reservoir model by a new adaptive delayed acceptance Metropolis Hastings algorithm. *Water Resources Research, 47*(10). https://doi.org/10.1029/2010WR010352 `[LIT:18 · B]`（书目 #99；Crossref 与 OpenAlex 均未返回页码字段（AGU 文章号制），按「仅著录 API 实返字段」从略，不得由记忆补填文章号；题名原串 `large‐scale` 用 U+2010，本著录已归一为 ASCII 连字符）

<!--block:B0561-->
Dentith, M., & Mudge, S. T. (2014). *Geophysics for the mineral exploration geoscientist*. Cambridge University Press. https://doi.org/10.1017/CBO9781139024358 `[LIT:14 · C]`（书目 #83；替代池内失真条目 [269][322] 的英文语境锚）

<!--block:B0562-->
Dentith, M., Yuan, H., Johnson, S., Murdie, R., & Piña-Varas, P. (2018). Application of deep-penetrating geophysical methods to mineral exploration: Examples from Western Australia. *Geophysics, 83*(3), WC29–WC41. https://doi.org/10.1190/geo2017-0482.1 `[LIT:14 · B]`（书目 #105；姓名含非 ASCII 字符 `ñ`（Piña-Varas），字符串比对须 UTF-8 逐字，不得替换为 ASCII 近似字符）

<!--block:B0564-->
Dodwell, T. J., Ketelsen, C., Scheichl, R., & Teckentrup, A. L. (2015). A hierarchical multilevel Markov chain Monte Carlo algorithm with applications to uncertainty quantification in subsurface flow. *SIAM/ASA Journal on Uncertainty Quantification, 3*(1), 1075–1108. https://doi.org/10.1137/130915005 `[LIT:18 · A]`（书目 #80）

<!--block:B0565-->
Earl, D. J., & Deem, M. W. (2005). Parallel tempering: Theory, applications, and new perspectives. *Physical Chemistry Chemical Physics, 7*(23), 3910–3916. https://doi.org/10.1039/b509983h `[LIT:10 · C]`（书目 #70）

<!--block:B0566-->
Egbert, G. D., & Booker, J. R. (1986). Robust estimation of geomagnetic transfer functions. *Geophysical Journal of the Royal Astronomical Society, 87*(1), 173–194. https://doi.org/10.1111/j.1365-246X.1986.tb04552.x `[LIT:16 · A]`（书目 #61）

<!--block:B0567-->
Eidsvik, J., Mukerji, T., & Bhattacharjya, D. (2015). *Value of information in the Earth sciences: Integrating spatial modeling and decision analysis*. Cambridge University Press. https://doi.org/10.1017/CBO9781139628785 `[LIT:15 · C · 校]`（书目 #48；DOI 校正值，声称号段 9781316228785 系 9781139628785 之误）

<!--block:B0568-->
Gallardo, L. A., & Meju, M. A. (2003). Characterization of heterogeneous near-surface materials by joint 2D inversion of dc resistivity and seismic data. *Geophysical Research Letters, 30*(13), 1658. https://doi.org/10.1029/2003GL017370 `[LIT:2 · A]`（书目 #21）

<!--block:B0569-->
Gallardo, L. A., & Meju, M. A. (2004). Joint two-dimensional DC resistivity and seismic travel time inversion with cross-gradients constraints. *Journal of Geophysical Research: Solid Earth, 109*(B3). https://doi.org/10.1029/2003JB002716 `[LIT:2 · A · 校]`（书目 #22；池内误著为 Geophysics 69(4) 且 DOI 撞车，真实出处经标题检索校正）

<!--block:B0570-->
Gallardo, L. A., & Meju, M. A. (2007). Joint two-dimensional cross-gradient imaging of magnetotelluric and seismic traveltime data for structural and lithological classification. *Geophysical Journal International, 169*(3), 1261–1272. https://doi.org/10.1111/j.1365-246X.2007.03366.x `[LIT:2 · B]`（书目 #23）

<!--block:B0571-->
Giraud, J., Pakyuz-Charrier, E., Jessell, M., Lindsay, M., Martin, R., & Ogarko, V. (2017). Uncertainty reduction through geologically conditioned petrophysical constraints in joint inversion. *Geophysics, 82*(6), ID19–ID34. https://doi.org/10.1190/geo2016-0615.1 `[LIT:3 · B · 校]`（书目 #30；全题名校正值，声明题名为改写杜撰）

<!--block:B0572-->
Goudie, R. J. B., Presanis, A. M., Lunn, D., De Angelis, D., & Wernisch, L. (2019). Joining and splitting models with Markov melding. *Bayesian Analysis, 14*(1), 81–109. https://doi.org/10.1214/18-BA1104 `[LIT:5 · B · 校]`（书目 #39；出处校正值，声明 JRSS-B 81(2) 与两个候选 DOI 均误）

<!--block:B0573-->
Grana, D., & Della Rossa, E. (2010). Probabilistic petrophysical-properties estimation integrating statistical rock physics with seismic inversion. *Geophysics, 75*(3), O21–O37. https://doi.org/10.1190/1.3386676 `[LIT:3 · B · 校]`（书目 #28；年份校正值 2010，声明 2017 错误；两位作者）

<!--block:B0574-->
Green, P. J. (1995). Reversible jump Markov chain Monte Carlo computation and Bayesian model determination. *Biometrika, 82*(4), 711–732. https://doi.org/10.1093/biomet/82.4.711 `[LIT:4, 11 · A]`（书目 #11）

<!--block:B0576-->
Grünwald, P., & van Ommen, T. (2017). Inconsistency of Bayesian inference for misspecified linear models, and a proposal for repairing it. *Bayesian Analysis, 12*(4). https://doi.org/10.1214/17-BA1085 `[LIT:7 · B]`（书目 #53）

<!--block:B0577-->
Guitton, A., & Symes, W. W. (2003). Robust inversion of seismic data using the Huber norm. *Geophysics, 68*(4), 1310–1319. https://doi.org/10.1190/1.1598124 `[LIT:16 · B]`（书目 #62）

<!--block:B0578-->
Haario, H., Saksman, E., & Tamminen, J. (2001). An adaptive Metropolis algorithm. *Bernoulli, 7*(2), 223–242. https://doi.org/10.2307/3318737 `[LIT:9 · A]`（书目 #65；JSTOR 登记号 DOI，Euclid 版为 10.3150/bj/1080222083）

<!--block:B0579-->
Haber, E., & Oldenburg, D. (1997). Joint inversion: A structural approach. *Inverse Problems, 13*(1), 63–77. https://doi.org/10.1088/0266-5611/13/1/006 `[LIT:2 · A]`（书目 #19）

<!--block:B0581-->
Hastie, D. I., & Green, P. J. (2012). Model choice using reversible jump Markov chain Monte Carlo. *Statistica Neerlandica, 66*(3), 309–338. https://doi.org/10.1111/j.1467-9574.2012.00516.x `[LIT:11 · C]`（书目 #74）

<!--block:B0582-->
Hawkins, R., & Sambridge, M. (2015). Geophysical imaging using trans-dimensional trees. *Geophysical Journal International, 203*(2), 972–1000. https://doi.org/10.1093/gji/ggv326 `[LIT:4 · B]`（书目 #16）

<!--block:B0583-->
Howard, R. A. (1966). Information value theory. *IEEE Transactions on Systems Science and Cybernetics, 2*(1), 22–26. https://doi.org/10.1109/TSSC.1966.300074 `[LIT:15 · A]`（书目 #46）

<!--block:B0585-->
Huan, X., & Marzouk, Y. M. (2013). Simulation-based optimal Bayesian experimental design for nonlinear systems. *Journal of Computational Physics, 232*(1), 288–317. https://doi.org/10.1016/j.jcp.2012.08.013 `[LIT:6 · B]`（书目 #43）

<!--block:B0586-->
Jacob, P. E., Murray, L. M., Holmes, C. C., & Robert, C. P. (2017). Better together? Statistical learning in models made of modules. *arXiv*. https://arxiv.org/abs/1708.08719 (DataCite DOI: 10.48550/arXiv.1708.08719) `[LIT:5 · D · 预印本，引用须标注 arXiv 版本]`（书目 #40）

<!--block:B0587-->
Jiang, W., Duan, J., Doublier, M. P., Clark, A., Schofield, A., Brodie, R. C., & Goodwin, J. (2022). Application of multiscale magnetotelluric data to mineral exploration: An example from the east Tennant region, Northern Australia. *Geophysical Journal International, 229*(3), 1628–1645. https://doi.org/10.1093/gji/ggac029 `[LIT:14 · B]`（书目 #106；`Doublier, M. P.` 依 team lead 裁定 2 统一著录（依核验实返姓名字段））

<!--block:B0588-->
Kaipio, J. P., & Somersalo, E. (2005). *Statistical and computational inverse problems* (Applied Mathematical Sciences). Springer. https://doi.org/10.1007/b138659 `[LIT:1 · C]`（书目 #7）

<!--block:B0589-->
Kennedy, M. C., & O'Hagan, A. (2001). Bayesian calibration of computer models. *Journal of the Royal Statistical Society: Series B (Statistical Methodology), 63*(3), 425–464. https://doi.org/10.1111/1467-9868.00294 `[LIT:8 · A]`（书目 #54）

<!--block:B0590-->
Korsch, R. J., & Doublier, M. P. (2016). Major crustal boundaries of Australia, and their significance in mineral systems targeting. *Ore Geology Reviews, 76*, 211–228. https://doi.org/10.1016/j.oregeorev.2015.05.010 `[LIT:14 · B · 校]`（书目 #103；年份校正值 **2016**（Crossref `published-print`=[[2016,7]]；OpenAlex 记 2015 系在线首发日）；期号 API 未返回，从略；`Doublier, M. P.` 依 team lead 裁定 2）

<!--block:B0591-->
Lelièvre, P. G., Farquharson, C. G., & Hurich, C. A. (2012). Joint inversion of seismic traveltimes and gravity data on unstructured grids with application to mineral exploration. *Geophysics, 77*(1), K1–K15. https://doi.org/10.1190/geo2011-0154.1 `[LIT:18 · B]`（书目 #100；年份按正式卷期 **2012** 著录（Crossref/OpenAlex 一致；s2 记 2010 系与同题 SEG 2010 会议摘要归并，可归因异常值、非校正值）；姓名含非 ASCII 字符 `è`）

<!--block:B0593-->
Lieberman, C., Willcox, K., & Ghattas, O. (2010). Parameter and state model reduction for large-scale statistical inverse problems. *SIAM Journal on Scientific Computing, 32*(5), 2523–2542. https://doi.org/10.1137/090775622 `[LIT:13 · A · 校]`（书目 #77；作者与题名校正值，声明 "Lieu" 错误）

<!--block:B0594-->
Lin, H., Guo, P., Saygin, E., Kennett, B. L. N., Qashqai, M. T., & Xing, L. (2026). Crustal heterogeneity and Moho uplift in the northern Gawler Craton from trans-dimensional Bayesian joint inversion of receiver functions and surface wave dispersion. *Geophysical Journal International, 247*(1). https://doi.org/10.1093/gji/ggag290 `[LIT:4, 14 · B]`（书目 #111；**页码 Crossref 返回空，从略且不得由记忆补填**；Semantic Scholar 题名为标题式大写、Crossref/OpenAlex 为句式大写，**串比对须先归一化大小写**）

<!--block:B0595-->
Lin, W., & Zhdanov, M. S. (2018). Joint multinary inversion of gravity and magnetic data using Gramian constraints. *Geophysical Journal International*. https://doi.org/10.1093/gji/ggy351 `[LIT:2 · B]`（书目 #25；Crossref 未返回卷期页，从略著录）

<!--block:B0596-->
Lines, L. R., Schultz, A. K., & Treitel, S. (1988). Cooperative inversion of geophysical data. *Geophysics, 53*(1), 8–20. https://doi.org/10.1190/1.1442403 `[LIT:2 · A · 校]`（书目 #20；DOI 补登）

<!--block:B0600-->
Lykkegaard, M. B., Dodwell, T. J., Fox, C., Mingas, G., & Scheichl, R. (2023). Multilevel delayed acceptance MCMC. *SIAM/ASA Journal on Uncertainty Quantification, 11*(1), 1–30. https://doi.org/10.1137/22M1476770 `[LIT:18 · B]`（书目 #101；年份按正式卷期 **2023** 著录（Crossref/OpenAlex 一致；s2 记 2022 系 arXiv 预印本年归并，非校正值）；题名 Crossref 作标题式大写，APA 7 已句式大写化）

<!--block:B0601-->
Malehmir, A., Durrheim, R., Bellefleur, G., Urosevic, M., Juhlin, C., White, D. J., Milkereit, B., & Campbell, G. (2012). Seismic methods in mineral exploration and mine planning: A general overview of past and present case histories and a look into the future. *Geophysics, 77*(5), WC173–WC190. https://doi.org/10.1190/geo2012-0028.1 `[LIT:14 · C]`（书目 #102；八位作者全列（参考文献表禁用 et al.）；OpenAlex 作 `Milovan Urošević`，本著录采 Crossref 注册形 `Urosevic, M.`）

<!--block:B0602-->
Malinverno, A. (2002). Parsimonious Bayesian Markov chain Monte Carlo inversion in a nonlinear geophysical problem. *Geophysical Journal International, 151*(3), 675–688. https://doi.org/10.1046/j.1365-246X.2002.01847.x `[LIT:4 · A · 校]`（书目 #12；DOI 校正值，池内原尾号 …01849.x）

<!--block:B0603-->
Manassero, M. C., Özaydın, S., Afonso, J. C., Shea, J. J., Ezad, I. S., Kirkby, A., Thiel, S., Fomin, I., & Czarnota, K. (2024). Lithospheric structure and melting processes in southeast Australia: New constraints from joint probabilistic inversions of 3D magnetotelluric and seismic data. *Journal of Geophysical Research: Solid Earth, 129*(3). https://doi.org/10.1029/2023JB028257 `[LIT:5 · B]`（书目 #110；**页码 Crossref 返回空，从略且不得由记忆补填**；**刊名三通道三型**——Crossref 带冒号 / OpenAlex 无冒号 / Semantic Scholar 用连字符，**以 Crossref 形式为准，串比对须容忍该差异**）

<!--block:B0604-->
Miller, J. W., & Dunson, D. B. (2019). Robust Bayesian inference via coarsening. *Journal of the American Statistical Association, 114*(527), 1113–1125. https://doi.org/10.1080/01621459.2018.1469995 `[LIT:7 · B]`（书目 #52）

<!--block:B0605-->
Minsley, B. J. (2011). A trans-dimensional Bayesian Markov chain Monte Carlo algorithm for model assessment using frequency-domain electromagnetic data. *Geophysical Journal International, 187*(1), 252–272. https://doi.org/10.1111/j.1365-246X.2011.05165.x `[LIT:4 · A · 校]`（书目 #15；DOI 校正值，池内原 DOI 撞车他文）

<!--block:B0606-->
Modrák, M., Moon, A. H., Kim, S., Bürkner, P., Huurre, N., Faltejsková, K., Gelman, A., & Vehtari, A. (2025). Simulation-based calibration checking for Bayesian computation: The choice of test quantities shapes sensitivity. *Bayesian Analysis, 20*(2), 461–488. https://doi.org/10.1214/23-BA1404 `[LIT:12 · B]`（书目 #59；按正式卷期 2025 著录；在线首发 2023，引作 2023 属常见首发年引法，全稿须统一口径）

<!--block:B0607-->
Moorkamp, M., Heincke, B., Jegen, M., Roberts, A. W., & Hobbs, R. W. (2011). A framework for 3-D joint inversion of MT, gravity and seismic refraction data. *Geophysical Journal International, 184*(1), 477–493. https://doi.org/10.1111/j.1365-246X.2010.04856.x `[LIT:2 · B · 校]`（书目 #24；真实题名校正值，声明题含 "receiver function" 系错误）

<!--block:B0608-->
Mosegaard, K., & Tarantola, A. (1995). Monte Carlo sampling of solutions to inverse problems. *Journal of Geophysical Research: Solid Earth, 100*(B7), 12431–12447. https://doi.org/10.1029/94JB03097 `[LIT:1 · A · 校]`（书目 #5；DOI 补登）

<!--block:B0609-->
National Academies of Sciences, Engineering, and Medicine. (2019). *Reproducibility and replicability in science*. National Academies Press. https://doi.org/10.17226/25303 `[LIT:19 · A]`（书目 #94）

<!--block:B0610-->
Nowak, W., de Barros, F. P. J., & Rubin, Y. (2010). Bayesian geostatistical design: Task-driven optimal site investigation when the geostatistical model is uncertain. *Water Resources Research, 46*(3). https://doi.org/10.1029/2009WR008312 `[LIT:6 · B]`（书目 #42）

<!--block:B0611-->
Peherstorfer, B., Willcox, K., & Gunzburger, M. (2018). Survey of multifidelity methods in uncertainty propagation, inference, and optimization. *SIAM Review, 60*(3), 550–591. https://doi.org/10.1137/16M1082469 `[LIT:13, 18 · C · 校]`（书目 #78；DOI 补登）

<!--block:B0613-->
Poole, D., & Raftery, A. E. (2000). Inference for deterministic simulation models: The Bayesian melding approach. *Journal of the American Statistical Association, 95*(452), 1244–1255. https://doi.org/10.1080/01621459.2000.10474324 `[LIT:5 · A · 校]`（书目 #38；DOI 校正值，声明尾号 …571 双源 404）

<!--block:B0614-->
Rainforth, T., Foster, A., Ivanova, D. R., & Bickford Smith, F. (2024). Modern Bayesian experimental design. *Statistical Science, 39*(1), 100–114. https://doi.org/10.1214/23-STS915 `[LIT:6 · C · 校]`（书目 #45；DOI 与页码校正值，声明 STS926 与 100–127 均误）

<!--block:B0615-->
Roberts, G. O., & Rosenthal, J. S. (2007). Coupling and ergodicity of adaptive Markov chain Monte Carlo algorithms. *Journal of Applied Probability, 44*(2), 458–475. https://doi.org/10.1239/jap/1183667414 `[LIT:9 · A]`（书目 #66）

<!--block:B0616-->
Rücker, C., Günther, T., & Wagner, F. M. (2017). pyGIMLi: An open-source library for modelling and inversion in geophysics. *Computers & Geosciences, 109*, 106–123. https://doi.org/10.1016/j.cageo.2017.07.011 `[LIT:17, 20 · B · 校]`（书目 #90；DOI 补登）

<!--block:B0617-->
Ryan, E. G., Drovandi, C. C., McGree, J. M., & Pettitt, A. N. (2016). A review of modern computational algorithms for Bayesian optimal design. *International Statistical Review, 84*(1), 128–154. https://doi.org/10.1111/insr.12107 `[LIT:6 · C]`（书目 #44）

<!--block:B0618-->
Sacchi, M. D., & Ulrych, T. J. (1995). High-resolution velocity gathers and offset space reconstruction. *Geophysics, 60*(4), 1169–1177. https://doi.org/10.1190/1.1443845 `[LIT:16 · B]`（书目 #60）

<!--block:B0620-->
Sambridge, M. (2014). A Parallel Tempering algorithm for probabilistic sampling and multimodal optimization. *Geophysical Journal International, 196*(1), 357–374. https://doi.org/10.1093/gji/ggt342 `[LIT:10 · A]`（书目 #71）

<!--block:B0621-->
Sambridge, M., Gallagher, K., Jackson, A., & Rickwood, P. (2006). Trans-dimensional inverse problems, model comparison and the evidence. *Geophysical Journal International, 167*(2), 528–542. https://doi.org/10.1111/j.1365-246X.2006.03155.x `[LIT:4 · A · 校]`（书目 #13；题名与四人署名校正值，声明误为单人）

<!--block:B0622-->
Sambridge, M., & Mosegaard, K. (2002). Monte Carlo methods in geophysical inverse problems. *Reviews of Geophysics, 40*(3). https://doi.org/10.1029/2000RG000089 `[LIT:1 · C]`（书目 #6）

<!--block:B0623-->
Sirovich, L. (1987). Turbulence and the dynamics of coherent structures. I. Coherent structures. *Quarterly of Applied Mathematics, 45*(3), 561–571. https://doi.org/10.1090/qam/910462 `[LIT:13 · A]`（书目 #75）

<!--block:B0624-->
Stodden, V., McNutt, M., Bailey, D. H., Deelman, E., Gil, Y., Hanson, B., Heroux, M. A., Ioannidis, J. P. A., & Taufer, M. (2016). Enhancing reproducibility for computational methods. *Science, 354*(6317), 1240–1241. https://doi.org/10.1126/science.aah6168 `[LIT:19 · A]`（书目 #93）

<!--block:B0625-->
Stuart, A. M. (2010). Inverse problems: A Bayesian perspective. *Acta Numerica, 19*, 451–559. https://doi.org/10.1017/S0962492910000061 `[LIT:1 · C]`（书目 #8）

<!--block:B0626-->
Sun, J., & Li, Y. (2016). Joint inversion of multiple geophysical data using guided fuzzy c-means clustering. *Geophysics, 81*(3), ID37–ID57. https://doi.org/10.1190/geo2015-0457.1 `[LIT:3 · B · 校]`（书目 #29；年份/题名介词/DOI 三处校正值）

<!--block:B0627-->
Talts, S., Betancourt, M., Simpson, D., Vehtari, A., & Gelman, A. (2018). Validating Bayesian inference algorithms with simulation-based calibration. *arXiv*. https://arxiv.org/abs/1804.06788 (DataCite DOI: 10.48550/arXiv.1804.06788) `[LIT:12 · D · 预印本，引用须标注 arXiv 版本]`（书目 #58；SBC 领域通行惯例）

<!--block:B0628-->
Tarantola, A. (2005). *Inverse problem theory and methods for model parameter estimation*. SIAM. https://doi.org/10.1137/1.9780898717921 `[LIT:1 · A]`（书目 #1）

<!--block:B0629-->
Tarantola, A., & Valette, B. (1982a). Generalized nonlinear inverse problems solved using the least squares criterion. *Reviews of Geophysics, 20*(2), 219–232. https://doi.org/10.1029/RG020i002p00219 `[LIT:1 · A]`（书目 #2）

<!--block:B0630-->
Tarantola, A., & Valette, B. (1982b). Inverse problems = quest for information. *Journal of Geophysics, 50*, 159–170. （无 DOI；OpenAlex: https://openalex.org/W1574224119）`[LIT:1 · A]`（书目 #3；OpenAlex 单源逐字段吻合核验，引用页码按原刊 50, 159–170 并给 OpenAlex 稳定链接）

<!--block:B0631-->
Vehtari, A., Gelman, A., Simpson, D., Carpenter, B., & Bürkner, P.-C. (2021). Rank-normalization, folding, and localization: An improved R-hat for assessing convergence of MCMC. *Bayesian Analysis, 16*(2), 667–718. https://doi.org/10.1214/20-BA1221 `[LIT:9 · B]`（书目 #69；页码经多源确认）

<!--block:B0632-->
Villa, U., Petra, N., & Ghattas, O. (2021). hIPPYlib: An extensible software framework for large-scale inverse problems governed by PDEs; Part I: Deterministic inversion and linearized Bayesian inference. *ACM Transactions on Mathematical Software, 47*(2), 1–34. https://doi.org/10.1145/3428447 `[LIT:20 · B]`（书目 #97）

<!--block:B0633-->
Vousden, W. D., Farr, W. M., & Mandel, I. (2016). Dynamic temperature selection for parallel tempering in Markov chain Monte Carlo simulations. *Monthly Notices of the Royal Astronomical Society, 455*(2), 1919–1937. https://doi.org/10.1093/mnras/stv2422 `[LIT:10 · B]`（书目 #72）

<!--block:B0634-->
Vozoff, K., & Jupp, D. L. B. (1975). Joint inversion of geophysical data. *Geophysical Journal of the Royal Astronomical Society, 42*(3), 977–991. https://doi.org/10.1111/j.1365-246X.1975.tb06462.x `[LIT:2 · A · 校]`（书目 #18；DOI 补登，按原刊年 1975 著录）

<!--block:B0637-->
Wang, X., Zhang, B., Lin, X., Xu, S., Yao, W., & Ye, R. (2016). Geochemical challenges of diverse regolith-covered terrains for mineral exploration in China. *Ore Geology Reviews, 73*, 417–431. https://doi.org/10.1016/j.oregeorev.2015.08.015 `[LIT:14 · C · 校]`（书目 #104；**两项校正值**——(i) 年份 **2016**（Crossref `published-print`=[[2016,3]]；OpenAlex 记 2015 为在线首发日，DOI 后缀内的 `2015` 是 Elsevier 在线首发编号、**非著录年份**）；(ii) Crossref 六位作者 `family`/`given` 全部倒置，已按 ORCID 作者自登记记录与 OpenAlex `raw_author_name` 纠正为 Wang/Zhang/Lin/Xu/Yao/Ye；期号 API 未返回，从略）

<!--block:B0639-->
Wilkinson, M. D., Dumontier, M., & Aalbersberg, I. J. (2016). The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data, 3*, 160018. https://doi.org/10.1038/sdata.2016.18 `[LIT:19 · A]`（书目 #92；作者表按核验记录实载前三位，记录原作 "et al."——大型社区共识署名，完整作者表未逐位著录，见著录说明）

<!--block:B0640-->
Wu, S., Sun, J., & Chen, J. (2025). Variational inference for geophysical Bayesian inverse problems using normalizing flows: An unsupervised approach to electromagnetic data inversion. *Geophysical Journal International, 242*(3). https://doi.org/10.1093/gji/ggaf239 `[LIT:1, 20 · B]`（书目 #10）

<!--block:B0643-->
Zhang, X., & Curtis, A. (2021). Bayesian geophysical inversion using invertible neural networks. *Journal of Geophysical Research: Solid Earth, 126*(7), e2021JB022320. https://doi.org/10.1029/2021JB022320 `[LIT:1 · B · 校]`（书目 #9；DOI 校正值，声明 10.1029/2020JB021806 双源 404；全文仅两位作者）
