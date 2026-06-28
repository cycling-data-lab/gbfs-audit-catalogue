"""Reproducible unified A1-A7 audit of France + the world, one pipeline.

Scientific contract
-------------------
1. FETCH & ARCHIVE (live, once): station_information for every MobilityData
   system is fetched and frozen to a Parquet lake, with a per-system provenance
   row (UTC timestamp, SHA-256 of the canonical frame, station count, status)
   and a cryptographic ``generate_manifest`` over the lake. This is the only
   non-deterministic step; its output is a frozen, citable artifact.
2. AUDIT (deterministic, from the archive): the single library function
   ``gbfs_toolkit.audit_static`` is applied identically to the French catalogue
   and to the archived world feeds. Re-running this stage on the archive yields
   byte-identical verdicts.
3. AGGREGATE (deterministic, seeded): system-level counts per class for FR and
   World, with cluster-bootstrap 95% CIs at a pinned seed.

The system inventory is the frozen MobilityData list shipped with the repo
(1,509 systems), so the corpus is fixed and reproducible.

Usage
-----
    python run_unified_audit.py            # full sweep, resumable
    python run_unified_audit.py --audit-only   # skip fetch, audit the archive

Resumability: a system whose Parquet already exists in the lake is skipped, so
the fetch stage can be interrupted and restarted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import gbfs_toolkit as gb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unified_audit as ua  # noqa: E402  (single-pipeline helpers)

# --------------------------------------------------------------------------
# Pinned, reproducible parameters.
# --------------------------------------------------------------------------
SEED = 42
A4_SIGMA = ua.A4_SIGMA
A7_SCOPE = ua.A7_SCOPE
N_MIN = ua.N_MIN
BOOTSTRAP_N = 10_000

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG_CSV = ROOT / "experiments/e2_threshold_sensitivity/mobilitydata_systems.csv"
FR_PARQUET = ROOT / "catalogue/stations_gold_standard_final.parquet"
OUT = ROOT / "experiments/unified_audit"
LAKE = OUT / "raw_world"
FETCH_MANIFEST = OUT / "world_fetch_manifest.csv"
VERDICT = OUT / "unified_verdict.parquet"
SUMMARY = OUT / "unified_summary.csv"
RESULTS = OUT / "RESULTS.json"


def _safe(sid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(sid))


def _sha256(frame: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(frame, index=True).values.tobytes()
    ).hexdigest()


# ==========================================================================
# Stage 1: fetch & archive (live, resumable).
# ==========================================================================
def fetch_and_archive(catalog: pd.DataFrame, batch: int = 40) -> None:
    LAKE.mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in LAKE.glob("*.parquet")}
    manifest = (
        pd.read_csv(FETCH_MANIFEST).to_dict("records")
        if FETCH_MANIFEST.exists()
        else []
    )
    seen = {r["system_id_safe"] for r in manifest}
    todo = [s for s in catalog["system_id"].dropna().astype(str)
            if _safe(s) not in done and _safe(s) not in seen]
    print(f"[fetch] {len(todo)} systems to fetch, {len(done)} already archived", flush=True)

    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        feeds = gb.fetch_multiple(chunk, catalog=catalog, max_workers=8)
        for sid, feed in feeds.items():
            safe = _safe(sid)
            country = catalog.loc[catalog.system_id.astype(str) == sid, "country_code"]
            country = country.iloc[0] if len(country) else None
            row = {"system_id": sid, "system_id_safe": safe, "country_code": country,
                   "fetched_at": datetime.now(timezone.utc).isoformat(),
                   "status": None, "n_stations": 0, "sha256": None, "gbfs_version": None}
            if isinstance(feed, Exception):
                row["status"] = f"unreachable:{type(feed).__name__}"
            else:
                try:
                    si = feed.station_information()
                except Exception as exc:  # noqa: BLE001
                    row["status"] = f"no_station_information:{type(exc).__name__}"
                    si = None
                if si is not None and len(si) and set(ua.REQUIRED).issubset(si.columns):
                    frame = si[ua.REQUIRED].copy()
                    frame.to_parquet(LAKE / f"{safe}.parquet")
                    row.update(status="ok", n_stations=len(frame),
                               sha256=_sha256(frame),
                               gbfs_version=str(getattr(feed, "version", None)))
                elif si is not None and len(si) == 0:
                    row["status"] = "empty"
                elif si is not None:
                    row["status"] = "missing_columns"
            manifest.append(row)
        pd.DataFrame(manifest).to_csv(FETCH_MANIFEST, index=False)
        ok = sum(1 for r in manifest if r["status"] == "ok")
        print(f"[fetch] {min(i + batch, len(todo))}/{len(todo)} processed, {ok} ok", flush=True)


# ==========================================================================
# Stage 2: deterministic audit from the archive.
# ==========================================================================
def load_world_frame() -> pd.DataFrame:
    files = sorted(LAKE.glob("*.parquet"))
    frames = [pd.read_parquet(f) for f in files]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ua.REQUIRED)


def audit_corpus(stations: pd.DataFrame, corpus: str, country_of: dict) -> pd.DataFrame:
    verdict = ua.audit_frame(stations)
    verdict["corpus"] = corpus
    verdict["country"] = verdict["system_id"].map(country_of)
    return verdict


def cluster_bootstrap_ci(sysflags: pd.DataFrame, klass: str, rng) -> tuple[float, float]:
    """95% CI of the system-level flag RATE, resampling systems with replacement."""
    x = sysflags[klass].to_numpy()
    n = len(x)
    if n == 0:
        return (float("nan"), float("nan"))
    means = np.array([x[rng.integers(0, n, n)].mean() for _ in range(BOOTSTRAP_N)])
    return (round(100 * float(np.percentile(means, 2.5)), 2),
            round(100 * float(np.percentile(means, 97.5)), 2))


def aggregate(verdict: pd.DataFrame, rng) -> dict:
    out = {}
    for label, sub in (("World", verdict),
                       ("FR", verdict[verdict.country == "FR"]),
                       ("non_FR", verdict[verdict.country != "FR"])):
        sysf = ua.system_flags(sub)
        block = {}
        for k in gb.AUDIT_FLAGS:
            n_sys = int(sysf[k].sum())
            lo, hi = cluster_bootstrap_ci(sysf, k, rng)
            block[k] = {"systems_flagged": n_sys, "ci95_rate_pct": [lo, hi]}
        block["_n_systems"] = int(len(sysf))
        block["_n_stations"] = int(sysf["n_stations"].sum())
        out[label] = block
    return out


# ==========================================================================
def main(audit_only: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = ua.load_catalog(str(CATALOG_CSV))
    country_of = dict(zip(catalog.system_id.astype(str), catalog.country_code))

    if not audit_only:
        fetch_and_archive(catalog)
        try:
            man = gb.generate_manifest(str(LAKE))
            (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=2, default=str))
            print("[manifest] cryptographic manifest written", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[manifest] skipped: {exc}", flush=True)

    print("[audit] auditing France (offline parquet) + archived world ...", flush=True)
    fr_raw = pd.read_parquet(FR_PARQUET)[ua.REQUIRED]
    fr_country = {s: "FR" for s in fr_raw.system_id.astype(str).unique()}
    world_raw = load_world_frame()

    name_of = dict(zip(catalog.system_id.astype(str), catalog.get("name")))

    rng = np.random.default_rng(SEED)
    fr_v = audit_corpus(fr_raw, "FR_catalogue", fr_country)
    parts = [fr_v]
    world_aggs = {}
    if len(world_raw):
        # Two scientifically distinct audits of the same archived feeds:
        #  - feed_only   : what GBFS alone supports (A1 not feed-intrinsic -> 0).
        #  - operator    : + carsharing classification from operator name (the
        #                  catalogue's S1 step), making A1 comparable.
        world_feed = audit_corpus(world_raw, "World_feed_only", country_of)
        world_op = audit_corpus(
            ua.apply_operator_types(world_raw, name_of), "World_operator", country_of)
        parts += [world_feed, world_op]
        world_aggs = {
            "feed_only": aggregate(world_feed, np.random.default_rng(SEED)),
            "operator": aggregate(world_op, np.random.default_rng(SEED)),
        }
    verdict = pd.concat(parts, ignore_index=True)
    verdict.to_parquet(VERDICT)

    rows = []
    for variant, agg in world_aggs.items():
        for corp, block in agg.items():
            for k in gb.AUDIT_FLAGS:
                rows.append({"variant": variant, "corpus": corp, "class": k,
                             "systems_flagged": block[k]["systems_flagged"],
                             "ci95_lo": block[k]["ci95_rate_pct"][0],
                             "ci95_hi": block[k]["ci95_rate_pct"][1],
                             "n_systems": block["_n_systems"]})
    pd.DataFrame(rows).to_csv(SUMMARY, index=False)

    # France-catalogue reference counts (offline, exact).
    fr_ref = ua.counts(ua.system_flags(fr_v))

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "params": {"a4_sigma": A4_SIGMA, "a7_scope": A7_SCOPE, "n_min": N_MIN,
                   "bootstrap_n": BOOTSTRAP_N},
        "toolkit_version": getattr(gb, "__version__", "unknown"),
        "inventory_systems": int(len(catalog)),
        "france_catalogue_counts": fr_ref,
        "world_feed_only": world_aggs.get("feed_only", "not_run"),
        "world_operator": world_aggs.get("operator", "not_run"),
        "fetch_manifest": str(FETCH_MANIFEST.relative_to(ROOT)) if FETCH_MANIFEST.exists() else None,
    }
    RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print("[done] wrote:", VERDICT.name, SUMMARY.name, RESULTS.name, flush=True)
    if world_aggs:
        for variant in ("feed_only", "operator"):
            w = world_aggs[variant]["World"]
            print(variant, "World A1-A7:",
                  {k: w[k]["systems_flagged"] for k in gb.AUDIT_FLAGS}, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-only", action="store_true")
    main(audit_only=ap.parse_args().audit_only)
