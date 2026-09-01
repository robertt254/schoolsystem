<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';
import ReceiptModal from '../components/ReceiptModal.vue';
import ItemizedFeeReceipt from '../components/ItemizedFeeReceipt.vue';
import ItemizedReceiptModal from '../components/ItemizedReceiptModal.vue';
import { exportCsv } from '../utils/csvExport';

// Per-term accountability table (fees vs expenses vs payroll vs petty cash)
const accountability = ref(null);
const loadAccountability = async () => {
    if (!authStore.canFinance) return;   // secretary handles fees only
    try {
        const res = await api.getTermAccountability(academicYear.value);
        accountability.value = res.data;
    } catch (e) { console.error(e); }
};

const exportAccountability = () => {
    if (!accountability.value) return;
    exportCsv(`term_accountability_${accountability.value.academic_year}.csv`,
        [['term', 'Term'], ['fees_collected', 'Fees Collected'], ['expenses', 'Expenses'],
         ['payroll', 'Payroll'], ['petty_cash_in', 'Petty Cash In'],
         ['petty_cash_out', 'Petty Cash Out'], ['net', 'Net']],
        [...accountability.value.terms, { term: 'TOTAL', ...accountability.value.totals }]);
};

const exportPaymentLog = () => {
    exportCsv('payment_log.csv',
        [['receipt_number', 'Receipt'], ['student_name', 'Student'], ['admission_number', 'Admission No'],
         ['grade_level', 'Grade'], ['payment_type', 'Type'], ['term', 'Term'],
         ['amount', 'Amount'], ['payment_date', 'Date'], ['recorded_by', 'Recorded By'], ['status', 'Status']],
        paymentLog.value);
};

const authStore = useAuthStore();
const dashboardStats = ref({
    total_expected: 0,
    total_collected: 0,
    outstanding_balance: 0
});

const currentTerm = ref('Term 1');
const academicYear = ref(new Date().getFullYear());
const students = ref([]);
const paymentLog = ref([]);
const monthly = ref([]);
const maxMonthly = ref(1);
const message = ref('');

const newInvoice = ref({ student_id: '', term: '', total_amount: '' });

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

// Type-ahead search so the invoice student picker can be found by name,
// admission number or class instead of scrolling a long dropdown.
const invoiceStudentSearch = ref('');
const filteredInvoiceStudents = computed(() => {
    const q = invoiceStudentSearch.value.trim().toLowerCase();
    if (!q) return students.value;
    return students.value.filter(s =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.admission_number || '').toLowerCase().includes(q) ||
        (s.grade_level || '').toLowerCase().includes(q));
});

const loadDashboard = async () => {
    try {
        // Resolve the school's active term first — all figures are per-term.
        const termRes = await api.getCurrentTerm();
        currentTerm.value = termRes.data.term;
        academicYear.value = termRes.data.academic_year;
    } catch (e) { console.error(e); }
    try {
        const statsRes = await api.getDashboardStats(currentTerm.value);
        const s = statsRes.data;
        dashboardStats.value = {
            total_expected: s.term_expected || 0,
            total_collected: s.term_collected || 0,
            outstanding_balance: Math.max((s.term_expected || 0) - (s.term_collected || 0), 0)
        };
    } catch (e) { console.error("Failed to load dashboard stats", e); }
    try {
        const res = await api.getPaymentLog(50);
        paymentLog.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getMonthlyCollection(academicYear.value);
        monthly.value = res.data;
        maxMonthly.value = Math.max(1, ...res.data.map(m => m.total));
    } catch (e) { console.error(e); }
};

const loadStudents = async () => {
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
};

// An "invoice" is recorded as a carry-forward charge: a positive amount the
// student owes for the given term, on top of the configured fee structure.
const createInvoice = async () => {
    if(!newInvoice.value.student_id || !newInvoice.value.term || !newInvoice.value.total_amount) return;
    message.value = '';
    try {
        await api.createCarryForward({
            student_id: parseInt(newInvoice.value.student_id),
            amount: parseFloat(newInvoice.value.total_amount),
            academic_year: String(academicYear.value),
            term: `Term ${parseInt(newInvoice.value.term)}`,
            note: 'Manual invoice'
        });
        newInvoice.value = { student_id: '', term: '', total_amount: '' };
        message.value = 'Charge recorded against the student.';
        loadDashboard();
    } catch (e) {
        console.error("Failed to create invoice", e);
        message.value = e.response?.data?.detail || 'Failed to record charge.';
    }
};

// receipt: single-payment receipts opened from the Payment Log below.
// itemizedReceipt: the multi-line slip shown right after ItemizedFeeReceipt
// records a batch of fee-receipt lines for one student.
const receipt = ref(null);
const itemizedReceipt = ref(null);

const onItemizedRecorded = (data) => {
    itemizedReceipt.value = data;
    message.value = '';
    loadDashboard();
};

const openReceipt = (p) => {
    receipt.value = p;
};

const deletePayment = async (p) => {
    if (!window.confirm(`Delete payment ${p.receipt_number} of ${money(p.amount)}? This is audited.`)) return;
    try {
        await api.deleteFeePayment(p.id);
        loadDashboard();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to delete payment.');
    }
};

