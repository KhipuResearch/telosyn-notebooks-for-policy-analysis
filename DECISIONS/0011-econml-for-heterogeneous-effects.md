<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0011 — `econml` for heterogeneous effects, in its own optional extra

- **Status:** Accepted
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-10-30
- **Amends:** ADR 0009 section 3.6 (dependency policy)

## 1. Context

Card Q02 estimates how the adjusted employment difference between adults with and without public coverage varies across covariate cells, with a
causal forest (honest splitting, doubly robust residualisation, a bootstrap-of-little-bags interval). The package has no forest estimator, and
scikit-learn has no causal forest. ADR 0009 section 3.6 reserved `econml` for this card and required, for any package added for one notebook: an
optional extra, never core; a lower bound; a cost and benefit paragraph; and an import that the declared-imports test can see. The owner released the
card on 2026-10-30 within these limits: its own extra, an ADR, CI time measured before and after with a total increase of at most 5 minutes, library
tests that do not require the package, seeded runs, and data that stay cells-only.

## 2. Decision

Add `econml>=0.17.0` as **its own optional extra**, `econml`, in `pyproject.toml`. It is not in the runtime dependencies, in `notebooks`, in `methods`
or in `test`. Only the Q02 notebook imports it. The two functions the notebook needs that are not the forest itself, the construction of cell units
and the best-linear-predictor calibration, are in `krl_tutorials_data.methods.cate`; that module imports only numpy, pandas and scipy, and its
known-answer tests (`tests/test_methods_cate.py`) run without `econml`. A test (`tests/test_src_imports_declared.py`) fails if `econml` is imported by
the package or by a library test, or is declared anywhere but its own extra. CI installs the extra (`pip install -e '.[notebooks,test,econml]'`)
because the notebook-import gate requires everything a notebook imports to be installable by CI.

**Existence, age and requirements, verified on PyPI on 2026-10-30.** Project `econml`, MIT licence, requires Python 3.9 or later. Release 0.17.0 was
uploaded 2026-07-31 and is the release the notebook ran against, so it is the lower bound; 0.16.0 is dated 2025-07-10. Its required dependencies are
`numpy>=2.0.2`, `numba>=0.60.0`, `scipy>=1.13.1`, `scikit-learn>=1.6.0,<1.10`, `sparse>=0.15.4`, `joblib>=1.4.2`, `statsmodels>=0.14.4`,
`pandas>=2.2.3`, `shap>=0.46.0`, `lightgbm>=4.5.0` and `packaging>=24.2`. In a clean Python 3.13.5 environment the notebook ran with `econml` 0.17.0,
`numpy` 2.5.4, `scikit-learn` 1.9.1, `pandas` 3.1.0 and `scipy` 1.18.1.

**API facts relied on, read from the installed package's docstrings and exercised, not assumed.** `CausalForestDML` takes `honest`, `n_estimators`,
`min_samples_leaf`, `max_samples`, `subforest_size`, `inference` and `random_state`; `fit` takes `sample_weight` and `groups`, where `groups` keeps
rows of one group together **in the cross-fitting folds** (the forest's own honesty and subsampling run over rows); `effect`, `effect_interval` and
`ate_interval` exist, and `ate_interval` averages over the rows given without weights. Two fits with the same seed gave identical effects.

## 3. Cost and benefit

*Benefit.* A published, tested forest with an honest-splitting variance estimate, so the notebook calibrates and reports a forest and not a hand-built
one that no reader could audit. *Cost.* Heavy transitive dependencies (`numba`, `shap`, `lightgbm`, `sparse`) for one notebook; a scikit-learn upper
bound (`<1.10`) that can conflict with a later scikit-learn; a dependency on a package whose releases are roughly annual.

**Measured cost.** Local install into a clean Python 3.13 environment: `pip install -e '.[notebooks,test]'` took 62 s; adding the `econml` extra took
a further 9 s. CI, one run each on `main` at `4a8789d` and on the card branch at `149c45e` (wall time of the workflow, and the sum of its jobs):

| Workflow | Before | After | Change |
|---|---|---|---|
| Notebook Release Gates, wall | 103 s | 125 s | +22 s |
| test, wall | 126 s | 137 s | +11 s |
| Sum of job times (Lane 1 static 100 s, test 3.11 95 s, test 3.12 121 s before; 120 s, 97 s and 133 s after) | 316 s | 350 s | +34 s |

Both are well inside the 5-minute limit. Runs on `main` in the same session varied from 90 s to 126 s for the same workflow, so a single pair of runs
cannot resolve changes of about half a minute; the conclusion is only that the increase is far below 5 minutes. The notebook is not executed in CI, so
its own run time (the fits take 6 s each, the whole notebook a few minutes) is not in these numbers.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| Implement a causal forest in the package | A large, unverified estimator with its own variance theory; the corpus's rule is known-answer tests against a reference, and no second implementation is in the dependency set |
| scikit-learn only (random-forest T-learner) | No honesty and no variance estimate; the notebook would report an interval it could not defend |
| An R package (`grf`) | Adds a second language and runtime to a Python corpus |

## 5. Consequences

The extra is installed by CI and by a reader who runs the Q02 notebook: `pip install -e '.[notebooks,econml]'`. Any later package added for one
notebook follows the same pattern (its own extra, `tests/test_documented_commands_work.py` treats extras other than the shared ones as covering their
module, and the declared-imports test checks it is imported by a notebook and by no library test). If a later release of `econml` or scikit-learn breaks
the pin, the Q02 notebook's stored output stays as the evidence of the run and the extra is the only thing that fails to install.
