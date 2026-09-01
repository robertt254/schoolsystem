<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';
import ReceiptModal from '../components/ReceiptModal.vue';
import SchoolBadge from '../components/SchoolBadge.vue';
import { printElement } from '../utils/printFrame';

const authStore = useAuthStore();
const students = ref([]);
const selectedStudent = ref('');
const studentSearch = ref('');

// Type-ahead filter so a statement can be pulled up quickly by name,
// admission number or class
const filteredStudents = computed(() => {
    const q = studentSearch.value.trim().toLowerCase();
    if (!q) return students.value;
    return students.value.filter(s =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.admission_number || '').toLowerCase().includes(q) ||
        (s.grade_level || '').toLowerCase().includes(q)
    );
});
const academicYear = ref(String(new Date().getFullYear()));
const balances = ref([]);        // per-term balance breakdowns
const payments = ref([]);
const carryForwards = ref([]);
const studentInfo = ref(null);
const terms = ["Term 1", "Term 2", "Term 3"];

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

const totalOutstanding = computed(() =>
    balances.value.reduce((s, b) => s + (b.outstanding_balance || 0), 0));
// Voided payments stay listed below for accountability but no longer count
// as money actually paid.
const totalPaid = computed(() =>
    payments.value.filter(p => !p.is_voided).reduce((s, p) => s + Number(p.amount || 0), 0));

const loadStudents = async () => {
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
};

const generate = async () => {
    if (!selectedStudent.value) return;
    const id = parseInt(selectedStudent.value);
    studentInfo.value = students.value.find(s => s.id === id) || null;
    balances.value = [];
    try {
        const results = await Promise.all(terms.map(t => api.getStudentFeeBalance(id, t)));
        balances.value = results.map(r => r.data);
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStudentPayments(id);
        payments.value = res.data;
    } catch (e) { console.error(e); payments.value = []; }
    try {
        const res = await api.getStudentCarryForwards(id);
        carryForwards.value = res.data;
    } catch (e) { console.error(e); carryForwards.value = []; }
};

const removeCarryForward = async (cf) => {
    if (!window.confirm(`Delete carry-forward of ${money(cf.amount)} (${cf.term} ${cf.academic_year})?`)) return;
    try {
        await api.deleteCarryForward(cf.id);
        generate();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to delete carry-forward.');
    }
};

const voidPayment = async (p) => {
    const reason = window.prompt(
        `Void payment ${p.receipt_number} of ${money(p.amount)}?\nThis stays on record for accountability, but no longer counts toward any balance or total.\n\nReason (required):`
    );
    if (reason === null) return;
    if (reason.trim().length < 3) {
        window.alert('A reason of at least 3 characters is required to void a payment.');
        return;
    }
    try {
        await api.voidFeePayment(p.id, reason.trim());
        generate();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to void payment.');
    }
};

const statementRoot = ref(null);
const printStatement = () => printElement(statementRoot.value, `Fee Statement — ${studentInfo.value?.first_name || ''} ${studentInfo.value?.last_name || ''}`);

// Branded receipt for a single payment
const receipt = ref(null);
const openReceipt = (p) => {
    receipt.value = {
        ...p,
        student_name: studentInfo.value ? `${studentInfo.value.first_name} ${studentInfo.value.last_name}` : '',
        admission_number: studentInfo.value?.admission_number || '',
        grade_level: studentInfo.value?.grade_level || ''
    };
};

