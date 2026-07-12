<template>
  <router-link
    v-if="isRouterLink"
    :to="to"
    :class="classes"
  >
    <span v-if="loading" class="btn-spinner" />
    <slot name="icon" />
    <slot />
  </router-link>
  <a
    v-else-if="isLink"
    :href="href"
    :class="classes"
  >
    <span v-if="loading" class="btn-spinner" />
    <slot name="icon" />
    <slot />
  </a>
  <button
    v-else
    :type="nativeType"
    :class="classes"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="btn-spinner" />
    <slot name="icon" />
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'outline', 'ghost', 'danger', 'accent', 'cta', 'link'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg', 'icon', 'icon-sm'].includes(v),
  },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  icon: { type: Boolean, default: false },
  nativeType: { type: String, default: 'button' },
  href: { type: String, default: '' },
  to: { type: [String, Object], default: '' },
})

const variantMap = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  outline: 'btn-outline',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
  accent: 'btn-accent',
  cta: 'btn-cta',
  link: 'btn-link',
}

const sizeMap = {
  sm: 'btn-sm',
  md: 'btn-md',
  lg: 'btn-lg',
  icon: 'btn-icon',
  'icon-sm': 'btn-icon-sm',
}

const isLink = computed(() => !!props.href)
const isRouterLink = computed(() => !!props.to)

const classes = computed(() => {
  const cls = ['btn']
  cls.push(variantMap[props.variant] || 'btn-primary')

  // 当 icon=true 且未主动指定 size 时，默认用 btn-icon
  if (props.icon && props.size === 'md') {
    cls.push('btn-icon')
  } else {
    cls.push(sizeMap[props.size] || 'btn-md')
  }

  // loading 仅在 button 模式下生效（非 <a>/<router-link>）
  if (props.loading && !isLink.value && !isRouterLink.value) {
    cls.push('btn-loading')
  } else if (props.loading && (isLink.value || isRouterLink.value)) {
    console.warn('[AppButton] loading is not supported when href or to is set (rendered as <a>/<router-link>)')
  }

  return cls
})
</script>
