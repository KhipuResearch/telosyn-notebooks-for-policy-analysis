"""Known-answer tests for ``krl_tutorials_data.methods.pooling``.

Written before the module. Pure numpy and scipy; nothing here imports ``pymc``.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy import integrate, stats

from krl_tutorials_data.methods import pooling

Z90 = 1.645


# ---------------------------------------------------------------------------------------- proportion error
def test_proportion_se_uses_the_published_subset_formula() -> None:
    # x = 200 of n = 1000, margins 40 and 100 (90%): p = 0.2, se_x = 40/1.645, se_n = 100/1.645
    se = pooling.proportion_se([200.0], [40.0], [1000.0], [100.0])
    sx, sn = 40 / Z90, 100 / Z90
    assert se[0] == pytest.approx(np.sqrt(sx**2 - 0.2**2 * sn**2) / 1000)


def test_proportion_se_falls_back_to_the_ratio_formula_when_the_radicand_is_negative() -> None:
    # a tiny numerator margin and a large denominator margin make the subset radicand negative
    se = pooling.proportion_se([500.0], [1.0], [1000.0], [400.0])
    sx, sn = 1 / Z90, 400 / Z90
    assert se[0] == pytest.approx(np.sqrt(sx**2 + 0.5**2 * sn**2) / 1000)


def test_proportion_se_is_nan_for_an_empty_universe_and_never_negative() -> None:
    se = pooling.proportion_se([0.0, 5.0], [0.0, 3.0], [0.0, 50.0], [0.0, 9.0])
    assert np.isnan(se[0]) and se[1] > 0


def test_proportion_se_rejects_unequal_lengths() -> None:
    with pytest.raises(ValueError, match="length"):
        pooling.proportion_se([1.0, 2.0], [1.0], [10.0, 10.0], [1.0, 1.0])


# --------------------------------------------------------------------------------------- moment estimator
def test_moment_tau2_is_observed_variance_minus_mean_sampling_variance_floored_at_zero() -> None:
    y = np.array([0.10, 0.20, 0.15, 0.25])
    s = np.array([0.01, 0.02, 0.01, 0.02])
    assert pooling.moment_tau2(y, s) == pytest.approx(np.var(y, ddof=1) - np.mean(s**2))
    assert pooling.moment_tau2(y, np.full(4, 1.0)) == 0.0


# ------------------------------------------------------------------------------------ conditional posterior
def _dense_conditional(y, s, tau, m0, s0):
    """theta | y, tau by conditioning a joint Gaussian over (mu, theta, y): independent of the module."""
    n = len(y)
    # variables: mu, theta_1..n ; observation y = theta + e
    prior_mean = np.concatenate([[m0], np.full(n, m0)])
    cov = np.zeros((n + 1, n + 1))
    cov[0, 0] = s0**2
    cov[1:, 1:] = tau**2 * np.eye(n) + s0**2
    cov[0, 1:] = cov[1:, 0] = s0**2
    h = np.hstack([np.zeros((n, 1)), np.eye(n)])
    s_y = h @ cov @ h.T + np.diag(s**2)
    gain = cov @ h.T @ np.linalg.inv(s_y)
    mean = prior_mean + gain @ (y - h @ prior_mean)
    post = cov - gain @ h @ cov
    return mean[1:], np.diag(post)[1:], mean[0]


def test_conditional_posterior_matches_dense_gaussian_conditioning() -> None:
    rng = np.random.default_rng(4)
    s = rng.uniform(0.01, 0.06, 9)
    y = 0.15 + rng.normal(0, 0.04, 9) + rng.normal(0, s)
    for tau in (0.005, 0.04, 0.3):
        mean, var, mu_mean = pooling.conditional_posterior(y, s, tau, 0.15, 0.10)
        m_ref, v_ref, mu_ref = _dense_conditional(y, s, tau, 0.15, 0.10)
        np.testing.assert_allclose(mean, m_ref, rtol=1e-9, atol=1e-12)
        np.testing.assert_allclose(var, v_ref, rtol=1e-9, atol=1e-14)
        assert mu_mean == pytest.approx(mu_ref, rel=1e-9)


def test_conditional_posterior_limits_are_no_pooling_and_complete_pooling() -> None:
    y = np.array([0.05, 0.20, 0.35])
    s = np.array([0.02, 0.02, 0.02])
    big, _, _ = pooling.conditional_posterior(y, s, 1e3, 0.15, 0.10)
    np.testing.assert_allclose(big, y, atol=1e-6)
    small, _, mu = pooling.conditional_posterior(y, s, 1e-9, 0.15, 0.10)
    np.testing.assert_allclose(small, mu, atol=1e-6)


# ----------------------------------------------------------------------------------------- exact reference
def _log_marginal(y, s, tau, m0, s0):
    """log p(y | tau) from the dense marginal covariance: independent of the module."""
    n = len(y)
    cov = tau**2 * np.eye(n) + np.diag(s**2) + s0**2 * np.ones((n, n))
    return stats.multivariate_normal(mean=np.full(n, m0), cov=cov).logpdf(y)


def _brute_force_theta_mean(y, s, i, m0, s0, tau_scale):
    def dens(tau):
        return np.exp(_log_marginal(y, s, tau, m0, s0)) * 2 * stats.norm.pdf(tau, 0, tau_scale)

    def num(tau):
        return pooling.conditional_posterior(y, s, tau, m0, s0)[0][i] * dens(tau)

    z = integrate.quad(dens, 0, 2.0, limit=400)[0]
    return integrate.quad(num, 0, 2.0, limit=400)[0] / z


def test_exact_posterior_matches_one_dimensional_quadrature_of_the_dense_model() -> None:
    rng = np.random.default_rng(8)
    s = rng.uniform(0.01, 0.06, 7)
    y = 0.15 + rng.normal(0, 0.04, 7) + rng.normal(0, s)
    out = pooling.exact_posterior(y, s, mu_prior=(0.15, 0.10), tau_prior=("halfnormal", 0.05))
    for i in range(len(y)):
        assert out.theta_mean[i] == pytest.approx(_brute_force_theta_mean(y, s, i, 0.15, 0.10, 0.05), abs=2e-6)
    # tau's posterior mean from the same quadrature
    def dens(t):
        return np.exp(_log_marginal(y, s, t, 0.15, 0.10)) * 2 * stats.norm.pdf(t, 0, 0.05)
    z = integrate.quad(dens, 0, 2.0, limit=400)[0]
    assert out.tau_mean == pytest.approx(integrate.quad(lambda t: t * dens(t), 0, 2.0, limit=400)[0] / z, abs=2e-6)


def test_exact_posterior_variance_obeys_the_law_of_total_variance() -> None:
    rng = np.random.default_rng(2)
    s = rng.uniform(0.01, 0.05, 6)
    y = 0.12 + rng.normal(0, 0.03, 6) + rng.normal(0, s)
    out = pooling.exact_posterior(y, s, mu_prior=(0.15, 0.10), tau_prior=("halfnormal", 0.05))
    assert np.all(out.theta_sd > 0)
    # conditional variance given tau is at most s_i^2 (shrinkage never widens beyond the data), and the total adds the spread of the mean
    assert np.all(out.theta_sd**2 <= s**2 + 0.10**2 + 0.05**2)
    # shrinkage factor lies in (0, 1)
    assert np.all((out.shrinkage_mean > 0) & (out.shrinkage_mean < 1))


def test_exact_posterior_supports_a_half_cauchy_tau_and_integrates_to_one() -> None:
    y = np.array([0.10, 0.18, 0.14, 0.22])
    s = np.array([0.02, 0.03, 0.02, 0.04])
    out = pooling.exact_posterior(y, s, mu_prior=(0.15, 0.10), tau_prior=("halfcauchy", 0.05))
    assert np.trapezoid(out.tau_density, out.tau_grid) == pytest.approx(1.0, abs=1e-6)
    assert out.tau_mean > 0


def test_exact_posterior_rejects_bad_input() -> None:
    y, s = np.array([0.1, 0.2]), np.array([0.02, 0.02])
    with pytest.raises(ValueError, match="positive"):
        pooling.exact_posterior(y, np.array([0.02, 0.0]), mu_prior=(0.15, 0.1), tau_prior=("halfnormal", 0.05))
    with pytest.raises(ValueError, match="length"):
        pooling.exact_posterior(y, s[:1], mu_prior=(0.15, 0.1), tau_prior=("halfnormal", 0.05))
    with pytest.raises(ValueError, match="prior"):
        pooling.exact_posterior(y, s, mu_prior=(0.15, 0.1), tau_prior=("uniform", 0.05))
    with pytest.raises(ValueError, match="positive"):
        pooling.exact_posterior(y, s, mu_prior=(0.15, -1.0), tau_prior=("halfnormal", 0.05))
