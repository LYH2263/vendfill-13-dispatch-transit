<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
onMounted(async () => {
  rows.value = await api('/lanes')
  // 只读最近一张历史补货单做打印预览；绝不在进入货道页时隐式落新单
  try { refill.value = await api('/refills/latest?location_id=1') } catch { refill.value = null }
})
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧最近补货小票</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0, 'vf-over': r.gap < 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">
          {{ r.stock }}/{{ r.capacity }} · 在途 {{ r.in_transit }} ·
          <span v-if="r.gap > 0">缺 {{ r.gap }}</span>
          <span v-else-if="r.gap === 0">满仓</span>
          <span v-else style="color:#c0392b">超占 {{ -r.gap }}</span>
        </div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 #{{ refill.id }} ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 · 历史单快照 —
      </p>
    </aside>
    <aside class="vf-receipt" v-else>
      <h2>*** 暂无补货单 ***</h2>
      <p class="muted" style="font-size:0.78rem;color:#6a5e48;text-align:center">
        请先到「补货小票」生成一张
      </p>
    </aside>
  </div>
</template>
