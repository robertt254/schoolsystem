<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const year = ref(new Date().getFullYear());
const rows = ref([]);          // saved entries for the selected year (editable amounts)
const message = ref('');
const saving = ref(false);

const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];
const terms = ["Term 1", "Term 2", "Term 3"];

const newEntry = ref({ grade_level: 'Grade 1', term: 'Term 1', fee_type: 'Tuition', amount: '' });

const tuitionRows = computed(() => rows.value.filter(r => r.grade_level !== 'General'));
const generalRows = computed(() => rows.value.filter(r => r.grade_level === 'General'));

const tuitionFor = (grade, term) =>
    tuitionRows.value.find(r => r.grade_level === grade && r.term === term && r.fee_type === 'Tuition');

const load = async () => {
    message.value = '';
    try {
        const res = await api.getFeeStructure();
        rows.value = res.data.filter(r => r.academic_year === parseInt(year.value));
    } catch (e) { console.error(e); }
};

const loadTemplate = async () => {
    message.value = '';
    try {
        const res = await api.getFeeStructureTemplate(parseInt(year.value));
        // Merge: keep saved amounts where they exist, add template rows otherwise
        const existing = new Set(rows.value.map(r => `${r.grade_level}|${r.term}|${r.fee_type}`));
        const additions = res.data
            .filter(t => !existing.has(`${t.grade_level}|${t.term}|${t.fee_type}`))
            .map(t => ({ ...t, id: null }));
        rows.value = [...rows.value, ...additions];
        message.value = 'Template loaded — review the amounts and press "Save Structure".';
    } catch (e) { console.error(e); }
};

const saveAll = async () => {
    saving.value = true;
    message.value = '';
    try {
        const res = await api.bulkSaveFeeStructure(rows.value.map(r => ({
            grade_level: r.grade_level,
            term: r.term,
            fee_type: r.fee_type,
            amount: parseFloat(r.amount) || 0,
            academic_year: parseInt(year.value)
        })));
        message.value = `Saved ${res.data.saved} fee structure entries for ${year.value}.`;
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to save structure.';
    }
    saving.value = false;
};

const addEntry = async () => {
    const e = newEntry.value;
    if (!e.fee_type || e.amount === '') return;
    try {
        await api.createFeeStructureEntry({
            grade_level: e.grade_level,
            term: e.term,
            fee_type: e.fee_type,
            amount: parseFloat(e.amount),
            academic_year: parseInt(year.value)
        });
        newEntry.value = { grade_level: 'Grade 1', term: 'Term 1', fee_type: 'Tuition', amount: '' };
        load();
    } catch (err) {
        message.value = err.response?.data?.detail || 'Failed to add entry.';
    }
};

const removeEntry = async (row) => {
    if (!row.id) {
        rows.value = rows.value.filter(r => r !== row);
        return;
    }
    if (!window.confirm(`Delete ${row.fee_type} for ${row.grade_level} ${row.term}?`)) return;
    try {
        await api.deleteFeeStructureEntry(row.id);
        load();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to delete entry.');
    }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Fee Structure</h1>
        <div class="flex gap-4 items-center">
            <input v-model="year" @change="load" type="number" class="border border-gray-300 p-2 rounded-md w-28 focus:ring-navy focus:border-navy" />
            <button v-if="authStore.isAdmin" @click="loadTemplate" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light">Load Template</button>
            <button v-if="authStore.isAdmin" @click="saveAll" :disabled="saving || rows.length === 0" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">
                {{ saving ? 'Saving…' : 'Save Structure' }}
            </button>
        </div>
    </div>
    <p v-if="message" class="text-sm font-medium" :class="message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Termly tuition grid -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Termly Tuition · {{ year }}</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                    <th v-for="t in terms" :key="t" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{{ t }}</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="g in grades" :key="g" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ g }}</td>
                    <td v-for="t in terms" :key="t" class="px-6 py-2 text-right">
                        <input v-if="tuitionFor(g, t)" v-model="tuitionFor(g, t).amount" :disabled="!authStore.isAdmin" type="number" min="0"
                               class="border border-gray-300 p-1.5 rounded-md w-28 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
                        <span v-else class="text-gray-300 text-sm">—</span>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Other fee items -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Other Fees & Optional Activities</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                    <th v-if="authStore.isAdmin" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in generalRows" :key="r.fee_type + r.term" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{{ r.fee_type }}</td>
                    <td class="px-6 py-3 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ r.term }}</span>
                    </td>
                    <td class="px-6 py-2 text-right">
                        <input v-model="r.amount" :disabled="!authStore.isAdmin" type="number" min="0"
                               class="border border-gray-300 p-1.5 rounded-md w-28 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg" />
                    </td>
                    <td v-if="authStore.isAdmin" class="px-6 py-3 whitespace-nowrap text-right text-sm font-medium">
                        <button @click="removeEntry(r)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="generalRows.length === 0">
                    <td :colspan="authStore.isAdmin ? 4 : 3" class="px-6 py-6 text-center text-gray-500 text-sm">No general fee items for {{ year }} — load the template to start.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Add custom entry -->
    <div v-if="authStore.isAdmin" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Add Fee Item</h2>
        <form @submit.prevent="addEntry" class="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Grade</label>
                <select v-model="newEntry.grade_level" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                    <option value="General">General (all grades)</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term / Category</label>
                <select v-model="newEntry.term" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                    <option value="Once">Once (e.g. Admission)</option>
                    <option value="Termly">Termly item</option>
                    <option value="Daily">Daily</option>
                    <option value="Optional">Optional activity</option>
                    <option value="Transport">Transport</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Fee Type</label>
                <input v-model="newEntry.fee_type" type="text" placeholder="e.g. Tuition, Swimming" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Amount</label>
                <input v-model="newEntry.amount" type="number" min="0" step="0.01" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Add Item</button>
        </form>
    </div>
  </div>
</template>
