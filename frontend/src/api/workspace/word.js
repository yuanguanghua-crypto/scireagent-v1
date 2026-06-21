import { http } from '@/api/http'

export function parseWord(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/products/parse-word/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
