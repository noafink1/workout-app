"""
Seed script — run once after `alembic upgrade head` to populate default exercises
and the example PowerBuilding program.

Usage:
    python seed.py
"""
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from app.auth import hash_password
from app.database import SessionLocal
from app.models import (
    Block, Exercise, ExerciseCategory, IntensityType,
    MuscleGroup, PlannedSet, Program, TrainingDay, User,
)


# ---------------------------------------------------------------------------
# Default exercise library
# ---------------------------------------------------------------------------

EXERCISES = [
    # Main lifts
    ("Squat",          ExerciseCategory.main_lift,  MuscleGroup.legs),
    ("Bench Press",    ExerciseCategory.main_lift,  MuscleGroup.chest),
    ("Deadlift",       ExerciseCategory.main_lift,  MuscleGroup.back),
    ("Overhead Press", ExerciseCategory.main_lift,  MuscleGroup.shoulders),
    # Legs
    ("Romanian Deadlift", ExerciseCategory.accessory, MuscleGroup.legs),
    ("Leg Press",         ExerciseCategory.accessory, MuscleGroup.legs),
    ("Leg Curl",          ExerciseCategory.accessory, MuscleGroup.legs),
    # Back
    ("Pull-up",           ExerciseCategory.accessory, MuscleGroup.back),
    ("Barbell Row",       ExerciseCategory.accessory, MuscleGroup.back),
    ("Dumbbell Row",      ExerciseCategory.accessory, MuscleGroup.back),
    # Arms
    ("Tricep Pushdown",   ExerciseCategory.accessory, MuscleGroup.arms),
    ("Bicep Curl",        ExerciseCategory.accessory, MuscleGroup.arms),
    # Shoulders
    ("Lateral Raise",     ExerciseCategory.accessory, MuscleGroup.shoulders),
    # Core
    ("Ab Wheel",          ExerciseCategory.accessory, MuscleGroup.core),
    ("Plank",             ExerciseCategory.accessory, MuscleGroup.core),
]


# ---------------------------------------------------------------------------
# Example program: 4 blocks × 4 days, realistic powerbuilding percentages
# ---------------------------------------------------------------------------
# Structure: [block_name, [(day_name, [(exercise_name, sets, reps, intensity_type, intensity_value), ...]), ...]]

EXAMPLE_PROGRAM = [
    # ── Block 1 — Accumulation (moderate intensity, higher volume) ────────
    ("Block 1 — Accumulation", [
        ("Day 1 — Squat & Push", [
            ("Squat",        4, 5, IntensityType.percentage, 75.0),
            ("Bench Press",  4, 5, IntensityType.percentage, 75.0),
            ("Romanian Deadlift", 3, 8, IntensityType.freeform, None),
            ("Tricep Pushdown",   3, 12, IntensityType.freeform, None),
        ]),
        ("Day 2 — Deadlift & Pull", [
            ("Deadlift",     4, 5, IntensityType.percentage, 75.0),
            ("Overhead Press", 3, 6, IntensityType.percentage, 72.0),
            ("Pull-up",      3, 8,  IntensityType.freeform, None),
            ("Barbell Row",  3, 8,  IntensityType.freeform, None),
        ]),
        ("Day 3 — Bench & Accessories", [
            ("Bench Press",  4, 6, IntensityType.percentage, 72.0),
            ("Squat",        3, 5, IntensityType.percentage, 70.0),
            ("Dumbbell Row", 3, 10, IntensityType.freeform, None),
            ("Bicep Curl",   3, 12, IntensityType.freeform, None),
            ("Lateral Raise", 3, 15, IntensityType.freeform, None),
        ]),
        ("Day 4 — Deadlift & Squat", [
            ("Deadlift",     3, 3, IntensityType.percentage, 80.0),
            ("Squat",        3, 3, IntensityType.percentage, 80.0),
            ("Leg Press",    3, 10, IntensityType.freeform, None),
            ("Ab Wheel",     3, 10, IntensityType.freeform, None),
        ]),
    ]),

    # ── Block 2 — Intensification (intensity rises, volume drops slightly) #
    ("Block 2 — Intensification", [
        ("Day 1 — Squat & Push", [
            ("Squat",        4, 4, IntensityType.percentage, 80.0),
            ("Bench Press",  4, 4, IntensityType.percentage, 80.0),
            ("Romanian Deadlift", 3, 6, IntensityType.freeform, None),
            ("Tricep Pushdown",   3, 10, IntensityType.freeform, None),
        ]),
        ("Day 2 — Deadlift & Pull", [
            ("Deadlift",     4, 4, IntensityType.percentage, 80.0),
            ("Overhead Press", 3, 5, IntensityType.percentage, 75.0),
            ("Pull-up",      3, 6, IntensityType.freeform, None),
            ("Barbell Row",  3, 6, IntensityType.freeform, None),
        ]),
        ("Day 3 — Heavy Bench", [
            ("Bench Press",  3, 3, IntensityType.percentage, 85.0),
            ("Bench Press",  3, 5, IntensityType.percentage, 75.0),
            ("Dumbbell Row", 3, 8, IntensityType.freeform, None),
            ("Bicep Curl",   3, 10, IntensityType.freeform, None),
        ]),
        ("Day 4 — Heavy Deadlift & Squat", [
            ("Deadlift",     3, 2, IntensityType.percentage, 88.0),
            ("Squat",        3, 2, IntensityType.percentage, 88.0),
            ("Leg Curl",     3, 10, IntensityType.freeform, None),
            ("Ab Wheel",     3, 10, IntensityType.freeform, None),
        ]),
    ]),

    # ── Block 3 — Peaking (heavy singles, low volume) ─────────────────────
    ("Block 3 — Peaking", [
        ("Day 1 — Squat Singles", [
            ("Squat",       2, 1, IntensityType.percentage, 90.0),
            ("Squat",       3, 3, IntensityType.percentage, 80.0),
            ("Bench Press", 3, 3, IntensityType.percentage, 80.0),
            ("Tricep Pushdown", 3, 10, IntensityType.freeform, None),
        ]),
        ("Day 2 — Deadlift Singles", [
            ("Deadlift",    2, 1, IntensityType.percentage, 90.0),
            ("Deadlift",    3, 3, IntensityType.percentage, 80.0),
            ("Pull-up",     3, 5, IntensityType.freeform, None),
        ]),
        ("Day 3 — Bench Singles", [
            ("Bench Press", 2, 1, IntensityType.percentage, 92.0),
            ("Bench Press", 3, 3, IntensityType.percentage, 82.0),
            ("Dumbbell Row", 3, 8, IntensityType.freeform, None),
        ]),
        ("Day 4 — Top Singles SBD", [
            ("Squat",     1, 1, IntensityType.percentage, 95.0),
            ("Bench Press", 1, 1, IntensityType.percentage, 95.0),
            ("Deadlift",  1, 1, IntensityType.percentage, 95.0),
        ]),
    ]),

    # ── Block 4 — Deload (recovery) ────────────────────────────────────────
    ("Block 4 — Deload", [
        ("Day 1 — Squat & Bench (light)", [
            ("Squat",       3, 5, IntensityType.percentage, 60.0),
            ("Bench Press", 3, 5, IntensityType.percentage, 60.0),
            ("Lateral Raise", 2, 15, IntensityType.freeform, None),
        ]),
        ("Day 2 — Deadlift (light)", [
            ("Deadlift",    3, 3, IntensityType.percentage, 60.0),
            ("Barbell Row", 2, 8, IntensityType.freeform, None),
        ]),
        ("Day 3 — Accessory flush", [
            ("Romanian Deadlift", 2, 10, IntensityType.freeform, None),
            ("Pull-up",           2, 8,  IntensityType.freeform, None),
            ("Bicep Curl",        2, 12, IntensityType.freeform, None),
            ("Plank",             2, 30, IntensityType.freeform, None),
        ]),
        ("Day 4 — Optional: movement only", [
            ("Squat",        2, 5, IntensityType.percentage, 55.0),
            ("Bench Press",  2, 5, IntensityType.percentage, 55.0),
            ("Deadlift",     2, 3, IntensityType.percentage, 55.0),
        ]),
    ]),
]


