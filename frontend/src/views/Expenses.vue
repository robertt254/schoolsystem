<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const expenses = ref([]);
const pettyCash = ref([]);
const message = ref('');

const newExpense = ref({ amount: '', category: '', justification: '' });
const newTx = ref({ transaction_type: 'OUT', amount: '', description: '', category: '' });

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

const pettyBalance = computed(() => pettyCash.value.length ? pettyCash.value[0].running_balance : 0);
const totalExpenses = computed(() => expenses.value.reduce((s, e) => s + Number(e.amount || 0), 0));

const load = async () => {
    try {
        const res = await api.getExpenses();
        expenses.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getPettyCash();
        pettyCash.value = res.data;
    } catch (e) { console.error(e); }
};

const addExpense = async () => {
    const f = newExpense.value;
    if (!f.amount || !f.justification) return;
    message.value = '';
    try {
        await api.createExpense({
            amount: parseFloat(f.amount),
            category: f.category || null,
            justification: f.justification
        });
        newExpense.value = { amount: '', category: '', justification: '' };
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to record expense.';
    }
};

const addTx = async () => {
    const f = newTx.value;
    if (!f.amount || !f.description) return;
    message.value = '';
    try {
        await api.createPettyCash({
            transaction_type: f.transaction_type,
            amount: parseFloat(f.amount),
            description: f.description,
            category: f.category || null
        });
        newTx.value = { transaction_type: 'OUT', amount: '', description: '', category: '' };
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to record transaction.';
    }
};

const removeTx = async (tx) => {
    if (!window.confirm('Delete this petty cash transaction?')) return;
    try {
        await api.deletePettyCash(tx.id);
        load();
    } catch (e) { console.error(e); }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Expenses & Petty Cash</h1>
    </div>
    <p v-if="message" class="text-sm font-medium text-red-accent">{{ message }}</p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Expenses Recorded</h3>
            <p class="text-3xl font-bold text-red-accent">{{ money(totalExpenses) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Petty Cash Balance</h3>
            <p class="text-3xl font-bold" :class="pettyBalance >= 0 ? 'text-green-600' : 'text-red-accent'">{{ money(pettyBalance) }}</p>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Record expense -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Record Expense</h2>
            <form @submit.prevent="addExpense" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Amount</label>
                        <input v-model="newExpense.amount" type="number" step="0.01" min="0" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Category</label>
                        <input v-model="newExpense.category" type="text" placeholder="e.g. Utilities" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Justification</label>
                    <input v-model="newExpense.justification" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                </div>
                <button type="submit" class="w-full py-2 px-4 rounded-md shadow-sm text-sm font-medium text-white bg-navy hover:bg-navy-light">Record Expense</button>
                <p class="text-xs text-gray-400">Only the principal or system admin can record expenses.</p>
            </form>
        </div>

        <!-- Petty cash transaction -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Petty Cash Transaction</h2>
            <form @submit.prevent="addTx" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Type</label>
                        <select v-model="newTx.transaction_type" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option value="IN">IN — top-up</option>
                            <option value="OUT">OUT — expenditure</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Amount</label>
                        <input v-model="newTx.amount" type="number" step="0.01" min="0" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Description</label>
                        <input v-model="newTx.description" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Category</label>
                        <input v-model="newTx.category" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <button type="submit" class="w-full py-2 px-4 rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700">Record Transaction</button>
            </form>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Expense list -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Expense Ledger</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="e in expenses" :key="e.id" class="hover:bg-gray-50">
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ dateFmt(e.expense_date) }}</td>
                        <td class="px-6 py-3 text-sm">
                            <p class="font-medium text-gray-900">{{ e.justification }}</p>
                            <p class="text-xs text-gray-500">{{ e.category || 'Uncategorised' }} · by {{ e.recorded_by }}</p>
                        </td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold text-red-accent">{{ money(e.amount) }}</td>
                    </tr>
                    <tr v-if="expenses.length === 0">
                        <td colspan="3" class="px-6 py-8 text-center text-gray-500 text-sm">No expenses recorded.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Petty cash ledger -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Petty Cash Ledger</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Balance</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider"></th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="t in pettyCash" :key="t.id" class="hover:bg-gray-50">
                        <td class="px-6 py-3 text-sm">
                            <p class="font-medium text-gray-900">{{ t.description }}</p>
                            <p class="text-xs text-gray-500">{{ dateFmt(t.transaction_date) }} · {{ t.recorded_by }}</p>
                        </td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold"
                            :class="t.transaction_type === 'IN' ? 'text-green-600' : 'text-red-accent'">
                            {{ t.transaction_type === 'IN' ? '+' : '−' }} {{ money(t.amount) }}
                        </td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(t.running_balance) }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-right text-sm">
                            <button v-if="authStore.canFinance" @click="removeTx(t)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                        </td>
                    </tr>
                    <tr v-if="pettyCash.length === 0">
                        <td colspan="4" class="px-6 py-8 text-center text-gray-500 text-sm">No petty cash transactions.</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
  </div>
</template>
