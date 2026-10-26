import http from '@/utils/http'

export function getProtocols(params = {}) {
  return http.get('/protocols/', { params })
}

export function getProtocol(id) {
  return http.get(`/protocols/${id}/`)
}

export function createProtocol(data) {
  return http.post('/protocols/', data)
}

export function updateProtocol(id, data) {
  return http.patch(`/protocols/${id}/`, data)
}
/**
 * 分类导航数据：每个 application 维度受控词表值各挂了多少条 published protocol。
 *
 * ⚠️ 返回的 `count` 是"该分类下的协议数"，而**一个协议可属于多个分类**
 *    ⇒ 各分类之和 > meta.covered_protocols（去重后的覆盖数）。
 *    这不是 bug，UI 上要说明，否则用户会以为数字对不上。
 */
export function getProtocolFacets(params = {}) {
  return http.get('/protocols/facets/', { params })
}
