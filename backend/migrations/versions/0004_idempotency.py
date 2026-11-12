"""idempotency keys

Revision ID: 0004_idempotency
Revises: 0003_order_reference
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_idempotency"
down_revision: Union[str, None] = "0003_order_reference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_key",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["order.id"], ondelete="CASCADE", name="fk_idempotency_order"
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_key")
