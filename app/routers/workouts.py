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
    AccessoryBest, Block, CompletedSet, Exercise, ExerciseCategory,
    IntensityType, OneRepMax, PlannedSet, ProgramRun, ScheduledWorkout, TrainingDay, User,
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
    Group planned sets by exercise_id only.
    Calculates per-set weights and fetches last-used weights for accessories.
    """
    groups: list[dict] = []
    current: Optional[dict] = None

    for ps in planned_sets:
        key = ps.exercise_id
        if current is None or current["key"] != key:
            if current:
                groups.append(current)

            one_rm_used: Optional[float] = None
            missing_1rm = False
            rm_exercise_name: Optional[str] = None

            if ps.intensity_type == IntensityType.percentage and ps.intensity_value:
                rm_exercise_id = ps.exercise.reference_exercise_id or ps.exercise_id
                if ps.exercise.reference_exercise_id:
                    ref_ex = db.query(Exercise).filter(Exercise.id == ps.exercise.reference_exercise_id).first()
                    rm_exercise_name = ref_ex.name if ref_ex else None
                one_rm_used = _get_current_1rm(user_id, rm_exercise_id, db)
                if not one_rm_used:
                    missing_1rm = True

            last_weight: Optional[float] = None
            if ps.exercise.category == ExerciseCategory.accessory:
                last_weight = _get_last_used_weight(user_id, ps.exercise_id, db)

            current = {
                "key": key,
                "exercise": ps.exercise,
                "one_rm_used": one_rm_used,
                "missing_1rm": missing_1rm,
                "rm_exercise_name": rm_exercise_name,
                "last_weight": last_weight,
                "set_weights": {},
                "sets": [],
            }
        else:
            # For subsequent sets in the same group, check if 1RM lookup is needed
            if (
                ps.intensity_type == IntensityType.percentage
                and ps.intensity_value
                and current["one_rm_used"] is None
                and not current["missing_1rm"]
            ):
                rm_exercise_id = ps.exercise.reference_exercise_id or ps.exercise_id
                current["one_rm_used"] = _get_current_1rm(user_id, rm_exercise_id, db)
                if not current["one_rm_used"]:
                    current["missing_1rm"] = True

        # Calculate per-set weight
        calc_w: Optional[float] = None
        if ps.intensity_type == IntensityType.percentage and ps.intensity_value and current["one_rm_used"]:
            calc_w = calculate_weight(current["one_rm_used"], ps.intensity_value)
        elif ps.intensity_type != IntensityType.percentage:
            calc_w = current["last_weight"]
        current["set_weights"][ps.id] = calc_w

        # Mark missing_1rm if any percentage set has no 1RM
        if ps.intensity_type == IntensityType.percentage and ps.intensity_value and current["one_rm_used"] is None:
            current["missing_1rm"] = True

        current["sets"].append(ps)

    if current:
        groups.append(current)

    return groups


def _get_workout_or_404(
    scheduled_workout_id: int, user_id: int, db: Session
) -> ScheduledWorkout:
    """Load a ScheduledWorkout, verifying it belongs to the current user.

    Raises 404 if the workout doesn't exist, 403 if it belongs to another user.
    """
    workout = (
        db.query(ScheduledWorkout)
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.program_run).joinedload(ProgramRun.program),
        )
        .filter(ScheduledWorkout.id == scheduled_workout_id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.program_run.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access forbidden")
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


def _build_extra_groups(workout_id: int, db: Session) -> list[dict]:
    """
    Return groups for unplanned sets added to a workout (planned_set_id IS NULL).
    Used to show extra exercises in the active-workout view before completion.
    """
    unplanned = (
        db.query(CompletedSet)
        .options(joinedload(CompletedSet.substituted_exercise))
        .filter(
            CompletedSet.scheduled_workout_id == workout_id,
            CompletedSet.planned_set_id == None,  # noqa: E711
        )
        .order_by(CompletedSet.logged_at, CompletedSet.id)
        .all()
    )
    seen: dict[str, dict] = {}
    for cs in unplanned:
        ex_name = cs.substituted_exercise.name if cs.substituted_exercise else "Unknown"
        if ex_name not in seen:
            seen[ex_name] = {"exercise_name": ex_name, "sets": []}
        seen[ex_name]["sets"].append(cs)
    return list(seen.values())


def _build_completed_groups(workout_id: int, db: Session) -> list[dict]:
    """
    Group CompletedSets for a finished workout by exercise name.
    Planned sets (planned_set_id IS NOT NULL) come first ordered by plan position.
    Unplanned sets added post-completion (planned_set_id IS NULL) follow, ordered by logged_at.
    Respects substitutions: uses the substituted exercise name when present.
    Returns a list of {exercise_name, sets} dicts.
    """
    all_sets = (
        db.query(CompletedSet)
        .options(
            joinedload(CompletedSet.planned_set).joinedload(PlannedSet.exercise),
            joinedload(CompletedSet.substituted_exercise),
        )
        .filter(CompletedSet.scheduled_workout_id == workout_id)
        .all()
    )

    # Planned sets first (sorted by plan order), unplanned last (sorted by logged_at)
    planned = [cs for cs in all_sets if cs.planned_set_id is not None]
    unplanned = [cs for cs in all_sets if cs.planned_set_id is None]
    planned.sort(key=lambda cs: (cs.planned_set.order, cs.planned_set.set_number))
    unplanned.sort(key=lambda cs: (cs.logged_at, cs.id))

    seen: dict[str, dict] = {}
    for cs in planned + unplanned:
        if cs.planned_set_id is not None:
            ex_name = (
                cs.substituted_exercise.name
                if cs.substituted_exercise
                else cs.planned_set.exercise.name
            )
        else:
            # Unplanned set: exercise stored in substituted_exercise_id
            ex_name = cs.substituted_exercise.name if cs.substituted_exercise else "Unknown"
        if ex_name not in seen:
            seen[ex_name] = {"exercise_name": ex_name, "sets": []}
        seen[ex_name]["sets"].append(cs)

    return list(seen.values())


@router.get("/{scheduled_workout_id}", response_class=HTMLResponse)
def workout_view(
    scheduled_workout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)
    already_completed = workout.completed_at is not None

    planned_sets = (
        db.query(PlannedSet)
        .options(joinedload(PlannedSet.exercise))
        .filter(PlannedSet.training_day_id == workout.training_day_id)
        .order_by(PlannedSet.order, PlannedSet.set_number)
        .all()
    )

    exercise_groups = _build_exercise_groups(planned_sets, current_user.id, db)
    completed_groups = _build_completed_groups(workout.id, db) if already_completed else []
    extra_groups = _build_extra_groups(workout.id, db) if not already_completed else []

    # All non-archived exercises for the substitution modal
    all_exercises = (
        db.query(Exercise)
        .filter(Exercise.is_archived == False)  # noqa: E712
        .order_by(Exercise.name)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "workout_view.html",
        {
            "user": current_user,
            "workout": workout,
            "exercise_groups": exercise_groups,
            "completed_groups": completed_groups,
            "all_exercises": all_exercises,
            "already_completed": already_completed,
            "extra_groups": extra_groups,
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


@router.post("/{scheduled_workout_id}/add-exercise")
async def add_exercise_to_workout(
    scheduled_workout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Add extra sets for a chosen exercise to an existing (completed) workout."""
    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)

    form = await request.form()
    exercise_id_str = str(form.get("exercise_id", "")).strip()
    if not exercise_id_str:
        return RedirectResponse(url=f"/workouts/{scheduled_workout_id}", status_code=303)

    try:
        exercise_id = int(exercise_id_str)
    except ValueError:
        return RedirectResponse(url=f"/workouts/{scheduled_workout_id}", status_code=303)

    exercise = (
        db.query(Exercise)
        .filter(Exercise.id == exercise_id, Exercise.is_archived == False)  # noqa: E712
        .first()
    )
    if not exercise:
        return RedirectResponse(url=f"/workouts/{scheduled_workout_id}", status_code=303)

    reps_list = form.getlist("reps")
    weight_list = form.getlist("weight_kg")
    rpe_list = form.getlist("rpe")

    for i, reps_raw in enumerate(reps_list):
        reps_str = str(reps_raw).strip()
        weight_str = str(weight_list[i]).strip() if i < len(weight_list) else ""
        rpe_str = str(rpe_list[i]).strip() if i < len(rpe_list) else ""

        actual_reps: Optional[int] = int(reps_str) if reps_str else None
        actual_weight: Optional[float] = float(weight_str) if weight_str else None
        notes: Optional[str] = f"RPE {rpe_str}" if rpe_str else None

        db.add(CompletedSet(
            scheduled_workout_id=workout.id,
            planned_set_id=None,
            substituted_exercise_id=exercise_id,
            actual_weight_kg=actual_weight,
            actual_reps=actual_reps,
            was_modified=False,
            notes=notes,
        ))

    db.commit()
    return RedirectResponse(url=f"/workouts/{scheduled_workout_id}?added=1", status_code=303)


