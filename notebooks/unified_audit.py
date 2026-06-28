"""Single, library-based GBFS semantic audit pipeline (A1-A7).

ONE rule set, applied identically to France and to the world, so the two
columns of the paper's taxonomy table are finally comparable. The audit is the
published library function ``gbfs_toolkit.audit_static`` (no operator-name
heuristics, no separate snapshot pipeline):

- France : the released station-level catalogue (offline, exact).
- World  : a live re-fetch of the MobilityData catalogue via the same library,
           audited with the same function and the same parameters.

This replaces the paper's two-pipeline situation (parquet ``enrich()`` for FR
versus an operator-name snapshot for the world) that made the FR and Global
columns non-comparable (e.g. A3 = 41 for FR under the broad post-audit
definition versus 33/4 for the world under the strict snapshot detector).
"""
from __future__ import annotations

import re

import pandas as pd

import gbfs_toolkit as gb
from gbfs_toolkit.io.catalog import _normalize_columns

# Carsharing operator keyword set, pinned verbatim from the audit snapshot
# (scripts/audit_live_systems.py / verify_snapshot.py). A1 is not feed-intrinsic:
# a GBFS feed does not self-declare carsharing, so the catalogue identifies it
# from the operator name. Applying this set identically to FR and World makes A1
# comparable, and the keyword list is fixed so the step is reproducible.
_CARSHARE = re.compile(
    r"\b(citiz|carsharing|car.?sharing|car2go|zipcar|stadtmobil|flinkster|"
    r"edrive|car.?ship|teilauto|quickrent|2em|mybuxi|conficars|getaround|"
    r"sixt.?share|miles|cambio|ford.?carsharing|ubeeqo|virtuo|tribu|invers|"
    r"deer)\b", re.I)

# Catalogue parameters, identical for both corpora.
A4_SIGMA = 3.0       # A4 robust-sigma threshold
A7_SCOPE = "all"     # A7 = system-wide NaN-capacity share (catalogue definition)
N_MIN = 20           # minimum stations for the A6/A7 base
CLASSES = [f"A{i}" for i in range(1, 8)]
REQUIRED = ["system_id", "station_id", "station_type", "capacity", "lat", "lon"]


def apply_operator_types(stations: pd.DataFrame, name_by_system: dict) -> pd.DataFrame:
    """Force ``station_type='carsharing'`` for systems whose operator name matches
    the carsharing keyword set (the catalogue's S1 step). Makes A1 comparable
    between corpora; reproducible because the keyword set is pinned.
    """
    out = stations.copy()
    names = out["system_id"].astype(str).map(name_by_system).fillna("")
    is_car = names.apply(lambda s: bool(_CARSHARE.search(s)))
    out.loc[is_car, "station_type"] = "carsharing"
    return out


def audit_frame(stations: pd.DataFrame) -> pd.DataFrame:
    """Run the single A1-A7 audit on a canonical station frame."""
    missing = [c for c in REQUIRED if c not in stations.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    return gb.audit_static(stations[REQUIRED].copy(), a7_scope=A7_SCOPE, a4_sigma=A4_SIGMA)


def system_flags(verdict: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-station flags to per-system (flagged iff any station flagged)."""
    g = verdict.groupby("system_id")[CLASSES].max().astype(int)
    g["n_stations"] = verdict.groupby("system_id").size()
    return g


def counts(sysflags: pd.DataFrame) -> dict:
    """System-level count per class."""
    return {c: int(sysflags[c].sum()) for c in CLASSES}


# --------------------------------------------------------------------------
# France: offline, exact, from the released parquet.
# --------------------------------------------------------------------------
def audit_france(parquet_path: str) -> pd.DataFrame:
    """Audit the released French catalogue with the single library pipeline."""
    df = pd.read_parquet(parquet_path)
    return audit_frame(df)


# --------------------------------------------------------------------------
# World: live re-fetch via the same library, same audit.
# --------------------------------------------------------------------------
def load_catalog(csv_path: str) -> pd.DataFrame:
    """Load the MobilityData systems list and expose a resolvable discovery URL.

    The plain ``url`` column (the operator website) is dropped so the resolver
    falls back to the GBFS auto-discovery endpoint rather than the homepage.
    """
    cat = _normalize_columns(pd.read_csv(csv_path))
    cat = cat.drop(columns=[c for c in ["url"] if c in cat.columns])
    disc = [c for c in cat.columns if "auto" in c and "discovery" in c]
    if disc:
        cat = cat.rename(columns={disc[0]: "auto_discovery_url"})
    return cat


def fetch_stations(system_ids, catalog: pd.DataFrame, *, max_workers: int = 8):
    """Fetch station_information for many systems; return (frame, per-system status)."""
    feeds = gb.fetch_multiple(list(system_ids), catalog=catalog, max_workers=max_workers)
    rows, status = [], {}
    for sid, feed in feeds.items():
        if isinstance(feed, Exception):
            status[sid] = f"unreachable: {type(feed).__name__}"
            continue
        try:
            si = feed.station_information()
        except Exception as exc:  # noqa: BLE001  (any feed-shape failure is a drop)
            status[sid] = f"no station_information: {type(exc).__name__}"
            continue
        if si is None or len(si) == 0:
            status[sid] = "empty station_information"
            continue
        if not set(REQUIRED).issubset(si.columns):
            status[sid] = "missing required columns"
            continue
        rows.append(si[REQUIRED])
        status[sid] = f"ok: {len(si)} stations"
    frame = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=REQUIRED)
    return frame, status


def audit_world(system_ids, catalog: pd.DataFrame, *, max_workers: int = 8):
    """Fetch and audit many systems with the single pipeline; return (verdict, status, frame)."""
    frame, status = fetch_stations(system_ids, catalog, max_workers=max_workers)
    verdict = audit_frame(frame) if len(frame) else pd.DataFrame(columns=["system_id", *CLASSES])
    return verdict, status, frame
