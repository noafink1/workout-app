"""
Pydantic schemas for request/response validation.
These same schemas will be used when passing data to the AI service later.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------

class ExerciseOut(BaseModel):
    id: int
    name: str
    category: str
    muscle_group: Optional[str]
    is_archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 1RM
# ---------------------------------------------------------------------------

class OneRepMaxCreate(BaseModel):
    exercise_id: int
    weight_kg: float
    date_set: date


class OneRepMaxOut(BaseModel):
    id: int
    exercise_id: int
    weight_kg: float
    date_set: date

    model_config = {"from_attributes": True}