def run_seed() -> None:
    db = SessionLocal()
    try:
        # Guard: skip if exercises already exist
        if db.query(Exercise).count() > 0:
            print("Database already seeded — skipping.")
            return

        print("Seeding exercise library...")
        exercise_map: dict[str, Exercise] = {}
        for name, category, muscle_group in EXERCISES:
            ex = Exercise(name=name, category=category, muscle_group=muscle_group)
            db.add(ex)
            exercise_map[name] = ex
        db.flush()  # assigns IDs without committing

        print("Seeding system user for example program...")
        import secrets
        system_user = User(
            email="system@powerbuilding.internal",
            hashed_password=hash_password(secrets.token_hex(32)),
            display_name="System",
            is_admin=True,
        )
        db.add(system_user)
        db.flush()

        print("Seeding example program...")
        program = Program(
            creator_user_id=system_user.id,
            name="Example PowerBuilding Program",
            description=(
                "A 4-block powerbuilding program progressing from accumulation "
                "through intensification to a peaking block, followed by a deload. "
                "Uses percentage-based loading off your Squat, Bench, and Deadlift 1RMs."
            ),
            is_public=True,
            is_draft=False,
        )
        db.add(program)
        db.flush()

        set_order = 0
        for block_idx, (block_name, days) in enumerate(EXAMPLE_PROGRAM, start=1):
            block = Block(program_id=program.id, block_number=block_idx, name=block_name)
            db.add(block)
            db.flush()

            for day_idx, (day_name, planned) in enumerate(days, start=1):
                day = TrainingDay(block_id=block.id, day_number=day_idx, name=day_name)
                db.add(day)
                db.flush()

                set_order = 0
                for ex_name, sets, reps, intensity_type, intensity_value in planned:
                    exercise = exercise_map[ex_name]
                    for set_num in range(1, sets + 1):
                        ps = PlannedSet(
                            training_day_id=day.id,
                            exercise_id=exercise.id,
                            order=set_order,
                            set_number=set_num,
                            reps=reps,
                            intensity_type=intensity_type,
                            intensity_value=intensity_value,
                        )
                        db.add(ps)
                        set_order += 1

        db.commit()
        print(f"Done! Seeded {len(EXERCISES)} exercises and 1 example program ({len(EXAMPLE_PROGRAM)} blocks).")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
