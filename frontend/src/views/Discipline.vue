<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const records = ref([]);
const students = ref([]);
const filterStatus = ref('');
const newRecord = ref({
    student_id: '',
    incident_date: new Date().toISOString().slice(0, 10),
    incident_type: '',
    description: '',
    action_taken: '',
    severity: 'Minor'
});

const load = async () => {
    try {
        const params = {};
        if (filterStatus.value) params.status = filterStatus.value;
        const res = await api.getDisciplineRecords(params);
        records.value = res.data;
    } catch (e) { console.error(e); }
};

const loadStudents = async () => {
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
};

const addRecord = async () => {
    if (!newRecord.value.student_id || !newRecord.value.incident_type || !newRecord.value.description) return;
    try {
        await api.createDisciplineRecord({
            student_id: parseInt(newRecord.value.student_id),
            incident_date: newRecord.value.incident_date,
            incident_type: newRecord.value.incident_type,
            description: newRecord.value.description,
            action_taken: newRecord.value.action_taken || null,
            severity: newRecord.value.severity
        });
        newRecord.value = { student_id: '', incident_date: new Date().toISOString().slice(0, 10), incident_type: '', description: '', action_taken: '', severity: 'Minor' };
        load();
    } catch (e) { console.error(e); }
};

const resolveRecord = async (record) => {
    try {
        await api.updateDisciplineRecord(record.id, { status: 'Resolved', action_date: new Date().toISOString().slice(0, 10) });
        load();
    } catch (e) { console.error(e); }
};

onMounted(() => {
    load();
    loadStudents();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Discipline</h1>
        <select v-model="filterStatus" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
            <option value="">All Records</option>
            <option value="Open">Open</option>
            <option value="Resolved">Resolved</option>
        </select>
    </div>

    <!-- Record incident — accountant has read-only access -->
    <div v-if="authStore.canDiscipline" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Record Incident</h2>
        <form @submit.prevent="addRecord" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Student</label>
                <select v-model="newRecord.student_id" required class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="">Select student</option>
                    <option v-for="s in students" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.grade_level }})</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Date</label>
                <input v-model="newRecord.incident_date" type="date" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Incident Type</label>
                <input v-model="newRecord.incident_type" type="text" placeholder="e.g. Fighting, Lateness" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select v-model="newRecord.severity" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option>Minor</option>
                    <option>Moderate</option>
                    <option>Serious</option>
                </select>
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input v-model="newRecord.description" type="text" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">Action Taken (optional)</label>
                <input v-model="newRecord.action_taken" type="text" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div class="md:col-span-4">
                <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light w-full md:w-auto">Save Record</button>
            </div>
        </form>
    </div>

    <!-- Records -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Incident</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in records" :key="r.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ r.incident_date }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">
                        {{ r.student_name }}
                        <span class="ml-1 px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ r.grade_level }}</span>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-900">
                        <p class="font-semibold">{{ r.incident_type }}</p>
                        <p class="text-xs text-gray-500">{{ r.description }}</p>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="{ 'bg-yellow-100 text-yellow-800': r.severity === 'Minor', 'bg-orange-100 text-orange-800': r.severity === 'Moderate', 'bg-red-100 text-red-800': r.severity === 'Serious' }">
                            {{ r.severity }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="r.status === 'Open' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'">
                            {{ r.status }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="r.status === 'Open' && authStore.canDiscipline" @click="resolveRecord(r)" class="text-navy hover:text-navy-light font-bold underline">Resolve</button>
                    </td>
                </tr>
                <tr v-if="records.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No disciplinary records.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
