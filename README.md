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

1. 在「点位」「货道」查看售货机布局与库存（含在途与活口缺口）。
2. 在「销量」了解近期出货。
3. 在「发车登记」按货道写入本次发出件数（必须 > 0），系统累加到在途。
4. 打开「补货单」按当前在途生成建议补货量；历史单行落库即冻结，发车不改旧单。
5. 在「满仓」「汇总」查看按当前在途现算的满仓货道与补货合计（超占不入满仓）。

### 世代规则

- **发车**：`POST /api/dispatches/lanes/{lane_id}`，件数 ≤ 0 返回 422，在途/汇总/历史单均不动。
- **活口**（`/api/lanes`、`/api/refills/full`、`/api/refills/summary`）：始终按货道当前在途现算缺口与状态，发车成功后立即一致；某道进入或离开超占时，满仓名单与计数同步跳变。
- **历史补货单**（`/api/refills/history`、`/api/refills/latest`）：补量与状态是生成时刻的快照，之后不再被改写；只有此后新生成的单（`POST /api/refills/run`）才按新在途计算。

## 开发与测试

```bash
docker compose exec api pytest -q
```
