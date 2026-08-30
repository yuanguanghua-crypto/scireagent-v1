import http from '@/utils/http'

// 收敛类聚合浏览 API（Step 3）
// 后端：GET /api/v1/convergence-classes/?group=rg|ap&source=curated|high_freq|kmeans&search=&page=&page_size=
//       GET /api/v1/convergence-classes/<class_id>/
// 响应信封 { success, data, meta }；size 降序；page_size 默认 20 上限 100

/** 获取收敛类列表（分页） */
export function getConvergenceClasses(params = {}) {
  return http.get('/convergence-classes/', { params })
}

/** 获取单个收敛类详情（含成员分页） */
export function getConvergenceClass(classId, params = {}) {
  // class_id 如 rg_c001 / ap_k011，含下划线，用 encodeURIComponent 包裹更稳妥
  return http.get(`/convergence-classes/${encodeURIComponent(classId)}/`, { params })
}
