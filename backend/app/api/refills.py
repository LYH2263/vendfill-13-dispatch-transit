import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Location, RefillOrder
from app.services.refill import live_snapshot, persist_order

router = APIRouter(prefix="/refills", tags=["refills"])


@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    """显式生成一张新世代补货单：按当前在途现算并落库。

    只影响此后的新单，既有的历史单行原样冻结，不被回改。
    """
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    order, snapshot = persist_order(db, location_id)
    return {"id": order.id, "location_id": location_id, **snapshot}


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    """读取最近一张历史补货单（冻结快照）；不存在返回 404，绝不隐式建单。"""
    order = db.scalars(
        select(RefillOrder)
        .where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).first()
    if not order:
        raise HTTPException(404, "尚无补货单")
    return {"id": order.id, "location_id": location_id, **json.loads(order.lines_json)}


@router.get("/orders")
def list_orders(location_id: int = 1, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(RefillOrder)
        .where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).all()
    return [
        {"id": o.id, "location_id": o.location_id, "created_at": o.created_at.isoformat()}
        for o in rows
    ]


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(RefillOrder, order_id)
    if not order:
        raise HTTPException(404, "补货单不存在")
    return {"id": order.id, "location_id": order.location_id,
            "created_at": order.created_at.isoformat(), **json.loads(order.lines_json)}


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    """满仓名单：按货道当前在途现算，不读历史单快照。

    车道进入超占（缺口 < 0）即从名单移除，离开超占回到缺口 0 即重新进入。
    """
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    data = live_snapshot(db, location_id)
    return {"location_id": location_id,
            "lanes": [l for l in data["lines"] if l["status"] == "full"]}


@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    """活口汇总：待补/满仓/超占计数与补量全部按当前在途现算。"""
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    data = live_snapshot(db, location_id)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
    }
