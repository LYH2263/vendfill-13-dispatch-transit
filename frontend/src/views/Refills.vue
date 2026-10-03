<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const orders = ref<any[]>([])
async function loadOrders() { orders.value = await api('/refills/orders?location_id=1') }
async function run() {
  data.value = await api('/refills/run?location_id=1', { method: 'POST' })
  await loadOrders()
}
async function view(id: number) { data.value = await api(`/refills/orders/${id}`) }
onMounted(loadOrders)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 每张单落库即冻结，发车不回改旧单</p>
  <button class="btn" @click="run">按当前在途生成补货单</button>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 #{{ data.id }} ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small>({{ l.status === 'need_fill' ? '待补' : l.status === 'full' ? '满仓' : '超占' }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
  <div class="card" style="margin-top:1rem">
    <h2 style="margin:0 0 0.5rem;font-size:1rem">历史补货单（冻结快照）</h2>
    <table>
      <thead><tr><th>单号</th><th>生成时间</th><th></th></tr></thead>
      <tbody>
        <tr v-for="o in orders" :key="o.id">
          <td>#{{ o.id }}</td>
          <td>{{ o.created_at }}</td>
          <td><button class="btn" style="font-size:0.7rem;padding:0.25rem 0.6rem" @click="view(o.id)">查看</button></td>
        </tr>
        <tr v-if="!orders.length"><td colspan="3" class="muted">尚无补货单</td></tr>
      </tbody>
    </table>
  </div>
</template>
