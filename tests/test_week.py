"""
Unit tests for app/routers/week.py — volume calculation and week utilities.

These tests use plain Python objects (no database required) so they run fast
and without any FastAPI or SQLAlchemy infrastructure.
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.routers.week import compute_muscle_volume, week_bounds, week_label


# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for ORM objects
# ---------------------------------------------------------------------------

def _exercise(muscle_group_value: str | None) -> MagicMock:
    ex = MagicMock()
    if muscle_group_value is None:
        ex.muscle_group = None
    else:
        mg = MagicMock()
        mg.value = muscle_group_value
        ex.muscle_group = mg
    return ex


def _completed_set(
    weight: float | None,
    reps: int | None,
    exercise_mg: str | None,
    subst_mg: str | None = None,
) -> MagicMock:
    cs = MagicMock()
    cs.actual_weight_kg = weight
    cs.actual_reps = reps
    cs.planned_set = MagicMock()
    cs.planned_set.exercise = _exercise(exercise_mg)
    if subst_mg is not None:
        cs.substituted_exercise_id = 99  # non-None triggers substitution path
        cs.substituted_exercise = _exercise(subst_mg)
    else:
        cs.substituted_exercise_id = None
        cs.substituted_exercise = None
    return cs


# ---------------------------------------------------------------------------
# compute_muscle_volume
# ---------------------------------------------------------------------------

class TestComputeMuscleVolume:
    def test_empty_list(self) -> None:
        assert compute_muscle_volume([]) == {}

    def test_single_set(self) -> None:
        cs = _completed_set(weight=100.0, reps=5, exercise_mg="legs")
        result = compute_muscle_volume([cs])
        assert result == {"legs": 500.0}

    def test_multiple_sets_same_group(self) -> None:
        sets = [
            _completed_set(weight=100.0, reps=5, exercise_mg="legs"),  # 500
            _completed_set(weight=80.0, reps=8, exercise_mg="legs"),   # 640
        ]
        result = compute_muscle_volume(sets)
        assert result == {"legs": pytest.approx(1140.0)}

    def test_multiple_muscle_groups(self) -> None:
        sets = [
            _completed_set(weight=100.0, reps=5, exercise_mg="legs"),
            _completed_set(weight=60.0, reps=10, exercise_mg="chest"),
        ]
        result = compute_muscle_volume(sets)
        assert result["legs"] == pytest.approx(500.0)
        assert result["chest"] == pytest.approx(600.0)

    def test_skips_no_weight(self) -> None:
        cs = _completed_set(weight=None, reps=5, exercise_mg="back")
        assert compute_muscle_volume([cs]) == {}

    def test_skips_no_reps(self) -> None:
        cs = _completed_set(weight=100.0, reps=None, exercise_mg="back")
        assert compute_muscle_volume([cs]) == {}

    def test_skips_no_muscle_group(self) -> None:
        cs = _completed_set(weight=100.0, reps=5, exercise_mg=None)
        assert compute_muscle_volume([cs]) == {}

    def test_substituted_exercise_used_for_muscle_group(self) -> None:
        # planned_set exercise is "back", but substitution is "shoulders"
        cs = _completed_set(weight=40.0, reps=12, exercise_mg="back", subst_mg="shoulders")
        result = compute_muscle_volume([cs])
        assert "shoulders" in result
        assert "back" not in result
        assert result["shoulders"] == pytest.approx(480.0)

    def test_volume_formula_is_reps_times_weight(self) -> None:
        cs = _completed_set(weight=75.0, reps=3, exercise_mg="chest")
        result = compute_muscle_volume([cs])
        assert result["chest"] == pytest.approx(225.0)


# ---------------------------------------------------------------------------
# week_bounds
# ---------------------------------------------------------------------------

class TestWeekBounds:
    def test_monday_returns_same_day(self) -> None:
        monday = date(2026, 3, 9)  # actual Monday
        mon, sun = week_bounds(monday)
        assert mon == date(2026, 3, 9)
        assert sun == date(2026, 3, 15)

    def test_sunday_returns_same_week(self) -> None:
        sunday = date(2026, 3, 15)
        mon, sun = week_bounds(sunday)
        assert mon == date(2026, 3, 9)
        assert sun == date(2026, 3, 15)

    def test_midweek_date(self) -> None:
        wednesday = date(2026, 3, 11)
        mon, sun = week_bounds(wednesday)
        assert mon == date(2026, 3, 9)
        assert sun == date(2026, 3, 15)

    def test_span_is_always_6_days(self) -> None:
        for day_offset in range(7):
            d = date(2026, 3, 9) + __import__("datetime").timedelta(days=day_offset)
            mon, sun = week_bounds(d)
            assert (sun - mon).days == 6


# ---------------------------------------------------------------------------
# week_label
# ---------------------------------------------------------------------------

class TestWeekLabel:
    def test_same_month(self) -> None:
        mon, sun = date(2026, 3, 9), date(2026, 3, 15)
        label = week_label(mon, sun)
        assert "Week 11" in label
        assert "Mar" in label
        assert "9" in label
        assert "15" in label

    def test_cross_month(self) -> None:
        mon, sun = date(2026, 3, 30), date(2026, 4, 5)
        label = week_label(mon, sun)
        assert "Mar" in label
        assert "Apr" in label
