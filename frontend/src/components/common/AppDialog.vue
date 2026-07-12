<template>
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div
        v-if="visible"
        ref="overlayRef"
        class="dialog-overlay"
        :class="{ 'dialog-overlay--danger': variant === 'danger' }"
        v-bind="dialogAttrs"
        @click.self="onOverlayClick"
      >
        <div
          class="dialog"
          :class="{ 'dialog--danger': variant === 'danger' }"
          :style="{ maxWidth: width }"
          role="dialog"
          :aria-labelledby="titleId || undefined"
        >
          <div class="dialog-header">
            <h3 :id="titleId || undefined">{{ title }}</h3>
            <button class="dialog-close" @click="emitCancel" aria-label="Close">&times;</button>
          </div>
          <div class="dialog-body">
            <slot />
          </div>
          <div class="dialog-footer">
            <slot name="footer">
              <AppButton v-if="showCancel" variant="ghost" @click="emitCancel">{{ cancelText }}</AppButton>
              <AppButton
                v-if="showConfirm"
                variant="primary"
                :loading="confirmLoading"
                @click="$emit('confirm')"
              >{{ confirmText }}</AppButton>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, toRef } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'
import AppButton from './AppButton.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '440px' },
  variant: { type: String, default: 'default', validator: (v) => ['default', 'danger'].includes(v) },
  closeOnClickOverlay: { type: Boolean, default: true },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  showConfirm: { type: Boolean, default: true },
  showCancel: { type: Boolean, default: true },
  confirmLoading: { type: Boolean, default: false },
  titleId: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'confirm', 'cancel'])

const overlayRef = ref(null)

function emitCancel() {
  emit('update:visible', false)
  emit('cancel')
}

function onOverlayClick() {
  if (props.closeOnClickOverlay) {
    emitCancel()
  }
}

const dialogAttrs = useDialogA11y(
  toRef(props, 'visible'),
  overlayRef,
  { titleId: props.titleId || undefined, close: emitCancel },
)
</script>
