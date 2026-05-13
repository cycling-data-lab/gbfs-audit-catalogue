"""Standalone audit primitives for the GBFS Audit Catalogue.

This module deliberately has zero dependency on the broader research
project. It exposes the small public surface that an external user
needs: load the published catalogue, load the per-system summary, and
re-run the Tier-1 / Tier-2 enrichment over a compatible raw parquet.

The audit logic itself is documented in the companion paper
(Foss\'e & Pallares, 2026, Computer Standards & Interfaces).

Anomaly granularity
-------------------
- A1 / A3 / A4 are *row-level* flags (this particular station is the
  problem).
- A2 / A5 / A6 / A7 are *system-level* flags (every row of a flagged
  system carries True). A2/A6/A7 require at least 20 stations in the
  system before the threshold is evaluated, to keep the audit verdict
  statistically meaningful on small fleets.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE_FILE = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"
SUMMARY_FILE = REPO_ROOT / "catalogue" / "stations_gold_standard_audit_summary.csv"
ZENODO_PARQUET_URL = (
    "https://zenodo.org/records/20125460/files/"
    "stations_gold_standard_final.parquet"
)

# Tunables (exposed as module-level constants so tests and downstream
# consumers can reference the exact thresholds documented in the paper).
A2_MIN_STATIONS = 20
A4_MIN_STATIONS = 5
A4_SIGMA = 3.0
A4_MIN_THRESHOLD_M = 1_000.0
A5_BBOX_MAX_KM2 = 50_000.0
A6_RATE_THRESHOLD = 0.01
A6_MIN_STATIONS = 20
A7_RATE_THRESHOLD = 0.50
A7_MIN_STATIONS = 20

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
        df = pd.read_parquet(CATALOGUE_FILE)
    else:
        df = pd.read_parquet(ZENODO_PARQUET_URL)

    # Streamlit / pyarrow round-trip stability : convert pandas nullable
    # extension dtypes (``Float64`` / ``Int64`` / etc.) back to the
    # equivalent numpy dtypes. The audit columns ``capacity_raw`` and
    # ``capacity_audited`` are intentionally NaN-friendly, and float64
    # carries NaN natively without extension-dtype overhead.
    for col in df.columns:
        s = df[col]
        dtype_name = str(s.dtype)
        if dtype_name == "Float64":
            df[col] = s.astype("float64")
        elif dtype_name == "Int64":
            df[col] = s.astype("float64")  # int + NaN -> float
        elif dtype_name == "boolean":
            df[col] = s.astype("bool")
    return df


def load_summary() -> pd.DataFrame:
    """Load the per-system audit summary (one row per audited system)."""
    return pd.read_csv(SUMMARY_FILE)


# ---------------------------------------------------------------------------
# Operator normalisation
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


# ---------------------------------------------------------------------------
# Geodesy
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0


def _project_meters(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Equirectangular projection to local metres around the dataset mean.

    Accurate enough for the sub-100 km neighbourhood queries used by the
    audit. For continental-scale queries the caller should switch to a
    proper haversine distance.
    """
    lat_r = np.deg2rad(np.asarray(lat, dtype="float64"))
    lon_r = np.deg2rad(np.asarray(lon, dtype="float64"))
    if lat_r.size == 0:
        return np.empty((0, 2), dtype="float64")
    mean_lat = float(np.nanmean(lat_r))
    x = _EARTH_RADIUS_M * lon_r * np.cos(mean_lat)
    y = _EARTH_RADIUS_M * lat_r
    return np.column_stack([x, y])


# ---------------------------------------------------------------------------
# Tier-1 : audit visibility flags (A1..A7)
# ---------------------------------------------------------------------------


def _flag_a2(out: pd.DataFrame) -> pd.Series:
    """A2 : placeholder capacity (constant non-zero across the system).

    A2 is only evaluated on the docked-bike subset of each system. On a
    free-floating system the capacity field is structurally meaningless
    (already captured by A3), so duplicating the verdict via A2 would
    inflate the audit counts the paper reports separately for A2 and A3.
    """
    docked = out[out["station_type"] == "docked_bike"]
    sys_caps = (
        docked.dropna(subset=["capacity"])
              .groupby("system_id")["capacity"]
              .agg(["nunique", "median", "size"])
    )
    flagged = set(sys_caps.index[
        (sys_caps["nunique"] == 1)
        & (sys_caps["median"] > 0)
        & (sys_caps["size"] >= A2_MIN_STATIONS)
    ])
    return out["system_id"].isin(flagged)


