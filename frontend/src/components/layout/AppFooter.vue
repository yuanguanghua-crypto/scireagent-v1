<script setup>
const currentYear = new Date().getFullYear()
</script>

<template>
  <!-- ★ 2026-11-27（A-105 / A-106）：全站**唯一**页脚。
       改动前 App.vue 里还挂着一个 `.site-footer`，于是每页底部两个页脚叠着，
       且品牌一处写 "SciReagent"、一处写 "SciReAgent"。
       同时这里原有 Documentation / API Reference / Support 三个链接，href 全是 `#`
       （点 Documentation 无反应、URL 都不变）——仓库里没有 /docs、/api-reference、
       /support 任何路由，这三项是**永久死链**，已删除，换成真实存在的
       Privacy Policy / Terms of Service。品牌统一按仓库主流写法 SciReagent
       （SITE_NAME、index.html、og:* 共 19 处用的都是它）。 -->
  <footer class="app-footer">
    <div class="footer-content">
      <div class="footer-left">
        <span class="copyright">&copy; {{ currentYear }} SciReagent. All rights reserved.</span>
      </div>
      <div class="footer-right">
        <router-link to="/privacy" class="footer-link">Privacy Policy</router-link>
        <span class="separator">|</span>
        <router-link to="/terms" class="footer-link">Terms of Service</router-link>
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
