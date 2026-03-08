"""
Exercises router — Phase 8.

Routes:
  GET  /exercises             → exercise library (grouped by muscle group)
  POST /exercises/new         → create a custom exercise
  POST /exercises/{id}/archive → soft-delete a user-owned custom exercise
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Exercise, ExerciseCategory, MuscleGroup, User

router = APIRouter(prefix="/exercises", tags=["exercises"])
templates = Jinja2Templates(directory="app/templates")

# Canonical display order for muscle groups
_MG_ORDER = ["chest", "back", "legs", "shoulders", "arms", "core"]


@router.get("", response_class=HTMLResponse)
def exercises_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    exercises = (
        db.query(Exercise)
        .filter(
            Exercise.is_archived == False,  # noqa: E712
            or_(
                Exercise.creator_user_id == None,       # noqa: E711  system exercises
                Exercise.creator_user_id == current_user.id,
            ),
        )
        .order_by(Exercise.name)
        .all()
    )

    # Group by muscle group, preserving canonical order
    by_group: dict[str, list[Exercise]] = defaultdict(list)
    ungrouped: list[Exercise] = []
    for ex in exercises:
        if ex.muscle_group:
            by_group[ex.muscle_group.value].append(ex)
        else:
            ungrouped.append(ex)

    groups = [
        (mg, by_group[mg])
        for mg in _MG_ORDER
        if mg in by_group
    ]
    for mg, exs in by_group.items():
        if mg not in _MG_ORDER:
            groups.append((mg, exs))

    error = request.query_params.get("error")

    return templates.TemplateResponse(
        "exercises.html",
        {
            "request": request,
            "user": current_user,
            "groups": groups,
            "ungrouped": ungrouped,
            "total": len(exercises),
            "muscle_group_options": _MG_ORDER,
            "category_options": [c.value for c in ExerciseCategory],
            "error": error,
        },
    )


@router.post("/new")
async def create_exercise(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()
    name = str(form.get("name", "")).strip()
    category_str = str(form.get("category", "accessory")).strip()
    muscle_group_str = str(form.get("muscle_group", "")).strip()

    if not name:
        return RedirectResponse(url="/exercises?error=Name+is+required", status_code=303)

    duplicate = (
        db.query(Exercise)
        .filter(
            func.lower(Exercise.name) == name.lower(),
            Exercise.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if duplicate:
        return RedirectResponse(
            url="/exercises?error=An+exercise+with+that+name+already+exists",
            status_code=303,
        )

    category = (
        ExerciseCategory(category_str)
        if category_str in [c.value for c in ExerciseCategory]
        else ExerciseCategory.accessory
    )
    muscle_group = (
        MuscleGroup(muscle_group_str)
        if muscle_group_str in _MG_ORDER
        else None
    )

    db.add(Exercise(
        name=name,
        category=category,
        muscle_group=muscle_group,
        creator_user_id=current_user.id,
    ))
    db.commit()
    return RedirectResponse(url="/exercises", status_code=303)


@router.post("/{exercise_id}/edit")
async def edit_exercise(
    exercise_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    ex = (
        db.query(Exercise)
        .filter(
            Exercise.id == exercise_id,
            Exercise.creator_user_id == current_user.id,
            Exercise.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if not ex:
        raise HTTPException(status_code=404)

    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return RedirectResponse(url="/exercises?error=Name+is+required", status_code=303)

    duplicate = (
        db.query(Exercise)
        .filter(
            func.lower(Exercise.name) == name.lower(),
            Exercise.id != exercise_id,
            Exercise.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if duplicate:
        return RedirectResponse(
            url="/exercises?error=An+exercise+with+that+name+already+exists",
            status_code=303,
        )

    category_str = str(form.get("category", "accessory")).strip()
    muscle_group_str = str(form.get("muscle_group", "")).strip()
    ex.name = name
    ex.category = (
        ExerciseCategory(category_str)
        if category_str in [c.value for c in ExerciseCategory]
        else ex.category
    )
    ex.muscle_group = MuscleGroup(muscle_group_str) if muscle_group_str in _MG_ORDER else None
    db.commit()
    return RedirectResponse(url="/exercises", status_code=303)


@router.post("/{exercise_id}/archive")
def archive_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    ex = (
        db.query(Exercise)
        .filter(
            Exercise.id == exercise_id,
            Exercise.creator_user_id == current_user.id,
            Exercise.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if not ex:
        raise HTTPException(status_code=404)

    ex.is_archived = True
    db.commit()
    return RedirectResponse(url="/exercises", status_code=303)
