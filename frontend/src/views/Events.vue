<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const events = ref([]);
const year = ref(new Date().getFullYear());
const termDates = ref(null);
const currentTerm = ref(null);
const message = ref('');

const eventTypes = ['exam', 'holiday', 'meeting', 'sports', 'other'];
const newEvent = ref({
    title: '', event_type: 'meeting',
    start_date: '', end_date: '', description: ''
});

const typeBadge = (t) => ({
    exam: 'bg-red-100 text-red-800',
    holiday: 'bg-green-100 text-green-800',
    meeting: 'bg-blue-100 text-blue-800',
    sports: 'bg-yellow-100 text-yellow-800',
    other: 'bg-gray-100 text-gray-600'
}[t] || 'bg-gray-100 text-gray-600');

const load = async () => {
    try {
        const res = await api.getEvents({ year: parseInt(year.value) });
        events.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getTermDates(parseInt(year.value));
        termDates.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getCurrentTerm();
        currentTerm.value = res.data;
    } catch (e) { console.error(e); }
};

const addEvent = async () => {
    const f = newEvent.value;
    if (!f.title || !f.start_date) return;
    message.value = '';
    try {
        await api.createEvent({
            title: f.title,
            description: f.description || null,
            event_type: f.event_type,
            start_date: f.start_date,
            end_date: f.end_date || null,
            all_day: true
        });
        newEvent.value = { title: '', event_type: 'meeting', start_date: '', end_date: '', description: '' };
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to create event.';
    }
};

const removeEvent = async (ev) => {
    if (!window.confirm(`Delete event "${ev.title}"?`)) return;
    try {
        await api.deleteEvent(ev.id);
        load();
    } catch (e) { console.error(e); }
};

const saveTermDates = async () => {
    message.value = '';
    try {
        await api.setTermDates({
            academic_year: parseInt(year.value),
            terms: termDates.value.terms.map(t => ({
                term: t.term,
                start_date: t.start_date,
                end_date: t.end_date
            }))
        });
        message.value = 'Term dates saved.';
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to save term dates.';
    }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">School Calendar & Events</h1>
        <div class="flex gap-4 items-center">
            <span v-if="currentTerm" class="px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800">
                Now: {{ currentTerm.term }} {{ currentTerm.academic_year }}
            </span>
            <input v-model="year" @change="load" type="number" class="border border-gray-300 p-2 rounded-md w-28 focus:ring-navy focus:border-navy" />
        </div>
    </div>
    <p v-if="message" class="text-sm font-medium" :class="message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Term dates -->
    <div v-if="termDates" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="flex justify-between items-center mb-4 border-b pb-2">
            <h2 class="text-xl font-bold text-navy">Term Dates · {{ year }}
                <span v-if="termDates.is_default" class="ml-2 px-2 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">defaults — not yet saved</span>
            </h2>
            <button v-if="authStore.isAdmin" @click="saveTermDates" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light">Save Term Dates</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div v-for="t in termDates.terms" :key="t.term" class="border border-gray-200 rounded-md p-4">
                <h3 class="font-bold text-navy mb-2">{{ t.term }}</h3>
                <label class="block text-xs text-gray-500">Start</label>
                <input v-model="t.start_date" :disabled="!authStore.isAdmin" type="date" class="border border-gray-300 p-1.5 rounded-md w-full text-sm mb-2 focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
                <label class="block text-xs text-gray-500">End</label>
                <input v-model="t.end_date" :disabled="!authStore.isAdmin" type="date" class="border border-gray-300 p-1.5 rounded-md w-full text-sm focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
            </div>
        </div>
    </div>

    <!-- Add event — admin/principal/secretary -->
    <div v-if="authStore.canComms" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Add Event</h2>
        <form @submit.prevent="addEvent" class="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input v-model="newEvent.title" type="text" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
                <select v-model="newEvent.event_type" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in eventTypes" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Start</label>
                <input v-model="newEvent.start_date" type="date" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">End (optional)</label>
                <input v-model="newEvent.end_date" type="date" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Add Event</button>
            <div class="md:col-span-5">
                <label class="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <input v-model="newEvent.description" type="text" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
        </form>
    </div>

    <!-- Events list -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Events · {{ year }}</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dates</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Event</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created By</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="ev in events" :key="ev.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ ev.start_date }}<span v-if="ev.end_date"> → {{ ev.end_date }}</span></td>
                    <td class="px-6 py-4 text-sm">
                        <p class="font-medium text-gray-900">{{ ev.title }}</p>
                        <p class="text-xs text-gray-500">{{ ev.description || '' }}</p>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full" :class="typeBadge(ev.event_type)">{{ ev.event_type }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ ev.created_by }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="authStore.isAdmin" @click="removeEvent(ev)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="events.length === 0">
                    <td colspan="5" class="px-6 py-8 text-center text-gray-500 text-sm">No events for {{ year }}.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
