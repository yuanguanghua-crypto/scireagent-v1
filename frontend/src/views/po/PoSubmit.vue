<script setup>
import { reactive, ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { submitPo, getOrderDetail, getMyQuotes } from '@/api/poPortal'
import { getProducts, getProductDetail } from '@/api/products'
import { getAddresses } from '@/api/addresses'
import { useBasketStore } from '@/stores/basket'
import { SHIPPING_METHODS } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { toast } from '@/components/common'

const router = useRouter()
const route = useRoute()
const basketStore = useBasketStore()
const submitting = ref(false)
const successOrderNo = ref('')
// ★ 2026-10-28：缺货拦截的结构化结果（后端 meta.error.details）
const shortages = ref([])
const shortageMessage = ref('')
// ★ 2026-11-27（A-147）：明细行的失败原因（常驻，不再只靠 toast）
const itemsError = ref('')
// ★ 2026-11-27（A-149）：提交成功后跳订单详情用
const successOrderId = ref(null)
let redirectTimer = null
const reorderSourceId = ref('')
// 交付日期下限：本地时区的今天（YYYY-MM-DD）。
// 用 toLocaleDateString('en-CA') 取本地时区日期，规避 toISOString() 的 UTC 偏移导致少一天。
const minDeliveryDate = ref(new Date().toLocaleDateString('en-CA'))

/**
 * ★ 2026-11-20（S4 / A-189）：日期与邮箱的**应用层**校验状态。
 *
 * ## 为什么必须自己做（而不是留给浏览器）
 * 本页表单里有三条 HTML5 原生约束：`#po-f5` 的 `min`、`#po-f9` 的 `type=email`、
 * 明细行数量框的 `min="1"`。只要任一不满足，浏览器就**直接吃掉 submit 事件** ——
 * `handleSubmit` 一行都不执行 ⇒ 无 toast、无横幅、无跳转、**0 个网络请求**。
 * QA 报的「提交按钮静默失效」就是这个签名（实测 6 场景已坐实，见
 * `_s4work/probe_a189.cjs`：过去日期/非法邮箱/数量 0 全部 0 请求、0 提示）。
 *
 * 原生的那个气泡虽然会弹，但它会飘走、不可追溯、也不在应用反馈区内，
 * 且**不做任何记录** —— 用户点完提交只看到"什么都没发生"。
 *
 * ## 做法
 * 表单加 `novalidate`（约束属性**保留**：日期选择器仍不许选过去、邮箱键盘不变），
 * 把拦截权收回到 `handleSubmit`，由 `validateDateAndEmail` 判定并落**行内常驻提示**
 * + 按钮旁汇总行。提交失败从此一定看得见。
 */
const formErrors = reactive({ date: '', email: '' })
const dateEl = ref(null)
const emailEl = ref(null)

// HTML5 `type=email` 的等价近似（要求有且仅有一个 @，两侧非空且无空格）。
// 刻意不写更严格的"必须带点"版本：原生 type=email 允许 `a@b`，
// 收紧会让原本能提交的地址被前端拦下（后端 EmailField 会另有更严的校验兜底）。
const EMAIL_RE = /^[^\s@]+@[^\s@]+$/

function validateDateAndEmail() {
  formErrors.date = ''
  formErrors.email = ''
  // 日期：ISO 字符串直接比大小即等价于 rangeUnderflow（`:min` 用的也是 YYYY-MM-DD）
  const d = String(form.requested_delivery_date || '').trim()
  if (d && d < minDeliveryDate.value) {
    formErrors.date = `Requested delivery date cannot be earlier than ${minDeliveryDate.value} (today).`
  }
  // 邮箱：允许留空（后端 required=False）
  const e = String(form.shipping_email || '').trim()
  if (e && !EMAIL_RE.test(e)) {
    formErrors.email = 'Please enter a valid email address, e.g. name@lab.edu.'
  }
  return !formErrors.date && !formErrors.email
}

const firstFormError = computed(() => formErrors.date || formErrors.email || '')

onMounted(async () => {
  // ★ 2026-11-27（A-186 / A-190）：两个"本该自动带入"的东西此前都没接 ——
  //   ① 地址簿里标了 default 的地址不会出现在 Ship-to/Bill-to；
  //   ② 购物车里的商品不会出现在明细行（页面永远从 "No line items yet." 开始）。
  //   顺序有讲究：reorder 的数据最具体，先让它填；购物车只在**仍然空**时才补，
  //   免得把两张单的商品混在一起。
  if (route.query.reorder) {
    reorderSourceId.value = route.query.reorder
    await loadReorder()
  }
  await prefillFromAddresses()
  if (!items.value.length) await prefillFromBasket()
  loadQuotes()
})

/** 把地址簿里的默认地址填进 Ship-to / Bill-to（A-186）。 */
async function prefillFromAddresses() {
  let list = []
  try {
    const res = await getAddresses()
    const payload = res.data || res
    list = Array.isArray(payload) ? payload : (payload.results || payload.data || [])
  } catch {
    return                      // 拿不到地址簿不该挡住填表
  }
  if (!Array.isArray(list) || !list.length) return

  const pick = (type) => list.find((a) => a.type === type && a.is_default)
    || list.find((a) => a.type === type)
    || null
  // ⚠️ 不要把 attention 拼进地址行：它已经填在「Recipient / Bill-to name」里了，
  //   再拼一次会得到 "Dr. X, 789 Science Park Drive, …"，收件人姓名出现两遍。
  const line = (a) => [a.line1, a.line2, a.city, a.state, a.postal_code, a.country]
    .filter((v) => v && String(v).trim()).join(', ')

  const ship = pick('shipping')
  if (ship) {
    form.shipping_name = form.shipping_name || ship.attention || ''
    form.shipping_phone = form.shipping_phone || ship.phone || ''
    form.shipping_address = form.shipping_address || line(ship)
    form.shipping_email = form.shipping_email || ''
  }
  const bill = pick('billing')
  if (bill) {
    form.billing_name = form.billing_name || bill.attention || ''
    form.billing_address = form.billing_address || line(bill)
  }
}

/**
 * 把购物车商品带入明细行（A-190）。
 *
 * ⚠️ 只在**明细为空**时补：用户可能已经手填了行，或刚从订单 Load from Order，
 *   那种情况下再塞一遍购物车就会得到一张混着两种来源的单子。
 * 单价取购物车行的 `unit_price`（后端已按阶梯价算过，见 `resolve_unit_price`），
 * 与结账页看到的是同一个数。
 */
async function prefillFromBasket() {
  try {
    await basketStore.loadBasket()
  } catch {
    return
  }
  const lines = basketStore.items || []
  if (!lines.length) return
  for (const ci of lines) {
    const skuId = ci.sku || ci.sku_id
    if (!skuId) continue
    items.value.push({
      productId: ci.product || ci.product_id,
      productName: ci.product_name || `Product #${ci.product || ci.product_id}`,
      // 只带这一档 SKU：购物车里选定的就是它，不必再拉整张价目表
      skus: [{
        id: skuId,
        sku_code: ci.sku_code || '',
        pack_size: ci.pack_size || '',
        price: ci.unit_price,
      }],
      skuId,
      quantity: ci.quantity || 1,
      unitPrice: ci.unit_price,
      searchResults: [],
      searching: false,
      searchSeq: 0,
    })
  }
  toast.info(`Carried over ${lines.length} item${lines.length === 1 ? '' : 's'} from your cart.`)
}

const quoteOptions = ref([])

async function loadQuotes() {
  try {
    const res = await getMyQuotes()
    const payload = res.data || res
    const list = payload.results || payload.data || payload || []
    // 只列可关联的报价（已核实 verified）；rejected/pending 不展示
    quoteOptions.value = Array.isArray(list) ? list.filter((q) => q.status === 'verified') : []
  } catch {
    quoteOptions.value = []
  }
}

const form = reactive({
  po_number: '',
  quote_id: '',
  grant_code: '',
  shipping_method: '',
  requested_delivery_date: '',
  shipping_name: '',
  shipping_address: '',
  shipping_phone: '',
  shipping_email: '',
  billing_name: '',
  billing_address: '',
  notes: '',
})

// 用户一改就重算（只在本就有错时算，避免边打字边冒红字）。
// 放在 `form` 之后：`watch` 本身惰性求值，但写成 immediate 的一天就会踩到 TDZ。
watch(
  () => [form.requested_delivery_date, form.shipping_email],
  () => {
    if (formErrors.date || formErrors.email) validateDateAndEmail()
  },
)

const items = ref([])
const files = ref([])
const searchTerm = ref('')

// 明细行数一变，就把"没有明细行"那条红字撤掉（A-147）
watch(() => items.value.length, () => { if (items.value.length) itemsError.value = '' })
// 离开页面时清掉自动跳转定时器，避免在别的页面被莫名带走
onUnmounted(() => { if (redirectTimer) { clearTimeout(redirectTimer); redirectTimer = null } })

function addItem() {
  items.value.push({
    productId: null,
    productName: '',
    skus: [],
    skuId: null,
    quantity: 1,
    unitPrice: '',
    searchResults: [],
    searching: false,
    // ★ 2026-10-28：每次搜索/选中自增，用于丢弃"迟到的旧响应"（见 searchProducts）
    searchSeq: 0,
  })
}

async function searchProducts(row, q) {
  if (!q || q.length < 2) {
    row.searchSeq += 1          // 作废进行中的请求
    row.searchResults = []
    row.searching = false
    return
  }
  // ★ 2026-10-28 修竞态：搜索是逐次键入触发的异步请求，早先发出的响应可能**晚于**
  //   用户选中产品才到达，把 `searchResults` 重新写回 ⇒ 下拉框在选中后又弹出来，
  //   浮在明细行上（生产实测截图可见），且可能误点。
  //   ⇒ 给每行一个自增序号，只接受"最新一次"的响应；selectProduct 也会自增以作废在途请求。
  const seq = (row.searchSeq += 1)
  row.searching = true
  try {
    const res = await getProducts({ search: q, page_size: 8 })
    if (seq !== row.searchSeq) return                 // 有更新的输入或已选中 ⇒ 丢弃
    const payload = res.data || res
    row.searchResults = payload.results || payload.data || payload || []
  } catch {
    if (seq === row.searchSeq) row.searchResults = []
  } finally {
    if (seq === row.searchSeq) row.searching = false
  }
}

async function selectProduct(row, product) {
  row.productId = product.id
  row.productName = product.name
  row.searchSeq += 1          // 作废在途搜索，避免选中后下拉又被弹回来
  row.searchResults = []
  row.searching = false
  try {
    const res = await getProductDetail(product.id)
    const detail = res.data || res
    // detail 端点把数据嵌套在 data.product 下（与 products store 一致）
    row.skus = detail.product?.skus || detail.skus || []
  } catch {
    row.skus = []
  }
}

function onSkuChange(row) {
  const sku = row.skus.find((s) => s.id === row.skuId)
  if (sku) row.unitPrice = sku.price
}

function removeItem(idx) {
  items.value.splice(idx, 1)
}

function onFileChange(e) {
  files.value = Array.from(e.target.files || [])
}

const grandTotal = computed(() =>
  items.value.reduce((sum, it) => sum + (Number(it.quantity) || 0) * (Number(it.unitPrice) || 0), 0)
)

async function loadReorder() {
  if (!reorderSourceId.value) return
  const res = await getOrderDetail(reorderSourceId.value)
  const o = res.data || res
  if (!o) return
  // ★ 2026-11-27（A-192）：**不再清空用户已经填过的字段**。
  //   原来这里有一行 `form.po_number = ''`，而 Bill-to 是无条件 `= o.billing_name || ''`
  //   —— 源单没有账单信息时就把用户填的 Bill-to 抹成空。
  //   "Load from Order" 的语义是**补**数据，不是重置表单；真正要重填的场景
  //   由「Submit another PO」负责（那是整张单重开）。
  //   取"源单有值才覆盖"的合并策略，PO 号与任何已填内容都不受影响。
  const setIf = (key, value) => { if (value) form[key] = value }
  setIf('grant_code', o.grant_code)
  setIf('shipping_method', o.shipping_method)
  setIf('shipping_name', o.shipping_name)
  setIf('shipping_address', o.shipping_address)
  setIf('shipping_phone', o.shipping_phone)
  setIf('shipping_email', o.shipping_email)
  setIf('billing_name', o.billing_name)
  setIf('billing_address', o.billing_address)
  ;(o.items || []).forEach((it) => {
    items.value.push({
      productId: it.product_id,
      productName: it.product_name || `Product #${it.product_id}`,
      skus: it.sku_id ? [{ id: it.sku_id, sku_code: it.sku_code, pack_size: it.pack_size, price: it.unit_price }] : [],
      skuId: it.sku_id,
      quantity: it.quantity,
      unitPrice: it.unit_price,
      searchResults: [],
      searching: false,
    })
  })
}

async function handleSubmit() {
  if (items.value.length === 0) {
    // ★ 2026-11-18（S4）：表单校验提示 `alert` → `toast.error`。
    //   原生 alert 阻塞主线程：连点两次提交会卡住两秒，且用户必须手点「确定」
    //   才能继续填表 —— 表单校验本该是"即时、可叠加、不打断输入"的反馈。
    // ★ 2026-11-27（A-147）：**再补一条常驻行内提示**。toast 3 秒就没了，
    //   而"没有明细行"这件事在页面上看不出任何红字，用户只会觉得"按钮没反应"。
    //   A-189 定的口径在这里同样适用：失败原因必须留在按钮旁边。
    itemsError.value = 'Add at least one line item before submitting.'
    toast.error('Add at least one line item.')
    return
  }
  const invalid = items.value.some((it) => !it.skuId || !it.quantity || !it.unitPrice)
  if (invalid) {
    itemsError.value = 'Each line item requires a SKU, quantity and unit price.'
    toast.error('Each line item requires a SKU, quantity and unit price.')
    return
  }
  itemsError.value = ''
  // ★ 2026-11-20（S4 / A-189）：日期与邮箱改为**应用层校验**，不再让浏览器原生校验吃掉 submit。
  //   见文件上方 `formErrors` 的说明。
  if (!validateDateAndEmail()) {
    // 把焦点送到第一个出错的字段：报错在页中部，常驻汇总在按钮旁，
    // 不聚焦的话用户得自己在长表单里找（原生气泡唯一做对的就是这件事）。
    const target = formErrors.date ? dateEl.value : emailEl.value
    if (target && typeof target.focus === 'function') target.focus()
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form,
      items: items.value.map((it) => ({
        product_id: it.productId,
        sku_id: it.skuId,
        quantity: Number(it.quantity),
        unit_price: String(it.unitPrice),
      })),
    }
    const res = await submitPo({ data: payload, files: files.value })
    const data = res.data || res
    successOrderNo.value = data.order_no || 'submitted'
    successOrderId.value = data.id ?? null
    // ★ 2026-11-27（A-149）：提交成功后**必须给出下一步**。
    //   此前建单成功却仍停在 /po/submit，只显示一行 "PO submitted successfully"
    //   —— 用户以为没提交成功，会再点一次（于是又撞上"重复 PO 号"）。
    //   现在：成功的 callout 仍保留（订单号要能核对/抄走），
    //   同时给一个显式「View order」入口，并在 4 秒后自动跳到订单详情。
    //   4 秒是留给"把订单号看/抄一遍"的窗口，不是技术限制。
    if (successOrderId.value) {
      if (redirectTimer) clearTimeout(redirectTimer)
      redirectTimer = setTimeout(() => {
        if (successOrderId.value) router.push(`/orders/${successOrderId.value}`)
      }, 4000)
    }
  } catch (err) {
    // 拦截器已 toast（一句话）；这里再把「哪几行缺货、要多少、只剩多少」结构化落页，
    // 因为 toast 4 秒就没了，而客户需要照着这张表去改数量或换产品。
    // ★ 2026-10-28：后端缺货拦截返回 code=OUT_OF_STOCK + meta.error.details[]。
    const e = err?.response?.data?.meta?.error || err?.data?.meta?.error
    if (e?.code === 'OUT_OF_STOCK' && Array.isArray(e.details)) {
      shortages.value = e.details
      shortageMessage.value = e.message || ''
    } else {
      shortages.value = []
      shortageMessage.value = ''
    }
    console.error('[PoSubmit] submit failed:', err)
  } finally {
    submitting.value = false
  }
}

