"""
Calendar router — Phase 5.

Routes:
  GET  /calendar                          → monthly calendar view
  GET  /calendar?year=Y&month=M          → specific month
  GET  /calendar/start/{program_id}      → start program form
  POST /calendar/start/{program_id}      → create ProgramRun + ScheduledWorkouts
  POST /calendar/reschedule/{sw_id}      → change scheduled date
  POST /calendar/skip/{sw_id}            → skip a scheduled workout
  POST /calendar/complete-run/{run_id}   → mark ProgramRun as complete
"""
import calendar as cal_module
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Block, Program, ProgramRun, ScheduledWorkout, TrainingDay, User,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prev_next_month(year: int, month: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return (prev_year, prev_month) and (next_year, next_month)."""
    if month == 1:
        prev = (year - 1, 12)
    else:
        prev = (year, month - 1)
    if month == 12:
        nxt = (year + 1, 1)
    else:
        nxt = (year, month + 1)
    return prev, nxt


def _load_month_workouts(
    year: int, month: int, user_id: int, db: Session
) -> dict[date, list[ScheduledWorkout]]:
    """Return {date: [ScheduledWorkout, ...]} for all non-skipped workouts in the month."""
    first_day = date(year, month, 1)
    last_day = date(year, month, cal_module.monthrange(year, month)[1])

    workouts = (
        db.query(ScheduledWorkout)
        .join(ProgramRun)
        .filter(
            ProgramRun.user_id == user_id,
            ScheduledWorkout.scheduled_date >= first_day,
            ScheduledWorkout.scheduled_date <= last_day,
            ScheduledWorkout.skipped == False,  # noqa: E712
        )
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.program_run).joinedload(ProgramRun.program),
        )
        .all()
    )

    by_date: dict[date, list] = defaultdict(list)
    for sw in workouts:
        by_date[sw.scheduled_date].append(sw)
    return dict(by_date)


# ---------------------------------------------------------------------------
# Calendar view
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
def calendar_view(
    request: Request,
    year: int = 0,
    month: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month

    days_in_month = cal_module.monthrange(year, month)[1]
    first_day = date(year, month, 1)
    prev_month, next_month = _prev_next_month(year, month)
    workout_by_date = _load_month_workouts(year, month, current_user.id, db)

    # Pre-compute per-day data so the template doesn't need to construct date objects
    days_data = [
        {
            "day_num": d,
            "date": date(year, month, d),
            "is_today": date(year, month, d) == today,
            "is_past": date(year, month, d) < today,
            "workouts": workout_by_date.get(date(year, month, d), []),
        }
        for d in range(1, days_in_month + 1)
    ]

    # Active program runs (not yet completed)
    active_runs = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.user_id == current_user.id,
            ProgramRun.completed_at == None,  # noqa: E711
        )
        .options(joinedload(ProgramRun.program))
        .order_by(ProgramRun.started_at.desc())
        .all()
    )

    # For each active run, count done vs total workouts
    run_stats = []
    for run in active_runs:
        total = (
            db.query(ScheduledWorkout)
            .filter(ScheduledWorkout.program_run_id == run.id)
            .count()
        )
        done = (
            db.query(ScheduledWorkout)
            .filter(
                ScheduledWorkout.program_run_id == run.id,
                ScheduledWorkout.completed_at != None,  # noqa: E711
            )
            .count()
        )
        remaining = (
            db.query(ScheduledWorkout)
            .filter(
                ScheduledWorkout.program_run_id == run.id,
                ScheduledWorkout.completed_at == None,  # noqa: E711
                ScheduledWorkout.skipped == False,  # noqa: E712
            )
            .count()
        )
        run_stats.append({
            "run": run,
            "total": total,
            "done": done,
            "remaining": remaining,
            "is_finished": total > 0 and remaining == 0,
        })

    # Missed workouts (past, incomplete, not skipped)
    missed = (
        db.query(ScheduledWorkout)
        .join(ProgramRun)
        .filter(
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.scheduled_date < today,
            ScheduledWorkout.completed_at == None,  # noqa: E711
            ScheduledWorkout.skipped == False,  # noqa: E712
        )
        .options(
            joinedload(ScheduledWorkout.block),
            joinedload(ScheduledWorkout.training_day),
            joinedload(ScheduledWorkout.program_run).joinedload(ProgramRun.program),
        )
        .order_by(ScheduledWorkout.scheduled_date)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "user": current_user,
            "today": today,
            "year": year,
            "month": month,
            "month_name": first_day.strftime("%B %Y"),
            "first_weekday": first_day.weekday(),  # 0=Mon, 6=Sun
            "days_in_month": days_in_month,
            "days_data": days_data,
            "prev_month": prev_month,
            "next_month": next_month,
            "run_stats": run_stats,
            "missed": missed,
        },
    )


# ---------------------------------------------------------------------------
# Start program
# ---------------------------------------------------------------------------

@router.get("/start/{program_id}", response_class=HTMLResponse)
def start_program_form(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.is_archived == False,  # noqa: E712
            Program.is_draft == False,
        )
        .options(
            joinedload(Program.blocks).joinedload(Block.training_days)
        )
        .first()
    )
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    # Only the program's creator can start it (unless it's public)
    if program.creator_user_id != current_user.id and not program.is_public:
        raise HTTPException(status_code=403)

    total_training_days = sum(len(b.training_days) for b in program.blocks)

    return templates.TemplateResponse(
        request,
        "program_start.html",
        {
            "user": current_user,
            "program": program,
            "today": date.today(),
            "total_training_days": total_training_days,
        },
    )


@router.post("/start/{program_id}")
async def start_program(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()

    program = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.is_archived == False,  # noqa: E712
            Program.is_draft == False,
        )
        .options(
            joinedload(Program.blocks).joinedload(Block.training_days)
        )
        .first()
    )
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    if program.creator_user_id != current_user.id and not program.is_public:
        raise HTTPException(status_code=403)

    # Reject duplicate: user already has an active run for this program
    existing_run = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.user_id == current_user.id,
            ProgramRun.program_id == program_id,
            ProgramRun.completed_at == None,  # noqa: E711
        )
        .first()
    )
    if existing_run:
        raise HTTPException(status_code=400, detail="This program is already active")

    # Parse start date
    start_date_str = str(form.get("start_date", ""))
    try:
        start_date = date.fromisoformat(start_date_str)
    except ValueError:
        start_date = date.today()

    # Parse selected training weekdays (0=Mon … 6=Sun)
    weekday_strs = form.getlist("weekdays")
    training_weekdays: list[int] = sorted(set(
        int(w) for w in weekday_strs if w.isdigit() and 0 <= int(w) <= 6
    ))
    if not training_weekdays:
        training_weekdays = [0, 2, 4]  # Mon/Wed/Fri fallback

    # All training days in program order
    all_training_days = [
        td
        for block in sorted(program.blocks, key=lambda b: b.block_number)
        for td in sorted(block.training_days, key=lambda d: d.day_number)
    ]
    if not all_training_days:
        raise HTTPException(status_code=400, detail="Program has no training days")

    # Round number = previous runs + 1
    round_number = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.program_id == program_id,
            ProgramRun.user_id == current_user.id,
        )
        .count()
    ) + 1

    # Create ProgramRun
    run = ProgramRun(
        user_id=current_user.id,
        program_id=program_id,
        round_number=round_number,
        current_block_id=all_training_days[0].block_id,
        current_day_id=all_training_days[0].id,
    )
    db.add(run)
    db.flush()

    # Assign each training day to the next available training date
    current_date = start_date
    td_idx = 0
    # Safety limit: don't loop forever if training_weekdays is empty
    safety = len(all_training_days) * 14
    steps = 0
    while td_idx < len(all_training_days) and steps < safety:
        if current_date.weekday() in training_weekdays:
            td = all_training_days[td_idx]
            db.add(ScheduledWorkout(
                program_run_id=run.id,
                block_id=td.block_id,
                training_day_id=td.id,
                scheduled_date=current_date,
            ))
            td_idx += 1
        current_date += timedelta(days=1)
        steps += 1

    db.commit()
    return RedirectResponse(url="/calendar", status_code=303)


# ---------------------------------------------------------------------------
# Reschedule / skip
# ---------------------------------------------------------------------------

@router.post("/reschedule/{sw_id}")
async def reschedule_workout(
    sw_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()

    sw = (
        db.query(ScheduledWorkout)
        .join(ProgramRun)
        .filter(
            ScheduledWorkout.id == sw_id,
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.completed_at == None,  # noqa: E711
        )
        .first()
    )
    if not sw:
        raise HTTPException(status_code=404)

    new_date_str = str(form.get("new_date", ""))
    try:
        sw.scheduled_date = date.fromisoformat(new_date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    db.commit()
    return RedirectResponse(url="/calendar", status_code=303)


@router.post("/skip/{sw_id}")
def skip_workout(
    sw_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    sw = (
        db.query(ScheduledWorkout)
        .join(ProgramRun)
        .filter(
            ScheduledWorkout.id == sw_id,
            ProgramRun.user_id == current_user.id,
            ScheduledWorkout.completed_at == None,  # noqa: E711
        )
        .first()
    )
    if not sw:
        raise HTTPException(status_code=404)

    sw.skipped = True
    db.commit()
    return RedirectResponse(url="/calendar", status_code=303)


# ---------------------------------------------------------------------------
# Complete a program run
# ---------------------------------------------------------------------------

@router.post("/complete-run/{run_id}")
def complete_program_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    run = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.id == run_id,
            ProgramRun.user_id == current_user.id,
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404)

    run.completed_at = datetime.utcnow()
    db.commit()
    # Redirect to PRs so user can enter new 1RMs
    return RedirectResponse(url="/prs", status_code=303)


# ---------------------------------------------------------------------------
# Abandon a program run (stop it without completing all sessions)
# ---------------------------------------------------------------------------

@router.post("/abandon/{run_id}")
def abandon_program_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    run = (
        db.query(ProgramRun)
        .filter(
            ProgramRun.id == run_id,
            ProgramRun.user_id == current_user.id,
            ProgramRun.completed_at == None,  # noqa: E711
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404)

    run.completed_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/calendar", status_code=303)
