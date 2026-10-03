"""补货单世代服务：历史单是落库时的快照，永不变更；活口汇总永远按当前 lane 现算。"""
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


def lane_payloads(db: Session, location_id: int) -> list[dict]:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return [
        {"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
         "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit}
        for l in lanes
    ]


def live_summary(db: Session, location_id: int) -> dict:
    """按货道当前库存/在途现算，不落库——满仓名单与汇总计数都以此为准。"""
    return summarize(build_fill_lines(lane_payloads(db, location_id)))


def create_refill_order(db: Session, location_id: int) -> tuple[RefillOrder, dict]:
    """生成一个新世代的补货单：仅快照生成时刻的活口状态，之后不再被改写。"""
    snapshot = live_summary(db, location_id)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(snapshot, ensure_ascii=False))
    db.add(order)
    db.commit()
    db.refresh(order)
    return order, snapshot


def serialize_order(order: RefillOrder) -> dict:
    return {"id": order.id, "location_id": order.location_id,
            "created_at": order.created_at.isoformat(), **json.loads(order.lines_json)}
