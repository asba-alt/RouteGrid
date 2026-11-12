"""order reference and customer name

Revision ID: 0003_order_reference
Revises: 0002_disruption
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_order_reference"
down_revision: Union[str, None] = "0002_disruption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order", sa.Column("customer_name", sa.String(), nullable=True))
    op.add_column("order", sa.Column("reference", sa.String(), nullable=True))
    op.create_index("ix_order_reference", "order", ["reference"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_order_reference", table_name="order")
    op.drop_column("order", "reference")
    op.drop_column("order", "customer_name")
