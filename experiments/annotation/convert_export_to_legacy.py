"""Convert a raw annotation export (new UI schema, one row per annotation)
into per-annotator legacy Q1–Q5 CSVs consumed by ``compute_reliability.py``.

The raw export is the hosted-backend dump (Supabase/PostgreSQL) with the
columns defined in ``storage._COLUMNS`` plus ``id``/``created_at`` and the
lower-cased ``flag_a1..a7``.  The Q1–Q5 mapping below is byte-for-byte the
same as ``storage._BaseStore.export_legacy_csv`` so the conversion is a pure
re-serialisation, not a re-interpretation, of the annotators' answers.

Usage:
    python -m experiments.annotation.convert_export_to_legacy \
        --export annotations_rows.csv \
        --outdir experiments/annotation
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

_DIR = Path(__file__).resolve().parent

# --- mappings (identical to storage.export_legacy_csv) ---------------------
_Q1 = {
    "station_vls": "oui", "trottinettes": "non", "autopartage": "non",
    "aucune_infrastructure": "non", "indetermine": "indéterminé",
}
_Q2 = {
    "coherente": "oui", "placeholder": "non",
    "champ_vide": "NaN (champ vide)", "zero_suspect": "non",
    "impossible": "indéterminé",
}
_Q4 = {
    "integree_reseau": "oui", "isolee_legitime": "oui",
    "isolee_suspecte": "non", "coordonnees_erronees": "non",
}
_Q5 = {
    "legitime": "vraie station (légitime)",
    "problematique": "station problématique",
    "indetermine": "indéterminé",
    "skipped": "skipped",
}


def _parse_infra(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            out = json.loads(value)
            return out if isinstance(out, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _q3(elems: Any) -> str:
    if isinstance(elems, list):
        return "non" if (not elems or elems == ["rien_visible"]) else "oui"
    return "indéterminé"


def to_legacy(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["system_id"] = df["system_id"]
    out["station_id"] = df["station_id"]
    out["stratum"] = df["stratum"]
    out["lat"] = df["lat"]
    out["lon"] = df["lon"]
    out["Q1_is_bikeshare"] = df["ground_reality"].map(_Q1).fillna("indéterminé")
    out["Q2_capacity_physical"] = (
        df["capacity_assessment"].map(_Q2).fillna("indéterminé")
    )
    out["Q3_exists_at_coords"] = (
        df["infrastructure_elements"].apply(_parse_infra).apply(_q3)
    )
    out["Q4_within_perimeter"] = df["location_assessment"].map(_Q4).fillna("oui")
    out["Q5_verdict"] = df["verdict"].map(_Q5).fillna(df["verdict"])
    out["annotator"] = df["annotator"]
    out["notes"] = df["notes"]
    out["duration_s"] = df["duration_s"]
    out["annotated_at"] = df["created_at"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--outdir", default=str(_DIR))
    args = ap.parse_args()

    df = pd.read_csv(args.export)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for annotator, grp in df.groupby("annotator"):
        legacy = to_legacy(grp.reset_index(drop=True))
        path = outdir / f"labels_{annotator}.csv"
        legacy.to_csv(path, index=False)
        print(f"wrote {path} ({len(legacy)} rows)")


if __name__ == "__main__":
    main()
