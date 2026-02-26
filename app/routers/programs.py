"""
Programs router — Program Builder Wizard + program list + duplicate.
Phase 4.

Wizard flow (draft saved to DB at each step):
  GET  /programs               → program list
  GET  /programs/new           → Step 1: name/desc/block count
  POST /programs/new           → save Step 1, redirect to Step 2
  GET  /programs/{id}/blocks   → Step 2: name blocks + day counts
  POST /programs/{id}/blocks   → save Step 2, redirect to Step 3
  GET  /programs/{id}/days     → Step 3: exercises per day (?block=N&day=N)
  POST /programs/{id}/days     → save one day, redirect to next day or review
  GET  /programs/{id}/review   → Step 4: read-only summary
  POST /programs/{id}/confirm  → mark is_draft=False
  POST /programs/{id}/duplicate→ deep copy → redirect to review
  POST /programs/{id}/delete   → soft-archive
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Block, Exercise, IntensityType,
    PlannedSet, Program, TrainingDay, User,
)

router = APIRouter(prefix="/programs", tags=["programs"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_program_or_404(program_id: int, user_id: int, db: Session) -> Program:
    prog = db.query(Program).filter(
        Program.id == program_id,
        Program.creator_user_id == user_id,
        Program.is_archived == False,  # noqa: E712
    ).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Program not found")
    return prog


def _load_full(program_id: int, user_id: int, db: Session) -> Program:
    prog = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.creator_user_id == user_id,
            Program.is_archived == False,  # noqa: E712
        )
        .options(
            joinedload(Program.blocks)
            .joinedload(Block.training_days)
            .joinedload(TrainingDay.planned_sets)
            .joinedload(PlannedSet.exercise)
        )
        .first()
    )
    if not prog:
        raise HTTPException(status_code=404, detail="Program not found")
    return prog


def _all_exercises(db: Session) -> list[Exercise]:
    return (
        db.query(Exercise)
        .filter(Exercise.is_archived == False)  # noqa: E712
        .order_by(Exercise.category, Exercise.name)
        .all()
    )


def _copy_block1_to_all(program: Program, db: Session) -> None:
    """Copy all PlannedSets from Block 1 to every other block, matching days by day_number."""
    blocks = sorted(program.blocks, key=lambda b: b.block_number)
    if len(blocks) < 2:
        return

    source_block = blocks[0]
    source_days = {d.day_number: d for d in source_block.training_days}

    for target_block in blocks[1:]:
        for target_day in target_block.training_days:
            source_day = source_days.get(target_day.day_number)
            if not source_day or not source_day.planned_sets:
                continue
            db.query(PlannedSet).filter(PlannedSet.training_day_id == target_day.id).delete()
            db.flush()
            for ps in sorted(source_day.planned_sets, key=lambda s: s.order):
                db.add(PlannedSet(
                    training_day_id=target_day.id,
                    exercise_id=ps.exercise_id,
                    order=ps.order,
                    set_number=ps.set_number,
                    reps=ps.reps,
                    intensity_type=ps.intensity_type,
                    intensity_value=ps.intensity_value,
                    notes=ps.notes,
                ))


def _build_exercise_groups(planned_sets) -> list[dict]:
    """
    Group consecutive PlannedSets by exercise into exercise cards.
    Within each card, consecutive sets with identical (reps, intensity_type, intensity_value)
    are merged into a set line with a count.
    """
    exercise_groups: list[dict] = []
    for ps in sorted(planned_sets, key=lambda s: s.order):
        if exercise_groups and exercise_groups[-1]["exercise_id"] == ps.exercise_id:
            eg = exercise_groups[-1]
        else:
            eg = {
                "exercise_id": ps.exercise_id,
                "exercise": ps.exercise,
                "set_lines": [],
            }
            exercise_groups.append(eg)

        key = (ps.reps, ps.intensity_type, ps.intensity_value)
        if eg["set_lines"] and eg["set_lines"][-1]["_key"] == key:
            eg["set_lines"][-1]["count"] += 1
        else:
            eg["set_lines"].append({
                "_key": key,
                "count": 1,
                "reps": ps.reps,
                "intensity_type": ps.intensity_type,
                "intensity_value": ps.intensity_value,
                "notes": ps.notes,
            })

    for eg in exercise_groups:
        for sl in eg["set_lines"]:
            del sl["_key"]
    return exercise_groups


# ---------------------------------------------------------------------------
# Program list
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
def program_list(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    my_programs = (
        db.query(Program)
        .filter(
            Program.creator_user_id == current_user.id,
            Program.is_archived == False,  # noqa: E712
        )
        .order_by(Program.created_at.desc())
        .all()
    )
    draft = next((p for p in my_programs if p.is_draft), None)
    confirmed = [p for p in my_programs if not p.is_draft]

    example_programs = (
        db.query(Program)
        .filter(Program.is_public == True, Program.is_draft == False)  # noqa: E712
        .filter(Program.creator_user_id != current_user.id)
        .all()
    )

    return templates.TemplateResponse(
        "program_list.html",
        {
            "request": request,
            "user": current_user,
            "programs": confirmed,
            "draft": draft,
            "example_programs": example_programs,
        },
    )


# ---------------------------------------------------------------------------
# Step 1 — Create program shell
# ---------------------------------------------------------------------------

@router.get("/new", response_class=HTMLResponse)
def wizard_step1_page(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "program_builder.html",
        {"request": request, "user": current_user, "step": 1, "program": None},
    )


@router.post("/new")
def wizard_step1_save(
    name: str = Form(...),
    description: str = Form(""),
    num_blocks: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not 1 <= num_blocks <= 20:
        raise HTTPException(status_code=400, detail="Blocks must be 1–20")

    program = Program(
        creator_user_id=current_user.id,
        name=name.strip(),
        description=description.strip() or None,
        is_draft=True,
    )
    db.add(program)
    db.flush()

    for i in range(1, num_blocks + 1):
        db.add(Block(program_id=program.id, block_number=i, name=f"Block {i}"))

    db.commit()
    return RedirectResponse(url=f"/programs/{program.id}/blocks", status_code=303)


# ---------------------------------------------------------------------------
# Step 2 — Name blocks + set day counts
# ---------------------------------------------------------------------------

@router.get("/{program_id}/blocks", response_class=HTMLResponse)
def wizard_step2_page(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = _load_full(program_id, current_user.id, db)
    return templates.TemplateResponse(
        "program_builder.html",
        {"request": request, "user": current_user, "step": 2, "program": program},
    )


@router.post("/{program_id}/blocks")
async def wizard_step2_save(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()
    program = _get_program_or_404(program_id, current_user.id, db)

    blocks = (
        db.query(Block)
        .filter(Block.program_id == program.id)
        .order_by(Block.block_number)
        .all()
    )

    for block in blocks:
        name = str(form.get(f"block_name_{block.id}", "")).strip()
        block.name = name or f"Block {block.block_number}"

        num_days = int(form.get(f"num_days_{block.id}", 1) or 1)
        num_days = max(1, min(num_days, 14))

        existing = sorted(block.training_days, key=lambda d: d.day_number)
        existing_count = len(existing)

        if num_days > existing_count:
            for d in range(existing_count + 1, num_days + 1):
                db.add(TrainingDay(block_id=block.id, day_number=d, name=f"Day {d}"))
        elif num_days < existing_count:
            for day in existing[num_days:]:
                if not day.planned_sets:
                    db.delete(day)

    db.commit()
    return RedirectResponse(url=f"/programs/{program_id}/days?block=1&day=1", status_code=303)


# ---------------------------------------------------------------------------
# Step 3 — Exercises per day
# ---------------------------------------------------------------------------

@router.get("/{program_id}/days", response_class=HTMLResponse)
def wizard_step3_page(
    program_id: int,
    request: Request,
    block: int = 1,
    day: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = _load_full(program_id, current_user.id, db)
    exercises = _all_exercises(db)

    current_block = next((b for b in program.blocks if b.block_number == block), None)
    current_day = None
    if current_block:
        current_day = next((d for d in current_block.training_days if d.day_number == day), None)

    if not current_block or not current_day:
        return RedirectResponse(url=f"/programs/{program_id}/review", status_code=303)

    # Build flat ordered list of (block_number, day_number) for prev/next navigation
    all_day_coords: list[tuple[int, int]] = [
        (b.block_number, d.day_number)
        for b in program.blocks
        for d in b.training_days
    ]
    try:
        pos = all_day_coords.index((block, day))
    except ValueError:
        pos = 0
    prev_nav = all_day_coords[pos - 1] if pos > 0 else None
    next_nav = all_day_coords[pos + 1] if pos < len(all_day_coords) - 1 else None

    exercise_groups = _build_exercise_groups(current_day.planned_sets) if current_day.planned_sets else []

    return templates.TemplateResponse(
        "program_builder.html",
        {
            "request": request,
            "user": current_user,
            "step": 3,
            "program": program,
            "current_block": current_block,
            "current_day": current_day,
            "all_day_coords": all_day_coords,
            "current_pos": pos,
            "prev_nav": prev_nav,
            "next_nav": next_nav,
            "exercises": exercises,
            "intensity_types": [e.value for e in IntensityType],
            "exercise_groups": exercise_groups,
        },
    )


@router.post("/{program_id}/days")
async def wizard_step3_save(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Save all exercise rows for one training day. Each row is a "set group":
      exercise_id[]     — exercise for this row
      set_count[]       — number of sets
      reps[]            — reps per set
      intensity_type[]  — "percentage"|"rpe"|"freeform"
      intensity_value[] — float or ""
      notes[]           — optional
    Plus:
      day_id            — which TrainingDay to save to
      next_block / next_day — where to navigate after saving
      go_review         — "1" if user clicked "Finish & Review"
    """
    form = await request.form()

    day_id = int(form.get("day_id", 0) or 0)
    next_block = int(form.get("next_block", 1) or 1)
    next_day = int(form.get("next_day", 1) or 1)
    go_review = form.get("go_review", "") == "1"
    go_copy_all = form.get("go_copy_all", "") == "1"

    training_day = db.query(TrainingDay).filter(TrainingDay.id == day_id).first()
    if not training_day:
        raise HTTPException(status_code=404)

    block = db.query(Block).filter(Block.id == training_day.block_id).first()
    _get_program_or_404(block.program_id, current_user.id, db)  # ownership check

    # Replace all planned sets for this day
    db.query(PlannedSet).filter(PlannedSet.training_day_id == day_id).delete()
    db.flush()

    exercise_ids   = form.getlist("exercise_id")
    set_counts     = form.getlist("set_count")
    reps_list      = form.getlist("reps")
    int_types      = form.getlist("intensity_type")
    int_values     = form.getlist("intensity_value")
    notes_list     = form.getlist("notes")

    order = 0
    for i, ex_id_str in enumerate(exercise_ids):
        try:
            ex_id = int(ex_id_str)
        except (ValueError, TypeError):
            continue

        num_sets = max(1, min(int(set_counts[i] or 1), 20))
        reps     = max(1, int(reps_list[i] or 1))

        try:
            int_type = IntensityType(int_types[i])
        except (ValueError, IndexError):
            int_type = IntensityType.freeform

        try:
            iv = int_values[i].strip()
            int_value: Optional[float] = float(iv) if iv else None
        except (ValueError, IndexError, AttributeError):
            int_value = None

        try:
            note = (notes_list[i] or "").strip() or None
        except IndexError:
            note = None

        for set_num in range(1, num_sets + 1):
            db.add(PlannedSet(
                training_day_id=day_id,
                exercise_id=ex_id,
                order=order,
                set_number=set_num,
                reps=reps,
                intensity_type=int_type,
                intensity_value=int_value,
                notes=note,
            ))
            order += 1

    db.commit()

    if go_copy_all:
        # Reload with full joins to access all blocks/days/sets for copy
        full_program = _load_full(program_id, current_user.id, db)
        _copy_block1_to_all(full_program, db)
        db.commit()
        # Navigate to Block 2, Day 1
        blocks = sorted(full_program.blocks, key=lambda b: b.block_number)
        if len(blocks) >= 2:
            b2 = blocks[1]
            days = sorted(b2.training_days, key=lambda d: d.day_number)
            d1_num = days[0].day_number if days else 1
            return RedirectResponse(
                url=f"/programs/{program_id}/days?block={b2.block_number}&day={d1_num}",
                status_code=303,
            )

    if go_review:
        return RedirectResponse(url=f"/programs/{program_id}/review", status_code=303)
    return RedirectResponse(
        url=f"/programs/{program_id}/days?block={next_block}&day={next_day}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Copy Block 1 to all blocks (standalone — called from empty-block banner)
# ---------------------------------------------------------------------------

@router.post("/{program_id}/copy-block1-to-all")
async def copy_block1_to_all(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()
    # After copying, return to whichever block/day the user was on
    target_block = int(form.get("target_block", 2) or 2)
    target_day = int(form.get("target_day", 1) or 1)

    program = _load_full(program_id, current_user.id, db)
    _copy_block1_to_all(program, db)
    db.commit()
    return RedirectResponse(
        url=f"/programs/{program_id}/days?block={target_block}&day={target_day}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Step 4 — Review & confirm
# ---------------------------------------------------------------------------

@router.get("/{program_id}/review", response_class=HTMLResponse)
def wizard_step4_review(
    program_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = _load_full(program_id, current_user.id, db)

    review_data = [
        {
            "block": block,
            "days": [
                {
                    "day": day,
                    "exercise_groups": _build_exercise_groups(day.planned_sets),
                }
                for day in sorted(block.training_days, key=lambda d: d.day_number)
            ],
        }
        for block in sorted(program.blocks, key=lambda b: b.block_number)
    ]

    return templates.TemplateResponse(
        "program_builder.html",
        {
            "request": request,
            "user": current_user,
            "step": 4,
            "program": program,
            "review_data": review_data,
        },
    )


@router.post("/{program_id}/confirm")
def wizard_confirm(
    program_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    program = _get_program_or_404(program_id, current_user.id, db)
    program.is_draft = False
    db.commit()
    return RedirectResponse(url="/programs", status_code=303)


# ---------------------------------------------------------------------------
# Duplicate
# ---------------------------------------------------------------------------

@router.post("/{program_id}/duplicate")
def duplicate_program(
    program_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # Allow duplicating own programs OR public programs from other users
    original = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.is_archived == False,  # noqa: E712
        )
        .options(
            joinedload(Program.blocks)
            .joinedload(Block.training_days)
            .joinedload(TrainingDay.planned_sets)
        )
        .first()
    )
    if not original:
        raise HTTPException(status_code=404, detail="Program not found")
    if original.creator_user_id != current_user.id and not original.is_public:
        raise HTTPException(status_code=403, detail="Not authorised")

    new_prog = Program(
        creator_user_id=current_user.id,
        name=f"Copy of {original.name}",
        description=original.description,
        is_draft=True,
    )
    db.add(new_prog)
    db.flush()

    for ob in original.blocks:
        nb = Block(program_id=new_prog.id, block_number=ob.block_number, name=ob.name)
        db.add(nb)
        db.flush()
        for od in ob.training_days:
            nd = TrainingDay(block_id=nb.id, day_number=od.day_number, name=od.name)
            db.add(nd)
            db.flush()
            for ops in sorted(od.planned_sets, key=lambda s: s.order):
                db.add(PlannedSet(
                    training_day_id=nd.id,
                    exercise_id=ops.exercise_id,
                    order=ops.order,
                    set_number=ops.set_number,
                    reps=ops.reps,
                    intensity_type=ops.intensity_type,
                    intensity_value=ops.intensity_value,
                    notes=ops.notes,
                ))

    db.commit()
    return RedirectResponse(url=f"/programs/{new_prog.id}/review", status_code=303)


# ---------------------------------------------------------------------------
# Archive (soft-delete)
# ---------------------------------------------------------------------------

@router.post("/{program_id}/delete")
def archive_program(
    program_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    program = _get_program_or_404(program_id, current_user.id, db)
    program.is_archived = True
    db.commit()
    return RedirectResponse(url="/programs", status_code=303)
