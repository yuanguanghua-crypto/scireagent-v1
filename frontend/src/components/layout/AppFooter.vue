<script setup>
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer">
    <div class="footer-content">
      <div class="footer-left">
        <span class="copyright">&copy; {{ currentYear }} SciReagent. All rights reserved.</span>
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
  position: relative;
  background: linear-gradient(180deg, #0A1628 0%, #020B1B 100%);
  border-top: 1px solid var(--color-border);
  padding: 0;
  flex-shrink: 0;
  overflow: hidden;
}
.footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 14px 24px;
}
.footer-left {
  display: flex;
  align-items: center;
}
.copyright {
  font-size: 13px;
  color: var(--color-text-secondary);
  letter-spacing: 0.02em;
}
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-link {
  font-size: 13px;
  color: var(--color-text-tertiary);
  text-decoration: none;
  transition: color 0.2s ease;
}
.footer-link:hover {
  color: var(--color-emerald-400);
}
.separator {
  color: #1E293B;
  font-size: 13px;
}
</style>
