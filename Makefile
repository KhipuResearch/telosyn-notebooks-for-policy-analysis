# © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Proprietary
.PHONY: setup test gates verify-provenance readmes surface check lint

PY ?= python3

setup:            ## install the package, a kernel, and the test tools
	$(PY) -m pip install -e '.[notebooks,test]'

test:             ## the full suite; no network, no keys
	$(PY) -m pytest tests/

gates:            ## the release gates only (tests/test_gate_*.py)
	$(PY) -m pytest tests/test_gate_*.py

verify-provenance: ## replay every provenance record against its digest (needs your keys)
	$(PY) scripts/verify_provenance_reproducibility.py

readmes:          ## regenerate the derived READMEs from the notebooks, then confirm nothing drifted
	$(PY) scripts/build_project_readmes.py
	$(PY) scripts/build_data_readme.py
	$(PY) scripts/build_project_readmes.py --check
	$(PY) scripts/build_data_readme.py --check

# The name patterns are private and are not in this repository. The check reads them from
# the file that KRL_SURFACE_DENYLIST names -- your own file, exported in your shell; there
# is no default location -- and exits 2, checking nothing, if it is not set.
# CI runs `--public-rules` instead (paths, caches, headers, generic trailers).
surface:          ## refuse names, paths, trailers, tool caches and unheadered files that must not reach the public repo
	$(PY) scripts/check_public_surface.py --tree --range origin/main

check: test readmes surface  ## what CI runs

lint:             ## format and lint the package and scripts
	$(PY) -m ruff check src scripts tests
	$(PY) -m ruff format --check src scripts tests
