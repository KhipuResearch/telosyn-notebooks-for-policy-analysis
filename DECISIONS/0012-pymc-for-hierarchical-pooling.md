<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0012 — `pymc` for hierarchical pooling, in its own optional extra

- **Status:** Accepted
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-10-30
- **Amends:** ADR 0009 section 3.6 (dependency policy)

## 1. Context

Card Q03 partially pools 133 Virginia county poverty estimates with a hierarchical model and shows the pooled and the unpooled estimates side by side.
The package has no sampler. ADR 0009 section 3.6 reserved `pymc` for this card and required, for any package added for one notebook: an optional
extra, never core; a lower bound; a cost and benefit paragraph; and an import that the declared-imports test can see. The owner released the card on
2026-10-30 within these limits: its own extra, an ADR, CI time measured before and after with a total increase of at most 5 minutes, library tests that
do not require the package, seeded runs, R-hat and effective sample size printed, and a stop on an R-hat above 1.01.

## 2. Decision

Add `pymc>=6.3.2; python_version >= '3.12'` as **its own optional extra**, `pymc`, in `pyproject.toml`. It is not in the runtime dependencies, in
`notebooks`, in `methods` or in `test`. Only the Q03 notebook imports it, and it takes its diagnostics from `pymc.stats`, which re-exports ArviZ's, so
the notebook imports no other sampler package. The functions the notebook needs that are not the sampler, the standard error of an ACS proportion, the
moment estimator and an **exact grid-integrated posterior** for the same model, are in `krl_tutorials_data.methods.pooling`; that module imports only
numpy and scipy, and its known-answer tests (`tests/test_methods_pooling.py`) run without `pymc`. A test (`tests/test_pymc_extra.py`) fails if `pymc`
is imported by the package or by a library test, or is declared anywhere but its own extra. CI installs the extra
(`pip install -e '.[notebooks,test,pymc]'`) because the notebook-import gate requires everything a notebook imports to be installable by CI.

**The Python marker.** Every `pymc` release since 6.0 requires Python 3.12 or later (5.28.5, released 2026-05-01, is the last that accepts 3.11), and CI
also runs 3.11. The first push without a marker failed on both 3.11 jobs ("no matching distribution found for pymc>=6.3.2"). The extra therefore
installs nothing on 3.11; the notebook is not executed in CI, so no job needs the package there. The alternative, a lower bound at 5.28.5, would declare
a version the notebook was never run against.

**Existence, age and requirements, verified on PyPI on 2026-10-30.** Project `pymc`, Apache-2.0, release 6.3.2 uploaded 2026-09-08 and the release the
notebook ran against, so it is the lower bound. Its required dependencies are `arviz>=1.1.0,<2`, `cachetools`, `cloudpickle`, `numpy>=1.25.0`,
`pandas`, `pytensor>=3.2.2,<3.4`, `rich`, `scipy`, `threadpoolctl` and `typing-extensions`. In a clean Python 3.13 environment the notebook ran with
`pymc` 6.3.2, `pytensor` 3.3.5, `arviz` 1.3.0, `numpy` 2.5.4, `scipy` 1.18.1 and `pandas` 3.1.0. `pytensor` compiles C code at the first sampling, so a
C++ compiler must be present; it was on the runner used here and on the author's machine.

**API facts relied on, exercised in a clean environment before the notebook was written.** `pm.sample` returns an ArviZ `DataTree`; a group is read with
`tree["posterior"].dataset` and `tree["sample_stats"].dataset` (a divergence flag is `diverging`). `pm.stats.rhat`, `pm.stats.ess(method="bulk" | "tail")`
and `pm.stats.bfmi` return a node that is read with `.dataset`, and ArviZ 1.x summaries default to an 89% interval, so the notebook computes its own 90%
quantiles. With `cores=1` and a `random_seed` the chains run one after another and two runs of the same notebook gave identical numbers. The posterior
predictive replicates come from `pm.sample_posterior_predictive(..., extend_inferencedata=True)` under the same seed, because the corpus's
no-randomness gate forbids a random-number generator in a notebook.

## 3. Cost and benefit

*Benefit.* A published, tested sampler with standard convergence diagnostics, so the notebook reports R-hat, effective sample sizes, divergences and
BFMI from the library's own definitions, and the exact grid calculation in the library gives an independent check on the sampler that a reader can
audit. *Cost.* A heavy transitive dependency (`pytensor` with a C compiler, `arviz`, `xarray`) for one notebook; a Python 3.12 floor for the extra; a
`pytensor` upper bound that can conflict with a later package; and a dependency on a package that releases about monthly.

**Measured cost.** Local install into a clean Python 3.13 environment: `pip install -e '.[notebooks,test]'` took about 60 s; adding `pymc` took a
further 13 s. CI, one run each on `main` at `4a8789d` and on the card branch at `65fc252` (wall time of the workflow, and the sum of its jobs):

| Workflow | Before | After | Change |
|---|---|---|---|
| Notebook Release Gates, wall | 103 s | 124 s | +21 s |
| test, wall | 126 s | 144 s | +18 s |
| Sum of job times (Lane 1 static 100 s, test 3.11 95 s, test 3.12 121 s before; 121 s, 85 s and 140 s after) | 316 s | 346 s | +30 s |

Both are well inside the 5-minute limit. Runs on `main` in the same session varied from 90 s to 126 s for the same workflow, so a single pair of runs
cannot resolve changes of about half a minute; the conclusion is only that the increase is far below 5 minutes. On 3.11 the extra installs nothing, so
the increase comes from the 3.12 job and the static lane. The notebook is not executed in CI, so its own run time (about six minutes for six fits of
4 chains by 10,000 draws) is not in these numbers.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| A Gibbs or Hamiltonian sampler written in the package | An unverified sampler with its own convergence theory; the corpus's rule is known-answer tests against a reference, and the exact grid calculation is that reference for the sampler we do use |
| The exact grid calculation alone, without a sampler | It covers only the normal-normal model; the card is to show a probabilistic-programming workflow, and the logit-scale and heavy-tailed variants are not conjugate |
| `numpyro` or `stan` | Another runtime (JAX, or a C++ toolchain and an interface package) with no advantage for a model this size |
| A lower bound of `pymc>=5.28.5` so that 3.11 installs it | Would declare a release the notebook never ran against |

## 5. Consequences

The extra is installed by CI (3.12 job) and by a reader who runs the Q03 notebook on Python 3.12 or later: `pip install -e '.[notebooks,pymc]'`. A
reader on 3.11 can read the stored outputs but not rerun the sampler. Any later package added for one notebook follows the same pattern (its own extra;
`tests/test_documented_commands_work.py` treats extras other than the shared ones as covering their module; the declared-imports test checks it is
imported by a notebook and by no library test). If a later release of `pymc` or `pytensor` breaks the pin, the Q03 notebook's stored output stays as
the evidence of the run and the extra is the only thing that fails to install. Q02's ADR 0011 makes the same decision for `econml`; the two branches
both edit the extras block, the CI install lines and `methods/__init__.py` and will conflict textually when the second is merged.
