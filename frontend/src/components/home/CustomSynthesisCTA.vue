<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function handleRequestQuote() {
  router.push('/products')
}
</script>

<template>
  <section class="cta-section" aria-label="Custom Synthesis">
    <div class="cta-content">
      <h2 class="cta-title">Need a custom modified nucleotide?</h2>
      <ul class="cta-features">
        <li>Modified dNTPs</li>
        <li>Fluorescent nucleotides</li>
        <li>Click chemistry reagents</li>
        <li>Scale-up synthesis</li>
      </ul>
      <button class="cta-btn" @click="handleRequestQuote">Request Quote</button>
    </div>
  </section>
</template>

<style scoped>
.cta-section {
  padding: 32px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%);
  border: 1px solid #99f6e4;
  border-radius: var(--radius-lg);
  text-align: center;
}
.cta-content { max-width: 480px; margin: 0 auto; }
.cta-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 16px;
}
.cta-features {
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.cta-features li {
  padding: 4px 12px;
  background: white;
  border: 1px solid #99f6e4;
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-secondary);
}
.cta-btn {
  padding: 12px 32px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: opacity 0.15s;
}
.cta-btn:hover { opacity: 0.9; }
</style>
