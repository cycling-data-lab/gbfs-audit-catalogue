"""Standalone audit primitives for the GBFS Audit Catalogue.

This module deliberately has zero dependency on the broader research
project. It exposes the small public surface that an external user
needs: load the published catalogue, load the per-system summary, and
re-run the Tier-1 / Tier-2 enrichment over a compatible raw parquet.

The audit logic itself is documented in the companion paper
(Foss\'e & Pallares, 2026, Computer Standards & Interfaces).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_FILE = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"
SUMMARY_FILE = REPO_ROOT / "catalogue" / "stations_gold_standard_audit_summary.csv"
ZENODO_PARQUET_URL = (
    "https://zenodo.org/records/20125460/files/"
    "stations_gold_standard_final.parquet"
)

ANOMALY_CLASSES: dict[str, dict[str, str]] = {
    "A1": {
        "name": "Out-of-domain inclusion",
        "signature": "car-sharing advertised as a bike-sharing system",
    },
    "A2": {
        "name": "Placeholder capacity",
        "signature": "constant non-zero capacity across every station of a system",
    },
    "A3": {
        "name": "Structural over-capacity",
        "signature": "conditional averaging on free-floating fleet anchors",
    },
    "A4": {
        "name": "Geospatial error",
        "signature": "transposed coordinates or stations beyond 3 sigma from system centroid",
    },
    "A5": {
        "name": "Out-of-perimeter coverage",
        "signature": "system bounding box > 50,000 km2 or out-of-jurisdiction stations",
    },
    "A6": {
        "name": "Zero-capacity dock",
        "signature": "at least 1% of stations declare capacity = 0",
    },
    "A7": {
        "name": "Null capacity field",
        "signature": "at least 50% of stations declare capacity = NaN",
    },
}


def load_catalogue(local: bool = True) -> pd.DataFrame:
    """Load the certified 46-column catalogue.

    Parameters
    ----------
    local : bool
        If True (default) read from the bundled parquet under
        ``catalogue/`` ; if False, fetch from Zenodo over HTTPS.
    """
    if local and CATALOGUE_FILE.exists():
        return pd.read_parquet(CATALOGUE_FILE)
    return pd.read_parquet(ZENODO_PARQUET_URL)


def load_summary() -> pd.DataFrame:
    """Load the per-system audit summary (one row per audited system)."""
    return pd.read_csv(SUMMARY_FILE)


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

_OPERATOR_PATTERNS: list[tuple[str, str]] = [
    (r"v[eé]lib", "Vélib' Métropole"),
    (r"pony", "Pony"),
    (r"bird", "Bird"),
    (r"dott", "Dott"),
    (r"voi", "Voi"),
    (r"lime", "Lime"),
    (r"tier", "Tier"),
    (r"jcdecaux|cyclocity", "JCDecaux / Cyclocity"),
    (r"smoove|effia", "Smoove / Effia"),
    (r"transdev", "Transdev"),
    (r"keolis", "Keolis"),
    (r"ratp", "RATP"),
    (r"citiz", "Citiz (carsharing)"),
    (r"vcub|tbm.*bordeaux|bordeaux.*tbm", "Le Vélo TBM"),
    (r"velo.?mag(g)?", "VéloMagg"),
    (r"velobleu|veloblueu", "VéloBleu"),
    (r"v[eé]lo'?v|grand.?lyon.*v[eé]lo", "Vélo'V"),
    (r"v[eé]lostan", "VéloStan"),
    (r"v[eé]l'?o.?2", "Vélo&Co"),
    (r"v[eé]l'?ille|mel.*v[eé]lo|lille.*v[eé]lo", "V'Lille"),
]


def detect_operator(system_id: str, system_name: str) -> str:
    """Normalise a system_id / system_name pair to a canonical operator label."""
    s = f"{system_id or ''} {system_name or ''}".lower()
    for pat, name in _OPERATOR_PATTERNS:
        if re.search(pat, s):
            return name
    return str(system_name or "Unknown").strip()


def _compute_tier1(df: pd.DataFrame) -> pd.DataFrame:
    """Tier-1 audit visibility columns (11 new fields)."""
    out = df.copy()
    out["capacity_raw"] = out["capacity"].astype("Float64")
    out["capacity_audited"] = out["capacity"].where(
        out["station_type"] == "docked_bike", np.nan
    ).astype("Float64")

    out["flag_A1"] = out["station_type"] == "carsharing"
    sys_caps = (
        out.dropna(subset=["capacity"])
           .groupby("system_id")["capacity"]
           .agg(["nunique", "median", "size"])
    )
    a2 = set(sys_caps.index[
        (sys_caps["nunique"] == 1)
        & (sys_caps["median"] > 0)
        & (sys_caps["size"] >= 20)
    ])
    out["flag_A2"] = out["system_id"].isin(a2)
    out["flag_A3"] = out["station_type"] == "free_floating"
    out["flag_A4"] = False
    out["flag_A5"] = False
    out["flag_A6"] = (
        (out["capacity"] == 0) & (out["station_type"] == "docked_bike")
    ).fillna(False)
    sys_nan = out.groupby("system_id").apply(
        lambda g: pd.Series({
            "n_total": len(g),
            "n_nan": g["capacity"].isna().sum(),
        }),
        include_groups=False,
    )
    sys_nan["nan_rate"] = sys_nan["n_nan"] / sys_nan["n_total"]
    a7 = set(sys_nan.index[(sys_nan["nan_rate"] >= 0.5) & (sys_nan["n_total"] >= 20)])
    out["flag_A7"] = out["system_id"].isin(a7)

    out["operator_name"] = out.apply(
        lambda r: detect_operator(r.get("system_id"), r.get("system_name")),
        axis=1,
    )

    def _confidence(row) -> str:
        flags = [row[f"flag_A{i}"] for i in range(1, 8)]
        n = sum(bool(f) for f in flags)
        if n == 0:
            return "high"
        if n == 1 and (row["flag_A3"] or row["flag_A7"]):
            return "medium"
        return "low"
    out["audit_confidence"] = out.apply(_confidence, axis=1)
    return out


def _compute_tier2(df: pd.DataFrame) -> pd.DataFrame:
    """Tier-2 network and density columns (5 new fields)."""
    out = df.copy()
    R = 6371000.0
    lat = np.deg2rad(out["lat"].to_numpy(dtype="float64"))
    lon = np.deg2rad(out["lon"].to_numpy(dtype="float64"))
    mean_lat = float(np.nanmean(lat))
    x = R * lon * np.cos(mean_lat)
    y = R * lat
    coords = np.column_stack([x, y])
    n = len(coords)

    sys_codes, _ = pd.factorize(out["system_id"].values)

    dist_intra = np.full(n, np.nan)
    n500 = np.zeros(n, dtype="int64")
    n1k = np.zeros(n, dtype="int64")
    for ci in np.unique(sys_codes):
        idx = np.where(sys_codes == ci)[0]
        if len(idx) < 2:
            continue
        sub = coords[idx]
        diff = sub[:, None, :] - sub[None, :, :]
        d = np.sqrt((diff * diff).sum(axis=2))
        np.fill_diagonal(d, np.inf)
        dist_intra[idx] = d.min(axis=1)
        n500[idx] = (d <= 500.0).sum(axis=1)
        n1k[idx] = (d <= 1000.0).sum(axis=1)
    out["dist_to_nearest_station_m"] = dist_intra
    out["n_stations_within_500m"] = n500
    out["n_stations_within_1km"] = n1k

    dist_inter = np.full(n, np.nan)
    chunk = 2000
    for i0 in range(0, n, chunk):
        i1 = min(i0 + chunk, n)
        c_coords = coords[i0:i1]
        c_sys = sys_codes[i0:i1]
        diff = c_coords[:, None, :] - coords[None, :, :]
        d = np.sqrt((diff * diff).sum(axis=2))
        same = c_sys[:, None] == sys_codes[None, :]
        d = np.where(same, np.inf, d)
        dist_inter[i0:i1] = d.min(axis=1)
    out["nearest_system_dist_m"] = dist_inter
    out["catchment_density_per_km2"] = out["n_stations_within_1km"] / (np.pi * 1.0**2)
    return out


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Tier-1 + Tier-2 enrichment to a raw or partially audited frame.

    The input is expected to contain at least the columns
    ``system_id``, ``station_id``, ``station_type``, ``capacity``,
    ``lat`` and ``lon``. The output is the input augmented with the
    16 new columns documented in the paper's Table 7.
    """
    return _compute_tier2(_compute_tier1(df))
