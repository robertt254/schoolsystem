<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const budgets = ref([]);
const year = ref(new Date().getFullYear());
const message = ref('');
const terms = ["Term 1", "Term 2", "Term 3"];
const newBudget = ref({ category: '', term: 'Term 1', budgeted_amount: '' });

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;

const load = async () => {
    try {
        const res = await api.getBudgets({ academic_year: parseInt(year.value) });
        budgets.value = res.data;
    } catch (e) { console.error(e); }
};

const addBudget = async () => {
    const f = newBudget.value;
    if (!f.category || !f.budgeted_amount) return;
    message.value = '';
    try {
        await api.createBudget({
            category: f.category,
            academic_year: parseInt(year.value),
            term: f.term,
            budgeted_amount: parseFloat(f.budgeted_amount)
        });
        newBudget.value = { category: '', term: 'Term 1', budgeted_amount: '' };
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to create budget line.';
    }
};

const removeBudget = async (b) => {
    if (!window.confirm(`Delete budget line "${b.category}" (${b.term})?`)) return;
    try {
        await api.deleteBudget(b.id);
        load();
    } catch (e) { console.error(e); }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Budgets</h1>
        <input v-model="year" @change="load" type="number" class="border border-gray-300 p-2 rounded-md w-28 focus:ring-navy focus:border-navy" />
    </div>
    <p v-if="message" class="text-sm font-medium text-red-accent">{{ message }}</p>

    <!-- New budget line -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Add Budget Line</h2>
        <form @submit.prevent="addBudget" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <input v-model="newBudget.category" type="text" placeholder="e.g. Utilities" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term</label>
                <select v-model="newBudget.term" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Budgeted Amount</label>
                <input v-model="newBudget.budgeted_amount" type="number" min="0" step="0.01" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Add Line</button>
        </form>
    </div>

    <!-- Budget vs actual -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Budget vs Actual · {{ year }}</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Term</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Budgeted</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actual Spent</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Variance</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="b in budgets" :key="b.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ b.category }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ b.term }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(b.budgeted_amount) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(b.actual_spent) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold"
                        :class="b.variance >= 0 ? 'text-green-600' : 'text-red-accent'">{{ money(b.variance) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="authStore.canFinance" @click="removeBudget(b)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="budgets.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No budget lines for {{ year }}.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
