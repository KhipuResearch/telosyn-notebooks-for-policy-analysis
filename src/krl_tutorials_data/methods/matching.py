"""Propensity scores, matching, inverse-probability weighting, balance.

Estimand
    ``att_from_matches`` estimates the average effect on the treated (ATT);
    ``ipw_effect`` estimates the ATE or ATT by Hajek-normalised weights.

Identifying assumption
    **Selection on observables**: conditional on the covariates, treatment is
    independent of potential outcomes, and every unit has a propensity strictly
    inside (0, 1). **Neither can be tested here.** Balance on what was measured
    says nothing about what was not; :func:`rosenbaum_bounds` and
    :func:`rosenbaum_critical_gamma` ask how strong hidden bias would have to be
    to change a conclusion, for binary outcomes stratified on the covariates.

Frequency weights
    ``frequency`` (a count of identical observations, not an adjustment) lets every
    estimator run on cells: a row standing for ``n`` people gives the same result as ``n``
    copies of it, which the tests check. It is distinct from ``weights``, the adjustment
    weights (for example inverse-probability weights) that a balance check evaluates.

Estimators and their limits
    * The score is a logit fitted by Newton-Raphson. Perfect separation raises
      ``RuntimeError``; a degenerate score is never returned.
    * Matching is 1:1 nearest neighbour on the score (or its logit), with a
      caliper in score units or, on the logit scale, in standard deviations of
      the logit. With replacement is the default; without replacement is greedy
      in input order and therefore order-dependent, which is documented rather
      than hidden.
    * The ATT standard error from matches is the sample standard error of the
      pair differences. With replacement a control can appear in several pairs,
      so that is **not** the Abadie-Imbens variance and ignores both the reuse
      and the estimation of the score; it is an approximation and is labelled
      as one.
    * The IPW standard error is the influence-function variance treating the
      propensity as known, so it ignores score estimation.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats  # type: ignore[import-untyped]
from scipy.special import gammaln  # type: ignore[import-untyped]

Float = NDArray[np.float64]
Int = NDArray[np.intp]
_EPS = 1e-10


@dataclass(frozen=True)
class LogitFit:
    """A fitted logistic propensity model; ``coef[0]`` is the intercept."""

    coef: Float
    propensity: Float
    n_iter: int


@dataclass(frozen=True)
class MatchResult:
    """Matched index pairs; ``treated[i]`` is matched to ``control[i]``."""

    treated: Int
    control: Int
    distance: Float
    n_dropped: int


@dataclass(frozen=True)
class AttResult:
    """An ATT from matched pairs."""

    estimate: float
    se: float
    n_pairs: int


@dataclass(frozen=True)
class IpwResult:
    """An inverse-probability-weighted effect."""

    estimate: float
    se: float
    n_used: int
    n_trimmed: int


@dataclass(frozen=True)
class BalanceRow:
    """Standardised mean difference of one covariate."""

    name: str
    smd: float


@dataclass(frozen=True)
class OverlapData:
    """Histogram data for an overlap figure, and the common-support interval."""

    edges: Float
    counts_treated: Int
    counts_control: Int
    common_support: tuple[float, float]


def _binary(d: ArrayLike) -> Float:
    dd = np.asarray(d, dtype=float)
    if dd.ndim != 1 or not np.all(np.isin(dd, (0.0, 1.0))):
        raise ValueError("treatment must be a one-dimensional binary (0/1) array")
    if dd.min() == dd.max():
        raise ValueError("treatment must contain both treated and control units")
    return dd


def _frequency(frequency: ArrayLike | None, n: int, d: Float) -> Float:
    """Validated frequency weights: finite, non-negative, both treatment groups present."""
    if frequency is None:
        return np.ones(n)
    f = np.asarray(frequency, dtype=float)
    if f.shape != (n,) or not np.all(np.isfinite(f)):
        raise ValueError("frequency must be finite and the same length as d")
    if np.any(f < 0):
        raise ValueError("frequency must be non-negative")
    if f[d == 1].sum() <= 0 or f[d == 0].sum() <= 0:
        raise ValueError("frequency leaves one treatment group with no weight")
    return f


def logit_propensity(
    x: ArrayLike,
    d: ArrayLike,
    *,
    frequency: ArrayLike | None = None,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> LogitFit:
    """Logistic regression of ``d`` on ``x`` with an intercept (Newton-Raphson).

    ``frequency`` gives each row a count of identical observations: the fit equals the
    fit on that many copies of the row, so cell counts can be fitted without expanding
    them. A row with zero frequency has no influence (its propensity is still returned).
    """
    dd = _binary(d)
    xx = np.asarray(x, dtype=float)
    if xx.ndim == 1:
        xx = xx[:, None]
    if xx.shape[0] != dd.shape[0]:
        raise ValueError("x and d must have the same number of rows")
    if not np.all(np.isfinite(xx)):
        raise ValueError("x contains non-finite values; none are dropped silently")
    freq = _frequency(frequency, dd.shape[0], dd)
    design = np.column_stack([np.ones(dd.shape[0]), xx])
    beta = np.zeros(design.shape[1])
    for it in range(1, max_iter + 1):
        p = 1.0 / (1.0 + np.exp(-(design @ beta)))
        w = freq * p * (1.0 - p)
        if w.max() < _EPS:
            raise RuntimeError("perfect separation: fitted probabilities collapsed to 0 or 1")
        step = np.linalg.solve(design.T @ (design * w[:, None]), design.T @ (freq * (dd - p)))
        beta = beta + step
        if np.abs(step).max() < tol:
            break
    else:
        raise RuntimeError("logit did not converge; the score may be separable (separation)")
    p = 1.0 / (1.0 + np.exp(-(design @ beta)))
    return LogitFit(coef=beta, propensity=p, n_iter=it)


def nearest_neighbour_match(
    score: ArrayLike,
    d: ArrayLike,
    *,
    caliper: float | None = None,
    replace: bool = True,
    scale: Literal["logit", "raw"] = "logit",
) -> MatchResult:
    """1:1 nearest-neighbour matching of treated units to controls on ``score``.

    ``scale="logit"`` matches on ``logit(score)`` and interprets ``caliper`` in
    standard deviations of the logit; ``scale="raw"`` matches on the score and
    interprets ``caliper`` in score units. Treated units with no control inside
    the caliper are dropped and counted. Without replacement the match is
    greedy in input order.
    """
    dd = _binary(d)
    s = np.asarray(score, dtype=float)
    if s.shape != dd.shape or not np.all(np.isfinite(s)):
        raise ValueError("score must be finite and the same length as d")
    if scale not in ("logit", "raw"):
        raise ValueError(f"scale must be 'logit' or 'raw', not {scale!r}")
    if caliper is not None and caliper <= 0:
        raise ValueError("caliper must be positive")
    metric = s
    limit = caliper
    if scale == "logit":
        clipped = np.clip(s, _EPS, 1 - _EPS)
        metric = np.log(clipped / (1 - clipped))
        if caliper is not None:
            limit = caliper * float(np.std(metric))
    t_idx = np.flatnonzero(dd == 1)
    c_idx = np.flatnonzero(dd == 0)
    available = np.ones(c_idx.size, dtype=bool)
    pairs_t: list[int] = []
    pairs_c: list[int] = []
    dist: list[float] = []
    for i in t_idx:
        gaps = np.abs(metric[c_idx] - metric[i])
        if not replace:
            gaps = np.where(available, gaps, np.inf)
        j = int(np.argmin(gaps))
        if not np.isfinite(gaps[j]) or (limit is not None and gaps[j] > limit):
            continue
        if not replace:
            available[j] = False
        pairs_t.append(int(i))
        pairs_c.append(int(c_idx[j]))
        dist.append(float(gaps[j]))
    return MatchResult(
        treated=np.asarray(pairs_t, dtype=np.intp),
        control=np.asarray(pairs_c, dtype=np.intp),
        distance=np.asarray(dist),
        n_dropped=int(t_idx.size - len(pairs_t)),
    )


def att_from_matches(y: ArrayLike, d: ArrayLike, match: MatchResult) -> AttResult:
    """Mean of matched-pair differences ``y_treated - y_control`` and its approximate SE."""
    yy = np.asarray(y, dtype=float)
    dd = _binary(d)
    if yy.shape != dd.shape or not np.all(np.isfinite(yy)):
        raise ValueError("y must be finite and the same length as d")
    if match.treated.size == 0:
        raise ValueError("no matched pairs: nothing to average")
    diff = yy[match.treated] - yy[match.control]
    n = diff.size
    se = float(np.std(diff, ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    return AttResult(estimate=float(diff.mean()), se=se, n_pairs=int(n))


def ipw_effect(
    y: ArrayLike,
    d: ArrayLike,
    propensity: ArrayLike,
    *,
    estimand: Literal["ate", "att"] = "ate",
    trim: tuple[float, float] | None = None,
    frequency: ArrayLike | None = None,
) -> IpwResult:
    """Hajek-normalised IPW estimate of the ATE or ATT with an influence-function SE.

    ``trim`` drops units whose propensity lies outside ``[low, high]`` and
    reports how many; nothing is dropped otherwise. With ``frequency`` each row stands for
    that many identical observations and the result equals the one on the expanded data;
    ``n_used`` and ``n_trimmed`` then count observations, not rows.
    """
    if estimand not in ("ate", "att"):
        raise ValueError(f"estimand must be 'ate' or 'att', not {estimand!r}")
    yy = np.asarray(y, dtype=float)
    dd = _binary(d)
    p = np.asarray(propensity, dtype=float)
    if yy.shape != dd.shape or p.shape != dd.shape:
        raise ValueError("y, d and propensity must have the same length")
    if not (np.all(np.isfinite(yy)) and np.all(np.isfinite(p))):
        raise ValueError("y and propensity must be finite")
    if np.any(p <= 0) or np.any(p >= 1):
        raise ValueError("propensity must lie strictly inside (0, 1)")
    freq = _frequency(frequency, yy.shape[0], dd)
    keep = np.ones(yy.shape, dtype=bool) if trim is None else (p >= trim[0]) & (p <= trim[1])
    n_trimmed = int(round(freq[~keep].sum()))
    yy, dd, p, freq = yy[keep], dd[keep], p[keep], freq[keep]
    if freq[dd == 1].sum() <= 0 or freq[dd == 0].sum() <= 0:
        raise ValueError("trimming left only one treatment group")
    n = float(freq.sum())
    if estimand == "ate":
        w1, w0 = dd / p, (1 - dd) / (1 - p)
    else:
        w1, w0 = dd, (1 - dd) * p / (1 - p)
    s1, s0 = float(np.sum(freq * w1)), float(np.sum(freq * w0))
    mu1 = float(np.sum(freq * w1 * yy) / s1)
    mu0 = float(np.sum(freq * w0 * yy) / s0)
    psi = n * (w1 * (yy - mu1) / s1 - w0 * (yy - mu0) / s0)
    return IpwResult(
        estimate=mu1 - mu0,
        se=float(np.sqrt(np.sum(freq * psi**2) / n**2)),
        n_used=int(round(n)),
        n_trimmed=n_trimmed,
    )


def standardized_mean_difference(
    x: ArrayLike,
    d: ArrayLike,
    *,
    weights: ArrayLike | None = None,
    frequency: ArrayLike | None = None,
) -> float:
    """``(mean_treated - mean_control) / sqrt((var_treated + var_control) / 2)``.

    With ``weights`` the means are weighted; the pooled denominator uses the
    **unweighted** variances, the convention that keeps the scale fixed so before and
    after are comparable. ``frequency`` counts identical observations: means and
    variances are taken as if each row were repeated that many times (the variance with
    ``sum(frequency) - 1`` in the denominator), and the denominator ignores ``weights``.
    Returns 0 when both groups are constant and equal; raises when only one group is
    present.
    """
    xx = np.asarray(x, dtype=float)
    dd = _binary(d)
    ww = np.ones_like(xx) if weights is None else np.asarray(weights, dtype=float)
    if xx.shape != dd.shape or ww.shape != xx.shape or not np.all(np.isfinite(xx)):
        raise ValueError("x, d and weights must be finite and the same length")
    ff = _frequency(frequency, xx.shape[0], dd)
    t, c = dd == 1, dd == 0
    m1 = float(np.average(xx[t], weights=ww[t] * ff[t]))
    m0 = float(np.average(xx[c], weights=ww[c] * ff[c]))

    def variance(group: NDArray[np.bool_]) -> float:
        f = ff[group]
        mean = np.average(xx[group], weights=f)
        return float(np.sum(f * (xx[group] - mean) ** 2) / (f.sum() - 1.0))

    enough = ff[t].sum() > 1 and ff[c].sum() > 1
    pooled = np.sqrt((variance(t) + variance(c)) / 2.0) if enough else 0.0
    if pooled == 0.0:
        return 0.0 if m1 == m0 else float("inf") * np.sign(m1 - m0)
    return (m1 - m0) / float(pooled)


def balance_table(
    x: ArrayLike,
    d: ArrayLike,
    *,
    names: Sequence[str],
    weights: ArrayLike | None = None,
    frequency: ArrayLike | None = None,
) -> list[BalanceRow]:
    """One :func:`standardized_mean_difference` per column of ``x``."""
    xx = np.asarray(x, dtype=float)
    if xx.ndim != 2 or xx.shape[1] != len(names):
        raise ValueError("names must give one name per column of x")
    return [
        BalanceRow(
            str(nm),
            standardized_mean_difference(xx[:, j], d, weights=weights, frequency=frequency),
        )
        for j, nm in enumerate(names)
    ]


def overlap_data(score: ArrayLike, d: ArrayLike, *, bins: int = 20) -> OverlapData:
    """Counts per bin for treated and control scores, and the common-support interval."""
    if bins < 1:
        raise ValueError("bins must be at least 1")
    dd = _binary(d)
    s = np.asarray(score, dtype=float)
    if s.shape != dd.shape or not np.all(np.isfinite(s)):
        raise ValueError("score must be finite and the same length as d")
    edges = np.linspace(float(s.min()), float(s.max()), bins + 1)
    ct, _ = np.histogram(s[dd == 1], bins=edges)
    cc, _ = np.histogram(s[dd == 0], bins=edges)
    support = (
        float(max(s[dd == 1].min(), s[dd == 0].min())),
        float(min(s[dd == 1].max(), s[dd == 0].max())),
    )
    return OverlapData(
        edges=edges,
        counts_treated=ct.astype(np.intp),
        counts_control=cc.astype(np.intp),
        common_support=support,
    )


# ---------------------------------------------------------------------------
# Stratification and sensitivity to hidden bias
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StratifiedResult:
    """ATT from strata that hold both treated and control units."""

    estimate: float
    n_strata_used: int
    n_strata_dropped: int
    share_treated_used: float


def stratified_effect(
    treated_events: ArrayLike,
    treated_n: ArrayLike,
    control_events: ArrayLike,
    control_n: ArrayLike,
) -> StratifiedResult:
    """ATT of a binary outcome by stratification on covariate cells.

    Per stratum ``s`` the effect is ``events1/n1 - events0/n0``; the ATT weights strata
    by their treated count. A stratum with no treated or no control unit has no
    comparison and is dropped, and the share of treated units that survive is reported
    (a result computed on a small share of the treated says so). Counts may be
    frequencies of any kind, but only counts of sampled units support inference.
    """
    e1, n1 = np.asarray(treated_events, dtype=float), np.asarray(treated_n, dtype=float)
    e0, n0 = np.asarray(control_events, dtype=float), np.asarray(control_n, dtype=float)
    if not (e1.shape == n1.shape == e0.shape == n0.shape) or e1.ndim != 1:
        raise ValueError("the four count arrays must be one-dimensional and of equal length")
    if np.any(e1 < 0) or np.any(e0 < 0) or np.any(e1 > n1) or np.any(e0 > n0):
        raise ValueError("events must lie between 0 and the group size in every stratum")
    both = (n1 > 0) & (n0 > 0)
    if not both.any() or n1[both].sum() <= 0:
        raise ValueError("no stratum holds both treated and control units")
    diff = e1[both] / n1[both] - e0[both] / n0[both]
    estimate = float(np.sum(n1[both] * diff) / n1[both].sum())
    return StratifiedResult(
        estimate=estimate,
        n_strata_used=int(both.sum()),
        n_strata_dropped=int((~both).sum() - ((n1 == 0) & (n0 == 0)).sum()),
        share_treated_used=float(n1[both].sum() / n1.sum()),
    )


@dataclass(frozen=True)
class RosenbaumBounds:  # pylint: disable=too-many-instance-attributes
    """Bounds on the one-sided p-value of a stratified binary-outcome test at one Gamma."""

    gamma: float
    statistic: float
    expected_upper: float
    variance_upper: float
    expected_lower: float
    variance_lower: float
    p_upper: float
    p_lower: float


def _noncentral_moments(n1: Float, n0: Float, events: Float, odds: float) -> tuple[Float, Float]:
    """Mean and variance of the treated-event count in each 2x2 table, for odds ratio ``odds``.

    Fisher's noncentral hypergeometric over the margins: ``P(k) ~ C(n1,k) C(n0,m-k) odds^k``
    on ``k = max(0, m - n0) .. min(n1, m)``, computed in log space stratum by stratum.
    """
    means = np.empty(n1.shape[0])
    variances = np.empty(n1.shape[0])
    log_odds = np.log(odds)
    for s in range(n1.shape[0]):
        a, b, m = int(n1[s]), int(n0[s]), int(events[s])
        k = np.arange(max(0, m - b), min(a, m) + 1)
        log_w = _log_choose(a, k) + _log_choose(b, m - k) + k * log_odds
        w = np.exp(log_w - log_w.max())
        w /= w.sum()
        mean = float(np.sum(w * k))
        means[s] = mean
        variances[s] = float(np.sum(w * (k - mean) ** 2))
    return means, variances


def _log_choose(n: int, k: NDArray[np.int_]) -> Float:
    return gammaln(n + 1.0) - gammaln(k + 1.0) - gammaln(n - k + 1.0)


def rosenbaum_bounds(
    treated_events: ArrayLike,
    treated_n: ArrayLike,
    control_events: ArrayLike,
    control_n: ArrayLike,
    *,
    gamma: float,
) -> RosenbaumBounds:
    """Rosenbaum sensitivity bounds for a stratified binary outcome.

    The statistic is ``T``, the number of treated units with the event, summed over the
    strata. Within a stratum, conditional on the margins, ``T_s`` is hypergeometric when
    treatment is unrelated to the outcome given the covariates; if an unmeasured factor
    can multiply the odds of treatment by at most ``gamma`` between two units in the same
    stratum, the odds ratio of the noncentral hypergeometric lies in ``[1/gamma, gamma]``.
    The upper bound of the one-sided p-value for ``T >= t`` uses ``gamma``; the lower
    uses ``1/gamma``. Each stratum's mean and variance are exact; the sum over strata is
    referred to a normal distribution with continuity correction, which needs many strata
    or large ones. ``gamma = 1`` is the test with no hidden bias.
    Rosenbaum (2002), *Observational Studies*, as recalled, not verified in this build.
    Counts must be counts of **sampled units**: weighted counts overstate the evidence.
    """
    if not gamma >= 1.0:
        raise ValueError("gamma must be at least 1")
    e1, n1 = np.asarray(treated_events, dtype=float), np.asarray(treated_n, dtype=float)
    e0, n0 = np.asarray(control_events, dtype=float), np.asarray(control_n, dtype=float)
    if not (e1.shape == n1.shape == e0.shape == n0.shape) or e1.ndim != 1:
        raise ValueError("the four count arrays must be one-dimensional and of equal length")
    for name, arr in (
        ("treated_events", e1),
        ("treated_n", n1),
        ("control_events", e0),
        ("control_n", n0),
    ):
        if np.any(arr < 0) or np.any(arr != np.round(arr)):
            raise ValueError(f"{name} must hold non-negative whole counts")
    if np.any(e1 > n1) or np.any(e0 > n0):
        raise ValueError("events must lie between 0 and the group size in every stratum")
    usable = (n1 > 0) & (n0 > 0) & ((e1 + e0) > 0) & ((e1 + e0) < (n1 + n0))
    if not usable.any():
        raise ValueError("no stratum has both groups and a mix of outcomes")
    n1u, n0u, mu = n1[usable], n0[usable], (e1 + e0)[usable]
    statistic = float(e1[usable].sum())
    mean_hi, var_hi = _noncentral_moments(n1u, n0u, mu, gamma)
    mean_lo, var_lo = _noncentral_moments(n1u, n0u, mu, 1.0 / gamma)
    sd_hi, sd_lo = float(np.sqrt(var_hi.sum())), float(np.sqrt(var_lo.sum()))
    if sd_hi == 0.0 or sd_lo == 0.0:
        raise ValueError("the strata carry no variation in the treated-event count")
    p_upper = float(stats.norm.sf((statistic - 0.5 - mean_hi.sum()) / sd_hi))
    p_lower = float(stats.norm.sf((statistic - 0.5 - mean_lo.sum()) / sd_lo))
    return RosenbaumBounds(
        gamma=float(gamma),
        statistic=statistic,
        expected_upper=float(mean_hi.sum()),
        variance_upper=float(var_hi.sum()),
        expected_lower=float(mean_lo.sum()),
        variance_lower=float(var_lo.sum()),
        p_upper=p_upper,
        p_lower=p_lower,
    )


def rosenbaum_critical_gamma(
    treated_events: ArrayLike,
    treated_n: ArrayLike,
    control_events: ArrayLike,
    control_n: ArrayLike,
    *,
    alpha: float = 0.025,
    gamma_max: float = 100.0,
    tol: float = 1e-4,
) -> float:
    """The smallest Gamma at which the worst-case one-sided p-value exceeds ``alpha``.

    The direction is the observed one: a count of treated events above its no-bias
    expectation is tested against the upper bound, below against the lower bound.
    ``alpha = 0.025`` one-sided corresponds to a two-sided 0.05. Returns 1.0 when the
    result is not significant even with no hidden bias, and ``inf`` when it is still
    significant at ``gamma_max``. Found by bisection; the p-value is monotone in Gamma.
    """
    if not 0.0 < alpha < 0.5:
        raise ValueError("alpha must lie in (0, 0.5)")
    args = (treated_events, treated_n, control_events, control_n)
    base = rosenbaum_bounds(*args, gamma=1.0)
    positive = base.statistic >= base.expected_upper

    def worst(g: float) -> float:
        bounds = rosenbaum_bounds(*args, gamma=g)
        if positive:
            return bounds.p_upper
        return float(1.0 - bounds.p_lower)

    if worst(1.0) > alpha:
        return 1.0
    if worst(gamma_max) <= alpha:
        return float("inf")
    low, high = 1.0, float(gamma_max)
    while high - low > tol:
        mid = 0.5 * (low + high)
        if worst(mid) > alpha:
            high = mid
        else:
            low = mid
    return 0.5 * (low + high)
