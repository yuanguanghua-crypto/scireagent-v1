/**
 * 实时预览桥接工具。
 *
 * openPreview(type, data) 负责实例化 CompliancePreviewModal 并向其 iframe postMessage
 * 真实文档数据（postMessage 桥接方案见 ARCH §7 #5）。
 *
 * - type: 'coa' | 'sds'
 * - data: COA / SDS 的 serializer 对象（CoaSerializer / SdsRevisionSerializer）
 *
 * 采用命令式挂载一个独立的 modal 实例，产品编辑页 / 产品详情页均可复用，无需各自内嵌组件。
 */
import { createApp } from 'vue'
import CompliancePreviewModal from '@/components/CompliancePreviewModal.vue'

let activeInstance = null

/**
 * 打开合规文档实时预览弹窗。
 * @param {'coa'|'sds'} type
 * @param {Object} data 文档 serializer 数据
 */
export function openPreview(type, data) {
  closePreview()
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(CompliancePreviewModal, {
    visible: true,
    type,
    previewData: data || {},
    onClose: () => closePreview(),
  })
  app.mount(host)
  activeInstance = { app, host }
}

/** 关闭并卸载当前预览弹窗（若存在）。 */
export function closePreview() {
  if (activeInstance) {
    try {
      activeInstance.app.unmount()
    } catch (_) { /* ignore */ }
    if (activeInstance.host && activeInstance.host.parentNode) {
      activeInstance.host.parentNode.removeChild(activeInstance.host)
    }
    activeInstance = null
  }
}

export default { openPreview, closePreview }
