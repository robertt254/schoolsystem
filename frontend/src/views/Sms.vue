<script setup>
import { ref, onMounted, watch } from 'vue';
import api from '../api';

const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];

const grade = ref('');
const messageText = ref('');
const recipientCount = ref(null);
const status = ref('');
const sending = ref(false);

const preview = async () => {
    try {
        const res = await api.smsPreview(grade.value || undefined);
        recipientCount.value = res.data.recipient_count;
    } catch (e) {
        recipientCount.value = null;
        console.error(e);
    }
};

watch(grade, preview);

const send = async () => {
    if (messageText.value.trim().length < 5) return;
    if (!window.confirm(`Send this SMS to ${recipientCount.value ?? '?'} guardian(s)${grade.value ? ' in ' + grade.value : ''}?`)) return;
    sending.value = true;
    status.value = '';
    try {
        const res = await api.smsBroadcast(messageText.value.trim(), grade.value || undefined);
        status.value = res.data.message;
        messageText.value = '';
    } catch (e) {
        status.value = e.response?.data?.detail || 'Failed to send broadcast.';
    }
    sending.value = false;
};

onMounted(preview);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">SMS Communications</h1>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Broadcast to Guardians</h2>
            <form @submit.prevent="send" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Audience</label>
                    <select v-model="grade" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                        <option value="">All parents & guardians</option>
                        <option v-for="g in grades" :key="g" :value="g">{{ g }} guardians only</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Message ({{ messageText.length }}/500)</label>
                    <textarea v-model="messageText" rows="5" maxlength="500" minlength="5" required
                              placeholder="Dear parent, ..."
                              class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy"></textarea>
                </div>
                <button type="submit" :disabled="sending || messageText.trim().length < 5"
                        class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">
                    {{ sending ? 'Sending…' : 'Send Broadcast' }}
                </button>
                <p v-if="status" class="text-sm font-medium" :class="status.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ status }}</p>
            </form>
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Reachable Guardians</h3>
            <p class="text-3xl font-bold text-navy">{{ recipientCount ?? '—' }}</p>
            <p class="text-sm text-gray-500 mt-2">{{ grade || 'All grades' }}</p>
            <p class="text-xs text-gray-400 mt-4">Counts unique guardian phone numbers on active student records. Absence alerts and payment receipts are sent automatically.</p>
        </div>
    </div>
  </div>
</template>
