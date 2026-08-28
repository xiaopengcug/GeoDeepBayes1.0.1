# Reproducibility and Adoption Checklist (Stage 4, r1)

This checklist is an implementation-facing supplement. It describes the environment and replay routes used during revision; it is not evidence of field validity, end-to-end fusion performance, production-scale practicality, or cross-platform reproducibility.

## 1. Scope and evidence ceiling

- Supported evidence in this manuscript: per-method component tests, a generic algorithm-correctness study, reduced-order compatibility exercises, open-data ingestion audits, and a failed gravity–magnetic joint pilot.
- The nine operator rows are component-level `Synthetic-run` evidence. They do not compose into a nine-method joint capability.
- The only joint asset exercised gravity and magnetics with a shared geometry nuisance and cross-gradient coupling. All 42 pilot runs failed the registered diagnostics hard gate; the coupling endpoint therefore has no valid evaluation point.
- Other cross-method nuisance and coupling combinations remain specification-only unless a separate evidence asset states otherwise.
- The Field-validated tier is empty. No additional synthetic run promotes an asset into that tier.

## 2. Revision environment baseline

The following baseline was observed on the revision host. It is descriptive, not a benchmark:

| Item | Observed value |
|---|---|
| Operating system | Microsoft Windows 10 Pro, 10.0.19045, 64-bit |
| Processor | Intel Core i7-8850H @ 2.60 GHz, 12 logical processors |
| Installed memory | 31.8 GiB |
| Python | 3.11.9 |
| NumPy | 1.26.4 |
| SciPy | 1.17.1 |
| pytest | 9.0.3 |
| SimPEG | 0.25.2 |

This historical revision-host snapshot differs from the clean release-replay environment locked by `.python-version` and `uv.lock` (Python 3.11.15, NumPy 2.4.6 and pytest 9.1.1). The locked files reproduce the released replay environment; the table records only the host on which revision work was observed. No runtime, memory, speed-up, or scaling number is claimed. A production-scale compute envelope would require a separately registered benchmark asset.

## 3. Repository and release state

- Public remote: `https://github.com/xiaopengcug/GeoDeepBayes1.0.1.git`.
- The paper-specific material is prepared on a curated release-candidate branch. Until a candidate commit passes the machine gate and a separate human verification, no tag, GitHub Release, DOI, or archive identifier is claimed.
- The repository is proprietary. Availability of a public remote does not grant a licence beyond the terms present in that repository.
- Vendor DLLs and licence-bound SDKs are not distributed. Optional adapters remain user-installed and user-licensed.
- The synthetic algorithm `raw-chains.npz` is distributed. The 65 historical gravity–magnetic joint-pilot chain arrays are not distributed, so their read-only replay remains an author-run hash-bound summary rather than an independent recomputation.
- The DO-27 derived `raw-numerics.npz` is distributed with its frozen Zenodo source record, upstream MIT text, and provenance boundary. The original DO-27 archive is not distributed.

## 4. Minimum component contract

An adopter must record, at minimum:

1. component and evidence identifier;
2. code revision or content hash;
3. input paths, byte sizes, hashes, provenance, and redistribution terms;
4. model parameter names, physical units, support, and transforms;
5. observation type, units, receiver/source geometry, and noise assumptions;
6. random seed or deterministic construction identifier;
7. diagnostic-contract hash and every threshold source;
8. output paths, hashes, evidence tier, verdict, and structured failure reason.

The conservative method schema is:

| Method | Verified component output | Model parameter/support | Evidence boundary |
|---|---|---|---|
| Gravity | gravity anomaly, mGal | cell density contrast, g cm^-3; 3-D volume | component synthetic only |
| Magnetic | total-field anomaly, nT | scalar susceptibility, SI; 3-D volume | component synthetic only |
| DC | voltage, V | cell log-conductivity, S m^-1; 3-D volume | component synthetic only |
| TDIP | secondary voltage, V | cell chargeability; 3-D volume | component synthetic only |
| SIP/FDIP | complex voltage, V | Cole–Cole parameters; 1-D or 2-D/2.5-D variant | component synthetic only |
| TEM | vertical dB/dt, T s^-1 | layered log-conductivity, S m^-1 | verified 1-D layered path only; 3-D is not verified |
| MT/AMT | impedance, V A^-1; 3-D tipper dimensionless | layered or cell log-conductivity, S m^-1 | component synthetic only |
| CSAMT | Ex, V m^-1; Hy, A m^-1 | cell log-conductivity, S m^-1; finite grounded line | component synthetic only |
| WFEM | Ex/Ey, V m^-1 | cell log-conductivity, S m^-1; grounded wire | component synthetic only; apparent resistivity requires an explicit geometric-factor definition |

Petrophysical coupling priors remain at the `Hypothesis` tier. Shared nuisance terms that have not been exercised in a named asset remain `unknown` rather than inferred from the formulation.

## 5. Clean-environment replay route

From the repository root, using Python 3.11 and the uv version locked by `pyproject.toml`:

```powershell
uv sync --locked --extra dev
uv run --locked pytest -q
uv run --locked python papers/paper01-rasti/scripts/replay_release.py
```

The release verifier independently checks the candidate release-tree member set and hashes, with `release-manifest.json` itself and generated `replay-result.json` declared as the only self/runtime exclusions. It also checks the clean-manuscript render, revision-bundle links, Zenodo licence fields, DO-27 source/attribution binding, and the registered summaries below. Its expected evidence results are:

- curated release test suite: `57 passed`;
- historical diagnostic replay: 65 source chain files preserved; transition count `Failed -> Failed = 65`; all 65 now carry the explicit `nonfinite_diagnostic` reason;
- degenerate-channel counts across those replayed files: 57 files with one, 3 with two, and 5 with six degenerate channels;
- post-hoc M2 reconstruction lineage: 42/42 ledger rows exactly reconstructed from hashed per-run metrics, while remaining explicitly distinct from runtime-generated batch evidence.

The positive control also exercises the published `joint_block.py` diagnostic instrument on deterministic healthy chains and must pass. These checks constitute an author-managed clean-environment replay. They are not an independent-team reproduction, and the 65 historical statuses are not recomputed from raw chain arrays in the release package.

## 6. Failure handling and escalation

- Non-finite input, non-finite derived diagnostics, and finite degenerate channels fail closed with a structured reason.
- A failed diagnostic gate quarantines endpoint interpretation; it cannot be used as evidence for or against coupling behaviour.
- Missing units, provenance, licence terms, hashes, or threshold sources stop evidence admission.
- A discrepancy between runtime and reconstructed batch artefacts is escalated to the method lead and data steward, and requires an independent validation record before reuse.
- Field transfer additionally requires geology, survey, petrophysics, and data-governance entry evidence under `EVD-FIELD-001`.

## 7. Reproducibility status

An independent-team clean-environment replay has not been completed. Before submission, the exact manuscript, code, evidence manifests, scripts, licences, and expected statuses must be bound to a manually verified immutable public revision and archive identifier. Until that occurs, the candidate branch is an inspection route only, not a citation-grade reproduction package for this manuscript.
