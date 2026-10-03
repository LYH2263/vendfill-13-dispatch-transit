<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

interface Lane {
  id: number
  slot_no: string
  sku_name: string
  capacity: number
  stock: number
  in_transit: number
  gap: number
}
interface DispatchRow { id: number; slot_no: string; sku_name: string; qty: number; dispatched_at: string }

const lanes = ref<Lane[]>([])
const dispatches = ref<DispatchRow[]>([])
const qtyByLane = ref<Record<number, string>>({})
const busy = ref<number | null>(null)
const error = ref('')

function statusOf(gap: number) {
  if (gap < 0) return { text: '超占', cls: 'badge-bad' }
  if (gap === 0) return { text: '满仓', cls: 'badge-ok' }
  return { text: '待补', cls: 'badge-warn' }
}

async function refresh() {
  lanes.value = await api('/lanes')
  dispatches.value = await api('/dispatches?location_id=1')
}

async function register(lane: Lane) {
  error.value = ''
  const qty = Number(qtyByLane.value[lane.id] ?? '')
  if (!Number.isInteger(qty) || qty <= 0) {
    error.value = `${lane.slot_no}：发车件数必须是大于 0 的整数`
    return
  }
  busy.value = lane.id
  try {
    await api(`/dispatches/lanes/${lane.id}`, { method: 'POST', body: JSON.stringify({ qty }) })
    qtyByLane.value[lane.id] = ''
    await refresh() // 货道在途、活口缺口立即重取
  } catch (e: any) {
    error.value = String(e?.message ?? e)
  } finally {
    busy.value = null
  }
}

onMounted(refresh)
</script>

<template>
  <h1>发车登记</h1>
  <p class="sub">本次发出按货道写入并累加到在途 · 缺口 = 容量 − 库存 − 在途（按新在途现算）</p>

  <p v-if="error" class="card" style="color:var(--vf-red);border-color:var(--vf-red)">{{ error }}</p>

  <div class="card">
    <table>
      <thead>
        <tr>
          <th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th><th>缺口</th><th>状态</th><th>本次发出</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in lanes" :key="r.id">
          <td>{{ r.slot_no }}</td>
          <td>{{ r.sku_name }}</td>
          <td>{{ r.stock }}</td>
          <td style="color:var(--vf-amber);font-weight:700">{{ r.in_transit }}</td>
          <td>{{ r.capacity }}</td>
          <td>{{ r.gap }}</td>
          <td><span class="badge" :class="statusOf(r.gap).cls">{{ statusOf(r.gap).text }}</span></td>
          <td>
            <input
              v-model="qtyByLane[r.id]"
              type="number"
              min="1"
              step="1"
              style="width:84px;background:#0a0e14;color:var(--vf-text);border:1px solid #3a4454;border-radius:3px;padding:0.3rem 0.4rem"
              @keyup.enter="register(r)"
            />
          </td>
          <td>
            <button class="btn" :disabled="busy === r.id" @click="register(r)">
              {{ busy === r.id ? '…' : '发车' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <h2 style="font-size:0.95rem;margin:1.1rem 0 0.5rem">发车流水</h2>
  <div class="card">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>发出件数</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="d in dispatches" :key="d.id">
          <td>{{ d.slot_no }}</td><td>{{ d.sku_name }}</td>
          <td style="color:var(--vf-amber);font-weight:700">+{{ d.qty }}</td>
          <td>{{ d.dispatched_at }}</td>
        </tr>
        <tr v-if="!dispatches.length"><td colspan="4" class="muted">暂无发车记录</td></tr>
      </tbody>
    </table>
  </div>
</template>
