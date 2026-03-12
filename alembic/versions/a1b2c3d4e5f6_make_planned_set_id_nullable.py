"""make planned_set_id nullable for extra sets

Revision ID: a1b2c3d4e5f6
Revises: b6c69cd4a2a7
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b6c69cd4a2a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('completed_sets', schema=None) as batch_op:
        batch_op.alter_column('planned_set_id',
                              existing_type=sa.Integer(),
                              nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('completed_sets', schema=None) as batch_op:
        batch_op.alter_column('planned_set_id',
                              existing_type=sa.Integer(),
                              nullable=False)
