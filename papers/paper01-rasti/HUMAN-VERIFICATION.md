# Formal-release human verification gate

Status: **PENDING — formal tag/release and Zenodo DOI are blocked**

This checklist implements the corresponding author's requirement that the release candidate receive human verification before formal publication.

## A. Identity and declarations

- [ ] Author order is exactly: Li Xiao Peng; Hu Xue Ping; Dong Jian; Chen Lei; Ma Li Xin.
- [ ] All five authors are affiliated with Shandong Provincial Geological Survey Institute.
- [ ] Corresponding author is Li Xiao Peng and the displayed email is correct.
- [ ] Li Xiao Peng's ORCID is `0009-0002-1814-9447`; no ORCID is attributed to another author.
- [ ] Funding states that no specific grant was received.
- [ ] CRediT roles match the author-approved allocation.

## B. Scientific and integrity boundary

- [ ] The title, Abstract, Results, Discussion, Conclusions, and Declarations consistently describe a formulation/protocol with component-level evidence.
- [ ] The gravity–magnetic joint pilot remains reported as diagnostics-gate `Failed` with no valid coupling endpoint.
- [ ] No passage claims field validation, discovery performance, resource quantities, production-scale readiness, or independent reproduction.
- [ ] The multi-scale mechanism remains described as specified but not exercised by a gate-passing assembled endpoint.
- [ ] The §2.2 discovery inventory and Table A.1 retain `unknown` for unreviewed full-text element cells; no withdrawn novelty score reappears.
- [ ] Alemie & Sacchi (2011) is described as a trivariate Cauchy prior, and the 42-run design is explicitly decomposed as 30 λ-grid, 2 adaptive-Metropolis, and 10 weighted runs.
- [ ] Main-text Tables 1–5a, Figures 1–5, P1–P6, and Eqs. (6.1)–(6.2) appear in order; every figure opens and matches its caption.

## C. Package and replay

- [ ] `release-manifest.json` contains only intended distributable files and every SHA-256 verifies.
- [ ] The clean manuscript contains no `<!--block:...-->` markers or `⟦...⟧` ARS notes.
- [ ] The anchored manuscript and provenance files are clearly separated from the clean editorial view.
- [ ] The clean-environment commands in `README.md` pass on the candidate commit.
- [ ] The published healthy-chain positive control passes through `src/geodeepbayes/benchmarks/joint_block.py`.
- [ ] The DO-27 derived attachment hash, frozen Zenodo source record, MIT text, and provenance boundary all verify.
- [ ] The replay is described as author-managed and does not claim independent reproduction.
- [ ] The revision bundle verifies all 19 internal path/hash links, and no redundant outer bundle copy remains.
- [ ] The high-confidence credential scan reports zero findings; no access token or private key is present in the candidate tree.
- [ ] Inclusion of the synthetic algorithm `raw-chains.npz` and DO-27 derived `raw-numerics.npz`, and exclusion of the 65 historical joint-pilot chain arrays, vendor SDKs/DLLs, and original DO-27 archive are acceptable and accurately disclosed.

## D. GitHub and Zenodo preview

- [ ] Proposed tag: `paper01-rasti-v1.0.0`.
- [ ] GitHub release title and notes accurately state the failed joint pilot and evidence ceiling.
- [ ] `CITATION.cff` creator names, order, affiliation, and ORCID are correct.
- [ ] `.zenodo.json` title, creator order, affiliation, keywords, explicit `access_right: open`, `license: other-closed`, and non-independent-reproduction boundary are correct.
- [ ] The repository remains enabled in the author's Zenodo GitHub integration.

## Author release decision

After completing the checklist, the corresponding author should provide an explicit statement that identifies the candidate commit SHA and authorizes:

1. creation and push of tag `paper01-rasti-v1.0.0`;
2. creation of the GitHub release;
3. Zenodo ingestion through the enabled GitHub integration.

Until that statement is received, the candidate branch may be pushed for inspection, but no formal tag/release/DOI will be created.
