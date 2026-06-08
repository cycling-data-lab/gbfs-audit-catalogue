# -*- coding: utf-8 -*-
"""Persistent storage for the human-validation annotation campaign (v2).

Same backend strategy as ``experiments/annotation/storage.py`` (SQLite local
by default, PostgreSQL/Supabase if ``ANNOTATION_DB_URL`` is set) but with the
v2 schema: four routed questions (Q0..Q3b), a per-question evidence log,
and the two rigor fields recommended in review (gold-trap flag, test-retest
round).

One row per (annotator, system_id, station_id, revisit_round): the same
annotator can re-annotate a station in round 1 (two weeks later) for
intra-rater reliability without overwriting the round-0 label.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

_DEFAULT_DB = Path(__file__).resolve().parent / "annotations_v2.db"

_COLUMNS = [
    "session_id", "annotator", "system_id", "station_id", "stratum",
    "lat", "lon",
    "q0_type", "q2_nb_docks_classe", "q3a_perimetre", "q3b_proximite",
    "sv_date", "sv_pano_id", "sv_status",
    "verdict", "evidence", "notes",
    "is_trap", "revisit_round", "duration_s", "created_at",
    "flag_A1", "flag_A2", "flag_A3", "flag_A4",
    "flag_A5", "flag_A6", "flag_A7",
]

_FLAG_RENAME = {f"flag_a{i}": f"flag_A{i}" for i in range(1, 8)}

_SQLITE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS annotations_v2 (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT NOT NULL,
    annotator          TEXT NOT NULL,
    system_id          TEXT NOT NULL,
    station_id         TEXT NOT NULL,
    stratum            TEXT,
    lat                REAL,
    lon                REAL,
    q0_type            TEXT,
    q2_nb_docks_classe TEXT,
    q3a_perimetre      TEXT,
    q3b_proximite      TEXT,
    sv_date            TEXT,
    sv_pano_id         TEXT,
    sv_status          TEXT,
    verdict            TEXT,
    evidence           TEXT,
    notes              TEXT,
    is_trap            INTEGER DEFAULT 0,
    revisit_round      INTEGER DEFAULT 0,
    duration_s         REAL,
    created_at         TEXT NOT NULL,
    flag_A1 INTEGER DEFAULT 0, flag_A2 INTEGER DEFAULT 0,
    flag_A3 INTEGER DEFAULT 0, flag_A4 INTEGER DEFAULT 0,
    flag_A5 INTEGER DEFAULT 0, flag_A6 INTEGER DEFAULT 0,
    flag_A7 INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_c_annotator ON annotations_v2(annotator);
CREATE UNIQUE INDEX IF NOT EXISTS idx_c_unique
    ON annotations_v2(annotator, system_id, station_id, revisit_round);
"""

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS annotations_v2 (
    id                 BIGSERIAL PRIMARY KEY,
    session_id         TEXT NOT NULL,
    annotator          TEXT NOT NULL,
    system_id          TEXT NOT NULL,
    station_id         TEXT NOT NULL,
    stratum            TEXT,
    lat                DOUBLE PRECISION,
    lon                DOUBLE PRECISION,
    q0_type            TEXT,
    q2_nb_docks_classe TEXT,
    q3a_perimetre      TEXT,
    q3b_proximite      TEXT,
    sv_date            TEXT,
    sv_pano_id         TEXT,
    sv_status          TEXT,
    verdict            TEXT,
    evidence           TEXT,
    notes              TEXT,
    is_trap            INTEGER DEFAULT 0,
    revisit_round      INTEGER DEFAULT 0,
    duration_s         DOUBLE PRECISION,
    created_at         TEXT NOT NULL,
    flag_A1 INTEGER DEFAULT 0, flag_A2 INTEGER DEFAULT 0,
    flag_A3 INTEGER DEFAULT 0, flag_A4 INTEGER DEFAULT 0,
    flag_A5 INTEGER DEFAULT 0, flag_A6 INTEGER DEFAULT 0,
    flag_A7 INTEGER DEFAULT 0,
    CONSTRAINT uq_v2 UNIQUE (annotator, system_id, station_id, revisit_round)
);
CREATE INDEX IF NOT EXISTS idx_c_annotator ON annotations_v2(annotator);
"""


class _Base:
    def save(self, row: dict[str, Any]) -> int: raise NotImplementedError
    def get_done_keys(self, annotator: str, revisit_round: int = 0) -> set[str]: raise NotImplementedError
    def get_annotation(self, annotator, system_id, station_id, revisit_round=0): raise NotImplementedError
    def get_all(self, annotator: str) -> pd.DataFrame: raise NotImplementedError
    def count(self, annotator: str) -> int: raise NotImplementedError
    def median_duration(self, annotator: str): raise NotImplementedError
    def delete_last(self, annotator: str, revisit_round: int = 0) -> None: raise NotImplementedError
    def close(self) -> None: ...

    def export_csv(self, annotator: str, path: Path) -> None:
        """Export in the column layout expected by compute_reliability.py."""
        df = self.get_all(annotator)
        rename = {
            "q0_type": "Q0_type",
            "q2_nb_docks_classe": "Q2_nb_docks_classe",
            "q3a_perimetre": "Q3a_perimetre",
            "q3b_proximite": "Q3b_proximite",
        }
        df = df.rename(columns=rename)
        df.to_csv(path, index=False)


class AnnotationStore(_Base):
    def __init__(self, db_path: str | Path | None = None):
        import sqlite3
        path = Path(db_path) if db_path else Path(
            os.environ.get("ANNOTATION_DB_PATH", str(_DEFAULT_DB)))
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SQLITE_SCHEMA)

    def save(self, row: dict[str, Any]) -> int:
        present = {k: row[k] for k in _COLUMNS if k in row}
        names = ", ".join(present)
        ph = ", ".join(["?"] * len(present))
        cur = self._conn.execute(
            f"INSERT OR REPLACE INTO annotations_v2 ({names}) VALUES ({ph})",
            list(present.values()))
        self._conn.commit()
        return cur.lastrowid or 0

    def get_done_keys(self, annotator: str, revisit_round: int = 0) -> set[str]:
        rows = self._conn.execute(
            "SELECT system_id, station_id FROM annotations_v2 "
            "WHERE annotator = ? AND revisit_round = ?",
            (annotator, revisit_round)).fetchall()
        return {f"{r['system_id']}|{r['station_id']}" for r in rows}

    def get_annotation(self, annotator, system_id, station_id, revisit_round=0):
        r = self._conn.execute(
            "SELECT * FROM annotations_v2 WHERE annotator=? AND system_id=? "
            "AND station_id=? AND revisit_round=?",
            (annotator, system_id, station_id, revisit_round)).fetchone()
        return dict(r) if r else None

    def get_all(self, annotator: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM annotations_v2 WHERE annotator=? ORDER BY created_at",
            self._conn, params=(annotator,))

    def count(self, annotator: str) -> int:
        r = self._conn.execute(
            "SELECT COUNT(*) AS n FROM annotations_v2 WHERE annotator=?",
            (annotator,)).fetchone()
        return r["n"] if r else 0

    def median_duration(self, annotator: str):
        rows = self._conn.execute(
            "SELECT duration_s FROM annotations_v2 WHERE annotator=? "
            "AND verdict != 'skipped' AND duration_s > 0 ORDER BY duration_s",
            (annotator,)).fetchall()
        return _median([r["duration_s"] for r in rows])

    def delete_last(self, annotator: str, revisit_round: int = 0) -> None:
        self._conn.execute(
            "DELETE FROM annotations_v2 WHERE id = (SELECT id FROM annotations_v2 "
            "WHERE annotator=? AND revisit_round=? ORDER BY created_at DESC, id DESC "
            "LIMIT 1)", (annotator, revisit_round))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class PostgresAnnotationStore(_Base):
    def __init__(self, dsn: str):
        import psycopg2
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute(_PG_SCHEMA)

    def save(self, row: dict[str, Any]) -> int:
        present = {k: row[k] for k in _COLUMNS if k in row}
        names = ", ".join(present)
        ph = ", ".join(["%s"] * len(present))
        updates = ", ".join(
            f"{c}=EXCLUDED.{c}" for c in present
            if c not in ("annotator", "system_id", "station_id", "revisit_round"))
        sql = (f"INSERT INTO annotations_v2 ({names}) VALUES ({ph}) "
               f"ON CONFLICT (annotator, system_id, station_id, revisit_round) "
               f"DO UPDATE SET {updates}")
        with self._conn.cursor() as cur:
            cur.execute(sql, list(present.values()))
        return 0

    def get_done_keys(self, annotator: str, revisit_round: int = 0) -> set[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT system_id, station_id FROM annotations_v2 "
                "WHERE annotator=%s AND revisit_round=%s",
                (annotator, revisit_round))
            return {f"{a}|{b}" for a, b in cur.fetchall()}

    def get_annotation(self, annotator, system_id, station_id, revisit_round=0):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM annotations_v2 WHERE annotator=%s AND system_id=%s "
                "AND station_id=%s AND revisit_round=%s",
                (annotator, system_id, station_id, revisit_round))
            r = cur.fetchone()
            if r is None:
                return None
            cols = [_FLAG_RENAME.get(c.name, c.name) for c in cur.description]
        return dict(zip(cols, r))

    def get_all(self, annotator: str) -> pd.DataFrame:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM annotations_v2 WHERE annotator=%s ORDER BY created_at",
                (annotator,))
            rows = cur.fetchall()
            cols = [_FLAG_RENAME.get(c.name, c.name) for c in cur.description]
        return pd.DataFrame(rows, columns=cols)

    def count(self, annotator: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM annotations_v2 WHERE annotator=%s",
                        (annotator,))
            return int(cur.fetchone()[0])

    def median_duration(self, annotator: str):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT duration_s FROM annotations_v2 WHERE annotator=%s "
                "AND verdict <> 'skipped' AND duration_s > 0 ORDER BY duration_s",
                (annotator,))
            return _median([r[0] for r in cur.fetchall()])

    def delete_last(self, annotator: str, revisit_round: int = 0) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM annotations_v2 WHERE id = (SELECT id FROM annotations_v2 "
                "WHERE annotator=%s AND revisit_round=%s ORDER BY created_at DESC, "
                "id DESC LIMIT 1)", (annotator, revisit_round))

    def close(self) -> None:
        self._conn.close()


def _median(vals):
    if not vals:
        return None
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _get_dsn() -> str | None:
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


def get_store() -> _Base:
    dsn = _get_dsn()
    if dsn and dsn.lower().startswith("postgres"):
        return PostgresAnnotationStore(dsn)
    return AnnotationStore()
