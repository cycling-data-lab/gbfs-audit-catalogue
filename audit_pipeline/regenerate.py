"""Regenerate the released artefacts (parquet + summary CSV) from the
audit pipeline.

Usage
-----
    python -m audit_pipeline.regenerate

The script is idempotent: re-running it on a parquet whose audit
columns are already populated yields the same output (modulo the
A4/A5 placeholder fix introduced in v1.0.1 of the pipeline).

Inputs / outputs
----------------
- Reads    catalogue/stations_gold_standard_final.parquet
- Writes   catalogue/stations_gold_standard_final.parquet
- Writes   catalogue/stations_gold_standard_audit_summary.csv

The 16 audit-pipeline columns produced by ``enrich()`` are dropped
from the input before re-enrichment so the run is deterministic
regardless of the previous state of those columns.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from audit_pipeline.core import (
    CATALOGUE_FILE,
    SUMMARY_FILE,
    enrich,
)

ENRICH_OUTPUTS: list[str] = [
    "capacity_raw",
    "capacity_audited",
    "flag_A1",
    "flag_A2",
    "flag_A3",
    "flag_A4",
    "flag_A5",
    "flag_A6",
    "flag_A7",
    "operator_name",
    "audit_confidence",
    "dist_to_nearest_station_m",
    "n_stations_within_500m",
    "n_stations_within_1km",
    "nearest_system_dist_m",
    "catchment_density_per_km2",
]


def regenerate_parquet(
    src: Path = CATALOGUE_FILE, dst: Path | None = None
) -> pd.DataFrame:
    """Re-run the audit pipeline over a previously released parquet."""
    dst = dst or src
    df = pd.read_parquet(src)
    raw = df.drop(columns=[c for c in ENRICH_OUTPUTS if c in df.columns])
    out = enrich(raw)
    out.to_parquet(dst, index=False)
    return out


def regenerate_summary(
    df: pd.DataFrame, dst: Path = SUMMARY_FILE
) -> pd.DataFrame:
    """Rebuild the per-system summary CSV from an enriched catalogue."""
    agg = {
        "n_stations": ("uid", "size"),
        "operator": ("operator_name", "first"),
    }
    for k in range(1, 8):
        agg[f"flag_A{k}"] = (f"flag_A{k}", "sum")
    for level in ("high", "medium", "low"):
        agg[f"n_{level}_confidence"] = (
            "audit_confidence",
            lambda s, lv=level: int((s == lv).sum()),
        )
    summary = df.groupby("system_id", as_index=False).agg(**agg)
    summary.to_csv(dst, index=False)
    return summary


def main() -> None:
    out = regenerate_parquet()
    summary = regenerate_summary(out)
    print(f"Parquet regenerated: {len(out):,} rows x {len(out.columns)} cols")
    print(f"Summary regenerated: {len(summary):,} systems")
    print()
    print("Per-class flag totals (stations / systems flagged):")
    for k in range(1, 8):
        n_st = int(out[f"flag_A{k}"].sum())
        n_sys = out.loc[out[f"flag_A{k}"], "system_id"].nunique()
        print(f"  A{k}: {n_st:>6} stations / {n_sys:>3} systems")
    print()
    print("Audit confidence distribution:")
    print(out["audit_confidence"].value_counts().to_string())


if __name__ == "__main__":
    main()
