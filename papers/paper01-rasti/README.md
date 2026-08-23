# Paper 01 RASTI release candidate

This directory is the release candidate for:

> *An Auditable Bayesian Fusion Framework for Deep Mineral Exploration Under Cover: Formulation, Component-Level Synthetic Evidence, and a Failed Joint Pilot*

It is prepared for submission to *RAS Techniques and Instruments* (RASTI). The package remains a release candidate until the corresponding author completes the required human verification and explicitly authorizes the formal GitHub tag/release.

## What is included

- `manuscript/manuscript-clean.md` — clean editorial view with author, affiliation, funding, and CRediT statements.
- `manuscript/manuscript-anchored.md` — ARS block-anchored source carrying internal evidence notes.
- `evidence/revision-bundle-r2/` — continuous Stage 2.5 → Stage 4 revision-authority bundle.
- `evidence/verification-final/` — read-only replay summaries for the algorithm component, the 65 historical joint sources, and the 42-row M2 reconstruction-lineage audit.
- `provenance/` — author-facts patch authorization and application records.
- `scripts/replay_release.py` — fail-closed release-manifest and registered-summary verifier.
- the other files under `scripts/` are historical Stage 4 replay-source snapshots;
  they retain project-relative assumptions for auditability and are not advertised as
  standalone portable entry points.

## Clean-environment replay

From the repository root, using Python 3.11 and uv 0.11.29:

```powershell
uv sync --frozen --extra dev
uv run --frozen pytest tests/diagnostics/test_diagnostics.py tests/paper01/test_release_replay.py -q
uv run --frozen python papers/paper01-rasti/scripts/replay_release.py
```

The expected component-level status is:

- diagnostic and release-replay tests pass;
- 65/65 historical joint-source statuses remain `Failed->Failed`;
- all 65 replay summaries stop fail-closed with `nonfinite_diagnostic`;
- the four registered algorithm thresholds pass;
- M2 reconstruction lineage is 42/42 exact with no unbound run id;
- every `release-manifest.json` member matches its SHA-256.

This is an **author-managed clean-environment replay**. It does not claim independent reproduction. The raw historical chain arrays are not included in this GitHub package; the published joint replay is therefore a hash-bound summary of an author-run read-only replay, not a recomputation from those raw arrays by a third party.

## Evidence and claim boundaries

- Evidence is component-level and synthetic/open-data-ingestion evidence only.
- The registered gravity–magnetic joint pilot failed its diagnostics gate; the package preserves that failure and does not convert it into a positive endpoint.
- No field validity, discovery rate, resource quantity, production-scale performance, or independent replication is claimed.
- The multi-scale mechanism is specified but was not exercised by a gate-passing assembled endpoint.
- Local absolute paths inside historical provenance records are retained as historical provenance. They are not portable access paths.

## Access and licence

The repository and this package are publicly accessible, but the project licence remains `Proprietary`; public availability does not grant a permissive open-source licence. No vendor DLL, licence-bound SDK, or raw DO27 input is included here. Third-party software and public-data records retain their own licences and attribution requirements.

## Release status

Before the formal tag/release, the corresponding author must manually verify at least:

1. author order, spelling, affiliation, corresponding-author email, and ORCID;
2. Funding and CRediT declarations;
3. manuscript title, Abstract, conclusions, and all evidence-boundary language;
4. package member list and SHA-256 manifest;
5. clean-environment replay output;
6. GitHub release title/tag and Zenodo metadata preview.

No DOI is claimed in the release-candidate branch. After explicit human approval, the formal GitHub release will trigger the enabled Zenodo integration; the resulting DOI will be recorded in the final manuscript and provenance package.
