<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];
const terms = ["Term 1", "Term 2", "Term 3"];
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const periods = [1, 2, 3, 4, 5, 6, 7, 8];

const selectedGrade = ref('Grade 1');
const selectedTerm = ref('Term 1');
const grid = ref({});
const isModalOpen = ref(false);
const entry = ref({ day_of_week: 'Monday', period: 1, subject: '', teacher_name: '', start_time: '', end_time: '' });

const load = async () => {
    try {
        const res = await api.getTimetable(selectedGrade.value, selectedTerm.value);
        grid.value = res.data.grid || {};
    } catch (e) { console.error(e); }
};

const openCell = (day, period) => {
    if (!authStore.isAdmin) return;
    const existing = grid.value[day]?.[period];
    entry.value = {
        day_of_week: day,
        period,
        subject: existing?.subject || '',
        teacher_name: existing?.teacher_name || '',
        start_time: existing?.start_time || '',
        end_time: existing?.end_time || ''
    };
    isModalOpen.value = true;
};

const saveEntry = async () => {
    if (!entry.value.subject) return;
    try {
        await api.upsertTimetableEntry({
            grade_level: selectedGrade.value,
            day_of_week: entry.value.day_of_week,
            period: entry.value.period,
            subject: entry.value.subject,
            teacher_name: entry.value.teacher_name || null,
            start_time: entry.value.start_time || null,
            end_time: entry.value.end_time || null,
            term: selectedTerm.value,
            academic_year: new Date().getFullYear()
        });
        isModalOpen.value = false;
        load();
    } catch (e) { console.error(e); }
};

const removeEntry = async () => {
    const existing = grid.value[entry.value.day_of_week]?.[entry.value.period];
    if (!existing) { isModalOpen.value = false; return; }
    try {
        await api.deleteTimetableEntry(existing.id);
        isModalOpen.value = false;
        load();
    } catch (e) { console.error(e); }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8 relative">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Timetable</h1>
        <div class="flex gap-4">
            <select v-model="selectedGrade" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
                <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
            </select>
            <select v-model="selectedTerm" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
                <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
            </select>
        </div>
    </div>

    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Period</th>
                        <th v-for="d in days" :key="d" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{{ d }}</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="p in periods" :key="p">
                        <td class="px-4 py-3 whitespace-nowrap text-sm font-bold text-navy">{{ p }}</td>
                        <td v-for="d in days" :key="d" @click="openCell(d, p)"
                            class="px-4 py-3 text-sm border-l border-gray-100"
                            :class="authStore.isAdmin ? 'cursor-pointer hover:bg-gray-50' : ''">
                            <div v-if="grid[d] && grid[d][p]">
                                <p class="font-semibold text-gray-900">{{ grid[d][p].subject }}</p>
                                <p class="text-xs text-gray-500">{{ grid[d][p].teacher_name || '' }}</p>
                                <p v-if="grid[d][p].start_time" class="text-xs text-gray-400">{{ grid[d][p].start_time }}–{{ grid[d][p].end_time }}</p>
                            </div>
                            <span v-else class="text-gray-300">—</span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <p v-if="authStore.isAdmin" class="px-6 py-3 text-xs text-gray-400 border-t">Click any cell to add or edit a lesson.</p>
    </div>

    <!-- Entry Modal -->
    <div v-if="isModalOpen" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-8">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-2xl font-bold text-navy">{{ entry.day_of_week }} · Period {{ entry.period }}</h3>
                <button @click="isModalOpen = false" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
            </div>
            <form @submit.prevent="saveEntry" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Subject</label>
                    <input v-model="entry.subject" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Teacher</label>
                    <input v-model="entry.teacher_name" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Start (HH:MM)</label>
                        <input v-model="entry.start_time" type="text" placeholder="08:00" pattern="\d{2}:\d{2}" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">End (HH:MM)</label>
                        <input v-model="entry.end_time" type="text" placeholder="08:40" pattern="\d{2}:\d{2}" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <div class="flex justify-between pt-4">
                    <button type="button" @click="removeEntry" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Save Lesson</button>
                </div>
            </form>
        </div>
    </div>
  </div>
</template>