def _flag_a4(out: pd.DataFrame, projected: np.ndarray) -> np.ndarray:
    """A4 : geospatial outliers detected from nearest-neighbour distance.

    For each system, compute the distance from every station to its
    nearest same-system neighbour, then apply a robust 3-$\\sigma$
    rule (median + 3 $\\times$ MAD-rescaled scale) on that one-dimensional
    distribution. A station is flagged A4 if its nearest neighbour is
    farther than the system-specific threshold, with a 1 km floor.

    This replaces the previous distance-to-centroid construction,
    which over-flagged nationwide multi-modal deployments (e.g.
    Deutsche Bahn's Call a Bike, where 37.8\\% of stations were
    flagged as outliers relative to a single centroid that lies
    nowhere on the actual network). The nearest-neighbour metric is
    intrinsic to each station's local cluster rather than to the
    geographically-arbitrary centroid, so it works on both unimodal
    and multi-modal systems without recalibration.
    """
    from scipy.spatial import cKDTree

    n = len(out)
    flag = np.zeros(n, dtype=bool)
    if n == 0:
        return flag
    sys_codes, _ = pd.factorize(out["system_id"].values)
    for code in np.unique(sys_codes):
        idx = np.where(sys_codes == code)[0]
        if len(idx) < A4_MIN_STATIONS:
            continue
        pts = projected[idx]
        if not np.all(np.isfinite(pts)):
            finite = np.isfinite(pts).all(axis=1)
            if finite.sum() < A4_MIN_STATIONS:
                continue
            idx_f = idx[finite]
            pts = pts[finite]
        else:
            idx_f = idx
        tree = cKDTree(pts)
        dists, _ = tree.query(pts, k=2)  # self + nearest
        nn_dist = dists[:, 1]
        nn_median = float(np.median(nn_dist))
        mad = float(np.median(np.abs(nn_dist - nn_median)))
        sigma_robust = 1.4826 * mad
        if sigma_robust > 0.0:
            # Standard robust-3-sigma envelope on the nearest-neighbour
            # distribution.
            threshold = max(
                nn_median + A4_SIGMA * sigma_robust, A4_MIN_THRESHOLD_M
            )
        else:
            # Degenerate scale (all neighbours equidistant, e.g. a
            # regular grid): fall back to a multiplicative criterion
            # so genuine outliers still flag.
            threshold = max(10.0 * nn_median, A4_MIN_THRESHOLD_M)
        flag[idx_f[nn_dist > threshold]] = True
    return flag


def _flag_a5(out: pd.DataFrame, projected: np.ndarray) -> np.ndarray:
    """A5 : out-of-perimeter coverage (system bounding box > threshold).

    The "out-of-jurisdiction" half of the paper's A5 signature requires
    an administrative polygon (IGN BD TOPO) that is not bundled with
    this minimal package ; downstream pipelines that have access to a
    jurisdiction layer can OR the resulting mask with this function's
    output.
    """
    n = len(out)
    flag = np.zeros(n, dtype=bool)
    if n == 0:
        return flag
    sys_codes, _ = pd.factorize(out["system_id"].values)
    for code in np.unique(sys_codes):
        idx = np.where(sys_codes == code)[0]
        if len(idx) < 2:
            continue
        pts = projected[idx]
        if not np.isfinite(pts).all():
            pts = pts[np.isfinite(pts).all(axis=1)]
            if len(pts) < 2:
                continue
        width_m = pts[:, 0].max() - pts[:, 0].min()
        height_m = pts[:, 1].max() - pts[:, 1].min()
        area_km2 = (width_m * height_m) / 1e6
        if area_km2 > A5_BBOX_MAX_KM2:
            flag[idx] = True
    return flag


def _flag_a6(out: pd.DataFrame) -> pd.Series:
    """A6 : ≥1% of docked-bike stations declare capacity = 0."""
    is_zero_dock = (out["capacity"].fillna(-1) == 0) & (
        out["station_type"] == "docked_bike"
    )
    sys_rate = is_zero_dock.groupby(out["system_id"]).mean()
    sys_size = out.groupby("system_id").size()
    flagged = set(sys_rate.index[
        (sys_rate >= A6_RATE_THRESHOLD) & (sys_size >= A6_MIN_STATIONS)
    ])
    return out["system_id"].isin(flagged)


def _flag_a7(out: pd.DataFrame) -> pd.Series:
    """A7 : ≥50% of a system's stations declare capacity = NaN."""
    is_nan = out["capacity"].isna()
    sys_rate = is_nan.groupby(out["system_id"]).mean()
    sys_size = out.groupby("system_id").size()
    flagged = set(sys_rate.index[
        (sys_rate >= A7_RATE_THRESHOLD) & (sys_size >= A7_MIN_STATIONS)
    ])
    return out["system_id"].isin(flagged)


def _audit_confidence(row: pd.Series) -> str:
    flags = [bool(row[f"flag_A{i}"]) for i in range(1, 8)]
    n = sum(flags)
    if n == 0:
        return "high"
    if n == 1 and (row["flag_A3"] or row["flag_A7"]):
        return "medium"
    return "low"


