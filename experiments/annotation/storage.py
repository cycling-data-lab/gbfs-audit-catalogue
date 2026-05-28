# -*- coding: utf-8 -*-
"""Persistent annotation storage — SQLite (local) or PostgreSQL (hosted).

Backend selection (``get_store()``):

- If ``ANNOTATION_DB_URL`` is set (environment variable or Streamlit
  secret) and starts with ``postgres``, a hosted PostgreSQL backend is
  used (e.g. Supabase).  Required for a shared online campaign, since
  Streamlit Cloud's filesystem is ephemeral.
- Otherwise a local SQLite file is used (``annotations.db``, or the path
  in ``ANNOTATION_DB_PATH``).  Zero-config for local development.

Both backends expose the same interface (save / get / export / import),
so the app code is identical regardless of where the data lives.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_DEFAULT_DB = Path(__file__).resolve().parent / "annotations.db"

# Column order used by every INSERT (both backends).
_COLUMNS = [
    "session_id", "annotator", "system_id", "station_id", "stratum",
    "lat", "lon",
    "ground_reality", "infrastructure_elements", "streetview_date",
    "capacity_assessment", "location_assessment",
    "verdict", "confidence", "notes",
    "duration_s", "created_at",
    "flag_A1", "flag_A2", "flag_A3", "flag_A4",
    "flag_A5", "flag_A6", "flag_A7",
]

# Postgres folds unquoted identifiers to lower-case, so flag_A1 is stored
# as flag_a1. Map back on read so downstream code keeps seeing flag_A1..A7.
_FLAG_RENAME = {f"flag_a{i}": f"flag_A{i}" for i in range(1, 8)}


# =====================================================================
# Shared base: export / import logic on top of backend primitives
# =====================================================================

class _BaseStore:
    """Backend-agnostic export/import built on the storage primitives."""

    # --- primitives implemented by subclasses ---
    def save(self, row: dict[str, Any]) -> int: raise NotImplementedError
    def get_done_keys(self, annotator: str) -> set[str]: raise NotImplementedError
    def get_annotation(self, annotator, system_id, station_id): raise NotImplementedError
    def get_all(self, annotator: str) -> pd.DataFrame: raise NotImplementedError
    def count(self, annotator: str) -> int: raise NotImplementedError
    def median_duration(self, annotator: str): raise NotImplementedError
    def close(self) -> None: ...

    # --- shared export ---
    def export_csv(self, annotator: str, path: Path) -> None:
        df = self.get_all(annotator)
        if "infrastructure_elements" in df.columns:
            df["infrastructure_elements"] = df["infrastructure_elements"].apply(
                lambda x: "|".join(x) if isinstance(x, list) else str(x),
            )
        df.to_csv(path, index=False)

    def export_legacy_csv(self, annotator: str, path: Path) -> None:
        """Q1–Q5 format compatible with ``compute_reliability.py``."""
        df = self.get_all(annotator)
        if df.empty:
            pd.DataFrame().to_csv(path, index=False)
            return

        out = pd.DataFrame()
        out["system_id"] = df["system_id"]
        out["station_id"] = df["station_id"]
        out["stratum"] = df["stratum"]
        out["lat"] = df["lat"]
        out["lon"] = df["lon"]

        q1 = {
            "station_vls": "oui", "trottinettes": "non", "autopartage": "non",
            "aucune_infrastructure": "non", "indetermine": "indéterminé",
        }
        out["Q1_is_bikeshare"] = df["ground_reality"].map(q1).fillna("indéterminé")

        q2 = {
            "coherente": "oui", "placeholder": "non",
            "champ_vide": "NaN (champ vide)", "zero_suspect": "non",
            "impossible": "indéterminé",
        }
        out["Q2_capacity_physical"] = (
            df["capacity_assessment"].map(q2).fillna("indéterminé")
        )

        def _q3(elems: Any) -> str:
            if isinstance(elems, list):
                return "non" if (not elems or elems == ["rien_visible"]) else "oui"
            return "indéterminé"

        out["Q3_exists_at_coords"] = df["infrastructure_elements"].apply(_q3)

        q4 = {
            "integree_reseau": "oui", "isolee_legitime": "oui",
            "isolee_suspecte": "non", "coordonnees_erronees": "non",
        }
        out["Q4_within_perimeter"] = df["location_assessment"].map(q4).fillna("oui")

        q5 = {
            "legitime": "vraie station (légitime)",
            "problematique": "station problématique",
            "indetermine": "indéterminé",
            "skipped": "skipped",
        }
        out["Q5_verdict"] = df["verdict"].map(q5).fillna(df["verdict"])

        out["annotator"] = df["annotator"]
        out["notes"] = df["notes"]
        out["duration_s"] = df["duration_s"]
        out["annotated_at"] = df["created_at"]
        out.to_csv(path, index=False)

    # --- shared import ---
    def import_legacy_csv(self, path: Path, session_id: str = "imported") -> int:
        """Import from a Q1–Q5 CSV.  Returns count of new rows."""
        df = pd.read_csv(path)
        n = 0
        for _, r in df.iterrows():
            ann = str(r.get("annotator", "unknown"))
            sid, stid = str(r["system_id"]), str(r["station_id"])
            if self.get_annotation(ann, sid, stid):
                continue

            q1 = str(r.get("Q1_is_bikeshare", ""))
            ground = (
                "station_vls" if q1 == "oui"
                else "aucune_infrastructure" if q1 == "non"
                else "indetermine"
            )
            q2 = str(r.get("Q2_capacity_physical", ""))
            cap = (
                "coherente" if q2 == "oui"
                else "champ_vide" if "NaN" in q2
                else "placeholder" if q2 == "non"
                else "impossible"
            )
            q4 = str(r.get("Q4_within_perimeter", ""))
            loc = "integree_reseau" if q4 == "oui" else "isolee_suspecte"

            v = str(r.get("Q5_verdict", ""))
            verdict = (
                "skipped" if "skipped" in v
                else "legitime" if ("propre" in v or "vraie station" in v
                                    or "faux positif" in v)
                else "problematique" if ("problématique" in v or "anomalie" in v)
                else "indetermine"
            )

            self.save({
                "session_id": session_id, "annotator": ann,
                "system_id": sid, "station_id": stid,
                "stratum": r.get("stratum"),
                "lat": r.get("lat"), "lon": r.get("lon"),
                "ground_reality": ground,
                "infrastructure_elements": [],
                "capacity_assessment": cap,
                "location_assessment": loc,
                "verdict": verdict, "confidence": 3,
                "notes": str(r.get("notes", "") or ""),
                "duration_s": float(r.get("duration_s", 0) or 0),
                "created_at": str(
                    r.get("annotated_at", datetime.now(timezone.utc).isoformat())
                ),
            })
            n += 1
        return n


# =====================================================================
# SQLite backend (local default)
# =====================================================================

_SQLITE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS annotations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id              TEXT    NOT NULL,
    annotator               TEXT    NOT NULL,
    system_id               TEXT    NOT NULL,
    station_id              TEXT    NOT NULL,
    stratum                 TEXT,
    lat                     REAL,
    lon                     REAL,
    ground_reality          TEXT,
    infrastructure_elements TEXT,
    streetview_date         TEXT,
    capacity_assessment     TEXT,
    location_assessment     TEXT,
    verdict                 TEXT    NOT NULL,
    confidence              INTEGER NOT NULL DEFAULT 3,
    notes                   TEXT,
    duration_s              REAL,
    created_at              TEXT    NOT NULL,
    flag_A1 INTEGER DEFAULT 0, flag_A2 INTEGER DEFAULT 0,
    flag_A3 INTEGER DEFAULT 0, flag_A4 INTEGER DEFAULT 0,
    flag_A5 INTEGER DEFAULT 0, flag_A6 INTEGER DEFAULT 0,
    flag_A7 INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ann_annotator ON annotations(annotator);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ann_unique
    ON annotations(annotator, system_id, station_id);
"""


