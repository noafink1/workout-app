"""
Weekly View router.

Routes:
  GET /week  → weekly summary: workouts by day, volume by muscle group
"""
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    CompletedSet, Exercise, PlannedSet, ProgramRun, ScheduledWorkout, User,
)

router = APIRouter(prefix="/week", tags=["week"])
templates = Jinja2Templates(directory="app/templates")

# Day names in ISO weekday order (Monday = 0)
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def week_bounds(today: date) -> tuple[date, date]:
    """Return (monday, sunday) of the ISO week containing *today*."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def week_label(monday: date, sunday: date) -> str:
    """Human-readable label, e.g. 'Week 11 · Mar 10–16'."""
    week_num = monday.isocalendar()[1]
    if monday.month == sunday.month:
        date_range = f"{monday.strftime('%b')} {monday.day}–{sunday.day}"
    else:
        date_range = f"{monday.strftime('%b')} {monday.day}–{sunday.strftime('%b')} {sunday.day}"
    return f"Week {week_num} · {date_range}"


def compute_muscle_volume(
    completed_sets: list[CompletedSet],
) -> dict[str, float]:
    """
    Given a list of CompletedSet ORM objects (with planned_set.exercise loaded),
    return a dict mapping muscle_group -> total_volume (sets × reps × weight_kg).

    Sets without a weight or reps recorded are skipped.
    Sets where the exercise has no muscle_group are skipped.
    """
    volume: dict[str, float] = defaultdict(float)
    for cs in completed_sets:
        if cs.actual_weight_kg is None or cs.actual_reps is None:
            continue
        # Substituted exercise takes priority for muscle group resolution
        exercise: Optional[Exercise] = (
            cs.substituted_exercise if cs.substituted_exercise_id else cs.planned_set.exercise
        )
        if exercise is None or exercise.muscle_group is None:
            continue
        mg = exercise.muscle_group.value
        volume[mg] += cs.actual_reps * cs.actual_weight_kg
    return dict(volume)


@router.get("", response_class=HTMLResponse)
def week_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today = date.today()
    monday, sunday = week_bounds(today)
    label = week_label(monday, sunday)

    # ── All completed workouts this week for this user ────────────────────────
    workouts = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date >= monday,
            ScheduledWorkout.scheduled_date <= sunday,
            ScheduledWorkout.completed_at.isnot(None),
        )
        .options(
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.completed_sets).joinedload(
                CompletedSet.planned_set
            ).joinedload(PlannedSet.exercise),
            joinedload(ScheduledWorkout.completed_sets).joinedload(
                CompletedSet.substituted_exercise
            ),
        )
        .order_by(ScheduledWorkout.scheduled_date)
        .all()
    )

    # ── Organise by day name (Mon–Sun) ────────────────────────────────────────
    workouts_by_day: dict[str, list[ScheduledWorkout]] = {
        day: [] for day in _DAY_NAMES
    }
    all_completed_sets: list[CompletedSet] = []

    for workout in workouts:
        day_name = _DAY_NAMES[workout.scheduled_date.weekday()]
        workouts_by_day[day_name].append(workout)
        all_completed_sets.extend(workout.completed_sets)

    # ── Volume per muscle group ───────────────────────────────────────────────
    muscle_volume = compute_muscle_volume(all_completed_sets)

    return templates.TemplateResponse(
        "week.html",
        {
            "request": request,
            "user": current_user,
            "week_label": label,
            "workouts_by_day": workouts_by_day,
            "muscle_volume": muscle_volume,
        },
    )
