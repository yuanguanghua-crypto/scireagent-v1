import { ElMessage } from 'element-plus'

export const toast = {
  success(msg, duration = 3000) {
    ElMessage.success({ message: msg, duration })
  },
  error(msg, duration = 3000) {
    ElMessage.error({ message: msg, duration })
  },
  warning(msg, duration = 3000) {
    ElMessage.warning({ message: msg, duration })
  },
  info(msg, duration = 3000) {
    ElMessage.info({ message: msg, duration })
  },
}

export default toast
