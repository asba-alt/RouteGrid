"""disruption

Revision ID: 0002_disruption
Revises: 0001_initial_schema
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_disruption"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disruption",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("route_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("affected_group_ids", sa.JSON(), nullable=True),
        sa.Column("resolution", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["vehicle.id"], name="fk_disruption_vehicle"
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["route.id"],
            ondelete="SET NULL",
            name="fk_disruption_route",
        ),
        sa.Index("idx_disruption_status", "status", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("disruption")
