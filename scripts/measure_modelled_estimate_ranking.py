"""Can a modelled small-area estimate support a ranking? Measured, not assumed.

Handbook §7.1 established that no census tract among 13,981 has a determined
rank on broadband share. This script asks the same question of CDC PLACES --
county level, far coarser geography, and a different KIND of estimate: a
model-based prediction carrying a credible interval, rather than a design-based
estimate carrying a sampling margin.

Every number quoted in handbook §7.2 comes from here. Deterministic: same
release, same numbers.

  A. Signal-to-noise      between-county SD against median interval width
  B. Reliability          lambda_i = tau^2 / (tau^2 + se_i^2), the hierarchical
                          shrinkage weight; tau^2 by the DerSimonian-Laird
                          moment estimator. The provider-profiling literature
                          conventionally requires ~0.7 to publish unit-level
                          comparisons.
  C. Rank identifiability §7.1's test, unchanged, so the two are comparable
  D. Rank intervals       Monte Carlo distribution of each unit's rank
  E. Funnel               detection against a precision-weighted benchmark,
                          replacing "who is first?" with "who is unusual?"
  F. Tiers                groups surviving a Bonferroni sequential partition
  G. Size artifact        does precision track population (Gelman & Price)
  H. Circularity          how much of the estimate -- and of the RANKING --
                          is recoverable from ACS covariates alone

Usage:
    python scripts/measure_modelled_estimate_ranking.py
    python scripts/measure_modelled_estimate_ranking.py --measures diabetes obesity
    python scripts/measure_modelled_estimate_ranking.py --skip-acs

CENSUS_API_KEY is needed for section H only; A-G need no credential.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests
from scipy import stats as st

PLACES_COUNTY_2025 = "i46a-9kgh"
PLACES_URL = f"https://data.cdc.gov/resource/{PLACES_COUNTY_2025}.json"
ACS_URL = "https://api.census.gov/data/2023/acs/acs5"
SEED = 20260914
Z95 = 1.959964
Z998 = 3.090232
DEFAULT_MEASURES = ("casthma", "obesity", "diabetes", "depression")


@dataclass(frozen=True)
class Measure:
    """One PLACES measure, parsed into estimate and approximate standard error."""

    name: str
    est: np.ndarray
    se: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    fips: np.ndarray
    pop: np.ndarray

    @property
    def n(self) -> int:
        return len(self.est)


def parse_interval(text: object) -> tuple[float, float]:
    """Parse PLACES' interval, which ships as the string ``'( 8.8, 11.3)'``.

    The space after the parenthesis is real. Extracting numerals is robust to it;
    slicing by position is not, and that is the trap this function exists to
    remove from every notebook that touches this source.
    """
    if not isinstance(text, str):
        return (float("nan"), float("nan"))
    found = re.findall(r"-?\d+\.?\d*", text)
    if len(found) < 2:
        return (float("nan"), float("nan"))
    return (float(found[0]), float(found[1]))


def fetch(measures: tuple[str, ...], *, session: requests.Session) -> dict[str, Measure]:
    """Pull one PLACES release and return each measure with its parsed interval."""
    columns = ["countyfips", "countyname", "statedesc", "totalpopulation"]
    for name in measures:
        columns += [f"{name}_crudeprev", f"{name}_crude95ci"]
    response = session.get(
        PLACES_URL, params={"$select": ",".join(columns), "$limit": 5000}, timeout=120
    )
    response.raise_for_status()
    frame = pd.DataFrame(response.json())
    if frame.empty:
        raise SystemExit("PLACES returned no rows; refusing to report on an empty frame.")

    parsed: dict[str, Measure] = {}
    for name in measures:
        est = pd.to_numeric(frame[f"{name}_crudeprev"], errors="coerce").to_numpy()
        bounds = frame[f"{name}_crude95ci"].map(parse_interval)
        lo = np.array([b[0] for b in bounds])
        hi = np.array([b[1] for b in bounds])
        # Symmetric-normal SE recovered from the interval. PLACES intervals are
        # mildly asymmetric (section A reports the worst case), so this is an
        # approximation and is labelled as one wherever it is used.
        se = (hi - lo) / (2 * Z95)
        keep = np.isfinite(est) & np.isfinite(se) & (se > 0)
        parsed[name] = Measure(
            name=name,
            est=est[keep],
            se=se[keep],
            lo=lo[keep],
            hi=hi[keep],
            fips=frame["countyfips"].to_numpy()[keep],
            pop=pd.to_numeric(frame["totalpopulation"], errors="coerce").to_numpy()[keep],
        )
    return parsed


def tau_squared(m: Measure) -> float:
    """Between-unit variance, DerSimonian-Laird moment estimator, floored at 0.

    When the floor binds, the observed spread is no larger than the sampling
    noise and the data are consistent with every unit sharing one value.
    """
    return max(float(m.est.var(ddof=1) - (m.se**2).mean()), 0.0)


def reliability(m: Measure, tau2: float) -> np.ndarray:
    """Per-unit reliability, identical to the hierarchical shrinkage weight."""
    return tau2 / (tau2 + m.se**2)


def determined_ranks(m: Measure) -> int:
    """§7.1's test: a unit's rank is determined if its interval overlaps no other."""
    count = 0
    for i in range(m.n):
        overlaps = (m.lo < m.hi[i]) & (m.hi > m.lo[i])
        overlaps[i] = False
        if not overlaps.any():
            count += 1
    return count


def rank_intervals(m: Measure, *, draws: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Monte Carlo 95% interval for each unit's rank.

    A practical stand-in for the posterior rank of Shen & Louis (1998): rank the
    draws, not the point estimates. Deliberately the OPTIMISTIC approximation --
    independent normal draws ignore the shared model structure that would
    correlate units, so real posterior ranks would be no sharper than these.
    """
    rng = np.random.default_rng(SEED)
    sample = m.est[None, :] + m.se[None, :] * rng.standard_normal((draws, m.n))
    ranks = (-sample).argsort(1).argsort(1) + 1
    return np.percentile(ranks, 2.5, axis=0), np.percentile(ranks, 97.5, axis=0)


