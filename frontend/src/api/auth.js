import http from '@/utils/http'

export function register(data) {
  return http.post('/auth/register', data)
}

export function login(data) {
  return http.post('/auth/login', data)
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
