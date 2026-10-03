import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Dispatch, Lane, Location, RefillOrder, Sale
from app.services.fill_engine import build_fill_lines, summarize


def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Location)) or 0) > 0:
        return
    loc = Location(code="VM-01", name="地铁口 A 点位", address="城东地铁 1 号口")
    db.add(loc)
    db.flush()
    lanes = [
        ("A1", "矿泉水", 20, 5, 0),
        ("A2", "可乐", 18, 18, 0),
        ("B1", "薯片", 12, 3, 2),
        ("B2", "巧克力", 15, 10, 5),
        ("C1", "能量棒", 10, 0, 0),
        ("C2", "口香糖", 24, 24, 2),
    ]
    by_slot: dict[str, Lane] = {}
    for slot, sku, cap, stock, transit in lanes:
        lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                    capacity=cap, stock=stock, in_transit=transit)
        db.add(lane)
        db.flush()
        by_slot[slot] = lane
    now = datetime(2026, 9, 16, 12, 0, 0)
    for i, lane in enumerate(by_slot.values()):
        db.add(Sale(lane_id=lane.id, qty=2 + i, sold_at=now - timedelta(hours=i)))
    db.commit()

    # 旧世代补货单：B1 在途 2 → 缺口 7、补量 7，落库后冻结
    payload = [
        {"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
         "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit}
        for l in sorted(by_slot.values(), key=lambda x: x.slot_no)
    ]
    db.add(RefillOrder(
        location_id=loc.id,
        created_at=datetime(2026, 9, 16, 12, 5, 0),
        lines_json=json.dumps(summarize(build_fill_lines(payload)), ensure_ascii=False),
    ))

    # 随后对 B1 发车 3 件：在途 2 → 5，活口缺口 7 → 4；旧单不回改
    b1 = by_slot["B1"]
    db.add(Dispatch(lane_id=b1.id, qty=3, created_at=datetime(2026, 9, 16, 12, 10, 0)))
    b1.in_transit = b1.in_transit + 3
    db.commit()