onMounted(loadStudents);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <div>
            <h1 class="text-3xl font-bold text-navy">Fee Statement</h1>
            <p class="text-sm text-gray-500">Bona School Kenya</p>
        </div>
        <button v-if="studentInfo" @click="printStatement" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Print</button>
    </div>

    <!-- Selector -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Search</label>
                <input v-model="studentSearch" type="text" placeholder="Name, admission no. or class…"
                       class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">Student ({{ filteredStudents.length }} match{{ filteredStudents.length === 1 ? '' : 'es' }})</label>
                <select v-model="selectedStudent" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="">Select student</option>
                    <option v-for="s in filteredStudents" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }} · {{ s.grade_level }})</option>
                </select>
            </div>
            <button @click="generate" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Generate Statement</button>
        </div>
    </div>

    <template v-if="studentInfo">
      <div ref="statementRoot" class="print-area space-y-8">
        <!-- Print-only letterhead -->
        <div class="hidden print:block text-center border-b-2 border-navy pb-4">
            <div class="flex justify-center mb-2">
                <SchoolBadge :size="80" />
            </div>
            <h2 class="text-2xl font-extrabold text-navy">THE BONA SCHOOL</h2>
            <p class="text-xs font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
            <p class="text-xs uppercase tracking-widest text-gray-500 mt-1">Official Fee Statement</p>
        </div>
        <!-- Header cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Student</h3>
                <p class="text-xl font-bold text-navy">{{ studentInfo.first_name }} {{ studentInfo.last_name }}</p>
                <p class="text-sm text-gray-500">{{ studentInfo.admission_number }} · {{ studentInfo.grade_level }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Paid (All Time)</h3>
                <p class="text-3xl font-bold text-green-600">{{ money(totalPaid) }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Outstanding ({{ academicYear }})</h3>
                <p class="text-3xl font-bold" :class="totalOutstanding > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(totalOutstanding) }}</p>
                <div v-if="totalOutstanding > 0" class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
            </div>
        </div>

        <!-- Per-term balances -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Term Balances · {{ academicYear }}</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Term</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expected Fee</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Rollover Credit</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Outstanding</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="b in balances" :key="b.term_checked" class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ b.term_checked }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(b.expected_term_fee) }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-green-600 font-semibold">{{ money(b.total_paid_this_term) }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(b.rollover_credit) }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-bold" :class="b.outstanding_balance > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(b.outstanding_balance) }}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Carry-forwards -->
        <div v-if="carryForwards.length" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Carry-Forwards & Manual Charges</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Year / Term</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Note</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="cf in carryForwards" :key="cf.id" class="hover:bg-gray-50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ cf.academic_year }} · {{ cf.term }}</td>
                        <td class="px-6 py-4 text-sm text-gray-900">{{ cf.note || '—' }} <span class="text-xs text-gray-400">by {{ cf.recorded_by }}</span></td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold" :class="cf.amount > 0 ? 'text-red-accent' : 'text-green-600'">
                            {{ cf.amount > 0 ? 'Owes' : 'Credit' }} {{ money(Math.abs(cf.amount)) }}
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <button v-if="authStore.isAdmin" @click="removeCarryForward(cf)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Payment history with receipts -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Payment History</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Receipt</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type / Term</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Allocation</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider no-print">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="p in payments" :key="p.id" class="hover:bg-gray-50" :class="p.is_voided ? 'opacity-60' : ''">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ p.receipt_number || '—' }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ dateFmt(p.payment_date) }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ p.payment_type }}<span v-if="p.activity"> · {{ p.activity }}</span> · {{ p.term }}</td>
                        <td class="px-6 py-4 text-sm text-gray-500">
                            <template v-if="p.allocation && p.allocation.length">
                                <span v-for="(a, i) in p.allocation" :key="i" class="mr-2 px-2 py-0.5 text-xs font-semibold rounded-full"
                                      :class="a.kind === 'arrears' ? 'bg-yellow-100 text-yellow-800' : a.kind === 'advance' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'">
                                    {{ a.term }}: {{ money(a.amount) }}
                                </span>
                            </template>
                            <span v-else>—</span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ money(p.amount) }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                                  :class="p.is_voided ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'">
                                {{ p.is_voided ? 'Voided' : 'Paid' }}
                            </span>
                            <span v-if="p.is_voided" class="block text-xs text-gray-400 mt-0.5">by {{ p.voided_by }} · {{ p.void_reason }}</span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium no-print">
                            <button @click="openReceipt(p)" class="text-navy hover:text-navy-light mx-1 font-bold underline">Receipt</button>
                            <button v-if="authStore.isAdmin && !p.is_voided" @click="voidPayment(p)" class="text-red-accent hover:text-red-hover mx-1 font-bold underline">Void</button>
                        </td>
                    </tr>
                    <tr v-if="payments.length === 0">
                        <td colspan="7" class="px-6 py-8 text-center text-gray-500 text-sm">No payments recorded for this student.</td>
                    </tr>
                </tbody>
            </table>
        </div>
      </div>
    </template>

    <ReceiptModal v-if="receipt" :payment="receipt" @close="receipt = null" />
  </div>
</template>
