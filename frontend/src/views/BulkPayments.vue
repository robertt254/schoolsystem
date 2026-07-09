<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';

const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];
const terms = ["Term 1", "Term 2", "Term 3"];
const paymentTypes = ['Tuition', 'Uniforms', 'Transport', 'Exam Fees'];

const selectedGrade = ref('Grade 1');
const selectedTerm = ref('Term 1');
const paymentType = ref('Tuition');
const rows = ref([]);          // [{student_id, name, admission_number, amount}]
const message = ref('');
const saving = ref(false);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const entered = computed(() => rows.value.filter(r => r.amount !== '' && r.amount !== null && parseFloat(r.amount) > 0));
const totalEntered = computed(() => entered.value.reduce((s, r) => s + parseFloat(r.amount), 0));

const loadStudents = async () => {
    message.value = '';
    try {
        const res = await api.getStudents({ grade: selectedGrade.value });
        rows.value = res.data.map(s => ({
            student_id: s.id,
            name: `${s.first_name} ${s.last_name}`,
            admission_number: s.admission_number,
            amount: ''
        }));
    } catch (e) { console.error(e); }
};

const save = async () => {
    if (!entered.value.length) return;
    if (!window.confirm(`Record ${entered.value.length} payment(s) totalling ${money(totalEntered.value)} for ${selectedTerm.value}?`)) return;
    saving.value = true;
    message.value = '';
    try {
        const res = await api.recordBulkPayments(entered.value.map(r => ({
            student_id: r.student_id,
            amount: parseFloat(r.amount),
            payment_type: paymentType.value,
            term: selectedTerm.value
        })));
        message.value = `Recorded ${res.data.created} payment(s) — receipts were generated for each.`;
        loadStudents();
    } catch (e) {
        console.error(e);
        message.value = e.response?.data?.detail || 'Failed to record payments.';
    }
    saving.value = false;
};

onMounted(loadStudents);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Bulk Fee Payments</h1>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Record Payments for a Whole Class</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 items-end mb-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Grade</label>
                <select v-model="selectedGrade" @change="loadStudents" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term</label>
                <select v-model="selectedTerm" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Payment Type</label>
                <select v-model="paymentType" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in paymentTypes" :key="t">{{ t }}</option>
                </select>
            </div>
            <button @click="save" :disabled="saving || entered.length === 0" class="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:opacity-50">
                {{ saving ? 'Saving…' : `Record ${entered.length} Payment(s)` }}
            </button>
        </div>
        <p class="text-sm text-gray-600 mb-3">
            Enter amounts only for students who paid — blank rows are skipped.
            Total entered: <span class="font-bold text-navy">{{ money(totalEntered) }}</span>
        </p>
        <p v-if="message" class="text-sm font-medium mb-3" :class="message.startsWith('Recorded') ? 'text-green-600' : 'text-red-accent'">{{ message }}</p>

        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount Paid</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in rows" :key="r.student_id" class="hover:bg-gray-50">
                    <td class="px-6 py-2 whitespace-nowrap text-sm font-medium text-navy">{{ r.admission_number }}</td>
                    <td class="px-6 py-2 whitespace-nowrap text-sm text-gray-900">{{ r.name }}</td>
                    <td class="px-6 py-2">
                        <input v-model="r.amount" type="number" min="0" step="0.01" placeholder="—"
                               class="border border-gray-300 p-1.5 rounded-md w-36 text-sm focus:ring-navy focus:border-navy" />
                    </td>
                </tr>
                <tr v-if="rows.length === 0">
                    <td colspan="3" class="px-6 py-8 text-center text-gray-500 text-sm">No students in this grade.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
