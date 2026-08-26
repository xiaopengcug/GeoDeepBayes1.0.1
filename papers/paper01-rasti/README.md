# Paper 01 RASTI release candidate

This directory is the release candidate for:

> *An Auditable Bayesian Fusion Framework for Deep Mineral Exploration Under Cover: Formulation, Component-Level Synthetic Evidence, and a Failed Joint Pilot*

It is prepared for submission to *RAS Techniques and Instruments* (RASTI). The package remains a release candidate until the corresponding author completes the required human verification and explicitly authorizes the formal GitHub tag/release.

## What is included

- `manuscript/manuscript-clean.md` — clean editorial view with author, affiliation, funding, and CRediT statements.
- `manuscript/manuscript-anchored.md` — ARS block-anchored source carrying internal evidence notes.
- `evidence/revision-bundle-r2/` — continuous Stage 2.5 → Stage 4 revision-authority bundle.
- `evidence/verification-final/` — read-only replay summaries for the algorithm component, the 65 historical joint sources, and the 42-row M2 reconstruction-lineage audit.
- `evidence/positive-control/` — deterministic healthy-chain input and expected output for the published joint-diagnostics instrument.
- `figures/` and `supplement/` — all reader-facing figures and the reproducibility/adoption supplement cited by the manuscript.
- `provenance/` — author-facts patch authorization and application records.
- `scripts/replay_release.py` — fail-closed release-tree, provenance, clean-render, and registered-summary verifier; its manifest scope explicitly excludes the self-referential manifest and generated replay result.
- the other files under `scripts/` are historical Stage 4 replay-source snapshots;
  they retain project-relative assumptions for auditability and are not advertised as
  standalone portable entry points.

## Clean-environment replay

From the repository root, using Python 3.11 and uv 0.11.29:

```powershell
uv sync --locked --extra dev
uv run --locked pytest -q
uv run --locked python papers/paper01-rasti/scripts/replay_release.py
```

The expected component-level status is:

- diagnostic and release-replay tests pass;
- the deterministic healthy-chain positive control passes through the published `joint_block.py` instrument;
- 65/65 historical joint-source statuses remain `Failed->Failed`;
- all 65 replay summaries stop fail-closed with `nonfinite_diagnostic`;
- the four registered algorithm thresholds pass;
- M2 reconstruction lineage is 42/42 exact with no unbound run id;
- all 19 paths and SHA-256 values in the self-contained revision bundle resolve;
- the R4 manuscript contract verifies factual repairs plus table, figure, paragraph, and equation order;
- the DO-27 derived attachment remains bound to its frozen Zenodo source record, upstream MIT text, and SHA-256;
- the high-confidence credential scan reports zero findings without printing candidate secrets;
- every intended distributable file outside the two declared exclusions (`release-manifest.json` itself and generated `replay-result.json`), and no unlisted file, matches `release-manifest.json`.

This is an **author-managed clean-environment replay**. It does not claim independent reproduction. The synthetic algorithm asset includes its frozen `raw-chains.npz`; the historical 65-file gravity–magnetic joint-pilot chain arrays are not included. The published 65/65 joint replay is therefore a hash-bound summary of an author-run read-only replay, not a third-party recomputation from those historical arrays.

## Evidence and claim boundaries

- Evidence is component-level and synthetic/open-data-ingestion evidence only.
- The registered gravity–magnetic joint pilot failed its diagnostics gate; the package preserves that failure and does not convert it into a positive endpoint.
- No field validity, discovery rate, resource quantity, production-scale performance, or independent replication is claimed.
- The multi-scale mechanism is specified but was not exercised by a gate-passing assembled endpoint.
- Local absolute paths inside historical provenance records are retained as historical provenance. They are not portable access paths.

## Access and licence

The repository and this package are publicly accessible, but the project licence remains `Proprietary`; public availability does not grant a permissive open-source licence. Zenodo metadata therefore explicitly uses `access_right: open` with `license: other-closed`. No vendor DLL, licence-bound SDK, or original DO-27 archive is included. The included DO-27 `raw-numerics.npz` is a derived numerical attachment and is accompanied by its frozen Zenodo source record, upstream MIT licence text, and a provenance statement that limits the MIT attribution to the upstream material. Other third-party software and public-data records retain their own licences and attribution requirements.

## Release status

Before the formal tag/release, the corresponding author must manually verify at least:

1. author order, spelling, affiliation, corresponding-author email, and ORCID;
2. Funding and CRediT declarations;
3. manuscript title, Abstract, conclusions, and all evidence-boundary language;
4. package member list and SHA-256 manifest;
5. clean-environment replay output;
6. GitHub release title/tag and Zenodo metadata preview.

No DOI is claimed in the release-candidate branch. After explicit human approval, the formal GitHub release will trigger the enabled Zenodo integration; the resulting DOI will be recorded in the final manuscript and provenance package.
