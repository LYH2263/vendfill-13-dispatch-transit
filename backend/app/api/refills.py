"""补货单 API。

世代边界：
- POST /run、GET /latest、GET /history 面向「历史补货单」——落库即冻结的快照，
  发车不会改写其中任何行的补量与状态；只有此后新生成的单才按新在途算。
- GET /full、GET /summary 面向「活口」——每次按货道当前在途现算，
  发车成功后立即与货道页一致（含满仓/超占跳变）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Location, RefillOrder
from app.services.refill_service import create_refill_order, live_summary, serialize_order

router = APIRouter(prefix="/refills", tags=["refills"])


@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "点位不存在")
    order, snapshot = create_refill_order(db, location_id)
    return {"id": order.id, "location_id": location_id, **snapshot}


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                       .order_by(RefillOrder.id.desc())).first()
    if order is None:
        if db.get(Location, location_id) is None:
            raise HTTPException(404, "点位不存在")
        order, _ = create_refill_order(db, location_id)
    return serialize_order(order)


@router.get("/history")
def history(location_id: int = 1, db: Session = Depends(get_db)):
    """已落库的历史补货单，按世代倒序；内容均为各自生成时刻的冻结快照。"""
    orders = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                        .order_by(RefillOrder.id.desc())).all()
    return [serialize_order(o) for o in orders]


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    """活口满仓名单：按当前在途现算。

    gap == 0 才是满仓；发车使某道进入超占（gap < 0）后立即从名单消失，
    离开超占回到 gap == 0 时立即重新出现。绝不读取历史单快照。
    """
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "点位不存在")
    summary = live_summary(db, location_id)
    return {"location_id": location_id,
            "lanes": [l for l in summary["lines"] if l["status"] == "full"]}


@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    """活口汇总：待补/满仓/超占计数与建议总量，全部按当前在途现算。"""
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "点位不存在")
    summary = live_summary(db, location_id)
    return {
        "location_id": location_id,
        "total_fill": summary["total_fill"],
        "need_fill_count": summary["need_fill_count"],
        "full_count": summary["full_count"],
        "overbooked_count": summary["overbooked_count"],
    }
