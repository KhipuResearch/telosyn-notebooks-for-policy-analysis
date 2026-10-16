# KRL Tutorials — Notebook Corpus Forensic Audit

**Artifact ID:** KRL-TUT-AUDIT-2026-09-13
**Auditor:** KRL Model Integrity (internal review function)
**Date:** 2026-09-13
**Corpus:** `<audited-tree>` — 53 notebooks
**Terminology.** This report avoids *fabrication* as a characterisation, because it imports a claim about intent that the artifacts do not evidence. Where a random draw or a hardcoded scalar is presented in an evaluative context, the finding is stated as an **undisclosed synthetic value presented without the provenance required to read it as observed or estimated**; where a conclusion is printed with no computational antecedent, it is stated as a **hardcoded claim with no demonstrated computational antecedent**. Both formulations are harder to dispute than the stronger word and describe the defect exactly.

**Verification posture:** Adversarial. Every claim below is graded **VERIFIED** (reproduced by execution or exact hash), **OBSERVED** (read directly from the artifact), **INFERRED**, or **UNCERTAIN**.

---

> **Redaction note (2026-10-15).** This is the audit of record for the corpus from which
> the published notebooks were rebuilt. Two families it examined are not published. Their
> file names and the path of the audited tree are replaced with neutral identifiers. Hashes,
> findings, grades and every figure are as issued.


## 1. Objective Restatement

Determine whether the 53 Jupyter notebooks constituting the private source repository's educational product are (a) **functional** — do they execute; (b) **methodologically sound** — are the statistical and causal claims supported by the code that produces them; and (c) **accurate** — do the narrative conclusions match the computed results. Produce a prioritised remediation plan. No code is modified by this pass.

**Decision this audit supports:** whether the tutorial corpus can be published, taught from, or shown to a design partner in its current state, and what must change before it can.

**Release contract applied.** The first issue of this report used a narrower failure condition — *a notebook that cannot execute, or that produces a number a reader would believe and act on which the code does not support*. That is a serviceable release trigger but not a scientific definition of validity: a notebook can be statistically invalid while producing nothing anyone acts on, and a good teaching notebook may deliberately demonstrate a bad analysis. The contract this report now applies, and which belongs in the repository itself:

> A notebook is releasable only if its executable state, data provenance, computational results, statistical interpretation and narrative claims are mutually consistent, and every reported quantity is explicitly classified as **empirical, estimated, simulated, illustrative or hypothetical**.

Under that contract the deliberate demonstration of a bad analysis is releasable — provided it says so. That distinction is what rescues D30 (§F-10).

---

## 2. Assumptions & Known Gaps

| # | Assumption | Strength | Effect if wrong |
|---|---|---|---|
| A1 | The audited tree is representative of the shipping corpus | **Verified** — 43 of 53 notebooks are byte-identical (SHA-1) to the working tree; 10 differ | Findings on the 10 differing files may be stale; all are domain-template clones sharing the same defects |
| A2 | A clean environment with the public scientific stack is a fair execution baseline | Strong — the notebooks explicitly advertise a no-API-key synthetic fallback path | Root ML notebooks additionally require the private `krl_data_connectors`; their failures are marked ENV-CONFOUNDED, not counted as defects |
| A3 | Stored outputs correspond to the code currently in the cell | **Falsified in ≥6 notebooks** (see F-11) | — |

**Known gaps (not resolved by this pass):**
- **Scope gap, declared:** this audit covered `notebooks/` (53 files) and not `the showcase sub-project/notebooks/` (23 further notebooks with PDF exports, a validation harness and unit tests). Identified by the subject after issue 1; partially characterised in **F-18**, not fully audited.
- The private packages `krl-data-connectors`, `krl-model-zoo` were not read; five UNCERTAIN items in §8 depend on them.
- Notebooks were executed in Python 3.11 (container); the corpus declares 3.13.7 kernels. Syntax errors are version-independent and were reproduced under both.
- No labelled ground-truth set exists anywhere in the repository, so no sentiment/NER/topic claim in the corpus is externally validatable, by anyone.

---

## 3. Options & Trade-Off Analysis

| Option | Statistical validity | Cost | Operational risk | Verdict |
|---|---|---|---|---|
| **A. Static analysis only** | Cannot establish functionality; every claim stays *inferred* | Minutes | Under-reports; false positives from scope-unaware parsing | **Rejected** — insufficient under this project's epistemic standard |
| **B. Full execution of all 53** | Definitive | Hours; needs 5 live API keys, private packages, GPU-class deps | Would confound environment failures with code defects | **Rejected** — cost disproportionate once (C) proves the blocking defect |
| **C. Compile-check all 53 + execute a stratified sample** ✅ | Compile status is *proof*, not inference; execution supplies empirical failure evidence at the exact cell | ~20 min | Sample may miss a notebook-specific defect | **Selected** |

**Why (C) is sufficient here:** `ast.parse` failure is a *proof of non-execution* — no environment, dependency set, or API key can make a `SyntaxError` cell run. Once 31 of 53 fail to compile, full execution of those 31 would add no information. Execution was therefore reserved for the 22 that *could* run, to test the more interesting question: what do the working notebooks actually produce?

---

## 4. Selected Approach & Rationale

Four independent instruments, each capable of falsifying the others:

1. **Compile gate** — `ast.parse` on all 691 code cells of all 53 notebooks (IPython magics neutralised, not stripped).
2. **Live kernel execution** — `nbclient` against a clean Python 3.11 + pandas/numpy/sklearn/statsmodels/scipy/plotly environment, outputs cleared first so the run measures *this* execution.
3. **Behavioural reproduction** — the data-loading and modelling logic extracted and re-run standalone, to measure what the notebooks *report* rather than whether they merely run.
4. **Structural forensics** — SHA-256 over code-source, exact `difflib` ratios, section-header fingerprinting, execution-count ordering, stored-output/code correspondence.

**Contracts and invariants asserted:** a notebook is FUNCTIONAL only if every code cell compiles *and* a clean kernel completes it; a reported metric is VALID only if it is computed from data at run time; a stated conclusion is SUPPORTED only if the code path that produces it can produce the opposite conclusion.

---

## 5. High-Level Design

```
53 .ipynb
   ├─ instrument 1: per-cell ast.parse ................ → compile.json   (functionality, proof)
   ├─ instrument 2: nbclient clean-kernel run .......... → exec_results.json (functionality, empirical)
   ├─ instrument 3: extracted-logic reproduction ....... → measured R², p-values (accuracy)
   └─ instrument 4: hash / difflib / header / exec-count → clone lineage, provenance
                                   │
                                   ▼
              cross-instrument reconciliation → Stage-7 adversarial falsification
                                   │
                                   ▼
                    graded findings + remediation plan
```

---

## 6. Analytical Findings

### 6.0 Severity taxonomy and evidence tiers

The CRITICAL/HIGH/MEDIUM grading in the first issue of this report conflated species of failure. A notebook that will not parse and a notebook that emits an unsupported causal claim are different defects with different owners, different fixes and different release consequences. Findings are therefore classified twice — by failure class, and by the strength of the evidence behind them.

| Class | Meaning | Findings |
|---|---|---|
| **S0** | Credential / secret exposure | F-14 |
| **S1** | Non-executable or non-parseable artifact | F-1, F-11 |
| **S2** | Invalid statistical computation | F-2, F-3, F-9, F-10, F-12, F-13 |
| **S3** | Unsupported scientific or causal claim | F-4, F-6, F-7, F-8 |
| **S4** | Provenance / reproducibility failure | F-11, F-15, F-17 |
| **S5** | Pedagogical / documentation defect | missing objectives, exercises, disclosures |
| **S6** | Engineering hygiene | F-16 |

