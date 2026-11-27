<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  getOrderDetail, createShipment, markShipped, markDelivered,
} from '@/api/adminPo'
import { fetchOrderQueue } from '@/composables/useOrderQueue'
import { formatCurrency } from '@/utils/helpers'
import { extractErrorMessage } from '@/utils/http'
import { StatusBadge, toast } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const selected = ref(null)
const detail = ref(null)

/**
 * 队列取数状态（★ S5 P-2）。
 *
 * 原实现 `getOrders({page_size:200})` 拉一页再客户端按状态筛 ⇒ 累计单量越过 200
 * 之后被挤出那一页的 confirmed 单**运营永远看不到**，且页面无任何提示。
 * 现在走服务端 `status__in` + 翻页取全，并把「队列共几单」如实显示出来。
 */
const QUEUE_STATUSES = ['confirmed', 'shipped', 'in_production']
const queueTotal = ref(0)
const queueTruncated = ref(false)
const queueError = ref('')

const shipForm = reactive({
  carrier: '',
  tracking_number: '',
  tracking_url: '',
  estimated_delivery: '',
  notes: '',
  items: [],
})
const receivedBy = ref({})

/**
 * 页内错误落位（★ A-095）。
 *
 * 为什么不只用 toast：`ElMessage` 默认 3 秒自动消失。发货被拒后运营往往已经在
 * 看别的地方，3 秒过去就只剩"我点了按钮，什么都没发生"——这正是 QA 报的
 * 「点了无反应」。所以校验/失败信息必须**留在页面上**直到下次提交。
 */
const shipError = ref('')
/** 提交中（防重复点击 —— 无此闸时连点两下会建出两条相同发货记录） */
const savingShipment = ref(false)

/**
 * 标记发货 / 标记送达的页内错误落位（★ A-096）。
 *
 * 与 `shipError` 分开：两者是不同表单区域的动作，共用一个 ref 会出现
 * 「刚填完物流信息报的错，被另一个操作的错误覆盖」这种对不上号的情况。
 */
const actionError = ref('')
/** 正在执行的标记动作键（`shipped-<id>` / `delivered-<id>`），用于禁用按钮 + 防重复提交 */
const actionBusy = ref('')

async function load() {
  loading.value = true
  queueError.value = ''
  try {
    // ★ S5 P-2：服务端按状态集合筛 + 翻页取全（见 useOrderQueue.js 头注）
    const { orders: rows, total, truncated } = await fetchOrderQueue(QUEUE_STATUSES)
    orders.value = rows
    queueTotal.value = total
    queueTruncated.value = truncated
  } catch (e) {
    // 取数失败必须落在页面上：否则左表只显示旧数据，运营会以为"队列就这些单"
    queueError.value = extractErrorMessage(
      e?.response?.data ?? e, 'Could not load the shipping queue.')
  } finally {
    loading.value = false
  }
}

async function openOrder(o) {
  selected.value = o.id
  const res = await getOrderDetail(o.id)
  detail.value = res.data || res
  shipForm.items = (detail.value.items || []).map((it) => ({
    order_item_id: it.id,
    sku_code: it.sku_code,
    quantity: it.quantity,
  }))
}

/** 清空物流输入（保留 items —— 它们由 `openOrder` 按订单明细重算） */
function resetShipForm() {
  shipForm.carrier = ''
  shipForm.tracking_number = ''
  shipForm.tracking_url = ''
  shipForm.estimated_delivery = ''
  shipForm.notes = ''
}

/**
 * ★ 2026-11-18（A-095）：发货前必须至少给出「承运商」或「运单号」，且要清空表单。
 *
 * 原先这里**零校验零反馈**：直接 `await createShipment(...)`，成功后既不提示、
 * 也不清空表单 —— 运营点完看不出成功还是失败，会重复提交出多条空发货记录。
 * 后端已同步加了同样的跨字段校验（真闸门在服务端），前端这一层只是为了少跑一次 400。
 */
