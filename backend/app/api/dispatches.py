from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Dispatch, Lane, Location
from app.services.dispatch_service import dispatch_lane
from app.services.fill_engine import compute_gap

router = APIRouter(prefix="/dispatches", tags=["dispatches"])


class DispatchIn(BaseModel):
    qty: int

    @field_validator("qty")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("发车件数必须大于 0")
        return v


@router.post("/lanes/{lane_id}")
def register_dispatch(lane_id: int, body: DispatchIn, db: Session = Depends(get_db)):
    """发车登记：qty 必须 > 0；成功后在途立即增加，活口缺口按新在途现算。

    历史补货单行（补量/状态）是落库快照，不受本次发车影响。
    """
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(404, "货道不存在")
    if db.get(Location, lane.location_id) is None:
        raise HTTPException(404, "点位不存在")
    before_transit = lane.in_transit
    lane, record = dispatch_lane(db, lane_id, body.qty)
    return {
        "id": record.id,
        "lane_id": lane_id,
        "location_id": lane.location_id,
        "qty": body.qty,
        "in_transit": lane.in_transit,
        "gap": compute_gap(lane.capacity, lane.stock, lane.in_transit),
        "prev_in_transit": before_transit,
    }


@router.get("")
def list_dispatches(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Dispatch).order_by(Dispatch.id.desc())
    rows = db.scalars(q).all()
    lane_q = select(Lane)
    if location_id is not None:
        lane_q = lane_q.where(Lane.location_id == location_id)
    lanes = {l.id: l for l in db.scalars(lane_q).all()}
    if location_id is not None:
        rows = [r for r in rows if r.lane_id in lanes]
    return [
        {"id": r.id, "lane_id": r.lane_id,
         "slot_no": lanes[r.lane_id].slot_no if r.lane_id in lanes else "",
         "sku_name": lanes[r.lane_id].sku_name if r.lane_id in lanes else "",
         "qty": r.qty, "dispatched_at": r.dispatched_at.isoformat()}
        for r in rows
    ]