| Tier | Meaning |
|---|---|
| **E1** | Static code evidence — read from the artifact |
| **E2** | Deterministic reproduction in a clean audit environment |
| **E3** | Internal cross-check against repository history, stored outputs or configuration |
| **E4** | Externally validated against primary-source documentation |
| **E5** | Independently replicated by a second reviewer or environment |

**Nothing in this report is E5.** No second reviewer or second environment has replicated these results. That is the single largest outstanding weakness in the audit, and the per-notebook manifest (§7) exists so that it can be closed by someone other than the author.

**E4 validations performed.** Two load-bearing semantic claims about Census variables were verified against the Census API data dictionary rather than inferred from code:

| Variable | Verified label (verbatim) | Consequence |
|---|---|---|
| `B27001_005E` | *"Estimate!!Total:!!Male:!!Under 6 years:!!No health insurance coverage"* | Confirms F-13. Used as a statewide uninsured rate; measured mean 0.16% against a true rate near 9% |
| `B15003_022E` | *"Estimate!!Total:!!Bachelor's degree"*, universe *"Population 25 Years and Over"* | Confirms F-13. Correct denominator is `B15003_001E`, not `B01003_001E` (total population, all ages) |

Both hold. Claims in this report about PLACES MRP covariates, FRED frequency behaviour and BLS definitions remain **E1/E3 and are listed as UNCERTAIN in §8** — they have *not* been raised to E4 and should not be relied on at E4 strength.

---

### 6.1 Headline

| Measure | Result | Grade |
|---|---|---|
| Notebooks that **fail to compile** | **31 / 53 (58%)** | VERIFIED (static + live kernel, identical cell indices) |
| Domain tutorials (D01–D33) that fail to compile | **31 / 33 (94%)** | VERIFIED |
| Notebooks with **zero stored outputs** (never executed, or cleared) | **38 / 53 (72%)** | OBSERVED |
| Notebooks presenting **RNG output as a metric** | **32 / 53**, 128 instances | VERIFIED |
| Domain tutorials with **learning objectives** (mandated by the operating brief) | **1 / 33** | OBSERVED |
| Domain tutorials with **exercises** (mandated by the operating brief) | **0 / 33** | OBSERVED |
| Domain tutorials using **real data** | **0 / 33** | VERIFIED |
| Notebooks that complete a clean `Restart & Run All` | **3 / 19 sampled** (D04, D30, `test_kernel`) | VERIFIED |

**Release disposition: BLOCKED.** The assessed artifacts do not meet minimum requirements for executable reproducibility, data-and-result provenance, statistical validity, narrative fidelity, or secrets hygiene. The defects are systemic and generator-level. Remediation belongs at the source-template and release-governance layers, not in notebook-by-notebook repair.

> **The corpus does not meet its own published standard.** The operating brief states: *"Every notebook must be executable end-to-end with `Restart & Run All`"*, *"Every notebook must state learning objectives at the top"*, *"Real-world data examples preferred over synthetic data"*, *"All notebooks must execute without error via `jupyter nbconvert --execute`"*. Each of these is violated by a majority of the corpus.

---

### F-1 · CRITICAL · 31 notebooks cannot execute — one template defect, replicated
**Grade: VERIFIED** (both instruments, same cell, same error)

A single generator defect deleted an `if` statement while leaving its indented body and `else:` branch intact. The orphaned block sits in the same logical section of every affected notebook, under five naming variants:

| Section name | Notebooks |
|---|---|
| `WORKSPACE INTEGRATION & ECOSYSTEM VERIFICATION` | 13 |
| `WORKSPACE INTEGRATION` | 7 |
| `WORKSPACE INTEGRATION & ECOSYSTEM COHESION` | 5 |
| `WORKSPACE COHESION & REGISTRY VERIFICATION` | 4 |
| `WORKSPACE INTEGRATION & REGISTRY VERIFICATION` | 2 |

Evidence — `D01_D01_income_and_poverty.ipynb`, cell 9, lines 60–64:
```python
# Cross-platform integration check

    print(" Khipu notebook executor available for production deployment")
else:
    print("ℹ  Khipu executor not found - notebook available for educational use")
```
Live kernel: `SyntaxError: invalid syntax (line 63)`. The `D10`/`D11`/`D08`/`D09` variant raises `IndentationError: unexpected indent (line 46)` from the same cause.

**Penetrance is 100%, and that resolves the 31-of-33 exception.** Exactly 31 of the 33 domain notebooks contain the `Khipu notebook executor` block, and exactly those 31 fail. D04 and D30 do not escape a defect — they never received the block. D04's cell 10 is an export-and-reproducibility cell; D30 is a differently authored notebook entirely. So this is not a defect that struck 31 notebooks unevenly; it is a defective emission that every receiving notebook inherited without exception. That is characteristic of a generation step, not of hand-editing.

**Precision on the failure mode:** this is a *parse* failure, not merely an execution failure. `ast.parse` rejects the source before any interpreter state exists, so no environment, dependency set, API key or kernel version can make these cells run. That is a stronger claim than "cannot execute" and it is the one the evidence supports.

**Aggravating factor:** the defective cell sits at position 9–11 of 10–12, *after* the analysis. Every affected notebook would run its full modelling and conclusion sections, print its results, and only then die. A reader sees a complete analysis followed by a traceback.

**Remediation:** one scripted fix across 31 files — restore the guard (`if khipu_executor_path.exists():`) or delete the section. **Effort: < 1 hour.** This is the single highest-leverage fix in the corpus.

---

### F-2 · CRITICAL · Random numbers are reported as model quality metrics
**Grade: VERIFIED** — 128 instances across 32 notebooks

`D04_D04_health.ipynb` cell 8 (`enhanced_model_comparison`), verbatim:
```python
if max_tier >= 4:
    # Add complexity metrics
    complexity_score = np.random.uniform(0.5, 1.0)  # Placeholder
    interpretability = np.random.uniform(0.3, 0.9)  # Placeholder
else:
    complexity_score = np.random.uniform(0.2, 0.6)
    interpretability = np.random.uniform(0.7, 1.0)

results.append({'Model': name, 'RMSE': rmse, 'R²': r2, 'MAE': mae,
                'Complexity': complexity_score, 'Interpretability': interpretability, ...})
```
The table is then printed with `to_string()` and narrated:
```python
print(f"Complexity: {best_model['Complexity']:.3f}")
print(f"Interpretability: {best_model['Interpretability']:.3f}")
```
Two of six columns in a results table labelled *"ENHANCED MODEL COMPARISON RESULTS"* are `np.random.uniform` draws, formatted to three decimals, with **no synthetic disclosure**, sitting beside genuinely computed RMSE and R². A reader cannot distinguish them.

This is the same **R14 fabrication class** identified in the 2026-07-04 platform examination. It is present here at 32× the file count.

---

### F-3 · CRITICAL · The regression target is chosen by column position, producing R² = 1.000 on a constant
**Grade: VERIFIED by standalone reproduction**

All 32 template notebooks select their target as *the last numeric column*:
```python
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
feature_cols = numeric_cols[:-1]   # All but last as features
target_col   = numeric_cols[-1]    # Last as target
```
For the Census branch, the synthetic frame is `{geoid, geo_name, value, year: 2023}` → numeric columns `['value', 'year']` → **features = `value`, target = `year`**, a constant.

