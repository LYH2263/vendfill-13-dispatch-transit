"""发车登记的世代隔离测试：

- 件数 ≤ 0 拒绝，在途 / 汇总 / 历史单均不动
- 发车按货道累加在途，货道页缺口按新在途现算
- 已落库历史补货单行的补量与状态不被回改
- 满仓名单与汇总按当前在途现算；车道进入超占即从满仓名单移除
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Dispatch, Lane, RefillOrder
from app.services.seed import seed_if_empty


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    db = TestingSession()
    seed_if_empty(db)
    yield db
    db.close()


@pytest.fixture()
def client(db_session):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def lane_by_slot(db, slot):
    return db.scalar(select(Lane).where(Lane.slot_no == slot))


def line_by_slot(order_payload, slot):
    return next(l for l in order_payload["lines"] if l["slot_no"] == slot)


# ---- 种子验收：旧单冻结，B1 已再发车 3 件 ----

def test_seed_b1_dispatch_increments_transit(db_session):
    b1 = lane_by_slot(db_session, "B1")
    assert b1.in_transit == 5  # 原始 2 + 发车 3
    assert db_session.scalar(select(func.count()).select_from(Dispatch)) == 1
    dispatch = db_session.scalar(select(Dispatch))
    assert dispatch.lane_id == b1.id and dispatch.qty == 3


def test_seed_old_order_frozen_at_generation(db_session, client):
    # 种子已落一张旧世代单，B1 按旧在途 2：缺口 7、补量 7
    orders = client.get("/api/refills/orders?location_id=1").json()
    assert len(orders) == 1
    old = client.get(f"/api/refills/orders/{orders[0]['id']}").json()
    b1 = line_by_slot(old, "B1")
    assert b1["in_transit"] == 2
    assert b1["gap"] == 7
    assert b1["fill_qty"] == 7
    assert b1["status"] == "need_fill"


def test_seed_live_views_reflect_new_transit(client):
    # 货道页：B1 缺口按新在途 5 现算为 4
    lanes = {l["slot_no"]: l for l in client.get("/api/lanes").json()}
    assert lanes["B1"]["in_transit"] == 5
    assert lanes["B1"]["gap"] == 4
    # 活口汇总：A1/B1/C1 待补，A2/B2 满仓，C2 在途 2 已超占
    s = client.get("/api/refills/summary?location_id=1").json()
    assert s["need_fill_count"] == 3
    assert s["full_count"] == 2
    assert s["overbooked_count"] == 1
    assert s["total_fill"] == 15 + 4 + 10
    # 满仓名单不得包含已超占的 C2
    full_slots = {l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]}
    assert full_slots == {"A2", "B2"}


# ---- 件数 ≤ 0 拒绝：在途、汇总、历史单都不动 ----

@pytest.mark.parametrize("bad_qty", [0, -1, -10])
def test_dispatch_nonpositive_rejected(db_session, client, bad_qty):
    b1 = lane_by_slot(db_session, "B1")
    before_transit = b1.in_transit
    before_dispatch_count = db_session.scalar(select(func.count()).select_from(Dispatch))
    before_order_count = db_session.scalar(select(func.count()).select_from(RefillOrder))
    summary_before = client.get("/api/refills/summary?location_id=1").json()

    r = client.post("/api/dispatches", json={"lane_id": b1.id, "qty": bad_qty})
    assert r.status_code == 400

    db_session.expire_all()
    assert lane_by_slot(db_session, "B1").in_transit == before_transit
    assert db_session.scalar(select(func.count()).select_from(Dispatch)) == before_dispatch_count
    assert db_session.scalar(select(func.count()).select_from(RefillOrder)) == before_order_count
    assert client.get("/api/refills/summary?location_id=1").json() == summary_before


def test_dispatch_unknown_lane_404(client):
    r = client.post("/api/dispatches", json={"lane_id": 9999, "qty": 1})
    assert r.status_code == 404


# ---- 成功发车：在途累加、旧单不动、新单按新在途 ----

def test_dispatch_then_old_frozen_new_recomputed(db_session, client):
    b1 = lane_by_slot(db_session, "B1")
    old_order_id = client.get("/api/refills/orders?location_id=1").json()[0]["id"]

    # 再发车 4 件：在途 5 → 9，活口缺口 4 → 0（B1 进入满仓）
    r = client.post("/api/dispatches", json={"lane_id": b1.id, "qty": 4})
    assert r.status_code == 200
    assert r.json()["in_transit"] == 9
    assert r.json()["qty"] == 4

    db_session.expire_all()
    lanes = {l["slot_no"]: l for l in client.get("/api/lanes").json()}
    assert lanes["B1"]["in_transit"] == 9 and lanes["B1"]["gap"] == 0

    # 旧单仍冻结：补量 7、状态 need_fill，行数不变
    old = client.get(f"/api/refills/orders/{old_order_id}").json()
    old_b1 = line_by_slot(old, "B1")
    assert old_b1["fill_qty"] == 7 and old_b1["gap"] == 7 and old_b1["status"] == "need_fill"

    # 满仓名单同跳：B1 进入满仓
    full_slots = {l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]}
    assert "B1" in full_slots

    # 再发 1 件：B1 缺口 0 → -1，进入超占，必须立刻离开满仓名单、汇总计数同跳
    r = client.post("/api/dispatches", json={"lane_id": b1.id, "qty": 1})
    assert r.status_code == 200
    s = client.get("/api/refills/summary?location_id=1").json()
    full_slots = {l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]}
    assert "B1" not in full_slots
    assert s["overbooked_count"] == 2  # B1 + C2
    assert s["full_count"] == 2        # 只剩 A2、B2
    assert s["need_fill_count"] == 2   # A1、C1
    b1_live = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "B1")
    assert b1_live["gap"] == -1

    # 此后新生成的单才按新在途算：B1 超占、补量 0
    new_order = client.post("/api/refills/run?location_id=1").json()
    new_b1 = line_by_slot(new_order, "B1")
    assert new_b1["in_transit"] == 10 and new_b1["gap"] == -1
    assert new_b1["fill_qty"] == 0 and new_b1["status"] == "overbooked"
    # 旧单依然不动
    old = client.get(f"/api/refills/orders/{old_order_id}").json()
    old_b1 = line_by_slot(old, "B1")
    assert old_b1["fill_qty"] == 7 and old_b1["in_transit"] == 2


def test_full_lane_entering_overbooked_drops_from_full_list(db_session, client):
    # A2 原本缺口 0（在满仓名单）；发车 1 件使其进入超占
    a2 = lane_by_slot(db_session, "A2")
    full_before = {l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]}
    assert "A2" in full_before
    client.post("/api/dispatches", json={"lane_id": a2.id, "qty": 1})
    full_after = {l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]}
    assert "A2" not in full_after  # 禁止货道已超占而满仓仍列该道
    a2_live = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "A2")
    assert a2_live["gap"] == -1


def test_latest_does_not_auto_create_order(db_session, client):
    # latest 只读历史单；删除全部单后应 404，绝不隐式落新单
    db_session.query(RefillOrder).delete()
    db_session.commit()
    r = client.get("/api/refills/latest?location_id=1")
    assert r.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(RefillOrder)) == 0
