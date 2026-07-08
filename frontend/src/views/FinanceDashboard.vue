<script setup>
import { ref, watch, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

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

const paymentTypes = ['Tuition', 'Uniforms', 'Transport', 'Exam Fees'];
const newInvoice = ref({ student_id: '', term: '', total_amount: '' });
const newPayment = ref({ invoice_id: '', amount: '', payment_type: 'Tuition' });

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

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

// Payments are applied waterfall-style by the backend: oldest arrears first,
// the remainder to the current term.
const makePayment = async () => {
    if(!newPayment.value.invoice_id || !newPayment.value.amount) return;
    message.value = '';
    try {
        const res = await api.recordFeePayment({
            student_id: parseInt(newPayment.value.invoice_id),
            amount: parseFloat(newPayment.value.amount),
            payment_type: newPayment.value.payment_type,
            term: currentTerm.value,
            current_term: currentTerm.value
        });
        newPayment.value = { invoice_id: '', amount: '', payment_type: 'Tuition' };
        message.value = `Payment recorded — receipt ${res.data.receipt_number}.`;
        loadDashboard();
    } catch (e) {
        console.error("Failed to process payment", e);
        message.value = e.response?.data?.detail || 'Failed to process payment.';
    }
}

// Bona's smart payment flow: when a student and amount are picked, preview how
// the waterfall will split the payment (arrears first, remainder to this term).
const allocationPreview = ref(null);
const smartTerm = ref(null);

watch(() => newPayment.value.invoice_id, async (sid) => {
    allocationPreview.value = null;
    smartTerm.value = null;
    if (!sid) return;
    try {
        const res = await api.getSmartTerm(parseInt(sid), currentTerm.value);
        smartTerm.value = res.data;
    } catch (e) { console.error(e); }
    previewAllocation();
});

let previewTimer = null;
watch(() => newPayment.value.amount, () => {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(previewAllocation, 400);
});

const previewAllocation = async () => {
    allocationPreview.value = null;
    const sid = parseInt(newPayment.value.invoice_id);
    const amount = parseFloat(newPayment.value.amount);
    if (!sid || !(amount > 0)) return;
    try {
        const res = await api.getAllocationPreview(sid, amount, currentTerm.value);
        allocationPreview.value = res.data;
    } catch (e) { console.error(e); }
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

onMounted(() => {
    loadDashboard();
    loadStudents();
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

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <!-- Invoicing Actions -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Generate Invoice</h2>
            <form @submit.prevent="createInvoice" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Student</label>
                    <select v-model="newInvoice.student_id" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                        <option value="">Select student</option>
                        <option v-for="s in students" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }})</option>
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

        <!-- Payments Actions -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Record Payment</h2>
            <form @submit.prevent="makePayment" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Student</label>
                    <select v-model="newPayment.invoice_id" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                        <option value="">Select student</option>
                        <option v-for="s in students" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }})</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Payment Amount</label>
                        <input v-model="newPayment.amount" type="number" step="0.01" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Payment Type</label>
                        <select v-model="newPayment.payment_type" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option v-for="t in paymentTypes" :key="t">{{ t }}</option>
                        </select>
                    </div>
                </div>
                <div v-if="smartTerm && smartTerm.outstanding_balance > 0" class="text-xs text-gray-600 bg-gray-bg rounded-md p-2">
                    Oldest unpaid term: <span class="font-semibold text-navy">{{ smartTerm.recommended_term }}</span> —
                    outstanding <span class="font-semibold text-red-accent">{{ money(smartTerm.outstanding_balance) }}</span>
                </div>
                <div v-if="allocationPreview" class="text-xs text-gray-600 bg-gray-bg rounded-md p-2">
                    This payment will apply as:
                    <span v-for="(a, i) in allocationPreview.allocation" :key="i" class="ml-1 px-2 py-0.5 font-semibold rounded-full"
                          :class="a.kind === 'arrears' ? 'bg-yellow-100 text-yellow-800' : a.kind === 'advance' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'">
                        {{ a.term }}: {{ money(a.amount) }}
                    </span>
                </div>
                <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500">
                    Process Payment
                </button>
                <p class="text-xs text-gray-400">Payments clear oldest arrears first; the remainder goes to {{ currentTerm }}.</p>
            </form>
        </div>
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

    <!-- Payment log -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Payment Log</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Receipt</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type / Term</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th v-if="authStore.isAdmin" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
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
                    <td v-if="authStore.isAdmin" class="px-6 py-3 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="p.status === 'active'" @click="deletePayment(p)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="paymentLog.length === 0">
                    <td :colspan="authStore.isAdmin ? 7 : 6" class="px-6 py-8 text-center text-gray-500 text-sm">No payments recorded yet.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
