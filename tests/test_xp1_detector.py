"""Tests for XP1 zombie station detector."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from experiments.xp1_dynamic_audit.detector import (
    StationLiveness,
    _frozen_fraction,
    _normalised_entropy,
    classify_stations,
)


class TestEntropy:
    def test_constant_series_has_zero_entropy(self):
        series = np.array([5, 5, 5, 5, 5, 5, 5, 5, 5, 5], dtype=float)
        assert _normalised_entropy(series) == 0.0

    def test_uniform_distribution_has_high_entropy(self):
        series = np.arange(100, dtype=float)
        H = _normalised_entropy(series)
        assert H > 0.9

    def test_bimodal_has_intermediate_entropy(self):
        # Unbalanced two-state series -> high but not maximal entropy.
        # A balanced 50/50 split is uniform over its support, so its
        # normalised entropy is exactly 1.0; an unbalanced split yields a
        # genuinely intermediate value strictly between 0 and 1.
        series = np.array([0] * 70 + [10] * 30, dtype=float)
        H = _normalised_entropy(series)
        assert 0.0 < H < 1.0


class TestFrozenFraction:
    def test_all_frozen(self):
        series = np.array([5, 5, 5, 5, 5], dtype=float)
        assert _frozen_fraction(series) == 1.0

    def test_all_changing(self):
        series = np.array([1, 2, 3, 4, 5], dtype=float)
        assert _frozen_fraction(series) == 0.0


class TestClassifyStations:
    def _make_snapshots(self, n_epochs: int = 200) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create synthetic snapshots: one live station, one zombie, one absent."""
        rng = np.random.default_rng(42)
        epochs = pd.date_range("2026-01-01", periods=n_epochs, freq="15min", tz="UTC")

        rows = []
        for t in epochs:
            # Live station: varying availability
            rows.append({
                "system_id": "sys1",
                "station_id": "live_stn",
                "num_bikes_available": int(rng.integers(0, 20)),
                "num_docks_available": int(rng.integers(0, 20)),
                "is_renting": True,
                "is_returning": True,
                "last_reported": t.timestamp(),
                "collected_at": t.isoformat(),
            })
            # Zombie station: frozen at 0
            rows.append({
                "system_id": "sys1",
                "station_id": "zombie_stn",
                "num_bikes_available": 0,
                "num_docks_available": 0,
                "is_renting": False,
                "is_returning": False,
                "last_reported": pd.Timestamp("2025-12-01", tz="UTC").timestamp(),
                "collected_at": t.isoformat(),
            })

        snapshots = pd.DataFrame(rows)
        snapshots["collected_at"] = pd.to_datetime(snapshots["collected_at"], utc=True)

        station_info = pd.DataFrame({
            "system_id": ["sys1", "sys1", "sys1"],
            "station_id": ["live_stn", "zombie_stn", "phantom_stn"],
        })

        return snapshots, station_info

    def test_live_station_classified_correctly(self):
        snapshots, station_info = self._make_snapshots()
        result = classify_stations(
            snapshots, station_info,
            min_snapshots=50,
            staleness_threshold_hours=72,
            reference_time=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
        live = result[result["station_id"] == "live_stn"]
        assert len(live) == 1
        assert live.iloc[0]["liveness"] == StationLiveness.LIVE.value

    def test_zombie_station_classified_correctly(self):
        snapshots, station_info = self._make_snapshots()
        result = classify_stations(
            snapshots, station_info,
            min_snapshots=50,
            staleness_threshold_hours=72,
            reference_time=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
        zombie = result[result["station_id"] == "zombie_stn"]
        assert len(zombie) == 1
        assert zombie.iloc[0]["liveness"] == StationLiveness.ZOMBIE.value

    def test_phantom_station_classified_as_decommissioned(self):
        snapshots, station_info = self._make_snapshots()
        result = classify_stations(
            snapshots, station_info,
            min_snapshots=50,
            reference_time=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
        phantom = result[result["station_id"] == "phantom_stn"]
        assert len(phantom) == 1
        assert phantom.iloc[0]["liveness"] == StationLiveness.DECOMMISSIONED.value
