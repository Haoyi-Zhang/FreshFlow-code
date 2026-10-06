# Freshness reconfiguration types

This repository is the executable and proof supplement for *Observation-Sensitive Freshness Types for Finite Stream Reconfiguration*. It checks a finite integer-time calculus for bounded geodistributed stream fragments. The repository is self-contained, uses only the Python standard library for scientific execution, and does not depend on the paper directory.

The implementation has three deliberately separate roles. The **producer** closes input difference zones, infers exact fixed-graph rows, constructs observation-sensitive refinement certificates, and residualizes valid non-quiescent prefixes. The **replay kernels** independently validate static and adaptive certificates; they do not import the inference algorithms or the exhaustive interpreter. The **finite oracles** enumerate every bounded integer input and edge-delay assignment selected by a campaign. Agreement among those roles is finite implementation evidence, not a proof assistant derivation of the general theorems.

## Scope

The calculus has immutable source generations, bounded integer difference zones, finite eager acyclic graphs, copy/pair/barrier nodes, separate data and gating dependencies, and independent bounded nonnegative edge delays. Readiness is constrained to be nonnegative at model ingestion, while births may be negative. Output freshness is the emission time minus the oldest contributing source birth. A policy may be empty; pending nonoutput work is still executed. The adaptive checker handles one zone on each side and controllers that observe readiness/event/receipt time but not source births. Runtime residualization assumes a valid logical birth-blind, age-erased prefix: exact event/receipt times and the determined past output key/term/time, NOT past output ages. Future ages are retained exactly.

The repository does **not** model a physical migration protocol, clock synchronization, unbounded queues or faults, mutable actors, recursive sessions, deployment throughput, or real network latency. The proof document is handwritten mathematics. Enumeration counts measure bounded model coverage only.

## Requirements

- Python 3.11 or later.
- On POSIX, `run_bounded.py` applies the available CPU-affinity/resource limits. On Windows it enforces only a 45-second wall timeout and records unavailable CPU/memory limits as null. This is not equivalent resource isolation.
- No network access, solver, package installation, GPU, or external service.

## Complete reproduction

From the extracted repository root:

```sh
python reproduce.py --out reproduced
```

The command runs 73 unit-test methods (with additional mutation and identifier subcases) and four deterministic campaigns through `run_bounded.py`, then compares every regenerated scientific JSON/JSONL value with `results/`. Only the environment-dependent `measurements` fields inside campaign summaries are ignored. The report is `reproduced/reproduction.json`; success means `"status": "pass"`. Use a fresh output directory; an existing directory is never deleted automatically. The shipped resource records belong to the prior 66-method run; they are not timings of the expanded suite.

A current Ubuntu 24.04/Python 3.12.14 execution passes all 73 methods and all four campaigns. The 14 scientific files (4,415 JSONL records) match the retained values, and both generated manuscript tables match bytewise. Current measurements and the actual test footer are in `results/measurements/current-linux/`; they do not replace the historical resource files. Each command is bounded to one core, 3 GiB address space, 40 CPU seconds and 45 wall seconds.

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
| `ftypes.experiments` | Original 128 singleton two-port/one-output cases plus four explicit supplements | 132 cases; 42,104 schedules; 402 actual changed-policy queries with another 127,848 interpreter assignments | 0 mismatches |
| `ftypes.adaptive_experiments` | 3 payload groups × all 16-by-16 ordered pairs | 768 comparisons; 4,440 common-support conditional cells; 449 executed separators with 4,959 full right-valuation branch checks | 319 accepted, 449 rejected, 0 mismatches |
| `ftypes.residual_experiments` | Original 32 small singleton cases plus the four supplements; every cut through the last event inclusive | 15,370 prefix visits; 2,672 distinct prefixes; 15,370 residual schedules | 0 mismatches |
| `ftypes.validation` | 12 named controls plus all 81 bounded 2-by-2 profile matrices | 324 attaining-cell witnesses | 0 failures/mismatches |

The four supplements explicitly cover an opaque pair with unit gate, a future unrelated birth giving a negative cross cell, nested pairing with three keys, and a completed output with pending nonoutput work. They are not additional Cartesian dimensions. Of 2,672 cut prefixes, 1,363 have no remaining outputs and 11 of those retain pending original work. Completely terminal cuts have the singleton empty future set.

The original static base is 8 interfaces × 8 shapes × widths 0/1. Interface indices are 0 independent, 1 birth-near, 2 p-before-q, 3 q-before-p, 4 cross-a-q, 5 cross-b-p, 6 the union of p-ready-zero and q-ready-high zones, and 7 locked readiness with near births. All base ports are singleton sources and all base cases have one output. The cut base uses indices 0–3, the same eight shapes and width 1, with smaller bounds. The eight actual shapes are direct copy; gated copy; pair; barrier-gated copy; serial copies with a q gate; parallel copies feeding a pair; barrier-gated pair; and a q copy gated by p followed by a copy. Width 0 fixes every base delay to zero; width 1 gives every base edge interval [0,1].

Raw case specifications, certificates, oracles, prefixes, witnesses, and summaries are in `results/`. Static `thresholds.jsonl` retains each actually modified input, inferred/replayed certificate, independent verdict and complete stale execution when rejected. The adaptive raw oracle groups full birth/readiness valuations from original bounds/constraints and never calls DBM closure or producer envelope helpers. For each separator it directly executes all right valuations. `results/resource-use.json` records current subprocess outcomes and available measurements; the Windows run does not claim the old POSIX CPU/memory guarantees.