def funnel(m: Measure) -> tuple[float, float, float]:
    """Precision-weighted benchmark, and the share outside 95% / 99.8% limits."""
    weight = 1 / m.se**2
    theta0 = float((weight * m.est).sum() / weight.sum())
    z = (m.est - theta0) / m.se
    return theta0, float((np.abs(z) > Z95).mean()), float((np.abs(z) > Z998).mean())


def exceedance(m: Measure, percentile: float = 90.0) -> tuple[float, float, float]:
    """P(theta_i > c): share confidently above, confidently below, indeterminate."""
    c = float(np.percentile(m.est, percentile))
    p = 1 - st.norm.cdf((c - m.est) / m.se)
    above = float((p > 0.95).mean())
    below = float((p < 0.05).mean())
    return c, above, below


def tiers(m: Measure) -> int:
    """Groups surviving a Bonferroni-controlled sequential partition.

    Walk units in descending order, opening a new tier only where the next unit
    sits significantly below the current tier's leader. Conservative by
    construction; the result is the number of distinctions the data support.
    """
    order = np.argsort(-m.est)
    est, se = m.est[order], m.se[order]
    z_crit = float(st.norm.ppf(1 - (0.05 / max(m.n - 1, 1)) / 2))
    count, leader = 1, 0
    for i in range(1, m.n):
        if (est[leader] - est[i]) / np.hypot(se[leader], se[i]) > z_crit:
            count += 1
            leader = i
    return count


