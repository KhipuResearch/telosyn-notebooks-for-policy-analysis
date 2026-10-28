"""Estimators shared by the causal, appraisal and synthesis notebooks.

Pure functions over ``numpy``, ``pandas`` and ``scipy``. Nothing in this package
performs I/O, prints, plots or reads a key; every function returns data a
notebook can display. Where an estimator uses randomness it takes a required
integer ``seed`` and builds its own generator, so that inference randomness is
declared at the call and a notebook never needs ``numpy.random`` itself.

See DECISIONS/0009-expansion-architecture.md, section 3.5.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

__all__ = ["cea", "did", "discount", "iv", "matching", "meta", "rdd", "resample", "synth"]
