"""
Weekly View router.

Routes:
  GET /week  → weekly summary: workouts by day, volume by muscle group
"""
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    PlannedSet, ProgramRun, ScheduledWorkout, TrainingDay, User,
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


def compute_muscle_sets(workouts: list[ScheduledWorkout]) -> dict[str, int]:
    """
    Given a list of ScheduledWorkout ORM objects (with training_day.planned_sets.exercise loaded),
    return a dict mapping muscle_group -> total planned set count.

    PlannedSets whose exercise has no muscle_group are skipped.
    """
    counts: dict[str, int] = defaultdict(int)
    for workout in workouts:
        if workout.training_day is None:
            continue
        for ps in workout.training_day.planned_sets:
            if ps.exercise and ps.exercise.muscle_group:
                counts[ps.exercise.muscle_group.value] += 1
    return dict(counts)


@router.get("", response_class=HTMLResponse)
def week_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today = date.today()
    monday, sunday = week_bounds(today)
    label = week_label(monday, sunday)

    # ── All scheduled (non-skipped) workouts this week for this user ─────────
    workouts = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date >= monday,
            ScheduledWorkout.scheduled_date <= sunday,
            ScheduledWorkout.skipped.is_(False),
        )
        .options(
            joinedload(ScheduledWorkout.training_day)
                .joinedload(TrainingDay.planned_sets)
                .joinedload(PlannedSet.exercise),
            joinedload(ScheduledWorkout.block),
        )
        .order_by(ScheduledWorkout.scheduled_date)
        .all()
    )

    # ── Organise by day name (Mon–Sun) ────────────────────────────────────────
    workouts_by_day: dict[str, list[ScheduledWorkout]] = {
        day: [] for day in _DAY_NAMES
    }

    for workout in workouts:
        day_name = _DAY_NAMES[workout.scheduled_date.weekday()]
        workouts_by_day[day_name].append(workout)

    # ── Planned set count per muscle group ───────────────────────────────────
    muscle_sets = compute_muscle_sets(workouts)

    return templates.TemplateResponse(
        request,
        "week.html",
        {
            "user": current_user,
            "week_label": label,
            "workouts_by_day": workouts_by_day,
            "muscle_sets": muscle_sets,
        },
    )