def _acs_covariates(session: requests.Session, key: str) -> pd.DataFrame:
    """County median age, median income, poverty rate and share 65+ from ACS 5-year."""
    variables = ["B01002_001E", "B19013_001E", "B17001_002E", "B17001_001E",
                 "B01001_001E", "B01001_020E", "B01001_044E"]
    rows = session.get(
        ACS_URL, params={"get": ",".join(variables), "for": "county:*", "key": key},
        timeout=120,
    ).json()
    acs = pd.DataFrame(rows[1:], columns=rows[0])
    for column in variables:
        acs[column] = pd.to_numeric(acs[column], errors="coerce")
        # Census annotates unavailable values with large negative jam codes.
        # They are annotations, not data, and must not reach a regression.
        acs.loc[acs[column] < 0, column] = np.nan
    acs["fips"] = acs["state"] + acs["county"]
    acs["poverty"] = 100 * acs.B17001_002E / acs.B17001_001E
    acs["pct65"] = 100 * (acs.B01001_020E + acs.B01001_044E) / acs.B01001_001E
    return acs.rename(columns={"B01002_001E": "med_age", "B19013_001E": "med_inc"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measures", nargs="+", default=list(DEFAULT_MEASURES))
    parser.add_argument("--skip-acs", action="store_true", help="omit section H")
    args = parser.parse_args(argv)

    session = requests.Session()
    session.headers["User-Agent"] = "telosyn-notebooks/1.0"
    data = fetch(tuple(args.measures), session=session)

    print(f"CDC PLACES county release {PLACES_COUNTY_2025} (2025), crude prevalence\n")

    print("A. SIGNAL-TO-NOISE")
    print(f"   {'measure':11} {'n':>5} {'between-SD':>11} {'med CI width':>13} {'ratio':>7} {'max asym':>9}")
    for m in data.values():
        width = float(np.median(m.hi - m.lo))
        sd = float(m.est.std(ddof=1))
        asym = float(np.max(np.abs((m.hi - m.est) - (m.est - m.lo))))
        print(f"   {m.name:11} {m.n:5} {sd:11.2f} {width:13.2f} {width / sd:7.2f} {asym:9.2f}")
    print("   ratio > 1: one county's uncertainty exceeds the spread across all counties\n")

    print("B. RELIABILITY   lambda = tau^2 / (tau^2 + se^2)")
    print(f"   {'measure':11} {'tau^2':>8} {'mean se^2':>10} {'pooled':>8} {'>=0.7':>8} {'>=0.9':>8}")
    for m in data.values():
        t2 = tau_squared(m)
        lam = reliability(m, t2)
        mean_s2 = float((m.se**2).mean())
        print(f"   {m.name:11} {t2:8.3f} {mean_s2:10.3f} {t2 / (t2 + mean_s2):8.3f}"
              f" {100 * (lam >= 0.7).mean():7.1f}% {100 * (lam >= 0.9).mean():7.1f}%")
    print("   0.7 is the conventional floor for publishing unit-level comparisons\n")

    print("C. RANK IDENTIFIABILITY   (§7.1 test, unchanged)")
    for m in data.values():
        d = determined_ranks(m)
        print(f"   {m.name:11} {d:>5} of {m.n} counties have a determined rank ({100 * d / m.n:.2f}%)")
    print()

    print("D. MONTE CARLO RANK INTERVALS")
    for m in data.values():
        lo_r, hi_r = rank_intervals(m)
        top = int(np.argmax(m.est))
        width = float(np.median(hi_r - lo_r))
        print(f"   {m.name:11} median 95% width {width:6.0f} of {m.n}"
              f" ({100 * width / m.n:3.0f}% of the list);"
              f" top county's own interval [{lo_r[top]:.0f}, {hi_r[top]:.0f}]")
    print()

    print("E. FUNNEL   (detection instead of ordering)")
    print(f"   {'measure':11} {'benchmark':>10} {'outside 95%':>12} {'outside 99.8%':>14}")
    for m in data.values():
        theta0, o95, o998 = funnel(m)
        print(f"   {m.name:11} {theta0:10.2f} {100 * o95:11.1f}% {100 * o998:13.1f}%")
    print()

    print("F. EXCEEDANCE   P(theta > 90th percentile of estimates)")
    print(f"   {'measure':11} {'c':>7} {'confidently above':>18} {'confidently below':>18} {'indeterminate':>14}")
    for m in data.values():
        c, above, below = exceedance(m)
        print(f"   {m.name:11} {c:7.1f} {100 * above:17.1f}% {100 * below:17.1f}%"
              f" {100 * (1 - above - below):13.1f}%")
    print("   the negative statement is far better supported than the positive one\n")

    print("G. SEPARABLE TIERS   (Bonferroni sequential partition)")
    for m in data.values():
        print(f"   {m.name:11} {tiers(m)} tiers across {m.n} counties")
    print()

    print("H. SIZE ARTIFACT   (Gelman & Price)")
    labels = ["Q1 smallest", "Q2", "Q3", "Q4 largest"]
    for m in data.values():
        ok = np.isfinite(m.pop) & (m.pop > 0)
        rho = float(st.spearmanr(np.log(m.pop[ok]), m.se[ok]).statistic)
        quartile = np.asarray(pd.qcut(m.pop[ok], 4, labels=labels))
        spread = [float(m.est[ok][quartile == lab].std(ddof=1)) for lab in labels]
        means = [float(m.est[ok][quartile == lab].mean()) for lab in labels]
        print(f"   {m.name:11} Spearman(log pop, se) = {rho:+.3f}"
              f" | SD by size quartile {spread[0]:.2f} -> {spread[3]:.2f}"
              f" | mean {means[0]:.2f} -> {means[3]:.2f}")
    print("   SD widening toward small units is the artifact signature; a mean")
    print("   gradient may be substantive and is not evidence of one\n")

    if args.skip_acs:
        return 0

    print("I. CIRCULARITY   how much survives without PLACES at all?")
    try:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
        from krl_tutorials_data.sources import load_key

        key = load_key("CENSUS_API_KEY")
    except Exception as exc:  # noqa: BLE001 - reported, never silently skipped
        print(f"   SKIPPED: {type(exc).__name__}: {exc}")
        return 0

    acs = _acs_covariates(session, key)
    for m in data.values():
        frame = (
            pd.DataFrame({"fips": m.fips, "est": m.est})
            .merge(acs[["fips", "med_age", "med_inc", "poverty", "pct65"]], on="fips")
            .dropna()
        )
        frame = frame[frame.med_inc > 0]
        design = np.column_stack([
            np.ones(len(frame)), frame.med_age, np.log(frame.med_inc),
            frame.poverty, frame.pct65,
        ])
        y = frame.est.to_numpy()
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        pred = design @ beta
        r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        shared = len(set(np.argsort(-y)[:100]) & set(np.argsort(-pred)[:100]))
        print(f"   {m.name:11} R^2 {r2:.3f} | Spearman(ranks) "
              f"{st.spearmanr(y, pred).statistic:+.3f} | top-100 overlap {shared}/100")
    print("   high overlap bounds the NEW information in the ranking; it is not")
    print("   evidence about which covariates the model used, nor about causation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
