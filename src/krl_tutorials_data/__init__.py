"""Real-data access layer for the KRL tutorial corpus.

There is no synthetic data generator in this package. A notebook that cannot
obtain real data raises and stops.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from .provenance import DataMode, DataProvenance
from .sources import (
    DataAccessError, MissingCredentialError, UpstreamError, ResponseShapeError,
    SchemaError, RangeError, fetch_acs, fetch_acs_wide, fetch_fred, fetch_bls, fetch_qcew, fetch_cbp, BLSRequestError,
    load_key, secrets_path,
    ACS_SENTINELS, CENSUS_GET_CEILING,
)
from .standardization import (
    StandardPopulation, StandardizationError, crude_rate,
    direct_standardized_rate, standardized_rate_estimate, standardized_rate_bounds,
    kitagawa_decomposition, KitagawaSplit,
)
from .reliability import (
    ReliabilityClass, ReliabilityError, CVThresholds, NCHS_THRESHOLDS,
    coefficient_of_variation, classify_reliability, RankInterval, rank_intervals,
    proportion_moe_is_degenerate,
)
from .connectors import (
    ConnectorUnavailableError, ConnectorContractError, BulkFilePinError,
    BulkFileSource, CONNECTOR_DISTRIBUTION, connectors_available,
    load_connector, verify_bulk_file, frame_from_bulk_file,
)
from .brackets import (
    BracketEdges, BracketError, UnidentifiedPercentileError,
    interpolated_percentile, median_from_brackets, percentile_is_identified,
    ACS_B25070_BRACKETS,
)
from .tabulation import Coverage, PartitionReport, PartitionError, check_partition
from .inequality import (
    ACS_B19001_BRACKETS, BracketScheme, lorenz_curve, gini_from_lorenz,
    gini_from_brackets,
)

__all__ = [
    "DataMode", "DataProvenance", "DataAccessError", "MissingCredentialError",
    "UpstreamError", "ResponseShapeError", "SchemaError", "RangeError",
    "fetch_acs", "fetch_acs_wide", "fetch_fred", "fetch_bls", "fetch_qcew", "fetch_cbp",
    "BLSRequestError",
    "load_key", "secrets_path",
    "ACS_SENTINELS",
    "CENSUS_GET_CEILING",
    "ACS_B19001_BRACKETS", "BracketScheme", "lorenz_curve", "gini_from_lorenz",
    "gini_from_brackets", "StandardPopulation", "StandardizationError",
    "crude_rate", "direct_standardized_rate", "standardized_rate_estimate",
    "standardized_rate_bounds",
    "kitagawa_decomposition", "KitagawaSplit", "ReliabilityClass",
    "ReliabilityError", "CVThresholds", "NCHS_THRESHOLDS",
    "coefficient_of_variation", "classify_reliability", "RankInterval",
    "rank_intervals", "proportion_moe_is_degenerate", "Coverage",
    "PartitionReport", "PartitionError", "check_partition", "BracketEdges",
    "BracketError", "UnidentifiedPercentileError", "interpolated_percentile",
    "median_from_brackets", "percentile_is_identified", "ACS_B25070_BRACKETS",
    "ConnectorUnavailableError", "ConnectorContractError", "BulkFilePinError",
    "BulkFileSource", "CONNECTOR_DISTRIBUTION", "connectors_available",
    "load_connector", "verify_bulk_file", "frame_from_bulk_file",
]
