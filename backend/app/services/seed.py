from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Lane, Location, Sale
from app.services.dispatch_service import dispatch_lane
from app.services.refill_service import create_refill_order

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Location)) or 0) > 0:
        return
    loc = Location(code="VM-01", name="地铁口 A 点位", address="城东地铁 1 号口")
    db.add(loc); db.flush()
    lanes = [
        ("A1", "矿泉水", 20, 5, 0),
        ("A2", "可乐", 18, 18, 0),
        ("B1", "薯片", 12, 3, 2),
        ("B2", "巧克力", 15, 10, 5),
        ("C1", "能量棒", 10, 0, 0),
        ("C2", "口香糖", 24, 24, 2),
    ]
    lane_ids = []
    for slot, sku, cap, stock, transit in lanes:
        lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku, capacity=cap, stock=stock, in_transit=transit)
        db.add(lane); db.flush()
        lane_ids.append(lane.id)
    now = datetime(2026, 9, 16, 12, 0, 0)
    for i, lid in enumerate(lane_ids):
        db.add(Sale(lane_id=lid, qty=2 + i, sold_at=now - timedelta(hours=i)))
    db.commit()

    # 旧世代补货单：此时 B1 在途=2，缺口=7，补量=7（need_fill）。落库后冻结。
    old_order, _ = create_refill_order(db, loc.id)

    # B1 再发车 3 件：B1 在途 2 → 5；旧单行不改，此后新生成的单才按新在途算（缺口 12-3-5=4）。
    b1 = db.scalars(select(Lane).where(Lane.location_id == loc.id, Lane.slot_no == "B1")).one()
    dispatch_lane(db, b1.id, 3)
