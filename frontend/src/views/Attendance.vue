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

const selectedGrade = ref('Grade 1');
const roster = ref([]);
const summary = ref([]);
const saving = ref(false);
const savedMessage = ref('');

const loadRoster = async () => {
    savedMessage.value = '';
    try {
        const res = await api.getTodayAttendance(selectedGrade.value);
        roster.value = res.data;
    } catch (e) { console.error(e); }
};

const loadSummary = async () => {
    try {
        const res = await api.getAttendanceSummary();
        summary.value = res.data;
    } catch (e) { console.error(e); }
};

const markAll = (present) => {
    roster.value.forEach(r => { r.is_present = present; });
};

const save = async () => {
    if (!roster.value.length) return;
    saving.value = true;
    savedMessage.value = '';
    try {
        await api.markBulkAttendance(roster.value.map(r => ({
            student_id: r.student_id,
            is_present: r.is_present,
            remarks: r.remarks || null
        })));
        savedMessage.value = `Attendance saved for ${selectedGrade.value}. Absentees' guardians are notified by SMS.`;
        loadSummary();
    } catch (e) {
        console.error(e);
        savedMessage.value = 'Failed to save attendance.';
    }
    saving.value = false;
};

onMounted(() => {
    loadRoster();
    loadSummary();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Attendance</h1>
        <span class="text-sm text-gray-500">{{ new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) }}</span>
    </div>

    <!-- Marking panel — accountant can view summaries but not mark -->
    <div v-if="authStore.canMarkAttendance" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Mark Today's Register</h2>
        <div class="flex flex-col md:flex-row gap-4 items-end mb-4">
            <div class="md:w-56">
                <label class="block text-sm font-medium text-gray-700 mb-1">Grade</label>
                <select v-model="selectedGrade" @change="loadRoster" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                </select>
            </div>
            <button @click="markAll(true)" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light">All Present</button>
            <button @click="markAll(false)" class="bg-red-accent text-white px-4 py-2 rounded-md hover:bg-red-hover">All Absent</button>
            <div class="flex-1"></div>
            <button @click="save" :disabled="saving" class="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:opacity-50">
                {{ saving ? 'Saving…' : 'Save Register' }}
            </button>
        </div>
        <p v-if="savedMessage" class="text-sm font-medium mb-3" :class="savedMessage.startsWith('Failed') ? 'text-red-accent' : 'text-green-600'">{{ savedMessage }}</p>

        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Present</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Remarks</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in roster" :key="r.student_id" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{{ r.name }}</td>
                    <td class="px-6 py-3 text-center">
                        <input type="checkbox" v-model="r.is_present" class="h-5 w-5 rounded border-gray-300 text-navy focus:ring-navy" />
                    </td>
                    <td class="px-6 py-3">
                        <input v-model="r.remarks" type="text" placeholder="Optional remark" class="border border-gray-300 p-1.5 rounded-md w-full text-sm focus:ring-navy focus:border-navy" />
                    </td>
                </tr>
                <tr v-if="roster.length === 0">
                    <td colspan="3" class="px-6 py-8 text-center text-gray-500 text-sm">No students in this grade.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Summary -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Attendance Summary (All Time)</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Records</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Present</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Rate</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="s in summary" :key="s.grade" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ s.grade }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ s.total_records }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ s.present }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right">
                        <span v-if="s.percentage !== null" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="s.percentage >= 90 ? 'bg-green-100 text-green-800' : s.percentage >= 75 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'">
                            {{ s.percentage }}%
                        </span>
                        <span v-else class="text-gray-400">—</span>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