## Repository map

- `ftypes/terms.py` — free payload algebra and lineage.
- `ftypes/dbm.py` — exact integer difference-bound closure, paths, potentials, and bounded enumeration.
- `ftypes/model.py` — strict JSON model validation.
- `ftypes/semantics.py` — exhaustive reference interpreter.
- `ftypes/static.py`, `ftypes/kernel.py` — fixed-graph inference and independent replay.
- `ftypes/adaptive.py`, `ftypes/adaptive_kernel.py` — single-zone row-cover decisions, separators, and independent replay.
- `ftypes/adaptive_oracle.py` — tiny raw-bound full-valuation reference and actual separator branch interpreter.
- `ftypes/residual.py` — observation validation and exact cut residualization.
- `ftypes/*_experiments.py`, `ftypes/validation.py` — frozen deterministic campaigns and negative controls.
- `tests/` — 73 unit-test methods and their named mutation/identifier subcases.
- `proofs/theory.md` — complete handwritten theorem arguments and boundaries.
- `claim_evidence_ledger.csv` — claim-to-proof/check/result mapping.
- `external_resources.csv`, `literature.csv` — provenance and literature calibration records.
- `inputs/`, `certificates/` — worked admitted and rejected examples.
- `results/` — complete selected raw results and resource records.

## Result interpretation

A successful command proves that the shipped program accepted its input under the implemented semantics. An oracle match shows equality on the enumerated bounded domain. Certificate replay detects the tested mutations and checks explicit paths, potentials, rows, terms, and obligations. None of those facts alone proves Python correctness, publication novelty, or correctness of an unmodeled distributed installer. The general semantic claims rely on `proofs/theory.md`; the paper states each model assumption and limitation.

## License

The repository code and original documentation are released under the license in `LICENSE`. Bibliographic records and publisher templates retain their own terms and are not relicensed by this file.

## Certificate and implementation details

Clock identifiers are `b_<source>`, `r_<port>`, and `zero`; terms are strings `unit`, `src(a)`, or `pair(...,...)`. Static replay uses the input node-list order and has no separate topological-order or selected-predecessor field. The schema identifiers remain unchanged. Rejection separators now require a complete feasible attaining `left_valuation`, the emitted whole `payload_term`, `emission_time`, and `special_reachable_right`; older incomplete rejecting certificates do not replay. `branch_observable=true` refers to the readiness-only predicate even when it is unreachable on the right.

Static certificates validate feasible closure potentials and tight paths, profiles, rows, terms and output comparisons; they do not contain negative cycles, a separate lineage record, or a full stale execution. The parsed input supplies the checked node-list topological order. Concrete rejected-threshold execution witnesses are separate campaign records in `results/static/thresholds.jsonl`. Residual `Zone.with_constraints` uses closure-based infeasibility detection and discards diagnosed empty members without exporting a negative-cycle witness. Z1's mathematical negative-cycle existence result is retained, but no cycle serialization or replay is claimed for the implementation.

The baseline is `1 + max D_(b_s,r_q)` over all timing ports q and sources s of the chosen payload. Its exactness follows by exchanging finite maxima of `T(r)+K(p,r)`; certificate generation performs no readiness enumeration. Replay binds all separator fields and proves safety for both ordinary and special right branches, separately from raw exhaustive execution.

Actual parser caps are 128 origins/ports/zones/nodes/outputs per list, 128 clocks, 4096 zone edges including bounds, 128-bit magnitude zone constants and delay endpoints, and term-string length 100,000/depth 128. Closure replay checks 256-bit magnitude distance cells; other derived integers, deadlines, epochs and JSON byte counts have no global magnitude/byte cap. Inferred expanded term size is an explicit cost, not a separately enforced cap. The semantic enumeration ceiling is 2,000,000 assignments; the adaptive raw Cartesian ceiling is 100,000. None is a scalability claim.

The full matrix certificate uses explicit paths and potentials for every clock, not only births. Floyd--Warshall costs cubic arithmetic work with up to quartic path-index copying in the current list representation. Replay kernels operate on parsed cases without calling closure; the shared input parser itself closes zones, so this separation is not a closure-free command-line pipeline. Adaptive replay requires a data-bearing port and validates any feasible same-payload cover, not only the producer's first cover. Prefix conditioning uses the same closure implementation; no independent cut-certificate replay or serialized negative-cycle evidence is supplied. The cut implementation is checked by exhaustive future-set comparison. Buffered receipts become availability zero; they preserve a strictly positive pending maximum, not the original arrival multiset.

Source identifiers in terms follow the model's letter-first, alphanumeric/hyphen convention, including Unicode letters. Constructor words are recognized by syntactic position rather than as identifier prefixes. Enumeration volume checks use exact integer interval widths before constructing a Cartesian product; a permitted wide interval is a resource refusal, not a host-sized range-length exception.

The prepared `.github/workflows/scientific-checks.yml` runs from this flat artifact root on Ubuntu 24.04, on pushes to `main`, pull requests, or manual dispatch. It gates source integrity, full finite reproduction, and generated paper-data equality, with a 300-second whole-run wall bound, CPU/address-space limits, and raw-output upload even after failure. Preparing this workflow and executing local checks do not establish a successful GitHub run.
