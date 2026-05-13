"""GBFS Audit Catalogue -- standalone audit pipeline.

Public API
----------
load_catalogue()  : pandas DataFrame of the certified 46-column catalogue
load_summary()    : per-system audit summary
enrich()          : add Tier-1 (audit visibility) + Tier-2 (network) columns
                     to any compatible raw parquet
ANOMALY_CLASSES   : dict mapping A1..A7 -> human-readable description
"""
from __future__ import annotations

from .core import (
    ANOMALY_CLASSES,
    enrich,
    load_catalogue,
    load_summary,
)

__version__ = "1.0.0"
__all__ = [
    "ANOMALY_CLASSES",
    "enrich",
    "load_catalogue",
    "load_summary",
    "__version__",
]
