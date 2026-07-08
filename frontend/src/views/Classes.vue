<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const summary = ref([]);
const selectedGrade = ref(null);
const roster = ref([]);
const loadingRoster = ref(false);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;

const loadSummary = async () => {
    try {
        const res = await api.getClassesSummary();
        summary.value = res.data;
    } catch (e) { console.error(e); }
};

const openRoster = async (grade) => {
    selectedGrade.value = grade;
    loadingRoster.value = true;
    try {
        const res = await api.getClassRoster(grade);
        roster.value = res.data;
    } catch (e) { console.error(e); }
    loadingRoster.value = false;
};

onMounted(loadSummary);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Classes</h1>
    </div>

    <!-- Grade summary cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div v-for="c in summary" :key="c.grade_level"
             @click="openRoster(c.grade_level)"
             class="bg-white rounded-xl shadow-sm border p-6 cursor-pointer transition-colors hover:border-navy"
             :class="selectedGrade === c.grade_level ? 'border-navy' : 'border-gray-200'">
            <div class="flex justify-between items-center mb-2">
                <h2 class="text-xl font-bold text-navy">{{ c.grade_level }}</h2>
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ c.total }} students</span>
            </div>
            <p class="text-sm text-gray-600">Present today: <span class="font-semibold text-green-600">{{ c.present_today }}</span></p>
            <p class="text-sm text-gray-600">Boys: <span class="font-semibold">{{ c.male }}</span> · Girls: <span class="font-semibold">{{ c.female }}</span></p>
        </div>
        <p v-if="summary.length === 0" class="text-gray-500 italic">No active students enrolled yet.</p>
    </div>

    <!-- Roster -->
    <div v-if="selectedGrade" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">{{ selectedGrade }} Roster</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Attendance</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Fee Balance</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="s in roster" :key="s.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ s.admission_number }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ s.first_name }} {{ s.last_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ s.attendance_pct === null ? '—' : s.attendance_pct + '%' }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold"
                        :class="(s.fee_balance || 0) > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(s.fee_balance) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <router-link :to="`/students/${s.id}`" class="text-navy hover:text-navy-light font-bold underline">Profile</router-link>
                    </td>
                </tr>
                <tr v-if="!loadingRoster && roster.length === 0">
                    <td colspan="5" class="px-6 py-8 text-center text-gray-500 text-sm">No students in this class.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
