"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "warehouse",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("operational", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "order",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "delivery_location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "order_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["order.id"], ondelete="CASCADE", name="fk_order_item_order"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        sa.CheckConstraint("weight_kg >= 0", name="ck_order_item_weight_non_negative"),
    )

    op.create_table(
        "driver",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
    )

    op.create_table(
        "vehicle",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("driver_id", sa.Uuid(), nullable=True),
        sa.Column("depot_warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("max_weight_kg", sa.Numeric(), nullable=False),
        sa.Column("operational", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["driver.id"], name="fk_vehicle_driver"
        ),
        sa.ForeignKeyConstraint(
            ["depot_warehouse_id"], ["warehouse.id"], name="fk_vehicle_depot_warehouse"
        ),
    )

    op.create_table(
        "route",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["vehicle.id"], name="fk_route_vehicle"
        ),
    )

    op.create_table(
        "fulfillment_group",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "delivery_location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("assigned_route_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
            ondelete="CASCADE",
            name="fk_fulfillment_group_order",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouse.id"], name="fk_fulfillment_group_warehouse"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_route_id"], ["route.id"], name="fk_fulfillment_group_route"
        ),
    )

    op.create_table(
        "fulfillment_group_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("fulfillment_group_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fulfillment_group_id"],
            ["fulfillment_group.id"],
            ondelete="CASCADE",
            name="fk_fulfillment_group_item_group",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_item.id"],
            ondelete="CASCADE",
            name="fk_fulfillment_group_item_order_item",
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_fulfillment_group_item_quantity_positive"
        ),
    )

    op.create_table(
        "inventory",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouse.id"],
            ondelete="CASCADE",
            name="fk_inventory_warehouse",
        ),
        sa.CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_non_negative"),
        sa.CheckConstraint("reserved >= 0", name="ck_inventory_reserved_non_negative"),
        sa.UniqueConstraint(
            "warehouse_id", "sku", name="uq_inventory_warehouse_sku"
        ),
    )

    op.create_table(
        "reservation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("fulfillment_group_id", sa.Uuid(), nullable=True),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouse.id"],
            ondelete="CASCADE",
            name="fk_reservation_warehouse",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
            ondelete="CASCADE",
            name="fk_reservation_order",
        ),
        sa.ForeignKeyConstraint(
            ["fulfillment_group_id"],
            ["fulfillment_group.id"],
            ondelete="CASCADE",
            name="fk_reservation_fulfillment_group",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_reservation_quantity_positive"),
    )

    op.create_table(
        "route_stop",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("fulfillment_group_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["route_id"], ["route.id"], ondelete="CASCADE", name="fk_route_stop_route"
        ),
        sa.ForeignKeyConstraint(
            ["fulfillment_group_id"],
            ["fulfillment_group.id"],
            name="fk_route_stop_fulfillment_group",
        ),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_stop_route_sequence"),
    )

    op.create_table(
        "telemetry_snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicle.id"],
            ondelete="CASCADE",
            name="fk_telemetry_snapshot_vehicle",
        ),
        sa.Index("idx_telemetry_vehicle_recorded", "vehicle_id", "recorded_at"),
    )

    op.create_table(
        "outbox_event",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Index("idx_outbox_published", "published", "occurred_at"),
    )


def downgrade() -> None:
    op.drop_table("outbox_event")
    op.drop_table("telemetry_snapshot")
    op.drop_table("route_stop")
    op.drop_table("reservation")
    op.drop_table("inventory")
    op.drop_table("fulfillment_group_item")
    op.drop_table("fulfillment_group")
    op.drop_table("route")
    op.drop_table("vehicle")
    op.drop_table("driver")
    op.drop_table("order_item")
    op.drop_table("order")
    op.drop_table("warehouse")
