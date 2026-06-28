"""Re-fetch vehicle_types for the audited systems and archive form factors.

Feed-intrinsic A1: a GBFS v3 feed declares car-sharing through
``vehicle_types.form_factor == "car"``, not through any operator name. This sweep
fetches vehicle_types for every system that was audited (published
station_information) and freezes the per-system form-factor set, so the certain
World A1 count is reproducible from the archive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import gbfs_toolkit as gb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unified_audit as ua  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG_CSV = ROOT / "experiments/e2_threshold_sensitivity/mobilitydata_systems.csv"
MANIFEST = ROOT / "experiments/unified_audit/world_fetch_manifest.csv"
OUT = ROOT / "experiments/unified_audit/world_vehicle_types.csv"


def main() -> None:
    catalog = ua.load_catalog(str(CATALOG_CSV))
    audited = pd.read_csv(MANIFEST)
    ids = audited.loc[audited["status"].astype(str).str.startswith("ok"), "system_id"].astype(str).tolist()
    done = set()
    rows: list[dict] = []
    if OUT.exists():
        prev = pd.read_csv(OUT)
        rows = prev.to_dict("records")
        done = set(prev["system_id"].astype(str))
    todo = [s for s in ids if s not in done]
    country = dict(zip(catalog.system_id.astype(str), catalog.country_code))
    print(f"[vt] {len(todo)} systems to fetch ({len(done)} done)", flush=True)

    batch = 40
    for i in range(0, len(todo), batch):
        feeds = gb.fetch_multiple(todo[i : i + batch], catalog=catalog, max_workers=8)
        for sid, feed in feeds.items():
            row = {"system_id": sid, "country_code": country.get(sid), "form_factors": None, "status": None}
            if isinstance(feed, Exception):
                row["status"] = f"unreachable:{type(feed).__name__}"
            else:
                try:
                    vt = feed.vehicle_types()
                    if vt is not None and len(vt) and "form_factor" in vt.columns:
                        ff = sorted({str(x) for x in vt["form_factor"].dropna()})
                        row["form_factors"] = "|".join(ff)
                        row["status"] = "ok"
                    else:
                        row["status"] = "no_vehicle_types"
                except Exception as exc:  # noqa: BLE001
                    row["status"] = f"error:{type(exc).__name__}"
            rows.append(row)
        pd.DataFrame(rows).to_csv(OUT, index=False)
        print(f"[vt] {min(i + batch, len(todo))}/{len(todo)}", flush=True)

    df = pd.DataFrame(rows)
    df["ff"] = df["form_factors"].fillna("").apply(lambda s: set(s.split("|")) if s else set())
    df["is_carsharing"] = df["ff"].apply(lambda f: ("car" in f) and ("bicycle" not in f))
    n_vt = (df["status"] == "ok").sum()
    a1 = int(df["is_carsharing"].sum())
    a1_fr = int(df[(df.country_code == "FR")]["is_carsharing"].sum())
    print(f"[vt] vehicle_types ok: {n_vt}/{len(df)}", flush=True)
    print(f"[vt] CERTAIN World A1 (form_factor=car, feed-intrinsic): {a1}  (FR among them: {a1_fr})", flush=True)


if __name__ == "__main__":
    main()
