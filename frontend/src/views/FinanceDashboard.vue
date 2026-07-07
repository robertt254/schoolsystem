<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const dashboardStats = ref({
    total_expected: 0,
    total_collected: 0,
    outstanding_balance: 0
});

const invoices = ref([]);
const newInvoice = ref({ student_id: '', term: '', total_amount: '' });
const newPayment = ref({ invoice_id: '', amount: '' });

const loadDashboard = async () => {
    try {
        const statsRes = await api.getFinanceDashboard();
        dashboardStats.value = statsRes.data;
    } catch (e) {
        console.error("Failed to load dashboard stats", e);
    }
};

const createInvoice = async () => {
    if(!newInvoice.value.student_id || !newInvoice.value.term || !newInvoice.value.total_amount) return;
    try {
        await api.createInvoice({
            student_id: parseInt(newInvoice.value.student_id),
            term: parseInt(newInvoice.value.term),
            total_amount: parseFloat(newInvoice.value.total_amount)
        });
        newInvoice.value = { student_id: '', term: '', total_amount: '' };
        loadDashboard();
    } catch (e) {
        console.error("Failed to create invoice", e);
    }
};

const makePayment = async () => {
    if(!newPayment.value.invoice_id || !newPayment.value.amount) return;
    try {
        await api.processPayment({
            invoice_id: parseInt(newPayment.value.invoice_id),
            amount: parseFloat(newPayment.value.amount)
        });
        newPayment.value = { invoice_id: '', amount: '' };
        loadDashboard();
    } catch (e) {
        console.error("Failed to process payment", e);
    }
}

onMounted(() => {
    loadDashboard();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Finance Dashboard</h1>
    </div>

    <!-- Stats Row -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Expected</h3>
            <p class="text-3xl font-bold text-navy">${{ dashboardStats.total_expected.toFixed(2) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Collected</h3>
            <p class="text-3xl font-bold text-green-600">${{ dashboardStats.total_collected.toFixed(2) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Outstanding Balance</h3>
            <p class="text-3xl font-bold text-red-accent">${{ dashboardStats.outstanding_balance.toFixed(2) }}</p>
            <div class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <!-- Invoicing Actions -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Generate Invoice</h2>
            <form @submit.prevent="createInvoice" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Student ID</label>
                    <input v-model="newInvoice.student_id" type="number" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
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
                    <label class="block text-sm font-medium text-gray-700">Invoice ID</label>
                    <input v-model="newPayment.invoice_id" type="number" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Payment Amount</label>
                    <input v-model="newPayment.amount" type="number" step="0.01" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm">
                </div>
                <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500">
                    Process Payment
                </button>
            </form>
        </div>
    </div>
  </div>
</template>