Reproduced exactly:
```
FEATURES = ['value']   TARGET = year
target unique values: [2023]   variance: 0.0
  Linear Regression: R² = 1.000   RMSE = 0.000000
  Random Forest:     R² = 1.000   RMSE = 0.000000
```
`D01_income_and_poverty` — a tutorial on income determinants — reports a **perfect model** for predicting the year 2023 from a random number, and prints `Best model: Linear Regression (R² = 1.000)`.

Where the frame has <2 numeric columns (the CDC/generic branch, e.g. D04), the fallback is worse in kind:
```python
y = X['feature_1'] * 2 + X['feature_2'] + np.random.randn(len(df)) * 0.1
```
The target is a deterministic linear function of the features. Measured: **Linear Regression R² = 0.996**. The tutorial teaches that a linear model explains 99.6% of variance in a health outcome.

---

### F-4 · CRITICAL · Conclusions are hardcoded strings, printed regardless of what was computed
**Grade: OBSERVED**

`D01` cell 8 prints, unconditionally:
```python
"Model Performance: Combined approaches achieve >85% prediction accuracy for income forecasting"
"Income Determinants: OLS regression identifies education, employment, and demographic
 factors as primary drivers of income variation"
```
Neither statement reads any computed variable. The model has no education or employment feature — it has `value` and `year`. `D13_crime_and_public_safety` asserts *"Analytical Accuracy: >90% for predictive models, >85% for causal inference"* while implementing **no causal inference at all** (`dowhy`/`econml`/DiD: 0 matches).

The notebook also ships a `'business_readiness': 'PRODUCTION'` field in its exported summary.

---

### F-5 · CRITICAL · D31, D32, D33 are byte-identical clones of D01
**Grade: VERIFIED by SHA-256 over code source**

```
D01 code-source sha256: f66c6aaee71affae
D31 code-source sha256: f66c6aaee71affae   ← civic trust
D32 code-source sha256: f66c6aaee71affae   ← civil freedom
D33 code-source sha256: f66c6aaee71affae   ← gender equality
exact difflib ratio D01↔D31 = 1.0
```
Three notebooks on civic trust, civil liberty, and gender equality contain **verbatim income-and-poverty code**, including Lorenz curves, Gini-index series IDs, Census table `B19013_001E`, and the printed conclusion *"prediction accuracy for **income forecasting**"*. A student opening the gender-equality tutorial is taught income inequality under a different title.

**Correction to an earlier draft of this audit:** a preliminary similarity figure of ~93% across the corpus was computed with `difflib.quick_ratio`, which is an *upper bound*, not a ratio. The **exact** median ratio to D01 across the other 32 domain notebooks is **45.7%** (min 1.1%, max 100.0%). The clone claim is therefore restated on structural rather than lexical grounds: 33 notebooks reduce to **12 distinct section-header sequences** of one 11-section scaffold, and all 31 compile failures occur inside the same logical section. The corpus is one generator's output with domain strings substituted — but it is not 93% textually identical, and this audit previously overstated that.

---

### F-6 · CRITICAL · "Causal" is a naming convention, not a method
**Grade: OBSERVED across 7 root notebooks**

In `ML_06`, `ML_04` (both files), `ML_05`, and the GRU paths of ML_01–ML_03, the entire causal content is an adjacency matrix built from **list ordering** and passed as a `use_causal_gates=True` argument to a supervised regressor:
```python
causal_dag = np.zeros((n_variables, n_variables))
for i in range(len(economic_vars)):
    for j in range(len(economic_vars), len(economic_vars) + len(social_vars)):
        causal_dag[i, j] = 1
```
No estimand, no treatment variable, no adjustment set, no positivity or exchangeability assumption, no refutation test. `ML_04` cell 24 perturbs an input feature and prints *"🎯 Causal Transformer enables monetary policy impact analysis!"* — a feature perturbation on a predictive model, presented as policy causal inference.

**The one exception proves the rule.** `ML_03.ipynb` implements genuine machinery — estimand, backdoor reasoning, propensity scores, AIPW, bootstrap, E-values, four falsification tests. Its executed output:

```
🚨 FAIL: Negative control effect is AS STRONG as main effect
🚨 FAIL: Statistically significant future→past effect
         ATE (poverty[t+1] → diabetes[t]): +2.1999 pp, 95% CI [+1.8202, +2.5914]
🚨 WEAK ROBUSTNESS (E < 1.5) … Results should be treated with skepticism
⚠️  Positivity violations: 38 obs;  Maximum weight = 26.11
⚠️  POOR balance post-IPW (SMD education = 0.312, uninsured = −0.382)
🎯 VERDICT: Data does NOT support poverty→diabetes at state level
```
Its summary cells (57, 62, 73) state: *"**Falsification Tests**: No association with pre-treatment outcomes"*, *"✅ **Honest About Failures**"*, *"Propensity Score Modeling: **Balanced** treatment/control groups ✅"*, *"**Verdict**: Academic peer reviewers will approve this methodology."*

**The notebook reports the falsification suite as passed. Three of its four tests failed.** That contradiction is E2-verified and is the finding.

**An inference I am withdrawing.** The first issue of this report treated the placebo-timing result — future poverty "causing" past diabetes at 3.6× the headline effect — as direct evidence that the main estimate is confounded. That inference is not supported, and I withdraw it. The test's mechanics are sound (verified: a genuine within-state `groupby('state')['poverty_rate'].shift(-1)` on a real 51-state × 7-year panel, n=261, E3), but state poverty rates are near-perfectly persistent year-over-year, so `poverty_high_lead` is close to collinear with the actual treatment `poverty_high`. The test therefore has little power to discriminate and would be expected to "fail" for **any** highly persistent exposure, whether or not the main estimate is valid. It is weak evidence about the ATE.

What survives is narrower and still release-blocking: the notebook's own diagnostics identify material, unresolved threats to identification — positivity violations, poor post-IPW balance on both confounders, an E-value of 1.29 — and the narrative asserts the opposite. The correct statement is not *"the effect is confounded"* but *"the causal estimand is not release-ready, and the claim that it was validated is inconsistent with the notebook's own diagnostic output."*

---

### F-7 · CRITICAL · Executed output contradicts the narrative, and always in the product's favour
**Grade: OBSERVED** — a directional pattern, not random error

| Notebook | Computed (stored output) | Stated (same file) |
|---|---|---|
| ML_03 | `Causal GRU R² −19.08` vs `Standard −12.02` | *"Causal GRU maintains accuracy while enforcing domain knowledge"* |
| ML_03 | `System Status: ⚠️ NEEDS IMPROVEMENT` | `Overall Completion: 11/11 (100%)`, every item `✅ COMPLETE` |
| ML_03 | `Predicted diabetes reduction: 0.0%` | *"✅ Causal model enables policy impact estimation!"* |
| ML_02 | 5-fold CV `Mean R²: −9.2020` | `System Status: ✅ PRODUCTION READY` |
| spatial media demo | `Kept: 0 articles in 0 clusters` / `❌ ERROR: No valid clusters` | `✓ Using OPTIMIZED ADAPTIVE weighting` → *"Winner: Adaptive ✓"* |
| D30 wellbeing | income p=0.13, coverage p=0.19, education p=0.07 | *"Income, health coverage, and education **significantly** predict life satisfaction"* |

**Sub-finding F-7a — a pre-written false excuse.** The identical two lines appear in the state notebook (cell 40) and the tract notebook (cell 66):
```python
print("   This is expected with current synthetic demonstration data")
print("   Should improve significantly with 100% real data integration")
```
Both were emitted in runs where CDC and Census APIs were verifiably called, and the same run's report prints `✅ Real Data Integration: 100%`. A hardcoded explanation for failure that is factually false about its own data is a governance defect, not a bug.

---

