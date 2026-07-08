<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';

const term = ref('Term 1');
const academicYear = ref(String(new Date().getFullYear()));
const defaulters = ref([]);
const loaded = ref(false);
const terms = ["Term 1", "Term 2", "Term 3"];

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const totalOutstanding = computed(() =>
    defaulters.value.reduce((sum, d) => sum + (d.outstanding_balance || 0), 0));

const load = async () => {
    try {
        const res = await api.getDefaulters(term.value, academicYear.value);
        defaulters.value = res.data;
        loaded.value = true;
    } catch (e) { console.error(e); }
};

const exportCsv = () => {
    const header = 'Admission No,Student,Grade,Expected,Paid,Outstanding\n';
    const body = defaulters.value.map(d =>
        `${d.admission_number},"${d.student_name}",${d.grade_level},${d.expected_fee},${d.total_paid},${d.outstanding_balance}`
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `defaulters_${term.value.replace(' ', '_')}_${academicYear.value}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
};

onMounted(async () => {
    try {
        const res = await api.getCurrentTerm();
        term.value = res.data.term;
        academicYear.value = String(res.data.academic_year);
    } catch (e) { console.error(e); }
    load();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Fee Defaulters</h1>
        <div class="flex gap-4 items-center">
            <select v-model="term" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
                <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
            </select>
            <button @click="exportCsv" :disabled="defaulters.length === 0" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">Export CSV</button>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Defaulters · {{ term }}</h3>
            <p class="text-3xl font-bold text-red-accent">{{ defaulters.length }}</p>
            <div class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Outstanding</h3>
            <p class="text-3xl font-bold text-navy">{{ money(totalOutstanding) }}</p>
        </div>
    </div>

    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Outstanding</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="d in defaulters" :key="d.student_id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ d.admission_number }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ d.student_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ d.grade_level }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(d.expected_fee + (d.carry_forward || 0)) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(d.total_paid + (d.rollover_credit || 0)) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-red-accent">{{ money(d.outstanding_balance) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <router-link :to="`/students/${d.student_id}`" class="text-navy hover:text-navy-light font-bold underline">Profile</router-link>
                    </td>
                </tr>
                <tr v-if="loaded && defaulters.length === 0">
                    <td colspan="7" class="px-6 py-8 text-center text-gray-500 text-sm">No defaulters for {{ term }}. 🎉</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
