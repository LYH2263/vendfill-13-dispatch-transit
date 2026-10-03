"""发车登记服务：按货道写入本次发出件数并累加到在途。

发车只改 lane.in_transit（与 dispatches 流水），不触碰任何已落库的历史补货单行；
历史单的补量与状态是旧世代快照，满仓/汇总则在读取时按新在途现算。
"""
from sqlalchemy.orm import Session

from app.models.models import Dispatch, Lane


def dispatch_lane(db: Session, lane_id: int, qty: int) -> tuple[Lane, Dispatch]:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise LookupError("货道不存在")
    lane.in_transit += qty
    record = Dispatch(lane_id=lane_id, qty=qty)
    db.add(record)
    db.commit()
    db.refresh(lane)
    db.refresh(record)
    return lane, record