### F-8 · CRITICAL · Simulated content reported with measured performance figures
**Grade: OBSERVED** — `D34 copy.ipynb`, cell 48, `execution_count: 110` (it ran)

```python
# Use simulation mode for demo
return [{'url': url,
         'content': f"Simulated content for {url}. ...",
         'success': True,
         'word_count': 150 + (hash(url) % 500),
         'scraped_at': datetime.utcnow().isoformat()} for url in urls[:10]]
```
Then, in the same cell:
```python
print(f"   Throughput: {len(scraped_articles) / elapsed:.2f} articles/sec")
print(f"   Success rate: {successful}/{len(scraped_articles)} ({successful/len(scraped_articles)*100:.1f}%)")
```
`word_count` is a pseudo-random integer presented as a measured document length; `success` is hardcoded `True`, so the stored 100% success rate is arithmetically guaranteed. The **URLs are real** (fetched live from GDELT in the same cell), which makes the fabricated payload harder to spot, not easier. Cell 52 does the same for NER: *"# Simulation: Extract capitalized words as entities"* under a header reading `⚡ PARALLEL NLP PROCESSING PIPELINE`.

---

### F-9 · CRITICAL · Quality metrics fall back to hardcoded constants inside bare `except:`
**Grade: OBSERVED** — 3 spatial notebooks

`D34_demo.ipynb` cell 20:
```python
except:
    # Fallback if metrics fail
    silhouette_fixed = 0.093
    davies_bouldin_fixed = 1.485
```
In `D34_spatial.ipynb` cell 19 and `D34_demo copy 2.ipynb` cell 13, **both arms** are hardcoded (`silhouette_adaptive = 0.30`, `davies_bouldin_adaptive = 1.20`) — the head-to-head comparison that concludes "adaptive wins" can be produced entirely from literals in an exception handler. These values print in the same format as measured ones.

Compounding: the stored run shows the adaptive method returned **zero clusters**, and the winner logic (`'Adaptive ✓' if largest_cluster_pct_adaptive < largest_cluster_pct_fixed`) awarded it the win at 0.0%. The notebook then printed success and assigned `df_clustered = df_adaptive.copy()` on an **empty DataFrame**, before cell 31 silently replaced it with a different method's result. Every downstream figure describes a clustering the notebook never announces.

---

### F-10 · CRITICAL · The one statistically literate notebook draws conclusions from pure noise
**Grade: VERIFIED by reproduction**

`D30_D30_subjective_wellbeing.ipynb` is the best notebook in the corpus: it has learning objectives, prerequisites, an explicit synthetic-data disclosure, real methods (statsmodels OLS, factor analysis, K-means with an elbow curve), and a proper reference list. It also compiles and executes cleanly.

Its data generator draws **every column independently**:
```python
state_data = pd.DataFrame({
    'life_satisfaction': np.random.normal(7.2, 0.8, 50).clip(1, 10),
    'median_income':     np.random.normal(65000, 15000, 50),
    'unemployment_rate': np.random.normal(4.5, 1.5, 50).clip(0, 15), ... })
```
True population correlation between every pair is **exactly zero**. Reproduced with the notebook's own seed (42):

```
OLS R² = 0.2091   adj R² = 0.1388   F p-value = 0.0291   ← model "significant"
  unemployment_rate   +0.128283   p = 0.0482   ← FALSE POSITIVE
  median_income       +0.000012   p = 0.1287
  health_coverage_pct +0.027444   p = 0.1902
  education_pct       −0.034262   p = 0.0743
largest spurious |r| among independent variables: 0.231
P(≥1 "significant determinant" in pure noise, 4 predictors, n=50) = 18.4%  [2000 sims]
```
The notebook renders a correlation heatmap of independent variables, runs factor analysis to "reveal latent dimensions" in data with no latent structure, and assigns cluster labels by **index** (`{0:'High Well-Being', 1:'Moderate', 2:'Lower'}`) rather than by cluster means — so the label may be inverted.

Its hardcoded takeaway — *"Income, health coverage, and education significantly predict life satisfaction"* — is false by construction **and** contradicted by its own printed p-values (0.13, 0.19, 0.07: none significant).

---

### F-11 · HIGH · Execution provenance is unsound in 6 of 7 root notebooks
**Grade: OBSERVED**

- Never executed at all: `ML_04` (×2), `ML_05`.
- Dies at import: `ML_06`, cell 5 `ImportError`.
- Dies mid-analysis and ships anyway: `ML_01`, cell 42 `NameError: name 'causal_mask' is not defined` — **22 downstream cells never ran**, including the production report and a 14,962-character policy-implications section.
- Non-monotonic execution counts: county notebook runs `11→14→16→17→19→5→2→6…` — ad-hoc interactive state, not a clean run.
- Interleaved runs: state notebook cell 40 prints "Fold 2/5" twice with different values.
- The one notebook with clean monotonic ordering (`ML_02`, 1→50) achieved it by **demoting two failing code cells to markdown** — cell 54 defines `select_causal_features_adaptive(...)` as prose, so the function is never defined at runtime.

`ML_01` is titled `_gru_` and trains **no GRU**; the only model that runs is `RandomForestRegressor`. Its cell 39 merge collapses 6,289 county records to **36 rows** (99.4% loss) while relabelling counties as "states".

---

### F-12 · HIGH · Universal panel leakage; preprocessing fitted before the split in 6 of 7
**Grade: OBSERVED**

Every notebook with repeated measures splits by row position or randomly over an entity–year panel — no grouped split, no fixed effects, no clustered standard errors anywhere in seven notebooks. `ML_01` cell 33: `Train R² 0.9099` vs `Test R² 0.6053`, with the same counties in both halves.

`fit_transform` on the full array precedes `train_test_split` in ML_06 (c13), ML_04 (c14), ML_04-copy (c11), ML_05 (c10), and both GRU paths of ML_01/ML_02. In `ML_04 copy.ipynb` cell 11 the comment and the code directly contradict each other:
```python
# Fit on training data only
X_scaled = scaler.fit_transform(X_flat).reshape(...)
```

**Tautological targets in 5 of 7.** `ML_05` cell 12 is the clearest:
```python
sequence = base_value + trend[:, None] + noise
X_sequences.append(sequence)
y_outcomes.append(sequence[-1].mean())   # y is literally a slice of X
```

---

### F-13 · HIGH · Real federal program names attached to fabricated numbers
**Grade: OBSERVED**

`ML_04` fetches FRED (`FEDFUNDS`, `CPIAUCSL`) and BLS (`LNS14000000`) into `fred_data`/`bls_data` — **neither variable is ever referenced again.** Under the header *"### 3.3 Merge Multi-Domain Data"*, no merge occurs; the modelling data is fabricated with `np.random`. The title block still lists FRED/BLS/BEA as Data Sources. `ML_05` cites NCES throughout and never obtains any NCES data.

Where the federal data *is* real, the constructs are wrong. In all three of ML_01–ML_03:
```python
year_data['uninsured_rate'] = year_data['B27001_005E'] / year_data['B01003_001E']
```
`B27001_005E` is *males under 6 with no health coverage*. Output confirms `uninsured_rate mean = 0.001588` (0.16%) against a true US rate near 9% — **off by ~50×**, and it is one of only two confounders in the entire causal identification strategy. `education_level` carries the same denominator error, and three "rates" in `ML_06` are computed as shares of a national total rather than rates.

---

### F-14 · HIGH · Live API-key prefixes are committed to git
**Grade: VERIFIED**

