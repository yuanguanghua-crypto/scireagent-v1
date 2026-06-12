<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goHome = () => {
  router.push('/')
}
</script>

<template>
  <div class="not-found">
    <div class="not-found-content">
      <h1>404</h1>
      <h2>Page Not Found</h2>
      <p>The page you're looking for doesn't exist or has been moved.</p>
      <button class="back-btn" @click="goHome">
        Back to Home
      </button>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
  text-align: center;
}

.not-found-content h1 {
  font-size: 6rem;
  font-weight: 700;
  color: var(--color-primary);
  margin: 0;
  line-height: 1;
}

.not-found-content h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text);
  margin: 16px 0 8px;
}

.not-found-content p {
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

.back-btn {
  padding: 10px 24px;
  background-color: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.back-btn:hover {
  background-color: var(--color-primary-hover);
}
</style>