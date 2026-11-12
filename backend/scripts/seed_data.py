"""Seed RouteGrid development data using a synchronous SQLAlchemy session.

Run from the backend directory:

    python -m scripts.seed_data

The script is deterministic and safe to re-run. Every entity is matched on a
natural key (warehouse name, driver name, vehicle external_id, (warehouse, sku)
for inventory, and a seed marker stored in ``order.raw_payload``), so existing
rows are never duplicated and existing data is never overwritten.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(PROJECT_ROOT / ".env")

from app.models import (  # noqa: E402
    Driver,
    Inventory,
    Order,
    OrderItem,
    Vehicle,
    Warehouse,
)

SEED_TAG = "routegrid-seed-v1"

WAREHOUSES = [
    ("Hyderabad Central Hub", "SRID=4326;POINT(78.4867 17.3850)"),
    ("Hyderabad North Depot", "SRID=4326;POINT(78.4347 17.4849)"),
    ("Hyderabad South Depot", "SRID=4326;POINT(78.4983 17.2544)"),
    ("Hyderabad East Depot", "SRID=4326;POINT(78.5949 17.4239)"),
    ("Hyderabad West Depot", "SRID=4326;POINT(78.3489 17.4139)"),
]

SKUS = [
    "Electronics-Laptop-15in",
    "Electronics-Laptop-13in",
    "Electronics-Monitor-24in",
    "Electronics-Mechanical-Keyboard",
    "Electronics-Wireless-Mouse",
    "Electronics-USB-C-Hub",
    "Electronics-Webcam-1080p",
    "Electronics-Headphones-Wireless",
    "Electronics-External-SSD-1TB",
    "Electronics-Router-WiFi6",
    "Grocery-Rice-5kg",
    "Grocery-Wheat-Flour-10kg",
    "Grocery-Sugar-1kg",
    "Grocery-Cooking-Oil-1L",
    "Grocery-Tea-Leaves-500g",
    "Grocery-Coffee-Beans-1kg",
    "Grocery-Lentils-1kg",
    "Grocery-Salt-1kg",
    "Grocery-Pasta-500g",
    "Grocery-Honey-500g",
    "Pharmacy-Paracetamol-500mg",
    "Pharmacy-Ibuprofen-200mg",
    "Pharmacy-Vitamin-C-1000mg",
    "Pharmacy-Antiseptic-Solution",
    "Pharmacy-Bandage-Roll",
    "Pharmacy-ORS-Sachet",
    "Pharmacy-Cough-Syrup",
    "Pharmacy-Sanitizer-500ml",
    "Pharmacy-Face-Mask-Box",
    "Pharmacy-Thermometer-Digital",
    "Home-Detergent-2kg",
    "Home-Dish-Soap-500ml",
    "Home-Paper-Towels-6pk",
    "Home-Trash-Bags-30pk",
    "Home-Light-Bulb-LED",
    "Home-Batteries-AA-8pk",
    "Home-Candle-Pack",
    "Home-Broom-Head",
    "Home-Mop-Bucket",
    "Home-Storage-Box-L",
]

DRIVER_NAMES = [f"Driver {i:02d}" for i in range(1, 26)]

VEHICLE_TIERS_KG = [500, 750, 1000, 1250, 1500]

ORDER_POINTS = [
    "SRID=4326;POINT(78.4747 17.3616)",
    "SRID=4326;POINT(78.5080 17.4030)",
    "SRID=4326;POINT(78.4480 17.4230)",
    "SRID=4326;POINT(78.4030 17.4460)",
    "SRID=4326;POINT(78.5590 17.4180)",
    "SRID=4326;POINT(78.5120 17.3260)",
    "SRID=4326;POINT(78.4370 17.3390)",
    "SRID=4326;POINT(78.6020 17.4720)",
    "SRID=4326;POINT(78.3690 17.3790)",
    "SRID=4326;POINT(78.4700 17.4780)",
]

# Realistic dispatch customers, so the UI never shows bare UUIDs.
CUSTOMERS = [
    "Sri Lakshmi Traders",
    "Deccan Medical Supplies",
    "Charminar Electronics",
    "Godavari Grocers",
    "Krishna Pharma Distributors",
    "Hitec Home Essentials",
    "Nizam Book Depot",
    "Anand Provision Stores",
    "Vijaya Diagnostics",
    "Secunderabad Hardware Mart",
    "Meghana Foods",
    "Golconda Stationers",
    "Padma Retail Chain",
    "Sai Teja Wholesale",
    "Begumpet Fresh Mart",
]

ORDER_COUNT = 10


def customer_id_for(index: int) -> str:
    """Deterministic customer id so repeated seeds produce the same rows."""
    return str(uuid5(NAMESPACE_URL, f"routegrid-customer-{index}"))


def _seed(session: Session) -> dict[str, int]:
    created = {"warehouses": 0, "inventory": 0, "drivers": 0, "vehicles": 0, "orders": 0}

    existing_warehouses = {w.name: w for w in session.scalars(select(Warehouse)).all()}
    warehouses: list[Warehouse] = []
    for name, wkt in WAREHOUSES:
        warehouse = existing_warehouses.get(name)
        if warehouse is None:
            warehouse = Warehouse(name=name, location=wkt, operational=True)
            session.add(warehouse)
            session.flush()
            created["warehouses"] += 1
        warehouses.append(warehouse)

    existing_inventory = {
        (row.warehouse_id, row.sku) for row in session.scalars(select(Inventory)).all()
    }
    for warehouse in warehouses:
        for idx, sku in enumerate(SKUS):
            if (warehouse.id, sku) in existing_inventory:
                continue
            session.add(
                Inventory(
                    warehouse_id=warehouse.id,
                    sku=sku,
                    on_hand=50 + (idx * 7) % 150,
                    reserved=0,
                )
            )
            created["inventory"] += 1
    session.flush()

    existing_drivers = {d.name: d for d in session.scalars(select(Driver)).all()}
    drivers: list[Driver] = []
    for name in DRIVER_NAMES:
        driver = existing_drivers.get(name)
        if driver is None:
            driver = Driver(name=name)
            session.add(driver)
            session.flush()
            created["drivers"] += 1
        drivers.append(driver)

    existing_vehicles = {
        v.external_id for v in session.scalars(select(Vehicle)).all()
    }
    for i, driver in enumerate(drivers):
        external_id = f"VH-{i + 1:03d}"
        if external_id in existing_vehicles:
            continue
        session.add(
            Vehicle(
                external_id=external_id,
                driver_id=driver.id,
                depot_warehouse_id=warehouses[i % len(warehouses)].id,
                max_weight_kg=Decimal(VEHICLE_TIERS_KG[i % len(VEHICLE_TIERS_KG)]),
                operational=True,
            )
        )
        created["vehicles"] += 1

    seeded_order_indices = set()
    for order in session.scalars(select(Order).where(Order.raw_payload.is_not(None))).all():
        payload = order.raw_payload
        if isinstance(payload, dict) and payload.get("seed") == SEED_TAG:
            seeded_order_indices.add(payload.get("index"))

    for i in range(ORDER_COUNT):
        if i in seeded_order_indices:
            continue
        order = Order(
            customer_id=customer_id_for(i) if i % 2 == 0 else None,
            customer_name=CUSTOMERS[i % len(CUSTOMERS)],
            reference=f"ORD-2026-{i + 1:04d}",
            status="PENDING_ALLOCATION",
            delivery_location=ORDER_POINTS[i],
            raw_payload={"seed": SEED_TAG, "index": i},
        )
        for j in range((i % 4) + 1):
            order.items.append(
                OrderItem(
                    sku=SKUS[(i * 3 + j) % len(SKUS)],
                    quantity=1 + (i + j) % 5,
                    weight_kg=Decimal(str(round(0.5 + ((i + j) % 7) * 0.75, 2))),
                )
            )
        session.add(order)
        created["orders"] += 1

    return created


def _backfill_identity(session: Session) -> int:
    """Give legacy rows a customer name and reference.

    Non-destructive: it only fills NULLs, so previously created orders stop
    showing blank customers and UUID-only references in the UI.
    """
    updated = 0
    for order in session.scalars(select(Order)).all():
        changed = False
        if not order.customer_name:
            order.customer_name = CUSTOMERS[int(order.id) % len(CUSTOMERS)]
            changed = True
        if not order.reference:
            order.reference = f"ORD-{order.id.hex[:8].upper()}"
            changed = True
        if changed:
            updated += 1
    return updated


def main() -> None:
    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
    with Session(engine) as session:
        try:
            created = _seed(session)
            backfilled = _backfill_identity(session)
            session.commit()
        except Exception:
            session.rollback()
            raise

        totals = {
            "warehouses": len(session.scalars(select(Warehouse)).all()),
            "inventory": len(session.scalars(select(Inventory)).all()),
            "drivers": len(session.scalars(select(Driver)).all()),
            "vehicles": len(session.scalars(select(Vehicle)).all()),
            "orders": len(session.scalars(select(Order)).all()),
        }

    if any(created.values()):
        print("Created: " + ", ".join(f"{v} {k}" for k, v in created.items()))
    else:
        print("Seed data already present, nothing to create.")
    if backfilled:
        print(f"Backfilled customer name/reference on {backfilled} existing order(s).")

    print(
        "Totals now: "
        f"{totals['warehouses']} warehouses, {totals['inventory']} inventory rows, "
        f"{totals['drivers']} drivers, {totals['vehicles']} vehicles, "
        f"{totals['orders']} orders"
    )


if __name__ == "__main__":
    main()
