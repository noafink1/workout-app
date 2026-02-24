"""
Progress & Stats router — Phase 6.

Routes:
  GET /progress  → main lifts 1RM trend, accessory bests, weekly volume chart
"""
import json
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    AccessoryBest, CompletedSet, Exercise, ExerciseCategory,
    OneRepMax, PlannedSet, ProgramRun, ScheduledWorkout, User,
)

router = APIRouter(prefix="/progress", tags=["progress"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _week_monday(d: date) -> date:
    """Return the Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
def progress_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today = date.today()

    # ── Main lift 1RM sparkline charts ──────────────────────────────────────
    main_lift_exercises = (
        db.query(Exercise)
        .filter(
            Exercise.category == ExerciseCategory.main_lift,
            Exercise.is_archived == False,  # noqa: E712
        )
        .order_by(Exercise.name)
        .all()
    )

    lift_charts: list[dict] = []
    for ex in main_lift_exercises:
        records = (
            db.query(OneRepMax)
            .filter(
                OneRepMax.user_id == current_user.id,
                OneRepMax.exercise_id == ex.id,
            )
            .order_by(OneRepMax.date_set, OneRepMax.id)
            .all()
        )
        current_1rm = records[-1] if records else None
        lift_charts.append({
            "exercise": ex,
            "current": current_1rm,
            "chart_labels": json.dumps([r.date_set.strftime("%d %b") for r in records]),
            "chart_values": json.dumps([r.weight_kg for r in records]),
            "has_data": bool(records),
        })

    # ── Accessory bests ─────────────────────────────────────────────────────
    accessory_bests = (
        db.query(AccessoryBest)
        .filter(AccessoryBest.user_id == current_user.id)
        .options(joinedload(AccessoryBest.exercise))
        .order_by(AccessoryBest.weight_kg.desc())
        .all()
    )

    # ── Weekly volume — last 8 weeks ─────────────────────────────────────────
    current_monday = _week_monday(today)
    week_mondays = [current_monday - timedelta(weeks=i) for i in range(7, -1, -1)]
    eight_weeks_ago = week_mondays[0]

    volume_rows = (
        db.query(
            ScheduledWorkout.scheduled_date,
            Exercise.muscle_group,
            func.count(CompletedSet.id).label("cnt"),
        )
        .join(CompletedSet, CompletedSet.scheduled_workout_id == ScheduledWorkout.id)
        .join(PlannedSet, CompletedSet.planned_set_id == PlannedSet.id)
        .join(Exercise, PlannedSet.exercise_id == Exercise.id)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date >= eight_weeks_ago,
            ScheduledWorkout.completed_at.isnot(None),
            Exercise.muscle_group.isnot(None),
        )
        .group_by(ScheduledWorkout.scheduled_date, Exercise.muscle_group)
        .all()
    )

    vol_by_week: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for scheduled_date, muscle_group, cnt in volume_rows:
        if muscle_group:
            wm = _week_monday(scheduled_date)
            vol_by_week[wm][muscle_group.value] += cnt

    muscle_groups = ["chest", "back", "legs", "shoulders", "arms", "core"]
    volume_json = json.dumps({
        "labels": [f"{wm.strftime('%b')} {wm.day}" for wm in week_mondays],
        "datasets": [
            {
                "label": mg.capitalize(),
                "data": [vol_by_week[wm].get(mg, 0) for wm in week_mondays],
            }
            for mg in muscle_groups
        ],
    })

    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "user": current_user,
            "lift_charts": lift_charts,
            "accessory_bests": accessory_bests,
            "volume_json": volume_json,
        },
    )
