"""
PRs router — 1RM management for Squat, Bench Press, Deadlift.
Phase 2.
"""
import json
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Exercise, ExerciseCategory, OneRepMax, User
from app.utils import round_to_nearest_2_5

router = APIRouter(prefix="/prs", tags=["prs"])
templates = Jinja2Templates(directory="app/templates")

# The three main lifts shown on the PRs page — order matters (matches the tabs)
MAIN_LIFT_NAMES = ["Squat", "Bench Press", "Deadlift"]


def _build_lift_data(user_id: int, db: Session) -> list[dict]:
    """
    Fetch current 1RM + full history for each of the three main lifts.
    Returns a list of dicts ready to pass to the template.
    """
    lifts: list[dict] = []

    for lift_name in MAIN_LIFT_NAMES:
        exercise = (
            db.query(Exercise)
            .filter(Exercise.name == lift_name, Exercise.is_archived == False)  # noqa: E712
            .first()
        )
        if not exercise:
            continue

        # All entries for this user + exercise, oldest → newest (for the chart x-axis)
        history_asc = (
            db.query(OneRepMax)
            .filter(OneRepMax.user_id == user_id, OneRepMax.exercise_id == exercise.id)
            .order_by(OneRepMax.date_set.asc(), OneRepMax.id.asc())
            .all()
        )

        current_1rm: OneRepMax | None = history_asc[-1] if history_asc else None

        # Chart.js needs JSON arrays (oldest first)
        chart_labels = [str(entry.date_set) for entry in history_asc]
        chart_values = [entry.weight_kg for entry in history_asc]

        lifts.append(
            {
                "exercise": exercise,
                "current_1rm": current_1rm,
                "history": list(reversed(history_asc)),  # newest first for the table
                "chart_labels": json.dumps(chart_labels),
                "chart_values": json.dumps(chart_values),
            }
        )

    return lifts


@router.get("", response_class=HTMLResponse)
def prs_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifts_data = _build_lift_data(current_user.id, db)
    return templates.TemplateResponse(
        "prs.html",
        {
            "request": request,
            "user": current_user,
            "lifts_data": lifts_data,
            "today": str(date.today()),
        },
    )


@router.post("/log")
def log_pr(
    request: Request,
    exercise_id: int = Form(...),
    weight_kg: float = Form(...),
    date_set: date = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # Validate exercise exists and is a main lift
    exercise = (
        db.query(Exercise)
        .filter(
            Exercise.id == exercise_id,
            Exercise.category == ExerciseCategory.main_lift,
            Exercise.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # Always round to nearest 2.5 kg
    rounded_weight = round_to_nearest_2_5(weight_kg)

    entry = OneRepMax(
        user_id=current_user.id,
        exercise_id=exercise.id,
        weight_kg=rounded_weight,
        date_set=date_set,
    )
    db.add(entry)
    db.commit()

    return RedirectResponse(url="/prs", status_code=303)
