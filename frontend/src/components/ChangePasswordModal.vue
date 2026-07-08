<script setup>
import { ref } from 'vue';
import api from '../api';

const emit = defineEmits(['close']);

const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const message = ref('');
const saving = ref(false);

const submit = async () => {
    message.value = '';
    if (newPassword.value !== confirmPassword.value) {
        message.value = 'New passwords do not match.';
        return;
    }
    if (newPassword.value.length < 8) {
        message.value = 'New password must be at least 8 characters.';
        return;
    }
    saving.value = true;
    try {
        await api.changePassword({
            current_password: currentPassword.value,
            new_password: newPassword.value
        });
        message.value = 'Password changed successfully.';
        setTimeout(() => emit('close'), 1200);
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to change password.';
    }
    saving.value = false;
};
</script>

<template>
  <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
    <div class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-8">
        <div class="flex justify-between items-center mb-6">
            <h3 class="text-2xl font-bold text-navy">Change Password</h3>
            <button @click="emit('close')" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
        </div>
        <form @submit.prevent="submit" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700">Current Password</label>
                <input v-model="currentPassword" type="password" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700">New Password (min 8 characters)</label>
                <input v-model="newPassword" type="password" required minlength="8" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700">Confirm New Password</label>
                <input v-model="confirmPassword" type="password" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
            </div>
            <p v-if="message" class="text-sm font-medium" :class="message.includes('successfully') ? 'text-green-600' : 'text-red-accent'">{{ message }}</p>
            <button type="submit" :disabled="saving" class="w-full py-2 px-4 rounded-md shadow-sm text-sm font-medium text-white bg-navy hover:bg-navy-light disabled:opacity-50">
                {{ saving ? 'Saving…' : 'Change Password' }}
            </button>
        </form>
    </div>
  </div>
</template>
