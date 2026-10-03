"""补货单世代相关辅助。

历史补货单（RefillOrder.lines_json）是落库时的快照：此后发车只改货道在途，
绝不回改任何旧单。当前活口缺口 / 汇总 / 满仓名单一律按货道最新在途现算，
不依赖历史快照——两者是不同世代。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


def lanes_payload(db: Session, location_id: int) -> list[dict]:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return [
        {
            "id": l.id,
            "slot_no": l.slot_no,
            "sku_name": l.sku_name,
            "capacity": l.capacity,
            "stock": l.stock,
            "in_transit": l.in_transit,
        }
        for l in lanes
    ]


def live_snapshot(db: Session, location_id: int) -> dict:
    """按货道当前在途现算的活口快照（不落库、不产生新世代单）。"""
    return summarize(build_fill_lines(lanes_payload(db, location_id)))


def persist_order(db: Session, location_id: int) -> tuple[RefillOrder, dict]:
    """按当前在途生成一张新世代补货单并落库；既有单行原样冻结。"""
    snapshot = live_snapshot(db, location_id)
    order = RefillOrder(
        location_id=location_id,
        created_at=datetime.utcnow(),
        lines_json=json.dumps(snapshot, ensure_ascii=False),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order, snapshot
