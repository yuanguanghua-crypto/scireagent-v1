<script setup>
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer">
    <div class="footer-content">
      <div class="footer-left">
        <span class="copyright">&copy; {{ currentYear }} LabPro Global. All rights reserved.</span>
      </div>
      <div class="footer-right">
        <a href="#" class="footer-link">Documentation</a>
        <span class="separator">|</span>
        <a href="#" class="footer-link">API Reference</a>
        <span class="separator">|</span>
        <a href="#" class="footer-link">Support</a>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer {
  background-color: var(--color-surface);
  border-top: 1px solid var(--color-border);
  padding: 12px 24px;
  flex-shrink: 0;
}

.footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
}

.footer-left {
  display: flex;
  align-items: center;
}

.copyright {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-link {
  font-size: 13px;
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: color 0.2s ease;
}

.footer-link:hover {
  color: var(--color-primary);
}

.separator {
  color: var(--color-border);
  font-size: 13px;
}
</style>