`notebooks/ML_03.ipynb` is **tracked in git**, and its cell-0 stored output contains:
```
🔑 Loading API keys from: <operator-path>/apikeys
   • CENSUS_API_KEY: <redacted>...
   • FRED_API_KEY: <redacted>...
   • BLS_API_KEY: <redacted>...
```
These prefixes match the live keys in `.env` (which is correctly gitignored and has **never** been committed — verified via `git log --all -- .env`). Ten characters is not a full key, but the repository carries a dual MIT / CC-BY-SA-4.0 licence and an open `CONTRIBUTING.md`, i.e. it is built to be published.

Also present: `jina_<redacted>...` (10 chars of a 65-char key, with its exact length) in `D34_demo.ipynb`; a GCP project id (redacted); **282 occurrences** of `<operator-home>/.../` across the notebook corpus; and licence-control bypass (`skip_license_check`, `KRL_SKIP_LICENSE_VALIDATION='true'`) in 7 notebooks, 16–20 calls each.

**Action: rotate CENSUS, FRED, BLS and Jina keys. Treat as compromised.**

---

### F-15 · HIGH · CI is structurally incapable of catching any of this ("false green")
**Grade: VERIFIED by reading the workflows**

Five of eight workflows are disabled: `test.yml.disabled`, `tests.yml.disabled`, `lint.yml.disabled`, `security-checks.yml.disabled`, `build-and-sign.yml.disabled`.

Of the two enabled notebook workflows:
- `notebook-validation.yml` calls `nbformat.read()` and prints `✅ Valid structure`. This validates that the file is **well-formed JSON** — it never compiles or executes a cell. All 53 notebooks pass it, including the 31 that cannot run.
- `tutorial-quality.yml` *does* check for learning objectives and references — but every content-quality step carries **`continue-on-error: true`** (lines 129, 183, 218, 250). Only directory- and file-existence checks can fail the build.

The corpus's stated testing requirement — *"All notebooks must execute without error via `jupyter nbconvert --execute`"* — **has no implementing check anywhere in CI.** The pipeline reports green on a corpus that is 58% non-executable.

---

### F-16 · MEDIUM · Undeclared dependencies and version-control debris

`mesa` (<tool>-based modelling) is imported by D06 and D11 and is **not in `pyproject.toml`** — the declared dependency list is `krl-core, krl-data-connectors, krl-models, krl-dashboard, jupyter, jupyterlab, notebook, pandas, numpy, matplotlib, seaborn, plotly`. Live kernel: `ModuleNotFoundError: No module named 'mesa'` at cell 6, *before* the F-1 syntax error.

`"Gradient Boosting": None,  # Placeholder` appears in all 32 template notebooks — named in the model suite, silently skipped, then counted in `f"Evaluated {len(comparison_results)} models"`.

Version-control debris in `D34/`: two byte-identical pairs (`advanced` ≡ `advanced copy`; `demo copy 2` ≡ `demo copy 4`), **1.20 MiB** wasted in the audited 12; **3.92 MiB across 14 duplicate groups** counting the 38 `*.ipynb.backup*` files. `D34_demo copy 2/4` are renamed stale backups from a known newline-corruption incident (`fix_cell9_newlines.py` sits in the same directory): four of their cells are newline-stripped into single lines beginning with `#`, silently commenting out the entire clustering, visualisation and bias steps. Neither has ever been executed.

---

### F-17 · HIGH · S4 · The production mechanism for 33 shipped artifacts is not under version control
**Grade: VERIFIED (E1/E3)**

F-1's 100% penetrance implicates a generation step. That generator is not in this repository. A search across both trees for any generator, scaffold, template or notebook-builder returns nothing that produces the `D01–D33` family.

The one template that does exist — `the showcase sub-project/templates/notebook_template.ipynb`, committed 2025-11-29 — is **unrelated** to the domain corpus. *(Correction: an earlier pass of this audit reported that this template carried the F-1 defect. That was a false positive from a substring match on the word "Khipu" in an import line. The template parses cleanly and shares no code with the domain family.)*

What that template does contain is the finding:

```python
from khipu_demo import is_demo_mode, DEMO_MODE
from khipu_demo.data import SyntheticDataGenerator, DataProvenance
from khipu_demo.visualization import get_palette, COLORBLIND_SAFE
...
print(f"🔒 Demo Mode: {DEMO_MODE}")
```

**A `DataProvenance` class, a `SyntheticDataGenerator`, and an explicit `DEMO_MODE` flag already exist in this repository.** They are precisely the provenance discipline whose absence causes F-2, F-3, F-8, F-9 and F-13. They were applied to the showcase and never to the tutorial corpus. The capability was present; the release gate that would have required it was not.

