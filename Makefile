# © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Proprietary
.PHONY: setup test gates verify-provenance readmes check lint

PY ?= python3

setup:            ## install the package, a kernel, and the test tools
	$(PY) -m pip install -e '.[notebooks,test]'

test:             ## the full suite; no network, no keys
	$(PY) -m pytest tests/

gates:            ## the nine release gates only
	$(PY) -m pytest tests/test_gate_*.py

verify-provenance: ## replay every provenance record against its digest (needs your keys)
	$(PY) scripts/verify_provenance_reproducibility.py

readmes:          ## regenerate the derived READMEs from the notebooks, then confirm nothing drifted
	$(PY) scripts/build_project_readmes.py
	$(PY) scripts/build_data_readme.py
	$(PY) scripts/build_project_readmes.py --check
	$(PY) scripts/build_data_readme.py --check

check: test readmes  ## what CI runs

lint:             ## format and lint the package and scripts
	$(PY) -m ruff check src scripts tests
	$(PY) -m ruff format --check src scripts tests
