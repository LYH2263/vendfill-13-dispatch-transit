<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const latestOrder = ref<any>(null)
onMounted(async () => {
  rows.value = await api('/lanes')
  const history = await api('/refills/history?location_id=1')
  latestOrder.value = history[0] ?? null // 只读最近一张已落库世代单，不在本页造新单
})
function statusText(s: string) {
  return s === 'need_fill' ? '待补' : s === 'full' ? '满仓' : '超占'
}
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧最近补货单（历史快照）</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 在途 {{ r.in_transit }} · 缺 {{ r.gap }}</div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="latestOrder">
      <h2>*** 补货建议单 #{{ latestOrder.id }} ***</h2>
      <div class="vf-receipt-line" v-for="l in latestOrder.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }} <small>({{ statusText(l.status) }})</small></span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        第 {{ latestOrder.id }} 代快照 · 发车不改本单
      </p>
    </aside>
  </div>
</template>
