# Freshness reconfiguration types

This repository is the executable and proof supplement for *Observation-Sensitive Freshness Types for Finite Stream Reconfiguration*. It checks a finite integer-time calculus for bounded geodistributed stream fragments. The repository is self-contained, uses only the Python standard library for scientific execution, and does not depend on the paper directory.

The implementation has three deliberately separate roles. The **producer** closes input difference zones, infers exact fixed-graph rows, constructs observation-sensitive refinement certificates, and residualizes valid non-quiescent prefixes. The **replay kernels** independently validate static and adaptive certificates; they do not import the inference algorithms or the exhaustive interpreter. The **finite oracles** enumerate every bounded integer input and edge-delay assignment selected by a campaign. Agreement among those roles is finite implementation evidence, not a proof assistant derivation of the general theorems.

## Scope

The calculus has immutable source generations, bounded integer difference zones, finite eager acyclic graphs, copy/pair/barrier nodes, separate data and gating dependencies, and independent bounded nonnegative edge delays. Output freshness is the emission time minus the oldest contributing source birth. The adaptive checker handles one zone on each side and controllers that observe readiness/event/receipt time but not source births. Runtime residualization assumes a valid logical prefix with exact event and receipt observations.

The repository does **not** model a physical migration protocol, clock synchronization, unbounded queues or faults, mutable actors, recursive sessions, deployment throughput, or real network latency. The proof document is handwritten mathematics. Enumeration counts measure bounded model coverage only.

## Requirements

- Python 3.11 or later.
- A POSIX platform for `run_bounded.py` resource limits and CPU affinity. The core checker and tests themselves use portable standard-library Python.
- No network access, solver, package installation, GPU, or external service.

## Complete reproduction

From the extracted repository root:

```sh
python reproduce.py --out reproduced
```

The command runs 43 unit tests and four deterministic campaigns through `run_bounded.py`, then compares every regenerated scientific JSON/JSONL value with `results/`. Only the environment-dependent `measurements` fields inside campaign summaries are ignored. The final report is `reproduced/reproduction.json`; success means `"status": "pass"`.

To regenerate the LaTeX data consumed by the manuscript:

```sh
python make_paper_data.py
```

This writes `paper-data/validation-macros.tex` and `paper-data/validation-table.tex` from the shipped summaries.

## Checker examples

Infer and replay an admitted fixed graph:

```sh
python -m ftypes.cli check inputs/static/worked-safe.json \
  --certificate reproduced-safe.certificate.json
python -m ftypes.cli replay inputs/static/worked-safe.json \
  --certificate certificates/static/worked-safe.certificate.json
python -m ftypes.cli oracle inputs/static/worked-safe.json
```

A stale policy is an expected semantic rejection and therefore exits with status 1:

```sh
python -m ftypes.cli check inputs/static/worked-stale.json
```

Infer an accepted opaque-payload refinement:

```sh
python -m ftypes.cli refine \
  inputs/adaptive/opaque-accepted.json \
  inputs/adaptive/opaque-accepted.json \
  --certificate reproduced-refinement.certificate.json
```

Replay the supplied support and row-cover rejection certificates. These are expected to return status 1 after successfully validating a rejecting certificate:

```sh
python -m ftypes.cli refine-replay \
  inputs/adaptive/support-left.json \
  inputs/adaptive/support-right.json \
  --certificate certificates/adaptive/support-rejection.certificate.json

python -m ftypes.cli refine-replay \
  inputs/adaptive/row-left-g1-00.json \
  inputs/adaptive/row-right-g1-08.json \
  --certificate certificates/adaptive/row-rejection.certificate.json
```

## Campaigns and shipped evidence

| Campaign | Deterministic selection | Exhaustive work | Result |
|---|---|---|---|
| `ftypes.experiments` | 8 interface families × 8 graph shapes × 2 delay widths | 128 cases; 41,748 schedules; 384 threshold decisions | 0 mismatches |
| `ftypes.adaptive_experiments` | 3 payload groups × all 16-by-16 ordered pairs | 768 comparisons; 2,674 conditional cells | 319 accepted, 449 rejected, 0 mismatches |
| `ftypes.residual_experiments` | 4 small interfaces × 8 graph shapes | 9,308 prefix visits; 1,225 distinct prefixes; 9,308 residual schedules | 0 mismatches |
| `ftypes.validation` | 12 named controls plus all 81 bounded 2-by-2 profile matrices | 324 attaining-cell witnesses | 0 failures/mismatches |

Raw case specifications, certificates, oracles, prefixes, witnesses, and summaries are in `results/`. `results/resource-use.json` records the bounded scientific subprocesses. The measured five-command clean campaign used one worker per command, 5.039 cumulative CPU seconds, 5.173 cumulative wall seconds, and 118,648 KiB maximum resident set size. Runtime measurements are descriptive of this execution environment, not performance claims.

## Repository map

- `ftypes/terms.py` — free payload algebra and lineage.
- `ftypes/dbm.py` — exact integer difference-bound closure, paths, potentials, and bounded enumeration.
- `ftypes/model.py` — strict JSON model validation.
- `ftypes/semantics.py` — exhaustive reference interpreter.
- `ftypes/static.py`, `ftypes/kernel.py` — fixed-graph inference and independent replay.
- `ftypes/adaptive.py`, `ftypes/adaptive_kernel.py` — single-zone row-cover decisions, separators, and independent replay.
- `ftypes/residual.py` — observation validation and exact cut residualization.
- `ftypes/*_experiments.py`, `ftypes/validation.py` — frozen deterministic campaigns and negative controls.
- `tests/` — 43 unit and mutation tests.
- `proofs/theory.md` — complete handwritten theorem arguments and boundaries.
- `claim_evidence_ledger.csv` — claim-to-proof/check/result mapping.
- `external_resources.csv`, `literature.csv` — provenance and literature calibration records.
- `inputs/`, `certificates/` — worked admitted and rejected examples.
- `results/` — complete selected raw results and resource records.

## Result interpretation

A successful command proves that the shipped program accepted its input under the implemented semantics. An oracle match shows equality on the enumerated bounded domain. Certificate replay detects the tested mutations and checks explicit paths, potentials, rows, terms, and obligations. None of those facts alone proves Python correctness, publication novelty, or correctness of an unmodeled distributed installer. The general semantic claims rely on `proofs/theory.md`; the paper states each model assumption and limitation.

## Artificial-intelligence use

A generative AI system was used substantively in research design, mathematical proof development, implementation, deterministic case construction, validation, analysis, literature synthesis, and manuscript drafting. The named human authors remain responsible for checking every claim and satisfying any venue authorship and disclosure policy before external use. This repository is an internal research artifact and does not represent an external submission.

## License

The repository code and original documentation are released under the license in `LICENSE`. Bibliographic records and publisher templates retain their own terms and are not relicensed by this file.
