# © 2026 Telosyn, Inc. All rights reserved.
# Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
#
# CONFIDENTIAL AND PROPRIETARY. Unauthorized use, reproduction, or
# distribution is strictly prohibited. See LICENSE for terms.

"""
Shared pytest fixtures and configuration for KRL test suite.

This module provides common fixtures, test utilities, and configuration
for all KRL tests. Import these fixtures in your test files using:

    from conftest import *
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

import pytest


# Add src directory to Python path for imports
@pytest.fixture(scope="session", autouse=True)
def add_src_to_path():
    """Add src directory to sys.path for clean imports."""
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    yield
    if str(src_path) in sys.path:
        sys.path.remove(str(src_path))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def test_data_dir(project_root) -> Path:
    """Return the test data directory."""
    data_dir = project_root / "tests" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def test_output_dir(project_root) -> Path:
    """Return the test output directory for temporary files."""
    output_dir = project_root / "tests" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def mock_env_vars(monkeypatch) -> Dict[str, str]:
    """
    Fixture to set mock environment variables for testing.
    
    Usage:
        def test_something(mock_env_vars):
            mock_env_vars['API_KEY'] = '<any value>'  # illustrative; not a credential
            # Your test code here
    """
    env_vars = {}
    
    def set_env(key: str, value: str):
        monkeypatch.setenv(key, value)
        env_vars[key] = value
    
    # Provide helper method
    env_vars.__setitem__ = set_env
    return env_vars


@pytest.fixture
def api_credentials() -> Dict[str, str]:
    """
    Provide API credentials for testing.
    
    In CI/CD, these should come from GitHub Secrets.
    Locally, they come from environment variables.
    For unit tests, use mock values.
    """
    return {
        'census_api_key': os.getenv('CENSUS_API_KEY', 'mock_census_key'),
        'fred_api_key': os.getenv('FRED_API_KEY', 'mock_fred_key'),
        'bls_api_key': os.getenv('BLS_API_KEY', 'mock_bls_key'),
    }


@pytest.fixture
def sample_dataframe():
    """Return a sample pandas DataFrame for testing."""
    try:
        import pandas as pd
        return pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie'],
            'value': [100, 200, 300]
        })
    except ImportError:
        pytest.skip("pandas not installed")


@pytest.fixture
def temp_cache_dir(tmp_path) -> Path:
    """Return a temporary cache directory for testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that require API credentials"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )


# Test collection customization
def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to skip certain tests based on environment.
    
    - Skip integration tests if running in quick mode
    - Skip API tests if no credentials available
    """
    skip_slow = pytest.mark.skip(reason="use -m 'not slow' to skip")
    skip_api = pytest.mark.skip(reason="API credentials not available")
    
    for item in items:
        # Skip slow tests if --fast flag is used
        if "slow" in item.keywords and config.getoption("-m") == "not slow":
            item.add_marker(skip_slow)
        
        # Skip API tests if no real credentials
        if "api" in item.keywords:
            has_credentials = any([
                os.getenv('CENSUS_API_KEY'),
                os.getenv('FRED_API_KEY'),
                os.getenv('BLS_API_KEY'),
            ])
            if not has_credentials and not item.get_closest_marker("unit"):
                item.add_marker(skip_api)




# ---------------------------------------------------------------------------
# Notebook release gates - appended by the 2026-09-13 remediation.
# Feeds each gate one Notebook per file under KRL_NOTEBOOK_ROOT
# (default: projects/). Everything above this line is unchanged.
# ---------------------------------------------------------------------------
from gate_support import parametrize_notebooks as _parametrize_notebooks


def pytest_generate_tests(metafunc):
    _parametrize_notebooks(metafunc)
