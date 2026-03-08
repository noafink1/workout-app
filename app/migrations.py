"""
Lightweight schema migrations for databases already created before a model change.
Called once at app startup — safe to run repeatedly (idempotent).
"""
from sqlalchemy import text

from app.database import engine


def run_migrations() -> None:
    with engine.connect() as conn:
        # Phase 9: add reference_exercise_id to exercises
        try:
            conn.execute(text(
                "ALTER TABLE exercises "
                "ADD COLUMN reference_exercise_id INTEGER REFERENCES exercises(id)"
            ))
            conn.commit()
        except Exception:
            pass  # column already exists