/**
 * 提交成功后重置成"一张空白新单"。
 *
 * ★ 2026-10-28：此前成功后表单原样保留、Submit 按钮仍可点 ⇒ 手滑再点一次就会
 *   **重复提交同一张 PO**（生产实测：成功横幅出现后整张表单内容与按钮都还在）。
 *   现在成功后按钮禁用并变文案，另给一个显式入口开新单，避免把用户堵死。
 */
function resetForNewPo() {
  successOrderNo.value = ''
  successOrderId.value = null
  if (redirectTimer) { clearTimeout(redirectTimer); redirectTimer = null }
  itemsError.value = ''
  shortages.value = []
  shortageMessage.value = ''
  // 新单不该继承上一张单的校验红字（watch 也会清，这里是显式保证）
  formErrors.date = ''
  formErrors.email = ''
  items.value = []
  files.value = []
  Object.assign(form, {
    po_number: '', quote_id: '', grant_code: '', shipping_method: '',
    requested_delivery_date: '', shipping_name: '', shipping_address: '',
    shipping_phone: '', shipping_email: '', billing_name: '',
    billing_address: '', notes: '',
  })
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Submit Purchase Order</h1>
        <p class="po-page-subtitle">Upload your PO and line items; we’ll confirm within 1 business day.</p>
      </div>
      <div class="po-row">
        <input v-model="reorderSourceId" class="po-input" style="width:120px" placeholder="Order ID" />
        <button class="po-btn po-btn-outline po-btn-sm" @click="loadReorder">Load from Order</button>
      </div>
    </div>

    <div v-if="successOrderNo" class="po-callout" style="margin-bottom:24px">
      PO submitted successfully. Order No: <strong class="po-mono">{{ successOrderNo }}</strong>
      <!-- ★ 2026-11-27（A-149）：原来只有一个「View My Orders」链接、且不自动跳转，
           用户以为没成功。现在直连到**这张单**的详情，并在 4 秒后自动跳过去。 -->
      <router-link
        v-if="successOrderId"
        :to="`/orders/${successOrderId}`"
        class="po-btn po-btn-primary po-btn-sm"
        style="margin-left:12px"
      >
        View this order
      </router-link>
      <router-link :to="{ name: 'PoOrders' }" class="po-btn po-btn-outline po-btn-sm" style="margin-left:8px">
        View My Orders
      </router-link>
    </div>

    <!-- ★ 2026-10-28：缺货拦截。后端 code=OUT_OF_STOCK 时把被拦的行逐条列出来 ——
         toast 4 秒就消失，客户需要照着这张表去改数量或换产品。
         为什么不做成"自动删掉缺货行继续下单"：那会静默改变客户的订单内容。 -->
    <div v-if="shortages.length" class="po-callout danger" style="margin-bottom:24px">
      <strong>These item(s) are out of stock — the order was NOT submitted.</strong>
      <p class="po-muted" style="margin:6px 0 10px; font-size:13px">
        Our team has been notified and will contact you about restocking or an alternative product.
      </p>
      <table class="po-table">
        <thead><tr><th>SKU</th><th>Product</th><th>Requested</th><th>Available</th></tr></thead>
        <tbody>
          <tr v-for="s in shortages" :key="s.sku_id">
            <td class="po-mono">{{ s.sku_code }}</td>
            <td>{{ s.product_name || '—' }}</td>
            <td>{{ s.requested_quantity }}</td>
            <!-- ★ out_of_stock 是运营手动标记，可能与账面库存矛盾（实测标记缺货但账面 1014）。
                 此时照抄数字会让客户觉得系统在自相矛盾 ⇒ 只报"不可订"。 -->
            <td>
              <strong v-if="s.reason === 'insufficient'">{{ s.available_quantity }}</strong>
              <span v-else class="po-muted">Unavailable</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ★ 2026-11-20（S4 / A-189）：`novalidate` —— 交给 handleSubmit 做应用层校验。
         `:min` / `type="email"` / `min="1"` 三个约束属性**全部保留**（选择器与键盘行为不变），
         只是不再允许浏览器用它们悄悄吃掉 submit。详见 script 里 formErrors 的注释。 -->
    <form class="po-card" novalidate @submit.prevent="handleSubmit">
      <h2 class="po-section-title">PO Information</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label" for="po-f1">PO Number（可选）</label>
          <input id="po-f1" v-model="form.po_number" class="po-input" placeholder="无 PO 号可留空" />
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f2">Quote / Reference #（可选）</label>
          <select id="po-f2" v-model="form.quote_id" class="po-select">
            <option value="">— 不关联报价 —</option>
            <option v-for="q in quoteOptions" :key="q.id" :value="q.id">
              {{ q.quote_no }} · {{ q.grand_total }}
            </option>
          </select>
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f3">Grant / Sponsor Code</label>
          <input id="po-f3" v-model="form.grant_code" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f4">Shipping Method</label>
          <select id="po-f4" v-model="form.shipping_method" class="po-select">
            <option value="">— Select —</option>
            <option v-for="m in SHIPPING_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f5">Requested Delivery Date</label>
          <input id="po-f5" ref="dateEl" v-model="form.requested_delivery_date" type="date" class="po-input" :min="minDeliveryDate"
                 :aria-invalid="formErrors.date ? 'true' : 'false'"
                 :aria-describedby="formErrors.date ? 'po-f5-error' : undefined" />
          <p v-if="formErrors.date" id="po-f5-error" class="po-field-error" data-testid="po-date-error">
            {{ formErrors.date }}
          </p>
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Ship-to</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label" for="po-f6">Recipient Name</label>
          <input id="po-f6" v-model="form.shipping_name" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f7">Phone</label>
          <input id="po-f7" v-model="form.shipping_phone" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label" for="po-f8">Address</label>
          <textarea id="po-f8" v-model="form.shipping_address" class="po-textarea" />
        </div>
        <div class="po-field">
          <label class="po-label" for="po-f9">Email</label>
          <input id="po-f9" ref="emailEl" v-model="form.shipping_email" type="email" class="po-input"
                 :aria-invalid="formErrors.email ? 'true' : 'false'"
                 :aria-describedby="formErrors.email ? 'po-f9-error' : undefined" />
          <p v-if="formErrors.email" id="po-f9-error" class="po-field-error" data-testid="po-email-error">
            {{ formErrors.email }}
          </p>
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Bill-to</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label" for="po-f10">Billing Name</label>
          <input id="po-f10" v-model="form.billing_name" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label" for="po-f11">Billing Address</label>
          <textarea id="po-f11" v-model="form.billing_address" class="po-textarea" />
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">PO Attachments</h2>
      <label class="po-dropzone">
        <input type="file" multiple accept=".pdf,.png,.jpeg,.jpg" style="display:none" @change="onFileChange" />
        Drag &amp; drop or click to upload (PDF / PNG / JPEG, ≤10MB)
      </label>
      <div>
        <span v-for="(f, i) in files" :key="i" class="po-file-chip">{{ f.name }}</span>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Line Items</h2>
      <table class="po-table" v-if="items.length">
        <thead>
          <tr>
            <th style="width:30%">Product</th>
            <th style="width:18%">SKU</th>
            <th style="width:10%">Qty</th>
            <th style="width:14%">Unit Price</th>
            <th style="width:14%">Subtotal</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in items" :key="idx">
            <td>
              <input
                class="po-input"
                :placeholder="row.productName || 'Search product…'"
                @input="searchProducts(row, $event.target.value)"
              />
              <div v-if="row.searching" class="po-muted">Searching…</div>
              <div v-if="row.searchResults.length" class="po-search-pop">
                <button
                  v-for="p in row.searchResults"
                  :key="p.id"
                  type="button"
                  class="po-search-item"
                  @click="selectProduct(row, p)"
                >
                  {{ p.name }} <span class="po-mono" v-if="p.catalog_no">{{ p.catalog_no }}</span>
                </button>
              </div>
              <div v-if="row.productName && !row.searchResults.length" class="po-muted">{{ row.productName }}</div>
            </td>
            <td>
              <select v-model="row.skuId" class="po-select" :disabled="!row.skus.length" @change="onSkuChange(row)">
                <option value="">— SKU —</option>
                <option v-for="s in row.skus" :key="s.id" :value="s.id">
                  {{ s.sku_code }} · {{ s.pack_size }}
                </option>
              </select>
            </td>
            <td><input v-model.number="row.quantity" type="number" min="1" class="po-input" /></td>
            <td><input v-model="row.unitPrice" class="po-input" placeholder="0.00" /></td>
            <td class="po-num">{{ formatCurrency((Number(row.quantity) || 0) * (Number(row.unitPrice) || 0)) }}</td>
            <td><button type="button" class="po-btn po-btn-danger po-btn-sm" @click="removeItem(idx)">Remove</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="po-muted">No line items yet.</p>
      <button type="button" class="po-btn po-btn-outline po-btn-sm" style="margin-top:12px" @click="addItem">+ Add Line Item</button>

      <div class="po-total-row">
        <span>Estimated Total</span>
        <span class="po-total-value">{{ formatCurrency(grandTotal) }}</span>
      </div>

      <!-- ★ 2026-11-20（S4 / A-189）：按钮旁的**常驻**失败原因。
           为什么在这里再写一遍（字段旁已有行内提示）：日期字段在页面中部，
           用户点的是底部按钮 —— 原先靠原生气泡"跳到出错字段"，气泡一飘就没了；
           这里保证「点了没成功」在按钮旁边就有解释，且不会自动消失。
           role="alert" 给读屏器（原生气泡本来就有的那点好处，这里保留）。 -->
      <p v-if="firstFormError" class="po-submit-error" role="alert" data-testid="po-submit-error">
        {{ firstFormError }}
      </p>
      <!-- ★ 2026-11-27（A-147）：明细行为空/缺字段的失败原因常驻在按钮上方 -->
      <p v-if="itemsError" class="po-submit-error" role="alert" data-testid="po-items-error">
        {{ itemsError }}
      </p>

      <div class="po-row" style="margin-top:16px">
        <!-- ★ 成功后禁用，避免重复提交同一张 PO（见 resetForNewPo 注释） -->
        <button type="submit" class="po-btn po-btn-accent po-btn-lg"
                :disabled="submitting || !!successOrderNo">
          {{ submitting ? 'Submitting…' : (successOrderNo ? 'Submitted' : 'Submit PO') }}
        </button>
        <button v-if="successOrderNo" type="button"
                class="po-btn po-btn-outline po-btn-lg" style="margin-left:12px"
                @click="resetForNewPo">
          Submit another PO
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
/* ★ 2026-11-20（S4 / A-189）：行内校验提示。用「错误色 + 常驻」而不是 toast —— 
   toast 3 秒消失，而用户需要照着它改字段。 */
.po-field-error {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: #b91c1c;
}
.po-submit-error {
  margin: 12px 0 0;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm, 4px);
}
.po-search-pop {
  position: absolute;
  z-index: 20;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  margin-top: 2px;
  max-height: 200px;
  overflow: auto;
  width: 100%;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}
.po-search-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: none;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text);
}
.po-search-item:hover { background: var(--color-primary-subtle); }
td { position: relative; }
</style>