class AnnotationStore(_BaseStore):
    """SQLite annotation store (local, zero-config)."""

    def __init__(self, db_path: str | Path | None = None):
        import sqlite3
        path = Path(db_path) if db_path else Path(
            os.environ.get("ANNOTATION_DB_PATH", str(_DEFAULT_DB))
        )
        self._path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SQLITE_SCHEMA)

    def save(self, row: dict[str, Any]) -> int:
        if isinstance(row.get("infrastructure_elements"), (list, tuple)):
            row = {**row, "infrastructure_elements": json.dumps(
                row["infrastructure_elements"], ensure_ascii=False)}
        present = {k: row[k] for k in _COLUMNS if k in row}
        names = ", ".join(present.keys())
        placeholders = ", ".join(["?"] * len(present))
        cur = self._conn.execute(
            f"INSERT OR REPLACE INTO annotations ({names}) VALUES ({placeholders})",
            list(present.values()),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def get_done_keys(self, annotator: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT system_id, station_id FROM annotations WHERE annotator = ?",
            (annotator,),
        ).fetchall()
        return {f"{r['system_id']}|{r['station_id']}" for r in rows}

    def get_annotation(self, annotator, system_id, station_id):
        row = self._conn.execute(
            "SELECT * FROM annotations "
            "WHERE annotator = ? AND system_id = ? AND station_id = ?",
            (annotator, system_id, station_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["infrastructure_elements"] = _parse_infra(d.get("infrastructure_elements"))
        return d

    def get_all(self, annotator: str) -> pd.DataFrame:
        df = pd.read_sql_query(
            "SELECT * FROM annotations WHERE annotator = ? ORDER BY created_at",
            self._conn, params=(annotator,),
        )
        if "infrastructure_elements" in df.columns:
            df["infrastructure_elements"] = df["infrastructure_elements"].apply(
                _parse_infra)
        return df

    def count(self, annotator: str) -> int:
        r = self._conn.execute(
            "SELECT COUNT(*) AS n FROM annotations WHERE annotator = ?",
            (annotator,),
        ).fetchone()
        return r["n"] if r else 0

    def median_duration(self, annotator: str):
        rows = self._conn.execute(
            "SELECT duration_s FROM annotations "
            "WHERE annotator = ? AND verdict != 'skipped' AND duration_s > 0 "
            "ORDER BY duration_s",
            (annotator,),
        ).fetchall()
        vals = [r["duration_s"] for r in rows]
        return _median(vals)

    def close(self) -> None:
        self._conn.close()


# =====================================================================
# PostgreSQL backend (hosted, e.g. Supabase)
# =====================================================================

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS annotations (
    id                      BIGSERIAL PRIMARY KEY,
    session_id              TEXT NOT NULL,
    annotator               TEXT NOT NULL,
    system_id               TEXT NOT NULL,
    station_id              TEXT NOT NULL,
    stratum                 TEXT,
    lat                     DOUBLE PRECISION,
    lon                     DOUBLE PRECISION,
    ground_reality          TEXT,
    infrastructure_elements TEXT,
    streetview_date         TEXT,
    capacity_assessment     TEXT,
    location_assessment     TEXT,
    verdict                 TEXT NOT NULL,
    confidence              INTEGER NOT NULL DEFAULT 3,
    notes                   TEXT,
    duration_s              DOUBLE PRECISION,
    created_at              TEXT NOT NULL,
    flag_A1 INTEGER DEFAULT 0, flag_A2 INTEGER DEFAULT 0,
    flag_A3 INTEGER DEFAULT 0, flag_A4 INTEGER DEFAULT 0,
    flag_A5 INTEGER DEFAULT 0, flag_A6 INTEGER DEFAULT 0,
    flag_A7 INTEGER DEFAULT 0,
    CONSTRAINT uq_annotation UNIQUE (annotator, system_id, station_id)
);
CREATE INDEX IF NOT EXISTS idx_ann_annotator ON annotations(annotator);
"""


class PostgresAnnotationStore(_BaseStore):
    """Hosted PostgreSQL backend (Supabase, Neon, RDS…)."""

    def __init__(self, dsn: str):
        import psycopg2  # lazy: only needed when a hosted DB is configured
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute(_PG_SCHEMA)

    def save(self, row: dict[str, Any]) -> int:
        if isinstance(row.get("infrastructure_elements"), (list, tuple)):
            row = {**row, "infrastructure_elements": json.dumps(
                row["infrastructure_elements"], ensure_ascii=False)}
        present = {k: row[k] for k in _COLUMNS if k in row}
        names = ", ".join(present.keys())
        placeholders = ", ".join(["%s"] * len(present))
        updates = ", ".join(
            f"{c}=EXCLUDED.{c}" for c in present
            if c not in ("annotator", "system_id", "station_id")
        )
        sql = (
            f"INSERT INTO annotations ({names}) VALUES ({placeholders}) "
            f"ON CONFLICT (annotator, system_id, station_id) "
            f"DO UPDATE SET {updates}"
        )
        with self._conn.cursor() as cur:
            cur.execute(sql, list(present.values()))
        return 0

    def get_done_keys(self, annotator: str) -> set[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT system_id, station_id FROM annotations WHERE annotator = %s",
                (annotator,),
            )
            return {f"{a}|{b}" for a, b in cur.fetchall()}

    def get_annotation(self, annotator, system_id, station_id):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM annotations "
                "WHERE annotator = %s AND system_id = %s AND station_id = %s",
                (annotator, system_id, station_id),
            )
            r = cur.fetchone()
            if r is None:
                return None
            cols = [c.name for c in cur.description]
        d = {_FLAG_RENAME.get(c, c): v for c, v in zip(cols, r)}
        d["infrastructure_elements"] = _parse_infra(d.get("infrastructure_elements"))
        return d

    def get_all(self, annotator: str) -> pd.DataFrame:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM annotations WHERE annotator = %s ORDER BY created_at",
                (annotator,),
            )
            rows = cur.fetchall()
            cols = [_FLAG_RENAME.get(c.name, c.name) for c in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        if "infrastructure_elements" in df.columns:
            df["infrastructure_elements"] = df["infrastructure_elements"].apply(
                _parse_infra)
        return df

    def count(self, annotator: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM annotations WHERE annotator = %s",
                (annotator,),
            )
            return int(cur.fetchone()[0])

    def median_duration(self, annotator: str):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT duration_s FROM annotations "
                "WHERE annotator = %s AND verdict <> 'skipped' AND duration_s > 0 "
                "ORDER BY duration_s",
                (annotator,),
            )
            vals = [r[0] for r in cur.fetchall()]
        return _median(vals)

    def close(self) -> None:
        self._conn.close()


# =====================================================================
# Helpers + factory
# =====================================================================

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


def _median(vals: list[float]):
    if not vals:
        return None
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _get_dsn() -> str | None:
    """Hosted-DB connection string from env var or Streamlit secret."""
    dsn = os.environ.get("ANNOTATION_DB_URL")
    if dsn:
        return dsn.strip()
    try:
        import streamlit as st
        if "ANNOTATION_DB_URL" in st.secrets:
            return str(st.secrets["ANNOTATION_DB_URL"]).strip()
    except Exception:
        pass
    return None


def get_store() -> _BaseStore:
    """Return the configured store: PostgreSQL if a DSN is set, else SQLite."""
    dsn = _get_dsn()
    if dsn and dsn.lower().startswith("postgres"):
        return PostgresAnnotationStore(dsn)
    return AnnotationStore()
