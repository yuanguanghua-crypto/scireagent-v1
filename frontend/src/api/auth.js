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

export function logout() {
  return http.post('/auth/logout')
}

export function getMe() {
  return http.get('/auth/me')
}

export function updateProfile(data) {
  return http.put('/auth/profile', data)
}
