<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const reportType = ref('enrollment');
const year = ref(new Date().getFullYear());
const term = ref('');
const rows = ref([]);
const columns = ref([]);
const generated = ref(false);
const terms = ["Term 1", "Term 2", "Term 3"];

const REPORTS = [
    { value: 'enrollment', label: 'Enrollment by Grade' },
    { value: 'collection', label: 'Fee Collection by Term' },
    { value: 'attendance', label: 'Attendance by Grade' },
    { value: 'exams', label: 'Exam Performance' }
];

const generate = async () => {
    rows.value = [];
    columns.value = [];
    generated.value = false;
    try {
        if (reportType.value === 'enrollment') {
            const res = await api.getEnrollmentSummary();
            columns.value = [['grade_level', 'Grade'], ['count', 'Students']];
            rows.value = res.data;
        } else if (reportType.value === 'collection') {
            const res = await api.getCollectionSummary({
                academic_year: year.value, ...(term.value ? { term: term.value } : {})
            });
            columns.value = [['term', 'Term'], ['total_paid', 'Total Collected'], ['num_payments', 'Payments'], ['unique_students', 'Students Paying']];
            rows.value = res.data;
        } else if (reportType.value === 'attendance') {
            const res = await api.getAttendanceSummary();
            columns.value = [['grade', 'Grade'], ['total_records', 'Records'], ['present', 'Present'], ['percentage', 'Rate %']];
            rows.value = res.data;
        } else if (reportType.value === 'exams') {
            const res = await api.getExamPerformanceSummary({
                ...(year.value ? { academic_year: String(year.value) } : {}),
                ...(term.value ? { term: term.value } : {})
            });
            columns.value = [['grade_level', 'Grade'], ['subject', 'Subject'], ['exam_type', 'Exam'], ['avg_score', 'Average'], ['highest', 'Highest'], ['lowest', 'Lowest'], ['num_students', 'Students']];
            rows.value = res.data;
        }
        generated.value = true;
    } catch (e) { console.error(e); }
};

const exportCsv = () => {
    if (!rows.value.length) return;
    const header = columns.value.map(c => c[1]).join(',') + '\n';
    const body = rows.value.map(r =>
        columns.value.map(c => {
            const v = r[c[0]];
            return typeof v === 'string' && v.includes(',') ? `"${v}"` : (v ?? '');
        }).join(',')
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${reportType.value}_report_${year.value}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
};

onMounted(generate);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Report Builder</h1>
        <button @click="exportCsv" :disabled="rows.length === 0" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">Export CSV</button>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Report</label>
                <select v-model="reportType" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="r in REPORTS" :key="r.value" :value="r.value">{{ r.label }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <input v-model="year" type="number" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term (optional)</label>
                <select v-model="term" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="">All terms</option>
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <button @click="generate" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Generate</button>
        </div>
    </div>

    <!-- Result table -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th v-for="c in columns" :key="c[0]" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{{ c[1] }}</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="(r, i) in rows" :key="i" class="hover:bg-gray-50">
                    <td v-for="c in columns" :key="c[0]" class="px-6 py-3 whitespace-nowrap text-sm"
                        :class="c === columns[0] ? 'font-medium text-navy' : 'text-gray-500'">
                        {{ typeof r[c[0]] === 'number' ? r[c[0]].toLocaleString() : (r[c[0]] ?? '—') }}
                    </td>
                </tr>
                <tr v-if="generated && rows.length === 0">
                    <td :colspan="columns.length || 1" class="px-6 py-8 text-center text-gray-500 text-sm">No data for this selection.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