Two further governance observations, both E3:
- The domain notebooks were last modified on **2026-04-30** by two commits describing cohort-wide remediation sweeps — `feat(tutorials): Native-Library Cleanup Discipline cohort-wide sweep` (#21) and `feat(d02): SIGBUS resolution + W3-042 cohort-fix` (#20). Two sweeps touched these files and neither executed them; a parse failure survived both.
- The domain family carries **zero stored outputs and zero execution counts across all 33 notebooks**, so for this family there is no output-versus-source mismatch to explain. They were committed without ever being run. The "plausible outputs coexisting with broken source" question applies only to the D34 and diabetes families, where it is answered by F-11 (interleaved runs, non-monotonic counts, code cells demoted to markdown).

**Remediation consequence.** Because no generator is under version control, the P0 scripted fix across 31 files is **containment, not remediation, and it is disposable work** — it will be discarded when the family is regenerated. It is still worth the hour, because it stops the corpus being visibly broken while the generator is located. But repairing 33 notebooks by hand would be the wrong response to a generator-level defect.

**Effort:** locate or reconstruct the generator — 1 week, and it blocks P2.

---

### F-18 · HIGH · S4 · Scope gap: a second, better-governed 23-notebook corpus was not audited — and it reframes the finding
**Grade: VERIFIED (E1/E2)** · *Added after the subject identified `the showcase sub-project/notebooks/pdf_exports` as holding executed notebooks with preserved results.*

This audit covered `notebooks/` — 53 files. It did **not** cover `the showcase sub-project/notebooks/`, a further **23 notebooks** with their own PDF exports, an `_executed.ipynb` artifact, a validation directory and a test suite. That is a scope gap in the original engagement and it is declared here rather than quietly closed.

Checking the contrast was cheap and it is the most useful governance evidence in the report:

| Measure | `notebooks/` domain family | `the showcase sub-project/notebooks/` |
|---|---|---|
| Notebooks | 33 | 23 |
| Parse failures | **31** | **1** *(and see the caveat below)* |
| Carrying stored outputs | **0** | **21** |
| Monotonic execution counts | **0** | **20** |
| Undisclosed-synthetic metric pattern (F-2) | **128 instances** | **0** |
| Exported execution evidence (PDF / `_executed.ipynb`) | none | 22 PDFs + 1 executed notebook |
| Validation harness | none | `validation/NB_VALIDATION_DID.ipynb`, `NB_VALIDATION_SCM.ipynb`, `METHODOLOGY_COMPARISON.md` |
| Unit tests | none | `test_clients.py`, `test_data.py`, `test_imports.py`, `test_visualization.py` |
| Learning objectives | 1 / 33 | **0 / 23** |
| Provenance discipline actually used | **0 / 33** | **0 / 23** |

**Three conclusions follow, and they change the shape of the remediation.**

**(a) The organisation demonstrably knows how to do this.** The showcase corpus is executed, output-preserved, PDF-exported, methodologically serious on its face (heterogeneous treatment effects, synthetic control, regression discontinuity, multi-unit SCM) and carries both a validation harness and unit tests. The tutorial corpus has none of that. This is not a capability gap. It is a **release-governance gap between two corpora in one repository**, which is a materially easier problem to fix than "the team cannot build valid notebooks."

**(b) F-17 is sharper than stated.** The `DataProvenance` / `SyntheticDataGenerator` / `DEMO_MODE` machinery is declared in `the showcase sub-project/templates/notebook_template.ipynb` and is used by **zero of the 33 tutorials and zero of the 23 showcase notebooks**. It exists in exactly one place — the template — and nothing downstream adopted it. Meanwhile showcase notebooks carry heavy `np.random` usage (up to 27 occurrences in one file) with no disclosure mechanism engaged. The provenance discipline was designed, committed, and never once instantiated.

**(c) The reviewer's root-governance question is answered, by file.** *How did plausible outputs come to coexist with broken source?* In `15-regression-discontinuity-toolkit.ipynb`: the execution-count vector is `[1, 3, 5, 7, None, None, None, None, 9, 10, None, None, None]` — non-contiguous, with 11 cells carrying stored outputs but only 6 carrying execution counts. **Five cells hold outputs with no execution count at all**: stale results from an earlier session, preserved across subsequent source edits. That is the mechanism. It is not exotic and it is not confined to one file; it is what happens when outputs are committed and no gate ever re-derives them.

> **⚠️ Tooling caveat, and a correction to my own instrument.** That notebook's parse failure is `f-string: unmatched '['` on the line `f'Est = {main_result['estimate']:.2f}'` — same-quote nesting inside an f-string. This is a `SyntaxError` on Python ≤ 3.11 but **legal under PEP 701 on Python 3.12+**. My audit interpreters were 3.10 (device) and 3.11 (container); the corpus declares 3.13.7 kernels. Under the declared runtime that cell parses, so **this is an artifact of my tooling, not a defect in that notebook.**
>
> I therefore re-ran the check for PEP 701 contamination across the entire corpus. **Result: zero f-string-class failures in all 53 notebooks.** The 31 domain failures decompose as **27 × `invalid syntax` on the literal line `else:`** and **4 × `unexpected indent` on `print(" Khipu notebook executor available")`**. Both classes are SyntaxErrors under every Python 3.x. **F-1 is uncontaminated and version-independent.** This is exactly the check the evidence tiers exist to force, and it should have been run before issue 1 shipped.

**Recommendation.** Audit the 23 showcase notebooks under the same protocol before regenerating anything — not because they are suspected, but because they are the closest thing in the repository to a working reference, and the canonical template of §P2 should be derived from whichever of them survives scrutiny rather than written from scratch.

**Effort:** 1 week to audit the showcase corpus; it should precede P2.

---

### 6.2 Per-notebook disposition

Legend — **cmpl**: compiles · **cell**: first failing cell · **unex**: unexecuted code cells · **fab**: fabricated-metric instances · **rnd**: `np.random` occurrences · **obj/tak/exr**: objectives / takeaways / exercises

```
notebook                                                         cmpl cell code unex fab rnd  obj tak exr
--------------------------------------------------------------------------------------------------------
D01_income_and_poverty                                             NO    9   11   11   4  18   -   -   -
D02_employment_and_labor                                           NO   10   12   12   4  26   -   -   -
D03_education                                                      NO   10   12   12   4  18   -   -   -
D04_health                                                        yes        10   10   4  26   -   -   -
D05_housing                                                        NO   11   11   11   4  26   -   -   -
D06_inequality_and_wealth                                          NO   11   11   11   4  21   -   -   -
D07_demographics_and_migration                                     NO   11   11   11   4  26   -   -   -
D08_consumer_behavior_and_spending                                 NO   10   10   10   4  18   -   -   -
D09_industry_and_economic_structure                                NO   10   10   10   4  26   -   -   -
D10_social_mobility_and_opportunity                                NO   10   10   10   4  34   -   -   -
D11_cultural_economics                                             NO   10   10   10   4  29   -   -   -
D12_environmental_economics                                        NO   10   12   12   4  26   -   -   -
D13_crime_and_public_safety                                        NO   10   12   12   4  26   -   -   -
D14_transportation_and_commuting                                   NO   10   12   12   4  26   -   -   -
D15_business_and_entrepreneurship                                  NO   10   12   12   4  18   -   -   -
D16_internet_and_technology_access                                 NO   10   12   12   4  18   -   -   -
D17_food_security_and_agriculture                                  NO   10   12   12   4  18   -   -   -
D18_social_services_and_safety_net                                 NO   10   12   12   4  18   -   -   -
D19_civic_engagement_and_political                                 NO   10   12   12   4  18   -   -   -
D20_digital_economy                                                NO   10   12   12   4  21   -   -   -
D21_social_capital                                                 NO   10   12   12   4  29   -   -   -
D22_cultural_consumption                                           NO   10   12   12   4  21   -   -   -
D23_transportation_equity                                          NO   10   12   12   4  26   -   -   -
D24_environmental_justice                                          NO   10   12   12   4  26   -   -   -
D25_food_and_nutrition                                             NO   10   12   12   4  18   -   -   -
D26_public_safety                                                  NO   10   12   12   4  26   -   -   -
D27_housing_affordability_and_gentrification                       NO   10   12   12   4  26   -   -   -
D28_mental_health_and_wellbeing                                    NO   10   12   12   4  26   -   -   -
D29_innovation_and_entrepreneurship                                NO   10   12   12   4  26   -   -   -
D30_subjective_wellbeing                                          yes        14   14   0  10   Y   Y   -
D31_civic_trust                        [byte-identical to D01]     NO    9   11   11   4  18   -   -   -
D32_freedom_civil                      [byte-identical to D01]     NO    9   11   11   4  18   -   -   -
D33_gender_equality                    [byte-identical to D01]     NO    9   11   11   4  18   -   -   -
D34                                            yes        17    0   0   1   -   Y   -
D34 copy                                       yes        37    2   0   1   -   Y   Y
D34_variant_b           [CANONICAL, line B]     yes        45    0   0   1   -   Y   -
D34_variant_b copy      [exact duplicate]       yes        45    0   0   1   -   Y   -
D34_variant_c         [best in cluster]       yes        16    0   0   0   -   Y   -
D34_spatial                                  yes        39    0   0   0   -   Y   -
D34_demo           [CANONICAL, line A]     yes        41    0   0   0   -   Y   -
D34_demo 2                                 yes        34    0   0   0   -   Y   -
D34_demo copy                              yes        14    1   0   0   -   -   -
D34_demo copy 2    [CORRUPT, never run]    yes        30   30   0   0   -   Y   -
D34_demo copy 3                            yes        13    0   0   0   -   -   -
D34_demo copy 4    [exact dup of copy 2]   yes        30   30   0   0   -   Y   -
ML_01          [crashes at cell 42]    yes        48   26   0  26   -   Y   Y
ML_02                                   yes        50    0   0  30   -   Y   Y
ML_03         [falsification FAILED]  yes        36    3   0  23   -   Y   Y
ML_04          [never executed]        yes        12   12   0  10   -   Y   -
ML_04 copy     [never executed]        yes        18   18   0   1   -   Y   -
ML_05                     [never executed]        yes        14   14   0   2   -   Y   -
ML_06                     [dies at import]        yes        17   14   0   1   -   Y   -
test_kernel                               [0 cells — delete]      yes         0    0   0   0   -   -   -
```

---

## 7. Verification & Tests

**What was run**

| Instrument | Coverage | Result |
|---|---|---|
| `ast.parse` per code cell | 53 / 53 notebooks, 691 code cells | 31 fail; cell indices recorded |
| `nbclient` clean-kernel execution | 19 notebooks (one per domain family + all 7 root ML + both compiling domain notebooks + `test_kernel`) | 3 PASS, 15 FAIL, 1 TIMEOUT |
| Standalone logic reproduction | D01/D04 data + model path; D30 OLS/correlation + 2,000-run Type I simulation | R²=1.000 and R²=0.996 confirmed; D30 false positive confirmed |
| SHA-256 / exact `difflib` / header fingerprint / exec-count ordering | 53 / 53 | clone lineage and provenance established |

**Cross-instrument agreement:** static and dynamic instruments agreed on **all 15 execution failures at the identical cell index and error class**. No disagreement.

**Regression suite to install (none currently exists)**

```python
# tests/test_notebooks_compile.py  — would have caught F-1 on the commit that introduced it
import ast, json, re, pathlib, pytest
NBS = sorted(pathlib.Path("notebooks").rglob("*.ipynb"))
@pytest.mark.parametrize("nb_path", NBS, ids=lambda p: p.name)
def test_every_code_cell_compiles(nb_path):
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        src = re.sub(r"^\s*[%!].*$", "pass", "".join(cell["source"]), flags=re.M)
        try:
            ast.parse(src)
        except SyntaxError as e:
            pytest.fail(f"{nb_path.name} cell {i}: {type(e).__name__}: {e.msg} (line {e.lineno})")
```

```python
# tests/test_no_fabricated_metrics.py  — would have caught F-2
FORBIDDEN = re.compile(
    r"(complexity_score|interpretability|confidence|reliability|coverage|accuracy|"
    r"silhouette\w*|davies\w*)\s*=\s*(np\.random|[0-9.]+\s*(#|$))", re.I)
```
Plus: `test_no_hardcoded_metric_in_except` (bare `except:` assigning a numeric literal to a metric name); `test_target_not_constant` (assert `y.var() > 0` before any `.fit`); `test_synthetic_disclosed` (any cell containing `np.random` that feeds a printed result must be preceded by a markdown disclosure); `test_no_secrets_in_outputs` (regex over stored outputs); `test_declared_deps_importable`.

**CI: two lanes, not one job.** A compile gate is necessary and nowhere near sufficient. The pipeline needs a fast lane on every pull request and a slow lane that alone can authorise release.

```
PULL-REQUEST LANE (fast, blocking)          RELEASE LANE (slow, blocking)
  1  notebook JSON + metadata contract        3  clean pinned env, Restart & Run All
  2  ast.parse every code cell                4  data acquisition + checksum manifest
     import / dependency declaration          5  statistical invariants:
     secret + output-leakage scan                  target configured, non-constant,
     banned-pattern scan (hardcoded                not among predictors
     conclusions, unseeded RNG metrics)            no preprocessing fit before split
                                                   no group leakage across entity/time
                                                   metrics on holdout, not train
                                              6  narrative-consistency gate
                                              7  human sign-off for causal / policy /
                                                 health / equity claims
```

**Gate 6 is the unusual one and it is the one this corpus most needs.** It is partially automatable: scan Markdown, comments and string literals for categorical assertions — *significant, causal, predicts, validated, passed, best, winner, robust, accurate, peer reviewers* — and for bare metric tokens, then require each to resolve against a claim record. It would mechanically reject a notebook where `p = 0.1287` appears in output while nearby prose says *significant* (F-10), or where `clusters = 0` coexists with `Winner: Adaptive` (F-9).

**`continue-on-error: true` must be forbidden on any release-blocking job.** If retained for informational linting it belongs in a visually separate lane that cannot produce a green release status — which is precisely the defect in F-15.

**Claim-to-computation provenance — the architectural fix for F-4, F-7 and F-8.** String-matching hardcoded conclusions is whack-a-mole. The durable fix is that no substantive conclusion may be authored as prose; it must be rendered from an object. Instead of

```python
print("Income, health coverage, and education significantly predict life satisfaction")
```

the notebook derives the claim:

```python
significant_terms = results.loc[results["p_value"] < alpha, "term"].tolist()
```

and emits a machine-readable record that the narrative gate can check:

```yaml
claim:
  id: claim_01
  text: "Education is associated with life satisfaction."
  type: association          # association | prediction | causal | simulation_demo
  estimand: regression_coefficient
  variable: education_pct
  estimate_ref: artifacts/model_results.parquet#education_pct
  uncertainty: {se: ..., ci95: [...]}
  p_value: ...
  data_mode: simulated       # empirical | estimated | simulated | illustrative | hypothetical
  data_source: null
  execution_id: ...
  caveat: "Not a causal estimate."
```

With that record in place the narrative cannot drift from the computation without failing a gate.

---

## 8. Self-Critique, Risks & Mitigations

**Errors found in this audit's own first pass, and corrected**

1. **Overstated similarity.** A preliminary figure of ~93% corpus similarity used `difflib.quick_ratio`, an *upper bound* on the true ratio. The exact median is **45.7%**. Corrected in F-5; the clone claim is now grounded in SHA-256 identity (D31/32/33) and section-header fingerprinting (12 sequences / 33 notebooks) rather than a lexical percentage.
2. **Scope-unaware name analysis over-reported.** An initial undefined-name pass flagged ~14 symbols per notebook by checking loads against *prior* cells only, ignoring intra-cell definitions. Nearly all were false positives. The D34 sub-audit resolved each remaining symbol individually and found `viz` in line B to be a **false positive** (string literal, not a variable) and `validated_articles` to be a *silent wrong number*, not a crash. Only `nx` in `D34_variant_b` cell 32 is a confirmed hard break, and it is latent.
3. **A static SyntaxError was dismissed.** `D34 copy` cell 48 fails `compile()` with `'await' outside function` — this is a static-analysis artefact; IPython permits top-level `await`. Recorded and dismissed, not reported as a defect.

**Five concrete failure modes of this audit**

| # | Failure mode | Mitigation / residual risk |
|---|---|---|
| 1 | Environment confound — root ML notebooks failed on the private `krl_data_connectors`, not necessarily on their own logic | Marked ENV-CONFOUNDED and **excluded** from the 31-failure count; their defects (F-6, F-11, F-12, F-13) are established by code reading and *stored outputs*, not by my execution |
| 2 | The backup may be stale relative to what ships | Quantified: 43/53 byte-identical; the 10 differing files are all template clones carrying the same defects. **Residual risk: low.** Re-run the compile gate on the working tree to close it — ~2 minutes |
| 3 | Python-version skew (3.11 audit vs 3.13.7 declared) | Syntax errors are version-independent and reproduced under both 3.10 and 3.11. **Residual risk: negligible** |
| 4 | Sampling — 34 of 53 notebooks were not executed | All 34 unexecuted are either compile-failures (proof of non-execution, no sample needed) or D34 variants covered by dedicated source review. **Residual risk: low** |
| 5 | Reviewer-generator homogeneity — this audit was produced by systems of the same class that generated the notebooks | **Not mitigated.** Stated on the record. Every CRITICAL finding is anchored to a verbatim quote and a reproducible command so a human or an independent tool can falsify it |

**Five UNCERTAIN items, and what resolves each**

1. Whether `FREDFullConnector.fetch_series(frequency='monthly')` interpolates quarterly `GDPC1` → read `krl-data-connectors/.../economic/`.
2. Whether the λ=0.15 "empirically optimised across 50+ policy topics" study exists → produce the sweep artefact, or withdraw the claim from cells 0/30/66.
3. Whether `GRUModel.causal_gates.causal_mask` assignment has any effect → read `krl-model-zoo/.../gru.py`. The constant-output behaviour is consistent with either a working mask or a dead network.
4. Whether the state notebook's stored outputs come from one run → only a fresh `Restart & Run All` resolves it.
5. The exact CDC PLACES MRP covariate set, on which the circularity argument for county/tract rests → PLACES methodology docs for the release years.

**What this audit does *not* claim:** that the underlying platform is unsound, that the authors intended to deceive, or that any external party was harmed. **No external party was harmed because no external party has used these notebooks.** That is the only thing standing between the current state and a materially worse one.

---

## 9. Recommended Next Steps

Effort estimates assume one engineer. **P0 items block any external exposure of this corpus.**

### Artifact classes — the precondition for all of it

One `notebook-validation` workflow cannot govern a demo, a simulation, a tutorial, a prototype and a causal analysis. Each notebook should declare its class in metadata, and the release lane should enforce the standard that class implies.

| Class | Purpose | Minimum release standard |
|---|---|---|
| Demo | Interface or code walkthrough | Explicitly non-empirical; no performance or domain claims |
| Simulation | Teaching a statistical concept | Declared DGP, seeded, no empirical framing |
| Tutorial | Teaching a real-data workflow | Fresh execution, real data lineage, exercises, limitations |
| Exploratory | Internal hypothesis generation | Provenance, caveats, no external causal conclusions |
| Predictive study | Estimation or prediction | Explicit target, split protocol, baselines, leakage tests, uncertainty |
| Causal analysis | Effect of an intervention | Estimand, assumptions, identification, diagnostics, sensitivity, independent review |
| External-facing | Partner or public consumption | All gates, plus editorial and legal/privacy review |

**Regenerate; do not repair.** D01–D33 are not 33 independent scientific products — F-1's 100% penetrance and F-5's hash identity establish them as manifestations of one generation mechanism. The remediation order follows from that:

```
  locate / reconstruct the generator  (F-17 — currently not in version control)
              │
              ▼
  build ONE canonical tutorial, reviewed and gate-passing
              │
              ▼
  regenerate D01–D33 from it  ──▶  stratified human review across domains
              │
              ▼
  causal family ──▶ SEPARATE research-review track, not the tutorial backlog
```

Assign new artifact IDs and a regeneration manifest. **Do not overwrite the forensic corpus in place** — preserve it, with a migration map from old notebook IDs to new artifacts.

### P0 — Contain (this week)

| # | Action | Finding | Effort |
|---|---|---|---|
| 1 | **Treat F-14 as a credential-exposure incident, not a rotation task.** Rotate CENSUS, FRED, BLS and Jina keys; **check provider audit logs for anomalous access during the exposure window**; purge or rewrite git history if policy requires (a new commit deleting the output does not remove it from history); invalidate caches, rendered previews, build artifacts and backups that may still carry the tokens; install `nbstripout` and pre-commit secret scanning; document scope — what was exposed, where, for how long, who had access. A 10-character prefix may or may not be exploitable depending on the provider's token design, but that is not the release criterion: it is sensitive credential material in tracked content. | F-14 · S0 | 4 h |
| 2 | **Fix the 31-notebook template defect** — restore the deleted `if` guard, or delete the `WORKSPACE INTEGRATION` section entirely (it is registry bookkeeping, notteaching content) | F-1 | 1 h |
| 3 | **Add the compile gate to CI and make it blocking.** Remove `continue-on-error: true` from all four `tutorial-quality.yml` content steps | F-15 | 2 h |
| 4 | **Quarantine the "causal" root notebooks.** Move to `notebooks/_quarantine/` with a README stating they are not validated. Do not show `ML_03` to any design partner until F-6 is resolved | F-6, F-7 | 1 h |
| 5 | **Delete** `D34_variant_b copy`, `D34_demo copy 2`, `copy 4` (corrupt, never executed), `test_kernel.ipynb`, and the 38 `*.ipynb.backup*` files | F-16 | 30 m |

### P1 — Make honest (2–4 weeks)

| # | Action | Finding | Effort |
|---|---|---|---|
| 6 | **Delete every fabricated metric.** Remove `complexity_score`/`interpretability` RNG columns; remove hardcoded silhouette/DB fallbacks; delete or clearly quarantine all `Simulat*` code paths and the cell-71 ROI block | F-2, F-8, F-9 | 1 w |
| 7 | **Delete every hardcoded conclusion.** Any printed claim must read a computed variable or be removed. Start with `>85% prediction accuracy`, the `PASS`/`PRODUCTION READY` banners, and F-7a's false synthetic-data excuse | F-4, F-7 | 1 w |
| 8 | **Reconcile `ML_03` with its own falsification output.** Either the ATE is withdrawn, or the negative-control and future→past failures are explained. The current summary cells must not survive either way | F-6 | 3 d |
| 9 | **Fix `uninsured_rate` / `education_level` denominators** (`B27001_005E`→correct uninsured table; `B15003_022E / B15003_001E`). Re-run every downstream estimate | F-13 | 2 d |
| 10 | **Retire D31, D32, D33.** They are D01 under three false titles — delete, or write them | F-5 | 1 d |

### P2 — Rebuild (6–10 weeks)

| # | Action | Finding | Effort |
|---|---|---|---|
| 11 | **Rebuild the domain template around one worked example on real data.** Fix the target-by-position defect at its root: the target must be named explicitly per domain, and asserted non-constant before any `.fit()`. Add learning objectives, prerequisites, exercises and key takeaways — the corpus's own mandated structure, currently present in 1 of 33 | F-3, F-1 | 3 w |
| 12 | **Do not destroy D30 — republish it as the false-discovery lesson it accidentally is.** Its experiment is excellent and its conclusion is wrong. Under an explicit `artifact_class: simulation` declaration, independent draws become the *point*: "how random data produces apparently significant relationships," with the measured 18.4% family-wise false-positive rate as the teaching result. Replace the stated takeaway; keep the structure. A second version with a known covariance matrix then makes the true coefficients recoverable and checkable. This is potentially the strongest notebook in the corpus | F-10 | 2 d |
| 13 | **Grouped splits and clustered SEs everywhere** there are repeated measures; fit all preprocessing inside the training fold | F-12 | 1 w |
| 14 | **Pin every dependency and model revision**; declare `mesa`; replace runtime `pip install` with a lockfile; pin data vintages | F-16 | 1 w |
| 15 | Install the regression suite from §7 | F-15 | 3 d |

### The one-line summary

> **The corpus does not provide a reliable chain from declared data source to computation, to reported quantity, to statistical interpretation, to narrative claim.** That chain is the scientific product; until it exists, execution is theatre — a kernel can run code perfectly and still emit conclusions that are statistically or causally indefensible.
>
> Scoped precisely: **all 33 domain tutorials carry zero stored outputs and zero execution counts** (E2), 31 of them fail to *parse* (E2), 0 of 33 use real data (E2), 1 of 33 has learning objectives (E1). The two that execute report a perfect model for predicting a constant, and a significant determinant drawn from pure noise (E2, reproduced). Elsewhere in the corpus execution demonstrably *did* occur — the D34 family carries monotonic execution counts, and ML_01–ML_03 called live CDC and Census endpoints. **The corpus-wide failure is uncontrolled execution provenance, not universal non-execution.** The fix for functionality is one hour. The fix for credibility is a rebuild — and it is worth doing, because F-6's falsification suite, F-9's honest `PROOF-OF-CONCEPT ONLY` caveat, and D30's structure show the capability is present in the same repository that produced the defects.

---

*Prepared under the KRL Model Integrity examination protocol. Every CRITICAL finding carries a file, a cell index, and a verbatim quote so that it can be independently falsified.*