async function submitShipment() {
  if (!selected.value || savingShipment.value) return
  const carrier = (shipForm.carrier || '').trim()
  const tracking = (shipForm.tracking_number || '').trim()
  if (!carrier && !tracking) {
    shipError.value = 'Fill in a carrier or a tracking number — '
      + 'a shipment with neither cannot be traced or claimed.'
    return
  }
  shipError.value = ''
  savingShipment.value = true
  try {
    // 注意 `items` 照常传（它是发货明细，与物流信息无关）
    await createShipment(selected.value, { ...shipForm, carrier, tracking_number: tracking })
    toast.success('Shipment created')
    resetShipForm()
    // ★ A-096：`load()` 与 `openOrder()` 一起刷新 —— 建完发货记录后订单通常从
    //   confirmed 变 in_production/shipped，左侧列表的 Status 列必须跟着变。
    const id = selected.value
    await Promise.all([load(), openOrder({ id })])
  } catch (e) {
    shipError.value = extractErrorMessage(
      e?.response?.data ?? e, 'Could not create the shipment.')
  } finally {
    savingShipment.value = false
  }
}

/**
 * ★ 2026-11-18（A-096）：标记发货 / 标记送达后的统一收尾。
 *
 * ## 原缺陷（实测代码，非凭记忆）
 * ```
 * async function doMarkShipped(id) {
 *   await markShipped(id)
 *   if (selected.value) openOrder({ id: selected.value })   // ← 忘了 await
 * }
 * ```
 * 三个问题叠在一起：
 *   1. `openOrder(...)` **没 await** ⇒ 失败变成 unhandled rejection，页面上什么都看不到；
 *   2. `load()` 从未被调用 ⇒ 左侧订单列表的 Status 列**永久停在旧状态**：刚把单标成
 *      shipped，左表还写着 confirmed，运营会以为没生效而重复操作；
 *   3. 成功路径**零反馈**（无 toast）⇒ 无法区分"真的成功了"与"点了没反应"。
 *
 * ## 刷新后"行从左侧消失"是有意保留的
 * `load()` 只收 `confirmed/shipped/in_production`。标成 delivered 后该单会掉出列表，
 * 但右侧详情**继续保留**——如果这时候把面板也关掉，运营刚点完"Marked as delivered"
 * 就看见整块消失，观感等同于操作失败。详情里状态徽章会显示 delivered，信息不缺。
 */
async function runShipAction(busyKey, work, okMsg) {
  if (actionBusy.value) return
  actionError.value = ''
  actionBusy.value = busyKey
  try {
    await work()
    toast.success(okMsg)
    const id = selected.value
    // 两个请求互不依赖 ⇒ 并发；`openOrder` 内部会重算 shipForm.items
    await Promise.all([load(), id ? openOrder({ id }) : Promise.resolve()])
  } catch (e) {
    actionError.value = extractErrorMessage(
      e?.response?.data ?? e, 'Could not update the shipment status.')
  } finally {
    actionBusy.value = ''
  }
}

function doMarkShipped(id) {
  return runShipAction(
    `shipped-${id}`,
    () => markShipped(id),
    'Shipment marked as shipped',
  )
}

