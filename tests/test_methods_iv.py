"""Known-answer tests for ``krl_tutorials_data.methods.iv``.

The data are built so that the right answer is known before the estimator runs, and each result
is checked against a second implementation written differently (the textbook projection form).

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import iv


def test_a_binary_instrument_gives_the_wald_ratio_worked_by_hand() -> None:
    """z = 0: y 1,3 and d 0,0.2 ; z = 1: y 5,7 and d 0.4,0.6.

    Reduced form (6 - 2) = 4; first stage (0.5 - 0.1) = 0.4; the IV estimate is 4 / 0.4 = 10.
    """
    z = np.array([0, 0, 1, 1.0])
    y = np.array([1, 3, 5, 7.0])
    d = np.array([0, 0.2, 0.4, 0.6])
    fit = iv.tsls(y, d, z, cluster=np.arange(4))
    assert fit.reduced_form_coef == pytest.approx(4.0)
    assert fit.first_stage_coef == pytest.approx(0.4)
    assert fit.coef == pytest.approx(10.0)


def test_iv_recovers_the_effect_where_ols_does_not() -> None:
    """y = 3 d + 2 v with d = 1 + z + v: the confounder v is balanced across z by construction.

    Substituting, y = 3 + 3 z + 5 v, so the reduced form is 3 and the first stage is 1: the IV
    estimate is exactly 3, while the OLS slope of y on d is pulled toward the confounder.
    """
    z = np.repeat([0.0, 1.0], 8)
    v = np.tile([-1.0, 1.0, -2.0, 2.0], 4)
    d = 1 + z + v
    y = 3 * d + 2 * v
    fit = iv.tsls(y, d, z, cluster=np.arange(16))
    assert fit.coef == pytest.approx(3.0, abs=1e-10)
    ols = np.polyfit(d, y, 1)[0]
    assert abs(ols - 3.0) > 0.5


def projection_form(y, d, z, controls, w):
    """Textbook 2SLS: (X'Pz X)^-1 X'Pz y on sqrt-weighted data."""
    root = np.sqrt(w)[:, None]
    base = np.column_stack([np.ones(len(y)), controls])
    x = root * np.column_stack([d, base])
    zz = root * np.column_stack([z, base])
    pz = zz @ np.linalg.solve(zz.T @ zz, zz.T)
    return np.linalg.solve(x.T @ pz @ x, x.T @ pz @ (root[:, 0] * y))


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_property_it_matches_the_projection_form_with_controls_and_weights(seed: int) -> None:
    """Coefficient equals (X'PzX)^-1 X'Pz y for random data, controls and weights."""
    rng = np.random.default_rng(seed)
    n = 60
    controls = rng.normal(size=(n, 2))
    z = rng.integers(0, 2, n).astype(float)
    v = rng.normal(size=n)
    d = 0.8 * z + 0.5 * controls[:, 0] + v
    y = 2 * d + controls[:, 1] + 1.5 * v + rng.normal(size=n)
    w = rng.uniform(0.5, 3.0, n)
    fit = iv.tsls(y, d, z, cluster=rng.integers(0, 6, n), controls=controls, weights=w)
    assert fit.coef == pytest.approx(projection_form(y, d, z, controls, w)[0], abs=1e-8)


def test_cluster_robust_variance_agrees_with_a_loop_over_clusters() -> None:
    """The standard error equals the sandwich assembled cluster by cluster."""
    rng = np.random.default_rng(4)
    n, groups = 48, 8
    cluster = np.repeat(np.arange(groups), n // groups)
    z = rng.integers(0, 2, n).astype(float)
    d = 0.7 * z + rng.normal(size=n)
    y = 1.5 * d + rng.normal(size=n)
    fit = iv.tsls(y, d, z, cluster=cluster, small_sample=False)
    x, zz = np.column_stack([d, np.ones(n)]), np.column_stack([z, np.ones(n)])
    bread = np.linalg.inv(zz.T @ x)
    beta = bread @ (zz.T @ y)
    e = y - x @ beta
    meat = sum(
        np.outer(zz[c == cluster].T @ e[c == cluster], zz[c == cluster].T @ e[c == cluster])
        for c in range(groups)
    )
    expected = np.sqrt((bread @ meat @ bread.T)[0, 0])
    assert fit.se == pytest.approx(expected, rel=1e-10)
    assert iv.tsls(y, d, z, cluster=cluster).se > fit.se  # the CR1 factor only inflates


def test_a_weight_is_a_count_of_copies() -> None:
    """Weighting a row by n equals repeating it n times, for coefficients and, without CR1, SEs."""
    rng = np.random.default_rng(6)
    n = 12
    z = rng.integers(0, 2, n).astype(float)
    d = 0.9 * z + rng.normal(size=n)
    y = 2 * d + rng.normal(size=n)
    count = rng.integers(1, 5, n)
    cluster = np.arange(n) % 4
    weighted = iv.tsls(y, d, z, cluster=cluster, weights=count, small_sample=False)
    expanded = iv.tsls(
        np.repeat(y, count),
        np.repeat(d, count),
        np.repeat(z, count),
        cluster=np.repeat(cluster, count),
        small_sample=False,
    )
    assert weighted.coef == pytest.approx(expanded.coef, abs=1e-10)
    assert weighted.se == pytest.approx(expanded.se, rel=1e-8)
    assert weighted.first_stage_f == pytest.approx(expanded.first_stage_f, rel=1e-8)


def test_first_stage_f_is_the_squared_cluster_t_and_a_strong_instrument_gives_a_large_one() -> None:
    """F is (coef / se) squared; a near-deterministic first stage is large, a noise one small."""
    rng = np.random.default_rng(1)
    n = 200
    z = rng.integers(0, 2, n).astype(float)
    cluster = rng.integers(0, 10, n)
    strong = iv.tsls(rng.normal(size=n), 2 * z + 0.1 * rng.normal(size=n), z, cluster=cluster)
    weak = iv.tsls(rng.normal(size=n), rng.normal(size=n), z, cluster=cluster)
    assert strong.first_stage_f == pytest.approx(
        (strong.first_stage_coef / strong.first_stage_se) ** 2
    )
    assert strong.first_stage_f > 1000 and weak.first_stage_f < 10
    assert strong.n_clusters == 10 and strong.n_params == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"weights": np.array([-1.0] + [1.0] * 5)}, "non-negative"),
        ({"weights": np.zeros(6)}, "non-negative"),
        ({"cluster": np.zeros(6)}, "at least two clusters"),
        ({"cluster": np.arange(5)}, "one label per row"),
        ({"controls": np.ones((5, 1))}, "finite"),
        ({"z": np.array([0.0, 0, 0, 0, 0, 0])}, "irrelevant"),
        ({"d": np.array([1.0, 1, 1, np.nan, 1, 1])}, "non-finite"),
        ({"y": np.ones((6, 2))}, "one-dimensional"),
    ],
)
def test_invalid_inputs_raise(change: dict, message: str) -> None:
    """Bad weights, clusters, controls, instruments and shapes are refused."""
    args = {
        "y": np.arange(6.0),
        "d": np.array([0, 1, 0, 1, 1, 0.5]),
        "z": np.array([0, 1, 0, 1, 1, 0.0]),
        "cluster": np.arange(6) % 3,
        "controls": None,
        "weights": None,
    }
    args.update(change)
    with pytest.raises(ValueError, match=message):
        iv.tsls(
            args["y"],
            args["d"],
            args["z"],
            cluster=args["cluster"],
            controls=args["controls"],
            weights=args["weights"],
        )


def test_too_few_observations_for_the_parameters_raises_when_corrected_for_small_samples() -> None:
    """Three rows and three parameters leave no degrees of freedom for the CR1 correction."""
    args = ([1.0, 2.0, 4.0], [0.0, 1.0, 3.0], [0.0, 2.0, 1.0])
    controls = np.array([[1.0], [5.0], [2.0]])
    with pytest.raises(ValueError, match="cannot support"):
        iv.tsls(*args, cluster=[0, 1, 2], controls=controls)
    assert np.isfinite(
        iv.tsls(*args, cluster=[0, 1, 2], controls=controls, small_sample=False).coef
    )
