"""
FastAPI application entry point for the PowerBuilding Workout Tracker.
"""
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

load_dotenv()

from app.auth import get_current_user
from app.database import get_db
from app.models import Exercise, OneRepMax, ProgramRun, ScheduledWorkout, User
from app.routers import auth, programs, workouts, prs, calendar, exercises, volume, progress, dashboard, ai

app = FastAPI(title="PowerBuilding Workout Tracker")

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(programs.router)
app.include_router(workouts.router)
app.include_router(prs.router)
app.include_router(calendar.router)
app.include_router(exercises.router)
app.include_router(volume.router)
app.include_router(progress.router)
app.include_router(dashboard.router)
app.include_router(ai.router)


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def homepage(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today = date.today()

    # ── Today's scheduled workout ────────────────────────────────────────────
    today_workout = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date == today,
            ScheduledWorkout.skipped == False,  # noqa: E712
        )
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
        )
        .first()
    )

    # ── Current 1RMs for the three main lifts ────────────────────────────────
    def _get_1rm(name: str) -> float | None:
        ex = db.query(Exercise).filter(Exercise.name == name).first()
        if not ex:
            return None
        entry = (
            db.query(OneRepMax)
            .filter(OneRepMax.user_id == current_user.id, OneRepMax.exercise_id == ex.id)
            .order_by(OneRepMax.date_set.desc(), OneRepMax.id.desc())
            .first()
        )
        return entry.weight_kg if entry else None

    squat_1rm    = _get_1rm("Squat")
    bench_1rm    = _get_1rm("Bench Press")
    deadlift_1rm = _get_1rm("Deadlift")

    # ── Active program run ───────────────────────────────────────────────────
    active_run = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.user_id == current_user.id,
            ProgramRun.completed_at == None,  # noqa: E711
        )
        .options(joinedload(ProgramRun.program))
        .order_by(ProgramRun.started_at.desc())
        .first()
    )

    run_stats: dict | None = None
    if active_run:
        total = (
            db.query(ScheduledWorkout)
            .filter(ScheduledWorkout.program_run_id == active_run.id)
            .count()
        )
        done = (
            db.query(ScheduledWorkout)
            .filter(
                ScheduledWorkout.program_run_id == active_run.id,
                ScheduledWorkout.completed_at != None,  # noqa: E711
            )
            .count()
        )
        run_stats = {
            "total": total,
            "done": done,
            "pct": int(done / total * 100) if total else 0,
        }

    # ── Last 3 completed sessions ────────────────────────────────────────────
    recent_sessions = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.completed_at != None,  # noqa: E711
        )
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.program_run).joinedload(ProgramRun.program),
        )
        .order_by(ScheduledWorkout.completed_at.desc())
        .limit(3)
        .all()
    )

    # ── Sessions completed this calendar week (Mon–today) ────────────────────
    week_start = today - timedelta(days=today.weekday())
    sessions_this_week = (
        db.query(ScheduledWorkout)
        .join(ProgramRun, ScheduledWorkout.program_run_id == ProgramRun.id)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date >= week_start,
            ScheduledWorkout.completed_at != None,  # noqa: E711
        )
        .count()
    )

    # ── First-time "get started" state ───────────────────────────────────────
    has_any_1rm = any([squat_1rm, bench_1rm, deadlift_1rm])
    has_any_run = (
        db.query(ProgramRun)
        .filter(ProgramRun.user_id == current_user.id)
        .first()
    ) is not None
    show_getting_started = not has_any_1rm and not has_any_run

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "today": today,
            "today_workout": today_workout,
            "squat_1rm": squat_1rm,
            "bench_1rm": bench_1rm,
            "deadlift_1rm": deadlift_1rm,
            "active_run": active_run,
            "run_stats": run_stats,
            "recent_sessions": recent_sessions,
            "sessions_this_week": sessions_this_week,
            "show_getting_started": show_getting_started,
        },
    )


# ---------------------------------------------------------------------------
# Global exception handler for 401 — redirect to login page
# ---------------------------------------------------------------------------

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException) -> RedirectResponse:
    return RedirectResponse(url="/auth/login")
