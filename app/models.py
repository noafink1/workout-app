"""
SQLAlchemy ORM models for the PowerBuilding Workout Tracker.

Data retention rule: Never hard-delete training history.
Use is_archived flags on programs and exercises instead of DELETE.
"""
import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExerciseCategory(str, enum.Enum):
    main_lift = "main_lift"
    accessory = "accessory"


class MuscleGroup(str, enum.Enum):
    chest = "chest"
    back = "back"
    legs = "legs"
    shoulders = "shoulders"
    arms = "arms"
    core = "core"


class IntensityType(str, enum.Enum):
    percentage = "percentage"
    rpe = "rpe"
    freeform = "freeform"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    one_rep_maxes: Mapped[list["OneRepMax"]] = relationship(back_populates="user")
    programs: Mapped[list["Program"]] = relationship(back_populates="creator")
    program_runs: Mapped[list["ProgramRun"]] = relationship(back_populates="user")
    accessory_bests: Mapped[list["AccessoryBest"]] = relationship(back_populates="user")


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------

class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[ExerciseCategory] = mapped_column(
        Enum(ExerciseCategory), nullable=False, default=ExerciseCategory.accessory
    )
    muscle_group: Mapped[Optional[MuscleGroup]] = mapped_column(Enum(MuscleGroup), nullable=True)
    # NULL creator_user_id = default/seeded exercise; set = user-created custom exercise
    creator_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    planned_sets: Mapped[list["PlannedSet"]] = relationship(back_populates="exercise")
    one_rep_maxes: Mapped[list["OneRepMax"]] = relationship(back_populates="exercise")
    accessory_bests: Mapped[list["AccessoryBest"]] = relationship(back_populates="exercise")


# ---------------------------------------------------------------------------
# OneRepMax
# ---------------------------------------------------------------------------

class OneRepMax(Base):
    __tablename__ = "one_rep_maxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    date_set: Mapped[date] = mapped_column(Date, nullable=False)

    user: Mapped["User"] = relationship(back_populates="one_rep_maxes")
    exercise: Mapped["Exercise"] = relationship(back_populates="one_rep_maxes")


# ---------------------------------------------------------------------------
# Program → Block → TrainingDay → PlannedSet
# ---------------------------------------------------------------------------

class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    creator_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # draft: program is mid-wizard and not yet confirmed
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="programs")
    blocks: Mapped[list["Block"]] = relationship(back_populates="program", order_by="Block.block_number")
    program_runs: Mapped[list["ProgramRun"]] = relationship(back_populates="program")


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.id"), nullable=False, index=True)
    block_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    program: Mapped["Program"] = relationship(back_populates="blocks")
    training_days: Mapped[list["TrainingDay"]] = relationship(back_populates="block", order_by="TrainingDay.day_number")


class TrainingDay(Base):
    __tablename__ = "training_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    block_id: Mapped[int] = mapped_column(Integer, ForeignKey("blocks.id"), nullable=False, index=True)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    block: Mapped["Block"] = relationship(back_populates="training_days")
    planned_sets: Mapped[list["PlannedSet"]] = relationship(back_populates="training_day", order_by="PlannedSet.order")


class PlannedSet(Base):
    __tablename__ = "planned_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    training_day_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_days.id"), nullable=False, index=True)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity_type: Mapped[IntensityType] = mapped_column(
        Enum(IntensityType), nullable=False, default=IntensityType.freeform
    )
    intensity_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    training_day: Mapped["TrainingDay"] = relationship(back_populates="planned_sets")
    exercise: Mapped["Exercise"] = relationship(back_populates="planned_sets")
    completed_sets: Mapped[list["CompletedSet"]] = relationship(back_populates="planned_set")


# ---------------------------------------------------------------------------
# ProgramRun → ScheduledWorkout → CompletedSet
# ---------------------------------------------------------------------------

class ProgramRun(Base):
    __tablename__ = "program_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_block_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("blocks.id"), nullable=True)
    current_day_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("training_days.id"), nullable=True)
    round_number: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship(back_populates="program_runs")
    program: Mapped["Program"] = relationship(back_populates="program_runs")
    scheduled_workouts: Mapped[list["ScheduledWorkout"]] = relationship(back_populates="program_run")


class ScheduledWorkout(Base):
    __tablename__ = "scheduled_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("program_runs.id"), nullable=False, index=True)
    block_id: Mapped[int] = mapped_column(Integer, ForeignKey("blocks.id"), nullable=False)
    training_day_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_days.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    session_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    program_run: Mapped["ProgramRun"] = relationship(back_populates="scheduled_workouts")
    block: Mapped["Block"] = relationship()
    training_day: Mapped["TrainingDay"] = relationship()
    completed_sets: Mapped[list["CompletedSet"]] = relationship(back_populates="scheduled_workout")


class CompletedSet(Base):
    __tablename__ = "completed_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scheduled_workout_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheduled_workouts.id"), nullable=False, index=True)
    planned_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("planned_sets.id"), nullable=False)
    actual_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    was_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    substituted_exercise_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scheduled_workout: Mapped["ScheduledWorkout"] = relationship(back_populates="completed_sets")
    planned_set: Mapped["PlannedSet"] = relationship(back_populates="completed_sets")
    substituted_exercise: Mapped[Optional["Exercise"]] = relationship(foreign_keys=[substituted_exercise_id])


# ---------------------------------------------------------------------------
# AccessoryBest
# ---------------------------------------------------------------------------

class AccessoryBest(Base):
    __tablename__ = "accessory_bests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    date_set: Mapped[date] = mapped_column(Date, nullable=False)

    user: Mapped["User"] = relationship(back_populates="accessory_bests")
    exercise: Mapped["Exercise"] = relationship(back_populates="accessory_bests")