function doMarkDelivered(s) {
  // ★ 2026-11-27（A-224）：签收人此前是"可填可不填"，实际运营一路点下来没人填，
  //   于是订单详情的 Received By 永远是空 —— 而这正是货损/丢件争议时唯一的凭证。
  //   改为前端必填：没填就不发请求，并明确告诉运营缺什么（不是静默失败）。
  if (!(receivedBy.value[s.id] || '').trim()) {
    actionError.value = 'Please enter who received the goods (Received by) before marking delivered.'
    return
  }
  actionError.value = ''
  return runShipAction(
    `delivered-${s.id}`,
    () => markDelivered(s.id, receivedBy.value[s.id].trim()),
    'Shipment marked as delivered',
  )
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Shipment Desk</h1>
        <p class="po-page-subtitle">Create multi-batch shipments and mark shipped / delivered.</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-form-grid">
      <div class="po-card">
        <h2 class="po-section-title">
          Confirmed / In-Transit Orders
          <span class="po-muted" data-testid="queue-total">({{ queueTotal }})</span>
        </h2>
        <p v-if="queueError" class="po-ship-error" data-testid="queue-error">{{ queueError }}</p>
        <p v-if="queueTruncated" class="po-queue-warn" data-testid="queue-truncated">
          Showing the first {{ orders.length }} of {{ queueTotal }} orders — the queue exceeds
          the page cap, so the rest is not listed here.
        </p>
        <table class="po-table" v-if="orders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Items</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id" :class="{ 'po-row-selected': selected === o.id }" @click="openOrder(o)" style="cursor:pointer">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" /></td>
              <td>{{ o.items_count }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No orders to ship.</div>
      </div>

      <div class="po-card" v-if="detail">
        <h2 class="po-section-title">Order {{ detail.order_no }}</h2>

        <!-- New shipment -->
        <h3 class="po-subsection-title">New Shipment</h3>
        <div class="po-form-grid">
          <div class="po-field"><label class="po-label">Carrier</label><input v-model="shipForm.carrier" class="po-input" data-testid="ship-carrier" /></div>
          <div class="po-field"><label class="po-label">Tracking #</label><input v-model="shipForm.tracking_number" class="po-input" data-testid="ship-tracking" /></div>
          <div class="po-field"><label class="po-label">Tracking URL</label><input v-model="shipForm.tracking_url" class="po-input" data-testid="ship-tracking-url" /></div>
          <div class="po-field"><label class="po-label">Est. Delivery</label><input v-model="shipForm.estimated_delivery" type="date" class="po-input" data-testid="ship-est-delivery" /></div>
        </div>
        <table class="po-table" style="margin-top:12px">
          <thead><tr><th>SKU</th><th>Qty to Ship</th></tr></thead>
          <tbody>
            <tr v-for="(it, i) in shipForm.items" :key="i">
              <td class="po-mono">{{ it.sku_code }}</td>
              <td><input v-model.number="it.quantity" type="number" min="0" class="po-input" style="width:100px" /></td>
            </tr>
          </tbody>
        </table>
        <p v-if="shipError" class="po-ship-error" data-testid="ship-error">{{ shipError }}</p>
        <button
          class="po-btn po-btn-accent"
          style="margin-top:12px"
          data-testid="ship-create"
          :disabled="savingShipment"
          @click="submitShipment"
        >{{ savingShipment ? 'Creating…' : 'Create Shipment' }}</button>

        <!-- Existing shipments -->
        <h3 class="po-subsection-title" style="margin-top:24px">Shipments</h3>
        <div v-for="s in (detail.shipments || [])" :key="s.id" class="po-shipment">
          <div class="po-between">
            <div class="po-row">
              <StatusBadge :status="s.status" />
              <span class="po-mono">{{ s.tracking_number || '—' }}</span>
              <span class="po-muted">{{ s.carrier }}</span>
            </div>
            <div class="po-row">
              <button
                v-if="s.status !== 'shipped' && s.status !== 'delivered'"
                class="po-btn po-btn-primary po-btn-sm"
                data-testid="ship-mark-shipped"
                :disabled="!!actionBusy"
                @click="doMarkShipped(s.id)"
              >Mark Shipped</button>
              <template v-if="s.status === 'shipped'">
                <input v-model="receivedBy[s.id]" class="po-input" style="width:120px" placeholder="Received by" />
                <button
                  class="po-btn po-btn-primary po-btn-sm"
                  data-testid="ship-mark-delivered"
                  :disabled="!!actionBusy"
                  @click="doMarkDelivered(s)"
                >Mark Delivered</button>
              </template>
            </div>
          </div>
        </div>
        <p v-if="actionError" class="po-ship-error" data-testid="ship-action-error">{{ actionError }}</p>
        <div v-if="!(detail.shipments || []).length" class="po-muted">No shipments yet.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
/* ★ S5 P-2：队列超出翻页上限时的显式提示（不再静默截断） */
.po-queue-warn {
  margin: 0 0 10px;
  padding: 8px 12px;
  border: 1px solid var(--color-warning, #d97706);
  border-radius: 4px;
  background: rgba(217, 119, 6, .06);
  color: inherit;
  font-size: 12px;
  line-height: 1.45;
}
.po-shipment { border:1px solid var(--color-border-light); border-radius:4px; padding:12px; margin-top:12px; }
/* ★ A-095：发货被拒的页内错误落位（留到下次提交，不随 toast 3 秒消失） */
.po-ship-error {
  margin: 10px 0 0;
  padding: 8px 12px;
  border: 1px solid var(--color-danger, #dc2626);
  border-radius: 4px;
  background: var(--color-danger-subtle, #fef2f2);
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  line-height: 1.45;
}
</style>
