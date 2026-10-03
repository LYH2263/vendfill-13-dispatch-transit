# VendFill 售货机补货

按货道容量、库存与在途量计算缺口，生成不超缺口、非负的补货单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4800 |
| API | http://localhost:9800 |
| API 文档 | http://localhost:9800/docs |
| Postgres | localhost:5449 |

健康检查：`GET http://localhost:9800/api/health`

## 使用说明

1. 在「点位」「货道」查看售货机布局、库存与在途。
2. 在「销量」了解近期出货。
3. 在「发车登记」按货道登记本次发出件数：件数必须大于 0；发车后该货道在途累加，活口缺口、满仓名单、汇总计数立刻按新在途现算。
4. 打开「补货小票」按当前在途生成建议补货量。每张单落库即冻结：此后发车不会回改旧单的补量与状态，只有新生成的单才按新在途计算。
5. 在「满仓」「汇总」查看已满货道与补货合计（均为当前在途的实时视图；货道进入或离开超占时名单与计数同跳）。

### 世代隔离

- 历史补货单行（`refill_orders.lines_json`）是落库时的快照，发车不回改。
- `/refills/summary`、`/refills/full` 始终按车道当前 `in_transit` 实时计算，不读历史快照。
- `/refills/latest` 仅在已有补货单时返回最近一张，不再隐式建单；无单时返回 404。

## 开发与测试

```bash
docker compose exec api pytest -q
```

本地无 Postgres 时，测试默认使用内存 sqlite（见 `backend/tests/conftest.py`），直接 `pytest -q` 即可。
