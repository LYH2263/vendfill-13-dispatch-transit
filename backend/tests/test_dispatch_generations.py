"""发车登记 + 世代隔离集成测试。"""
from app.models.models import Lane, Location


def _mk_location(db) -> int:
    loc = Location(code="VM-01", name="测试点位", address="")
    db.add(loc)
    db.flush()
    # A1 待补 gap=15；A2 满仓 gap=0；B1 待补 gap=7；B2 满仓 gap=0；C2 超占 gap=-2
    for slot, sku, cap, stock, transit in [
        ("A1", "矿泉水", 20, 5, 0),
        ("A2", "可乐", 18, 18, 0),
        ("B1", "薯片", 12, 3, 2),
        ("B2", "巧克力", 15, 10, 5),
        ("C2", "口香糖", 24, 24, 2),
    ]:
        db.add(Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                    capacity=cap, stock=stock, in_transit=transit))
    db.commit()
    return loc.id


def _by_slot(lines: list[dict]) -> dict[str, dict]:
    return {l["slot_no"]: l for l in lines}


def test_seed_scenario(db_session):
    """种子：B1 再发车 3 → 在途+3，旧单补量 7 冻结，新单按新在途补量 4。"""
    from app.services.seed import seed_if_empty
    seed_if_empty(db_session)
    db_session.expire_all()

    b1 = next(l for l in db_session.query(Lane).all() if l.slot_no == "B1")
    assert b1.in_transit == 5  # 2 + 3

    from app.models.models import Dispatch, RefillOrder
    dispatch = db_session.query(Dispatch).filter(Dispatch.lane_id == b1.id).one()
    assert dispatch.qty == 3

    orders = db_session.query(RefillOrder).order_by(RefillOrder.id).all()
    assert len(orders) == 1
    old_b1 = _by_slot(__import__("json").loads(orders[0].lines_json)["lines"])["B1"]
    assert old_b1["in_transit"] == 2
    assert old_b1["gap"] == 7
    assert old_b1["fill_qty"] == 7
    assert old_b1["status"] == "need_fill"

    # 此后新生成的单才按新在途算
    from app.services.refill_service import create_refill_order, live_summary
    _, new_summary = create_refill_order(db_session, 1)
    new_b1 = _by_slot(new_summary["lines"])["B1"]
    assert new_b1["in_transit"] == 5
    assert new_b1["gap"] == 4
    assert new_b1["fill_qty"] == 4

    # 满仓名单与汇总跟新状态：A1/B1/C1 待补，A2/B2 满仓，C2 超占（B1 不在满仓）
    live = live_summary(db_session, 1)
    assert live["need_fill_count"] == 3
    assert live["full_count"] == 2
    assert live["overbooked_count"] == 1
    full_slots = {l["slot_no"] for l in live["lines"] if l["status"] == "full"}
    assert full_slots == {"A2", "B2"}

    # 旧单行依旧没被改掉
    db_session.expire_all()
    old_b1_again = _by_slot(__import__("json").loads(orders[0].lines_json)["lines"])["B1"]
    assert old_b1_again["fill_qty"] == 7
    assert old_b1_again["in_transit"] == 2


