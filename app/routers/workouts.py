"""
Workouts router — Today's Workout view and completion.
Phase 3.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    AccessoryBest, Block, CompletedSet, Exercise, ExerciseCategory, IntensityType,
    OneRepMax, PlannedSet, ProgramRun, ScheduledWorkout, TrainingDay, User,
)
from app.utils import calculate_weight

router = APIRouter(prefix="/workouts", tags=["workouts"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_1rm(user_id: int, exercise_id: int, db: Session) -> Optional[float]:
    """Return the most recent 1RM weight for a user+exercise, or None."""
    entry = (
        db.query(OneRepMax)
        .filter(OneRepMax.user_id == user_id, OneRepMax.exercise_id == exercise_id)
        .order_by(OneRepMax.date_set.desc(), OneRepMax.id.desc())
        .first()
    )
    return entry.weight_kg if entry else None


def _get_last_used_weight(user_id: int, exercise_id: int, db: Session) -> Optional[float]:
    """Return the last weight logged by the user for an exercise (for accessory pre-fill)."""
    result = (
        db.query(CompletedSet.actual_weight_kg)
        .join(PlannedSet, CompletedSet.planned_set_id == PlannedSet.id)
        .join(ScheduledWorkout, CompletedSet.scheduled_workout_id == ScheduledWorkout.id)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == user_id,
            PlannedSet.exercise_id == exercise_id,
            CompletedSet.actual_weight_kg.isnot(None),
        )
        .order_by(CompletedSet.logged_at.desc())
        .first()
    )
    return result[0] if result else None


def _build_exercise_groups(
    planned_sets: list[PlannedSet],
    user_id: int,
    db: Session,
) -> list[dict]:
    """
    Group consecutive planned sets by (exercise_id, intensity_type, intensity_value).
    Calculates weights for percentage-based sets and fetches last-used weights for accessories.
    """
    groups: list[dict] = []
    current: Optional[dict] = None

    for ps in planned_sets:
        key = (ps.exercise_id, ps.intensity_type, ps.intensity_value)
        if current is None or current["key"] != key:
            if current:
                groups.append(current)

            # Determine display weight / pre-fill weight
            calculated_weight: Optional[float] = None
            one_rm_used: Optional[float] = None
            missing_1rm = False
            rm_exercise_name: Optional[str] = None

            if ps.intensity_type == IntensityType.percentage and ps.intensity_value:
                rm_exercise_id = ps.exercise.reference_exercise_id or ps.exercise_id
                if ps.exercise.reference_exercise_id:
                    ref_ex = db.query(Exercise).filter(Exercise.id == ps.exercise.reference_exercise_id).first()
                    rm_exercise_name = ref_ex.name if ref_ex else None
                one_rm_used = _get_current_1rm(user_id, rm_exercise_id, db)
                if one_rm_used:
                    calculated_weight = calculate_weight(one_rm_used, ps.intensity_value)
                else:
                    missing_1rm = True

            last_weight: Optional[float] = None
            if ps.exercise.category == ExerciseCategory.accessory:
                last_weight = _get_last_used_weight(user_id, ps.exercise_id, db)

            current = {
                "key": key,
                "exercise": ps.exercise,
                "intensity_type": ps.intensity_type,
                "intensity_value": ps.intensity_value,
                "calculated_weight": calculated_weight,
                "one_rm_used": one_rm_used,
                "missing_1rm": missing_1rm,
                "rm_exercise_name": rm_exercise_name,
                "last_weight": last_weight,
                "sets": [],
            }

        current["sets"].append(ps)

    if current:
        groups.append(current)

    return groups


def _get_workout_or_404(
    scheduled_workout_id: int, user_id: int, db: Session
) -> ScheduledWorkout:
    """Load a ScheduledWorkout, verifying it belongs to the current user."""
    workout = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ScheduledWorkout.id == scheduled_workout_id,
            ProgramRun.user_id == user_id,
        )
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.program_run).joinedload(ProgramRun.program),
        )
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/today")
def today_redirect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect to today's scheduled workout, or back to home if none."""
    today = date.today()
    workout = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date == today,
            ScheduledWorkout.skipped == False,  # noqa: E712
        )
        .first()
    )
    if workout:
        return RedirectResponse(url=f"/workouts/{workout.id}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@router.get("/{scheduled_workout_id}", response_class=HTMLResponse)
def workout_view(
    scheduled_workout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)

    planned_sets = (
        db.query(PlannedSet)
        .options(joinedload(PlannedSet.exercise))
        .filter(PlannedSet.training_day_id == workout.training_day_id)
        .order_by(PlannedSet.order, PlannedSet.set_number)
        .all()
    )

    exercise_groups = _build_exercise_groups(planned_sets, current_user.id, db)

    # All non-archived exercises for the substitution modal
    all_exercises = (
        db.query(Exercise)
        .filter(Exercise.is_archived == False)  # noqa: E712
        .order_by(Exercise.name)
        .all()
    )

    return templates.TemplateResponse(
        "workout_view.html",
        {
            "request": request,
            "user": current_user,
            "workout": workout,
            "exercise_groups": exercise_groups,
            "all_exercises": all_exercises,
            "already_completed": workout.completed_at is not None,
        },
    )


@router.post("/{scheduled_workout_id}/complete")
async def complete_workout(
    scheduled_workout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from datetime import datetime, timezone

    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)

    if workout.completed_at is not None:
        return RedirectResponse(url="/", status_code=303)

    form = await request.form()
    session_notes = str(form.get("session_notes", "")).strip() or None
    planned_set_ids: list[str] = form.getlist("planned_set_id")

    for ps_id_str in planned_set_ids:
        try:
            ps_id = int(ps_id_str)
        except ValueError:
            continue

        weight_str = str(form.get(f"weight_kg_{ps_id}", "")).strip()
        reps_str = str(form.get(f"actual_reps_{ps_id}", "")).strip()
        sub_str = str(form.get(f"sub_{ps_id}", "")).strip()

        actual_weight: Optional[float] = float(weight_str) if weight_str else None
        actual_reps: Optional[int] = int(reps_str) if reps_str else None
        sub_id: Optional[int] = int(sub_str) if sub_str else None

        # Determine if the user modified the prescribed values
        ps = (
            db.query(PlannedSet)
            .options(joinedload(PlannedSet.exercise))
            .filter(PlannedSet.id == ps_id)
            .first()
        )
        was_modified = False
        if ps and actual_reps is not None and actual_reps != ps.reps:
            was_modified = True

        completed = CompletedSet(
            scheduled_workout_id=workout.id,
            planned_set_id=ps_id,
            actual_weight_kg=actual_weight,
            actual_reps=actual_reps,
            was_modified=was_modified,
            substituted_exercise_id=sub_id,
        )
        db.add(completed)

        # ── Auto-update AccessoryBest ────────────────────────────────────
        if (
            ps
            and actual_weight is not None
            and actual_reps is not None
            and ps.exercise.category == ExerciseCategory.accessory
        ):
            # Use the substitute exercise's best if the set was substituted
            best_exercise_id = sub_id if sub_id else ps.exercise_id
            existing = (
                db.query(AccessoryBest)
                .filter(
                    AccessoryBest.user_id == current_user.id,
                    AccessoryBest.exercise_id == best_exercise_id,
                )
                .first()
            )
            is_new_best = (
                not existing
                or actual_weight > existing.weight_kg
                or (actual_weight == existing.weight_kg and actual_reps > existing.reps)
            )
            if is_new_best:
                if existing:
                    existing.weight_kg = actual_weight
                    existing.reps = actual_reps
                    existing.date_set = workout.scheduled_date
                else:
                    db.add(AccessoryBest(
                        user_id=current_user.id,
                        exercise_id=best_exercise_id,
                        weight_kg=actual_weight,
                        reps=actual_reps,
                        date_set=workout.scheduled_date,
                    ))

    workout.completed_at = datetime.now(timezone.utc)
    workout.session_notes = session_notes
    db.commit()

    return RedirectResponse(url="/", status_code=303)
