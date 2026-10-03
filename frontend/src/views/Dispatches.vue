<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const lanes = ref<any[]>([])
const records = ref<any[]>([])
const laneId = ref<number | null>(null)
const qty = ref<number>(1)
const error = ref('')
const busy = ref(false)
const lastResult = ref<any>(null)

async function loadAll() {
  lanes.value = await api('/lanes')
  if (!laneId.value && lanes.value.length) laneId.value = lanes.value[0].id
  records.value = await api('/dispatches')
}

async function submit() {
  error.value = ''
  lastResult.value = null
  if (laneId.value == null) {
    error.value = '请选择货道'
    return
  }
  if (!Number.isInteger(qty.value) || qty.value <= 0) {
    error.value = '发车件数必须为大于 0 的整数'
    return
  }
  busy.value = true
  try {
    lastResult.value = await api('/dispatches', {
      method: 'POST',
      body: JSON.stringify({ lane_id: laneId.value, qty: qty.value }),
    })
    await loadAll()
  } catch (e: any) {
    error.value = String(e?.message || e)
  } finally {
    busy.value = false
  }
}

onMounted(loadAll)
</script>
<template>
  <h1>发车登记</h1>
  <p class="sub">登记本次发出件数 · 写入按货道的发车记录并累加到在途</p>
  <div class="card">
    <div style="display:flex;gap:0.75rem;flex-wrap:wrap;align-items:flex-end">
      <label>
        <div class="muted">货道</div>
        <select v-model.number="laneId">
          <option v-for="l in lanes" :key="l.id" :value="l.id">
            {{ l.slot_no }} · {{ l.sku_name }}（在途 {{ l.in_transit }} / 缺 {{ l.gap }}）
          </option>
        </select>
      </label>
      <label>
        <div class="muted">本次发出件数</div>
        <input v-model.number="qty" type="number" min="1" step="1" style="width:140px" />
      </label>
      <button class="btn" :disabled="busy" @click="submit">{{ busy ? '提交中…' : '确认发车' }}</button>
    </div>
    <p v-if="error" style="color:#c0392b;margin:0.75rem 0 0">发车被拒：{{ error }}</p>
    <p v-if="lastResult" style="color:#1e7e34;margin:0.75rem 0 0">
      已登记：{{ lastResult.slot_no }} {{ lastResult.sku_name }} 发出 {{ lastResult.qty }} 件，
      在途现为 {{ lastResult.in_transit }}
    </p>
  </div>

  <div class="card" style="margin-top:1rem">
    <h2 style="margin:0 0 0.5rem;font-size:1rem">发车记录</h2>
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>发出件数</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in records" :key="r.id">
          <td>{{ r.slot_no }}</td>
          <td>{{ r.sku_name }}</td>
          <td>{{ r.qty }}</td>
          <td>{{ r.created_at }}</td>
        </tr>
        <tr v-if="!records.length"><td colspan="4" class="muted">尚无发车记录</td></tr>
      </tbody>
    </table>
  </div>
</template>
