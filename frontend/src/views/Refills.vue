<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const history = ref<any[]>([])
async function loadHistory() { history.value = await api('/refills/history?location_id=1') }
async function run() {
  data.value = await api('/refills/run?location_id=1', { method: 'POST' })
  await loadHistory() // 新世代落库；旧单补量与状态保持不变
}
function statusText(s: string) {
  return s === 'need_fill' ? '待补' : s === 'full' ? '满仓' : '超占'
}
onMounted(loadHistory)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 每张单按生成时刻在途快照，落库即冻结</p>
  <button class="btn" @click="run">按当前在途生成补货单</button>
  <div class="vf-machine-layout" style="margin-top:1rem">
    <div v-if="data">
      <div class="vf-receipt">
        <h2>*** VendFill 补货单 #{{ data.id }}（新世代）***</h2>
        <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
          <span>货道 / 商品</span><span>补量</span>
        </div>
        <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
          <span>{{ l.slot_no }} {{ l.sku_name }}
            <small>({{ statusText(l.status) }})</small>
          </span>
          <span>{{ l.fill_qty }} / 缺{{ l.gap }} / 在途{{ l.in_transit }}</span>
        </div>
        <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
      </div>
    </div>
    <div class="card" style="margin:0">
      <div class="muted" style="margin-bottom:0.4rem">历史补货单（旧行不改）</div>
      <table>
        <thead><tr><th>世代</th><th>待补/满仓/超占</th><th>总补量</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="o in history" :key="o.id">
            <td>#{{ o.id }}</td>
            <td>{{ o.need_fill_count }} / {{ o.full_count }} / {{ o.overbooked_count }}</td>
            <td>{{ o.total_fill }}</td>
            <td>{{ o.created_at }}</td>
          </tr>
          <tr v-if="!history.length"><td colspan="4" class="muted">尚未生成补货单</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
