"""发车登记。

发车按货道写入本次发出件数（Dispatch 行），并把件数累加到该货道的在途
（Lane.in_transit）。发车不回改任何已落库的历史补货单行：旧单补量与状态
保持冻结，此后新生成的补货单才按新在途计算。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Dispatch, Lane

router = APIRouter(prefix="/dispatches", tags=["dispatches"])


class DispatchIn(BaseModel):
    lane_id: int
    qty: int = Field(..., description="本次发出件数，必须为正整数")


@router.post("")
def register_dispatch(payload: DispatchIn, db: Session = Depends(get_db)):
    # 件数 ≤ 0 一律拒绝：在途、汇总、历史单都不动
    if payload.qty <= 0:
        raise HTTPException(400, "发车件数必须大于 0")
    lane = db.get(Lane, payload.lane_id)
    if not lane:
        raise HTTPException(404, "货道不存在")
    record = Dispatch(lane_id=lane.id, qty=payload.qty)
    db.add(record)
    lane.in_transit = lane.in_transit + payload.qty
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "lane_id": lane.id,
        "slot_no": lane.slot_no,
        "sku_name": lane.sku_name,
        "qty": record.qty,
        "in_transit": lane.in_transit,
        "created_at": record.created_at.isoformat(),
    }


@router.get("")
def list_dispatches(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Dispatch, Lane).join(Lane, Lane.id == Dispatch.lane_id)
    if location_id is not None:
        q = q.where(Lane.location_id == location_id)
    q = q.order_by(Dispatch.id.desc())
    return [
        {
            "id": d.id,
            "lane_id": d.lane_id,
            "slot_no": lane.slot_no,
            "sku_name": lane.sku_name,
            "location_id": lane.location_id,
            "qty": d.qty,
            "created_at": d.created_at.isoformat(),
        }
        for d, lane in db.execute(q).all()
    ]