onMounted(async () => {
    await loadDashboard();   // resolves the academic year first
    loadStudents();
    loadAccountability();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Finance Dashboard</h1>
        <span class="px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800">{{ currentTerm }} · {{ academicYear }}</span>
    </div>

    <!-- Stats Row -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Expected</h3>
            <p class="text-3xl font-bold text-navy">{{ money(dashboardStats.total_expected) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Collected</h3>
            <p class="text-3xl font-bold text-green-600">{{ money(dashboardStats.total_collected) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Outstanding Balance</h3>
            <p class="text-3xl font-bold text-red-accent">{{ money(dashboardStats.outstanding_balance) }}</p>
            <div class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
        </div>
    </div>

    <p v-if="message" class="text-sm font-medium" :class="message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Itemized fee receipt — mirrors the school's paper receipt book -->
    <div class="mt-8">
        <ItemizedFeeReceipt :students="students" :current-term="currentTerm" :academic-year="academicYear"
                             @recorded="onItemizedRecorded" />
    </div>

    <!-- Invoicing Actions -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mt-8 max-w-xl">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Generate Invoice</h2>
        <form @submit.prevent="createInvoice" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700">Student</label>
                <input v-model="invoiceStudentSearch" type="text" placeholder="Search by name, admission no. or class…"
                       class="mt-1 mb-2 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                <select v-model="newInvoice.student_id" required class="block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                    <option value="">Select student ({{ filteredInvoiceStudents.length }} match{{ filteredInvoiceStudents.length === 1 ? '' : 'es' }})</option>
                    <option v-for="s in filteredInvoiceStudents" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }})</option>
                </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Term (1-3)</label>
                    <input v-model="newInvoice.term" type="number" min="1" max="3" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Amount</label>
                    <input v-model="newInvoice.total_amount" type="number" step="0.01" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
                </div>
            </div>
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-navy hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy">
                Create Invoice
            </button>
        </form>
    </div>

    <!-- Monthly collection -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Monthly Collection · {{ academicYear }}</h2>
        <div class="flex items-end gap-2 h-40">
            <div v-for="m in monthly" :key="m.month" class="flex-1 flex flex-col items-center justify-end h-full">
                <span class="text-xs text-gray-500 mb-1" v-if="m.total > 0">{{ Math.round(m.total / 1000) }}k</span>
                <div class="w-full bg-navy rounded-t" :style="{ height: (m.total / maxMonthly * 100) + '%' }" :class="m.total > 0 ? '' : 'bg-gray-bg'"></div>
                <span class="text-xs text-gray-500 mt-1">{{ m.month }}</span>
            </div>
        </div>
    </div>

    <!-- Term accountability -->
    <div v-if="accountability" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Term Accountability · {{ accountability.academic_year }}</h2>
            <button @click="exportAccountability" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Export CSV</button>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Term</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Fees Collected</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expenses</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Payroll</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Petty Cash In</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Petty Cash Out</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Net</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="row in accountability.terms" :key="row.term" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ row.term }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-green-600 font-semibold">{{ money(row.fees_collected) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(row.expenses) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(row.payroll) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(row.petty_cash_in) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(row.petty_cash_out) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-bold" :class="row.net >= 0 ? 'text-green-600' : 'text-red-accent'">{{ money(row.net) }}</td>
                </tr>
                <tr class="bg-gray-50 font-bold">
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-navy">TOTAL</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-green-600">{{ money(accountability.totals.fees_collected) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-700">{{ money(accountability.totals.expenses) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-700">{{ money(accountability.totals.payroll) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-700">{{ money(accountability.totals.petty_cash_in) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-700">{{ money(accountability.totals.petty_cash_out) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right" :class="accountability.totals.net >= 0 ? 'text-green-600' : 'text-red-accent'">{{ money(accountability.totals.net) }}</td>
                </tr>
            </tbody>
        </table>
        <p class="px-6 py-3 text-xs text-gray-400 border-t">
            Net = fees − expenses − payroll − petty cash out. Expenses, payroll and petty cash are assigned to
            terms by their dates using the school calendar; petty cash top-ups (In) are informational since they
            usually come out of collected fees.
        </p>
    </div>

    <!-- Payment log -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Payment Log</h2>
            <button @click="exportPaymentLog" :disabled="paymentLog.length === 0" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light disabled:opacity-50 text-sm">Export CSV</button>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Receipt</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type / Term</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="p in paymentLog" :key="p.id" class="hover:bg-gray-50" :class="p.status === 'deleted' ? 'opacity-60' : ''">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ p.receipt_number || '—' }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-900">{{ p.student_name }} <span class="text-xs text-gray-400">{{ p.admission_number }}</span></td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ p.payment_type }} · {{ p.term }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ money(p.amount) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ dateFmt(p.payment_date || p.deleted_at) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="p.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
                            {{ p.status === 'active' ? 'Paid' : 'Deleted' }}
                        </span>
                    </td>
                    <td class="px-6 py-3 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="p.status === 'active'" @click="openReceipt(p)" class="text-navy hover:text-navy-light mx-1 font-bold underline">Receipt</button>
                        <button v-if="authStore.isAdmin && p.status === 'active'" @click="deletePayment(p)" class="text-red-accent hover:text-red-hover mx-1 font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="paymentLog.length === 0">
                    <td colspan="7" class="px-6 py-8 text-center text-gray-500 text-sm">No payments recorded yet.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <ReceiptModal v-if="receipt" :payment="receipt" @close="receipt = null" />
    <ItemizedReceiptModal v-if="itemizedReceipt" :data="itemizedReceipt" @close="itemizedReceipt = null" />
  </div>
</template>
