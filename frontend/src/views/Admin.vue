<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';
import { exportCsv } from '../utils/csvExport';

const authStore = useAuthStore();
const logs = ref([]);
const logFilter = ref({ action: '', resource: '' });
const logsPageSize = 20;
const moreLogsAvailable = ref(false);
const exportDate = ref(new Date().toISOString().slice(0, 10));
const archived = ref([]);
const message = ref('');

// Promotion tool
const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];
const promoGrade = ref('Grade 1');
const promoTarget = ref('Grade 2');
const promoStudents = ref([]);
const selectedIds = ref([]);

// Reset tool
const resetConfirm = ref('');
const resetFinance = ref(false);

// Data backups (system admin only) — for migration to local hosting
const backups = ref([]);
const backupBusy = ref(false);
const fmtSize = (b) => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

const loadBackups = async () => {
    if (!authStore.isSystemAdmin) return;
    try {
        const res = await api.listBackups();
        backups.value = res.data;
    } catch (e) { console.error(e); }
};

const createBackup = async () => {
    backupBusy.value = true;
    try {
        await api.createBackup();
        await loadBackups();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Backup failed.');
    }
    backupBusy.value = false;
};

const downloadBackup = async (filename) => {
    try {
        const res = await api.downloadBackup(filename);
        const url = URL.createObjectURL(res.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Download failed.');
    }
};

const dateFmt = (iso) => iso ? new Date(iso).toLocaleString() : '—';

const _logParams = () => {
    const params = {};
    if (logFilter.value.action) params.action = logFilter.value.action;
    if (logFilter.value.resource) params.resource = logFilter.value.resource;
    return params;
};

const loadLogs = async () => {
    try {
        const res = await api.getAuditLogs({ ..._logParams(), limit: logsPageSize, offset: 0 });
        logs.value = res.data;
        moreLogsAvailable.value = res.data.length === logsPageSize;
    } catch (e) { console.error(e); }
};

const loadMoreLogs = async () => {
    try {
        const res = await api.getAuditLogs({ ..._logParams(), limit: logsPageSize, offset: logs.value.length });
        logs.value = [...logs.value, ...res.data];
        moreLogsAvailable.value = res.data.length === logsPageSize;
    } catch (e) { console.error(e); }
};

// Export one day's full audit trail as CSV
const exportDayLogs = async () => {
    try {
        const res = await api.getAuditLogs({
            date_from: exportDate.value, date_to: exportDate.value, limit: 500
        });
        if (!res.data.length) {
            window.alert(`No audit entries on ${exportDate.value}.`);
            return;
        }
        exportCsv(`audit_log_${exportDate.value}.csv`,
            [['timestamp', 'Time'], ['user_name', 'User'], ['action', 'Action'],
             ['resource', 'Resource'], ['resource_id', 'Record ID'], ['detail', 'Detail']],
            res.data);
    } catch (e) { console.error(e); }
};

const loadArchived = async () => {
    try {
        const res = await api.getArchivedStudents();
        archived.value = res.data;
    } catch (e) { console.error(e); }
};

const loadPromoStudents = async () => {
    selectedIds.value = [];
    try {
        const res = await api.getStudents({ grade: promoGrade.value });
        promoStudents.value = res.data;
    } catch (e) { console.error(e); }
};

const toggleAll = (ev) => {
    selectedIds.value = ev.target.checked ? promoStudents.value.map(s => s.id) : [];
};

const promote = async () => {
    if (!selectedIds.value.length) return;
    if (!window.confirm(`Promote ${selectedIds.value.length} student(s) from ${promoGrade.value} to ${promoTarget.value}?`)) return;
    message.value = '';
    try {
        const res = await api.promoteStudents(selectedIds.value, promoTarget.value);
        message.value = `Promoted ${res.data.promoted} student(s)` + (res.data.graduated ? `, graduated ${res.data.graduated}` : '') + '.';
        loadPromoStudents();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Promotion failed.';
    }
};

const runYearTransition = async () => {
    if (!window.confirm('Run the END-OF-YEAR transition? EVERY active student moves up one grade and Grade 6 students graduate. This cannot be undone.')) return;
    message.value = '';
    try {
        const res = await api.yearTransition();
        message.value = `Year transition complete — ${res.data.promoted} promoted, ${res.data.graduated} graduated.`;
        loadPromoStudents();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Year transition failed.';
    }
};

const restore = async (s) => {
    try {
        await api.restoreStudent(s.id);
        loadArchived();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to restore student.');
    }
};

const doReset = async () => {
    message.value = '';
    try {
        const res = await api.resetData(resetConfirm.value, resetFinance.value);
        const cleared = Object.entries(res.data.cleared || {}).map(([t, n]) => `${t}: ${n}`).join(', ');
        message.value = `Data reset complete. Cleared — ${cleared || 'nothing'}.`;
        resetConfirm.value = '';
        loadLogs();
        loadArchived();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Reset failed.';
    }
};

onMounted(() => {
    loadLogs();
    loadArchived();
    loadPromoStudents();
    loadBackups();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Administration</h1>
    </div>
    <p v-if="message" class="text-sm font-medium" :class="message.includes('failed') || message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Promotion -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="flex justify-between items-center mb-4 border-b pb-2">
            <h2 class="text-xl font-bold text-navy">Student Promotion</h2>
            <button @click="runYearTransition" class="bg-red-accent text-white px-4 py-2 rounded-md hover:bg-red-hover">Run Year Transition (all grades)</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end mb-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">From Grade</label>
                <select v-model="promoGrade" @change="loadPromoStudents" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">To Grade</label>
                <select v-model="promoTarget" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                </select>
            </div>
            <button @click="promote" :disabled="selectedIds.length === 0" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">
                Promote Selected ({{ selectedIds.length }})
            </button>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left"><input type="checkbox" @change="toggleAll" class="h-4 w-4 rounded border-gray-300 text-navy focus:ring-navy" /></th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="s in promoStudents" :key="s.id" class="hover:bg-gray-50">
                    <td class="px-6 py-3"><input type="checkbox" v-model="selectedIds" :value="s.id" class="h-4 w-4 rounded border-gray-300 text-navy focus:ring-navy" /></td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ s.admission_number }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-900">{{ s.first_name }} {{ s.last_name }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ s.status }}</td>
                </tr>
                <tr v-if="promoStudents.length === 0">
                    <td colspan="4" class="px-6 py-6 text-center text-gray-500 text-sm">No students in {{ promoGrade }}.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Archived students -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Archived Students</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="s in archived" :key="s.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ s.admission_number }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ s.first_name }} {{ s.last_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ s.grade_level }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button @click="restore(s)" class="text-navy hover:text-navy-light font-bold underline">Restore</button>
                    </td>
                </tr>
                <tr v-if="archived.length === 0">
                    <td colspan="4" class="px-6 py-6 text-center text-gray-500 text-sm">No archived students.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Audit log -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex flex-col md:flex-row justify-between md:items-center gap-4 p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Audit Log</h2>
            <div class="flex flex-wrap gap-3 items-center">
                <select v-model="logFilter.action" @change="loadLogs" class="border border-gray-300 p-2 rounded-md bg-white text-sm focus:ring-navy focus:border-navy">
                    <option value="">All actions</option>
                    <option>CREATE</option>
                    <option>UPDATE</option>
                    <option>DELETE</option>
                </select>
                <input v-model="logFilter.resource" @keyup.enter="loadLogs" type="text" placeholder="Resource e.g. fee, student" class="border border-gray-300 p-2 rounded-md text-sm focus:ring-navy focus:border-navy" />
                <button @click="loadLogs" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Filter</button>
                <span class="border-l border-gray-200 pl-3 flex gap-2 items-center">
                    <input v-model="exportDate" type="date" class="border border-gray-300 p-2 rounded-md text-sm focus:ring-navy focus:border-navy" />
                    <button @click="exportDayLogs" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Export Day CSV</button>
                </span>
            </div>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Detail</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="l in logs" :key="l.id" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ dateFmt(l.timestamp) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{{ l.user_name }}</td>
                    <td class="px-6 py-3 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="{ 'bg-green-100 text-green-800': l.action === 'CREATE', 'bg-blue-100 text-blue-800': l.action === 'UPDATE', 'bg-red-100 text-red-800': l.action === 'DELETE' }">
                            {{ l.action }}
                        </span>
                    </td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ l.resource }} <span class="text-gray-400">#{{ l.resource_id || '' }}</span></td>
                    <td class="px-6 py-3 text-sm text-gray-500 max-w-md truncate">{{ l.detail }}</td>
                </tr>
                <tr v-if="logs.length === 0">
                    <td colspan="5" class="px-6 py-6 text-center text-gray-500 text-sm">No audit entries.</td>
                </tr>
            </tbody>
        </table>
        <div v-if="moreLogsAvailable" class="p-4 text-center border-t">
            <button @click="loadMoreLogs" class="text-navy hover:text-navy-light font-bold underline text-sm">Show 20 more</button>
        </div>
    </div>

    <!-- Data backups -->
    <div v-if="authStore.isSystemAdmin" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="flex justify-between items-center mb-4 border-b pb-2">
            <h2 class="text-xl font-bold text-navy">Data Backups</h2>
            <button @click="createBackup" :disabled="backupBusy" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">
                {{ backupBusy ? 'Backing up…' : 'Create Backup Now' }}
            </button>
        </div>
        <p class="text-sm text-gray-600 mb-4">
            Full snapshots of every record, taken automatically every 24 hours (last 7 kept).
            Download a snapshot and restore it into a local database with
            <span class="font-mono text-xs bg-gray-bg px-1 rounded">python restore_backup.py &lt;file&gt; --wipe</span>
            when moving the system in-house. Only the system administrator can access these.
        </p>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Snapshot</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="b in backups" :key="b.filename" class="hover:bg-gray-50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ b.filename }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ new Date(b.created_at).toLocaleString() }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ fmtSize(b.size_bytes) }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-right text-sm font-medium">
                        <button @click="downloadBackup(b.filename)" class="text-navy hover:text-navy-light font-bold underline">Download</button>
                    </td>
                </tr>
                <tr v-if="backups.length === 0">
                    <td colspan="4" class="px-6 py-6 text-center text-gray-500 text-sm">No snapshots yet — click "Create Backup Now".</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Danger zone -->
    <div v-if="authStore.isSystemAdmin" class="bg-white rounded-xl shadow-sm border border-red-accent p-6 relative overflow-hidden">
        <h2 class="text-xl font-bold text-red-accent mb-2">Danger Zone — Reset Operational Data</h2>
        <p class="text-sm text-gray-600 mb-4">Wipes students, fees, assessments, attendance, exams, discipline, borrows and audit logs. Logins, fee structure, term dates, subjects, library catalogue, events and budgets are kept. Type <span class="font-bold">RESET</span> to confirm.</p>
        <div class="flex flex-col md:flex-row gap-4 items-start md:items-center">
            <input v-model="resetConfirm" type="text" placeholder="Type RESET" class="border border-gray-300 p-2 rounded-md focus:ring-red-accent focus:border-red-accent" />
            <label class="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" v-model="resetFinance" class="h-4 w-4 rounded border-gray-300 text-red-accent focus:ring-red-accent" />
                Also clear payroll, expenses & petty cash
            </label>
            <button @click="doReset" :disabled="resetConfirm.trim().toUpperCase() !== 'RESET'" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">Reset Data</button>
        </div>
        <div class="absolute right-0 top-0 h-1 bg-red-accent w-full"></div>
    </div>
  </div>
</template>
