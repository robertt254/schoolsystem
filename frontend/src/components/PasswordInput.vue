<script setup>
import { ref } from 'vue';

defineProps({
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    required: { type: Boolean, default: false },
    minlength: { type: [String, Number], default: undefined },
    inputClass: { type: String, default: 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 pr-12 text-gray-900 bg-white focus:ring-navy focus:border-navy sm:text-sm' }
});
const emit = defineEmits(['update:modelValue']);
const visible = ref(false);
</script>

<template>
  <div class="relative">
    <input :type="visible ? 'text' : 'password'"
           :value="modelValue"
           @input="emit('update:modelValue', $event.target.value)"
           :placeholder="placeholder"
           :required="required"
           :minlength="minlength"
           :class="inputClass" />
    <button type="button" @click="visible = !visible"
            class="absolute inset-y-0 right-0 px-3 flex items-center text-xs font-semibold text-gray-500 hover:text-navy"
            :aria-label="visible ? 'Hide password' : 'Show password'">
      {{ visible ? 'Hide' : 'Show' }}
    </button>
  </div>
</template>
