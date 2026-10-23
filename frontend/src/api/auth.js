import http from '@/utils/http'

export function register(data) {
  return http.post('/auth/register', data)
}

export function login(data) {
  return http.post('/auth/login', data)
}

export function verifyEmail(token) {
  return http.get('/auth/verify-email', { params: { token } })
}

export function resendVerification(email) {
  return http.post('/auth/resend-verification', { email })
}

/** 申请密码重置链接。后端对「邮箱是否已注册」返回完全相同的响应（防枚举），
 *  所以前端不要根据返回值判断邮箱是否存在。 */
export function requestPasswordReset(email) {
  return http.post('/auth/request-password-reset', { email })
}

/** 用 token 设置新密码。成功后后端会吊销该用户全部登录凭证，需重新登录。 */
export function resetPassword(token, newPassword) {
  return http.post('/auth/reset-password', { token, new_password: newPassword })
}

export function logout() {
  return http.post('/auth/logout')
}

export function getMe() {
  return http.get('/auth/me')
}

export function updateProfile(data) {
  return http.put('/auth/profile', data)
}
