<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const values = [
  {
    icon: '🎯',
    title: 'Precision by Design',
    text: 'Every reagent is traced back to the research goal, method, and protocol it serves — no orphan products, no guesswork.',
  },
  {
    icon: '🔗',
    title: 'Connected Knowledge',
    text: 'A living knowledge graph links goals, applications, methods, protocols, and products so discoveries stay reproducible.',
  },
  {
    icon: '🧪',
    title: 'Verified Compliance',
    text: 'SDS and COA are generated and stored per batch, with literature evidence captured from trusted sources.',
  },
]
</script>

<template>
  <div class="about">
    <!-- Hero -->
    <section class="about-hero">
      <div class="about-hero-inner">
        <p class="eyebrow">ABOUT SCIREAGENT</p>
        <h1>From research goal to precision reagent</h1>
        <p class="lede">
          SciReAgent is a reagent discovery platform by LabPro Global. We connect the
          full research chain — research goals, applications, methods, protocols, and
          the high-purity products that bring them to the bench — in one traceable graph.
        </p>
      </div>
    </section>

    <!-- Mission -->
    <section class="about-section">
      <div class="about-container">
        <h2>Our mission</h2>
        <p>
          Make every reagent choice reproducible and defensible. Instead of searching a
          flat catalog, researchers start from the biology they care about and follow a
          verified path to the exact product, batch, and compliance document they need.
        </p>
      </div>
    </section>

    <!-- Values -->
    <section class="about-section alt">
      <div class="about-container">
        <h2>What we stand for</h2>
        <div class="value-grid">
          <article v-for="v in values" :key="v.title" class="value-card">
            <div class="value-icon">{{ v.icon }}</div>
            <h3>{{ v.title }}</h3>
            <p>{{ v.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="about-section">
      <div class="about-container about-cta">
        <h2>Explore the catalog</h2>
        <p>Browse products connected to real methods and protocols.</p>
        <button class="cta-btn" @click="router.push('/products')">View Products</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.about {
  padding-top: 68px; /* clear fixed nav */
}

.about-hero {
  background: linear-gradient(160deg, #0f172a 0%, #0b2545 60%, #0f172a 100%);
  color: #fff;
  padding: 96px 0 80px;
}
.about-hero-inner {
  max-width: 880px;
  margin: 0 auto;
  padding: 0 32px;
}
.eyebrow {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: #5eead4;
  margin: 0 0 16px;
}
.about-hero h1 {
  font-size: clamp(2rem, 4vw, 3.1rem);
  font-weight: 800;
  line-height: 1.1;
  margin: 0 0 20px;
  letter-spacing: -0.02em;
}
.lede {
  font-size: 1.1rem;
  line-height: 1.7;
  color: #cbd5e1;
  margin: 0;
  max-width: 720px;
}

.about-section {
  padding: 64px 0;
}
.about-section.alt {
  background: var(--color-bg-alt);
}
.about-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 32px;
}
.about-container h2 {
  font-size: 1.7rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 16px;
  letter-spacing: -0.01em;
}
.about-container p {
  font-size: 1.02rem;
  line-height: 1.75;
  color: var(--color-text-secondary);
  margin: 0;
}

.value-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-top: 28px;
}
.value-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 14px);
  padding: 24px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.value-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}
.value-icon {
  font-size: 1.8rem;
  margin-bottom: 12px;
}
.value-card h3 {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}
.value-card p {
  font-size: 0.92rem;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin: 0;
}

.about-cta {
  text-align: center;
}
.about-cta p {
  margin-bottom: 24px;
}
.cta-btn {
  padding: 12px 28px;
  background-color: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.cta-btn:hover {
  background-color: var(--color-primary-hover, #0f766e);
}
</style>
