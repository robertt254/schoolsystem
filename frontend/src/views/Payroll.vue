<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const month = ref(new Date().toISOString().slice(0, 7));  // YYYY-MM
const preview = ref([]);
const history = ref([]);
const message = ref('');
const running = ref(false);
const payslip = ref(null);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;

const unpaid = computed(() => preview.value.filter(p => !p.already_paid && p.basic_salary > 0));
const totalNet = computed(() => unpaid.value.reduce((s, p) =>
    s + Math.max(0, p.basic_salary + (parseFloat(p.allowances) || 0) - (parseFloat(p.deductions) || 0)), 0));

const load = async () => {
    message.value = '';
    try {
        const res = await api.getMonthlyPayroll(month.value);
        preview.value = res.data.preview;
        history.value = res.data.history;
    } catch (e) {
        console.error(e);
        message.value = e.response?.data?.detail || 'Failed to load payroll.';
    }
};

const runPayroll = async () => {
    if (!unpaid.value.length) return;
    if (!window.confirm(`Run payroll for ${unpaid.value.length} staff (${money(totalNet.value)}) for ${month.value}?`)) return;
    running.value = true;
    message.value = '';
    try {
        const res = await api.runMonthPayroll(month.value, unpaid.value.map(p => ({
            staff_id: p.staff_id,
            allowances: parseFloat(p.allowances) || 0,
            deductions: parseFloat(p.deductions) || 0
        })));
        message.value = `Paid ${res.data.created} staff` + (res.data.skipped ? `, skipped ${res.data.skipped} (no salary set or already paid)` : '') + '.';
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Payroll run failed.';
    }
    running.value = false;
};

const openPayslip = async (id) => {
    try {
        const res = await api.getPayslip(id);
        payslip.value = res.data;
    } catch (e) { console.error(e); }
};

// System-admin only: undo an erroneous payroll run for the month
const voidMonth = async () => {
    if (!window.confirm(`VOID the entire ${month.value} payroll run? All ${history.value.length} payslip(s) will be deleted. This is audited.`)) return;
    try {
        await api.voidPayrollMonth(month.value);
        message.value = `Payroll for ${month.value} voided.`;
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to void payroll.';
    }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8 relative">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Payroll & Payslips</h1>
        <div class="flex gap-4 items-center">
            <input v-model="month" @change="load" type="month" class="border border-gray-300 p-2 rounded-md focus:ring-navy focus:border-navy" />
            <button @click="runPayroll" :disabled="running || unpaid.length === 0" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">
                {{ running ? 'Running…' : `Run Payroll (${unpaid.length})` }}
            </button>
        </div>
    </div>
    <p v-if="message" class="text-sm font-medium" :class="message.includes('failed') || message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Preview -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Salary Preview · {{ month }}</h2>
            <span class="text-sm text-gray-500">Pending total: <span class="font-bold text-navy">{{ money(totalNet) }}</span></span>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Staff</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Basic</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Allowances</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Deductions</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Net Pay</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="p in preview" :key="p.staff_id" class="hover:bg-gray-50" :class="p.already_paid ? 'opacity-60' : ''">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <p class="text-sm font-medium text-gray-900">{{ p.staff_name }}</p>
                        <p class="text-xs text-gray-500">{{ p.job_title || p.role }}</p>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(p.basic_salary) }}</td>
                    <td class="px-6 py-2 text-right">
                        <input v-model="p.allowances" :disabled="p.already_paid" type="number" min="0"
                               class="border border-gray-300 p-1.5 rounded-md w-24 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
                    </td>
                    <td class="px-6 py-2 text-right">
                        <input v-model="p.deductions" :disabled="p.already_paid" type="number" min="0"
                               class="border border-gray-300 p-1.5 rounded-md w-24 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">
                        {{ money(Math.max(0, p.basic_salary + (parseFloat(p.allowances) || 0) - (parseFloat(p.deductions) || 0))) }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="p.already_paid ? 'bg-green-100 text-green-800' : p.basic_salary > 0 ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'">
                            {{ p.already_paid ? 'Paid' : p.basic_salary > 0 ? 'Pending' : 'No salary set' }}
                        </span>
                    </td>
                </tr>
                <tr v-if="preview.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No staff records found.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- History -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Payslips · {{ month }}</h2>
            <button v-if="authStore.isSystemAdmin && history.length" @click="voidMonth" class="text-red-accent hover:text-red-hover text-sm font-bold underline">Void Month</button>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Staff</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Net Pay</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recorded By</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="h in history" :key="h.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ h.staff_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ money(h.net_pay) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ h.recorded_by }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button @click="openPayslip(h.id)" class="text-navy hover:text-navy-light font-bold underline">Payslip</button>
                    </td>
                </tr>
                <tr v-if="history.length === 0">
                    <td colspan="4" class="px-6 py-8 text-center text-gray-500 text-sm">No payroll run for this month yet.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Payslip Modal -->
    <div v-if="payslip" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-8">
            <div class="flex justify-between items-center mb-6 border-b pb-3">
                <h3 class="text-2xl font-bold text-navy">Payslip · {{ payslip.payment_month }}</h3>
                <button @click="payslip = null" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
            </div>
            <div class="space-y-2 text-sm">
                <p class="text-lg font-bold text-gray-900">{{ payslip.staff_name }}</p>
                <p class="text-gray-500">{{ payslip.job_title || '' }}</p>
                <div class="grid grid-cols-2 gap-2 border-t pt-3 mt-3">
                    <span class="text-gray-500">Basic Salary</span><span class="text-right font-semibold">{{ money(payslip.basic_salary) }}</span>
                    <span class="text-gray-500">Allowances</span><span class="text-right font-semibold text-green-600">+ {{ money(payslip.allowances) }}</span>
                    <span class="text-gray-500">Deductions</span><span class="text-right font-semibold text-red-accent">− {{ money(payslip.deductions) }}</span>
                    <span class="text-navy font-bold border-t pt-2">Net Pay</span><span class="text-right font-bold text-navy border-t pt-2">{{ money(payslip.net_pay) }}</span>
                </div>
                <div class="grid grid-cols-2 gap-2 border-t pt-3 mt-3 text-xs text-gray-500">
                    <span>KRA PIN: {{ payslip.kra_pin || '—' }}</span>
                    <span>NSSF: {{ payslip.nssf_number || '—' }}</span>
                    <span>NHIF: {{ payslip.nhif_number || '—' }}</span>
                    <span>By: {{ payslip.recorded_by }}</span>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>