def _compute_tier1(
    df: pd.DataFrame, projected: Optional[np.ndarray] = None
) -> pd.DataFrame:
    """Tier-1 audit visibility columns (11 new fields)."""
    out = df.copy()
    if projected is None:
        projected = _project_meters(
            out["lat"].to_numpy(dtype="float64"),
            out["lon"].to_numpy(dtype="float64"),
        )

    out["capacity_raw"] = out["capacity"].astype("Float64")
    out["capacity_audited"] = (
        out["capacity"]
        .where(out["station_type"] == "docked_bike", np.nan)
        .astype("Float64")
    )

    out["flag_A1"] = out["station_type"] == "carsharing"
    out["flag_A2"] = _flag_a2(out)
    out["flag_A3"] = out["station_type"] == "free_floating"
    out["flag_A4"] = _flag_a4(out, projected)
    out["flag_A5"] = _flag_a5(out, projected)
    out["flag_A6"] = _flag_a6(out)
    out["flag_A7"] = _flag_a7(out)

    out["operator_name"] = [
        detect_operator(sid, sname)
        for sid, sname in zip(out.get("system_id", []), out.get("system_name", []))
    ]
    out["audit_confidence"] = out.apply(_audit_confidence, axis=1)
    return out


# ---------------------------------------------------------------------------
# Tier-2 : network geometry (KD-tree based KNN)
# ---------------------------------------------------------------------------


def _compute_tier2(
    df: pd.DataFrame, projected: Optional[np.ndarray] = None
) -> pd.DataFrame:
    """Tier-2 network and density columns (5 new fields).

    Uses ``scipy.spatial.cKDTree`` so the audit runs in O(n log n) on
    the global catalogue rather than the O(n^2) chunked dense matrix of
    the v1.0 release.
    """
    from scipy.spatial import cKDTree

    out = df.copy()
    if projected is None:
        projected = _project_meters(
            out["lat"].to_numpy(dtype="float64"),
            out["lon"].to_numpy(dtype="float64"),
        )
    n = len(out)
    sys_codes, _ = pd.factorize(out["system_id"].values)

    dist_intra = np.full(n, np.nan)
    n500 = np.zeros(n, dtype="int64")
    n1k = np.zeros(n, dtype="int64")
    dist_inter = np.full(n, np.nan)

    finite = np.isfinite(projected).all(axis=1)

    for code in np.unique(sys_codes):
        idx = np.where(sys_codes == code)[0]
        idx = idx[finite[idx]]
        if len(idx) < 2:
            n500[idx] = 0
            n1k[idx] = 0
            continue
        sub = projected[idx]
        tree = cKDTree(sub)
        dists, _ = tree.query(sub, k=2)
        dist_intra[idx] = dists[:, 1]
        # query_ball_point with return_length includes the self-match;
        # subtract 1 to count *other* same-system neighbours within R.
        counts_500 = tree.query_ball_point(sub, 500.0, return_length=True)
        counts_1k = tree.query_ball_point(sub, 1000.0, return_length=True)
        n500[idx] = np.asarray(counts_500, dtype="int64") - 1
        n1k[idx] = np.asarray(counts_1k, dtype="int64") - 1

    # Cross-system nearest neighbour : per system, build a tree of the
    # complement and query k=1. Constant memory per iteration.
    if finite.any() and n >= 2:
        for code in np.unique(sys_codes):
            idx = np.where(sys_codes == code)[0]
            idx = idx[finite[idx]]
            other = np.where((sys_codes != code) & finite)[0]
            if len(idx) == 0 or len(other) == 0:
                continue
            tree = cKDTree(projected[other])
            d, _ = tree.query(projected[idx], k=1)
            dist_inter[idx] = d

    out["dist_to_nearest_station_m"] = dist_intra
    out["n_stations_within_500m"] = n500
    out["n_stations_within_1km"] = n1k
    out["nearest_system_dist_m"] = dist_inter
    # Disc area of radius 1 km : pi * 1^2 km^2. The column is strictly
    # proportional to ``n_stations_within_1km`` and is preserved for
    # interface compatibility with the published parquet.
    out["catchment_density_per_km2"] = out["n_stations_within_1km"] / np.pi
    return out


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Tier-1 + Tier-2 enrichment to a raw or partially audited frame.

    The input is expected to contain at least the columns
    ``system_id``, ``station_id``, ``station_type``, ``capacity``,
    ``lat`` and ``lon``. The output is the input augmented with the
    16 new columns documented in the paper's Table 7.
    """
    projected = _project_meters(
        df["lat"].to_numpy(dtype="float64"),
        df["lon"].to_numpy(dtype="float64"),
    )
    return _compute_tier2(_compute_tier1(df, projected), projected)