@router.post("/{scheduled_workout_id}/update-set/{completed_set_id}")
async def update_completed_set(
    scheduled_workout_id: int,
    completed_set_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Edit reps and/or weight on an existing CompletedSet."""
    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)

    cs = (
        db.query(CompletedSet)
        .filter(
            CompletedSet.id == completed_set_id,
            CompletedSet.scheduled_workout_id == workout.id,
        )
        .first()
    )
    if not cs:
        raise HTTPException(status_code=404, detail="Set not found")

    form = await request.form()
    reps_str = str(form.get("actual_reps", "")).strip()
    weight_str = str(form.get("actual_weight_kg", "")).strip()

    cs.actual_reps = int(reps_str) if reps_str else None
    cs.actual_weight_kg = float(weight_str) if weight_str else None
    db.commit()

    return RedirectResponse(url=f"/workouts/{scheduled_workout_id}", status_code=303)


@router.post("/{scheduled_workout_id}/add-comment")
async def add_comment_to_workout(
    scheduled_workout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Update the session notes / comment on a workout."""
    workout = _get_workout_or_404(scheduled_workout_id, current_user.id, db)

    form = await request.form()
    comment = str(form.get("comment", "")).strip()
    workout.session_notes = comment or None
    db.commit()

    return RedirectResponse(url=f"/workouts/{scheduled_workout_id}?commented=1", status_code=303)
