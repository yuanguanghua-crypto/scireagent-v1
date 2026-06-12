import http from '@/utils/http'

export function getHomeData() {
  return http.get('/site/home')
}

export function getNavigation() {
  return http.get('/site/navigation')
}