def test_dispatch_increments_transit_and_live_views_align(client, db_session):
    loc_id = _mk_location(db_session)

    # 旧世代补货单落库
    old = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert _by_slot(old["lines"])["B1"]["fill_qty"] == 7

    # 发车 3
    b1 = db_session.query(Lane).filter_by(slot_no="B1").one()
    resp = client.post(f"/api/dispatches/lanes/{b1.id}", json={"qty": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["in_transit"] == 5
    assert body["prev_in_transit"] == 2
    assert body["gap"] == 4

    # 货道页：在途与按新在途现算的缺口立刻一致
    lanes = {l["slot_no"]: l for l in client.get("/api/lanes").json()}
    assert lanes["B1"]["in_transit"] == 5
    assert lanes["B1"]["gap"] == 4

    # 汇总计数按活口：A1/B1 待补(2)，A2/B2 满仓(2)，C2 超占(1)
    s = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert s["need_fill_count"] == 2
    assert s["full_count"] == 2
    assert s["overbooked_count"] == 1

    full_slots = {l["slot_no"] for l in
                  client.get(f"/api/refills/full?location_id={loc_id}").json()["lanes"]}
    assert full_slots == {"A2", "B2"}  # C2 已超占不得列满仓；B1 仍待补

    # 历史单：B1 补量/状态/在途快照原样保留
    hist = client.get(f"/api/refills/history?location_id={loc_id}").json()
    assert len(hist) == 1
    old_b1 = _by_slot(hist[0]["lines"])["B1"]
    assert old_b1["in_transit"] == 2
    assert old_b1["gap"] == 7
    assert old_b1["fill_qty"] == 7
    assert old_b1["status"] == "need_fill"

    # 新世代单按新在途
    new = client.post(f"/api/refills/run?location_id={loc_id}").json()
    new_b1 = _by_slot(new["lines"])["B1"]
    assert new_b1["in_transit"] == 5
    assert new_b1["gap"] == 4
    assert new_b1["fill_qty"] == 4

    # 两张单都在历史里，旧单仍不变
    hist = client.get(f"/api/refills/history?location_id={loc_id}").json()
    assert len(hist) == 2
    assert _by_slot(hist[1]["lines"])["B1"]["fill_qty"] == 7
    assert _by_slot(hist[0]["lines"])["B1"]["fill_qty"] == 4


def test_full_list_jumps_when_lane_enters_and_leaves_overbooked(client, db_session):
    loc_id = _mk_location(db_session)
    client.post(f"/api/refills/run?location_id={loc_id}")

    b2 = db_session.query(Lane).filter_by(slot_no="B2").one()  # gap=0 满仓
    a1 = db_session.query(Lane).filter_by(slot_no="A1").one()  # gap=15 待补

    def full_slots():
        return {l["slot_no"] for l in
                client.get(f"/api/refills/full?location_id={loc_id}").json()["lanes"]}

    # 满仓道发车 2 → 进入超占，必须立刻从满仓名单消失
    client.post(f"/api/dispatches/lanes/{b2.id}", json={"qty": 2})
    assert "B2" not in full_slots()
    s = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert s["overbooked_count"] == 2  # B2 + C2
    assert s["full_count"] == 1        # 仅 A2

    # 待补道发满 15 → 进入满仓，名单同跳
    client.post(f"/api/dispatches/lanes/{a1.id}", json={"qty": 15})
    assert "A1" in full_slots()
    s = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert s["full_count"] == 2  # A1 + A2
    assert s["need_fill_count"] == 1  # 仅 B1

    # 再发 1 → 离开满仓进入超占，名单再跳
    client.post(f"/api/dispatches/lanes/{a1.id}", json={"qty": 1})
    assert "A1" not in full_slots()
    s = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert s["overbooked_count"] == 3

    # 历史旧单里 B2/A1 的状态仍是发车前的冻结快照
    hist = client.get(f"/api/refills/history?location_id={loc_id}").json()
    old = _by_slot(hist[-1]["lines"])
    assert old["B2"]["status"] == "full"
    assert old["A1"]["status"] == "need_fill"


def test_nonpositive_dispatch_rejected_and_nothing_moves(client, db_session):
    loc_id = _mk_location(db_session)
    client.post(f"/api/refills/run?location_id={loc_id}")
    b1 = db_session.query(Lane).filter_by(slot_no="B1").one()

    before_summary = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    before_full = client.get(f"/api/refills/full?location_id={loc_id}").json()

    for bad in (0, -1, -10):
        resp = client.post(f"/api/dispatches/lanes/{b1.id}", json={"qty": bad})
        assert resp.status_code == 422, bad

    db_session.expire_all()
    b1 = db_session.query(Lane).filter_by(slot_no="B1").one()
    assert b1.in_transit == 2  # 在途不动

    from app.models.models import Dispatch
    assert db_session.query(Dispatch).count() == 0  # 无发车流水
    assert client.get(f"/api/refills/summary?location_id={loc_id}").json() == before_summary
    assert client.get(f"/api/refills/full?location_id={loc_id}").json() == before_full

    hist = client.get(f"/api/refills/history?location_id={loc_id}").json()
    assert len(hist) == 1  # 历史单不增不改
    assert _by_slot(hist[0]["lines"])["B1"]["fill_qty"] == 7


def test_dispatch_unknown_lane_404(client, db_session):
    _mk_location(db_session)
    resp = client.post("/api/dispatches/lanes/9999", json={"qty": 1})
    assert resp.status_code == 404
