<script setup>
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer">
    <!-- 静态粒子剪影：呼应首页粒子网络，首尾深海色包裹 -->
    <div class="footer-particles" aria-hidden="true">
      <svg viewBox="0 0 1200 40" preserveAspectRatio="none">
        <g stroke="#5EEAD4" stroke-width="0.6" fill="none">
          <line x1="80" y1="22" x2="200" y2="14" opacity="0.25"/>
          <line x1="200" y1="14" x2="320" y2="26" opacity="0.30"/>
          <line x1="320" y1="26" x2="460" y2="18" opacity="0.22"/>
          <line x1="460" y1="18" x2="580" y2="24" opacity="0.28"/>
          <line x1="580" y1="24" x2="720" y2="12" opacity="0.25"/>
          <line x1="720" y1="12" x2="860" y2="28" opacity="0.30"/>
          <line x1="860" y1="28" x2="1000" y2="20" opacity="0.22"/>
          <line x1="1000" y1="20" x2="1120" y2="16" opacity="0.26"/>
        </g>
        <g>
          <circle cx="80" cy="22" r="1.8" fill="#5EEAD4" opacity="0.5"/>
          <circle cx="200" cy="14" r="1.4" fill="#99F6E4" opacity="0.45"/>
          <circle cx="320" cy="26" r="1.6" fill="#5EEAD4" opacity="0.5"/>
          <circle cx="460" cy="18" r="1.2" fill="#38BDF8" opacity="0.4"/>
          <circle cx="580" cy="24" r="1.8" fill="#5EEAD4" opacity="0.5"/>
          <circle cx="720" cy="12" r="1.4" fill="#99F6E4" opacity="0.45"/>
          <circle cx="860" cy="28" r="1.6" fill="#5EEAD4" opacity="0.5"/>
          <circle cx="1000" cy="20" r="1.2" fill="#B2B0FF" opacity="0.4"/>
          <circle cx="1120" cy="16" r="1.5" fill="#5EEAD4" opacity="0.5"/>
        </g>
      </svg>
    </div>
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
  border-top: 1px solid rgba(94, 234, 212, 0.12);
  padding: 0;
  flex-shrink: 0;
  overflow: hidden;
}
.footer-particles {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  height: 40px;
  opacity: 0.75;
}
.footer-particles svg {
  width: 100%;
  height: 100%;
  display: block;
}
.footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
  padding: 14px 24px;
}
.footer-left {
  display: flex;
  align-items: center;
}
.copyright {
  font-size: 13px;
  color: #64748B;
  letter-spacing: 0.02em;
}
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-link {
  font-size: 13px;
  color: #94A3B8;
  text-decoration: none;
  transition: color 0.2s ease;
}
.footer-link:hover {
  color: #5EEAD4;
}
.separator {
  color: #1E293B;
  font-size: 13px;
}
</style>
