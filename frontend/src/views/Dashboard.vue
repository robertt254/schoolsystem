<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const stats = ref({
  total_students: 0,
  total_staff: 0,
  total_revenue: 0,
  today_attendance_pct: null,
  term_collected: 0,
  term_expected: 0,
  term_pct: 0,
  defaulters_count: 0,
  recent_activity: []
});
const gradeStats = ref([]);
const currentTerm = ref('Term 1');

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const timeAgo = (iso) => {
  if (!iso) return '';
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

const maxGradeCount = ref(1);

const load = async () => {
  try {
    const termRes = await api.getCurrentTerm();
    currentTerm.value = termRes.data.term;
  } catch (e) { console.error(e); }
  try {
    const res = await api.getDashboardStats(currentTerm.value);
    stats.value = res.data;
  } catch (e) { console.error(e); }
  try {
    const res = await api.getGradeStats();
    gradeStats.value = res.data;
    maxGradeCount.value = Math.max(1, ...res.data.map(g => g.count));
  } catch (e) { console.error(e); }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-3xl font-bold text-navy">Bona School Kenya — Dashboard</h1>
        <p class="text-gray-700 mt-1">Welcome to the Bona School management system.</p>
      </div>
      <span class="px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800">{{ currentTerm }}</span>
    </div>

    <!-- Stat Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Students</h3>
        <p class="text-3xl font-bold text-navy">{{ stats.total_students }}</p>
        <router-link to="/students" class="text-sm text-blue-500 hover:underline">View Students</router-link>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Staff</h3>
        <p class="text-3xl font-bold text-navy">{{ stats.total_staff }}</p>
        <router-link to="/teachers" class="text-sm text-blue-500 hover:underline">View Staff</router-link>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Net Revenue</h3>
        <p class="text-3xl font-bold" :class="stats.total_revenue >= 0 ? 'text-green-600' : 'text-red-accent'">{{ money(stats.total_revenue) }}</p>
        <router-link to="/finance" class="text-sm text-blue-500 hover:underline">Finance</router-link>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Attendance Today</h3>
        <p class="text-3xl font-bold text-navy">{{ stats.today_attendance_pct === null ? '—' : stats.today_attendance_pct + '%' }}</p>
        <router-link to="/attendance" class="text-sm text-blue-500 hover:underline">Mark Attendance</router-link>
      </div>
    </div>

    <!-- Term collection + defaulters -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="flex justify-between items-center mb-2">
          <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider">{{ currentTerm }} Fee Collection</h3>
          <span class="text-sm font-semibold text-navy">{{ stats.term_pct }}%</span>
        </div>
        <div class="w-full bg-gray-bg rounded-full h-3 mb-3">
          <div class="bg-navy h-3 rounded-full transition-all" :style="{ width: Math.min(stats.term_pct, 100) + '%' }"></div>
        </div>
        <p class="text-sm text-gray-600">
          Collected <span class="font-bold text-green-600">{{ money(stats.term_collected) }}</span>
          of <span class="font-bold text-navy">{{ money(stats.term_expected) }}</span> expected.
        </p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
        <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Fee Defaulters</h3>
        <p class="text-3xl font-bold text-red-accent">{{ stats.defaulters_count }}</p>
        <router-link to="/defaulters" class="text-sm text-blue-500 hover:underline">View Defaulters</router-link>
        <div class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Enrollment by grade -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Enrollment by Grade</h2>
        <div class="space-y-2">
          <div v-for="g in gradeStats" :key="g.grade" class="flex items-center gap-3">
            <span class="w-24 text-sm text-gray-700 flex-shrink-0">{{ g.grade }}</span>
            <div class="flex-1 bg-gray-bg rounded-full h-4">
              <div class="bg-navy h-4 rounded-full" :style="{ width: (g.count / maxGradeCount * 100) + '%' }"></div>
            </div>
            <span class="w-8 text-sm font-semibold text-navy text-right">{{ g.count }}</span>
          </div>
          <p v-if="gradeStats.every(g => g.count === 0)" class="text-sm text-gray-500 italic">No students enrolled yet.</p>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Recent Activity</h2>
        <ul v-if="stats.recent_activity.length" class="divide-y divide-gray-200 max-h-80 overflow-y-auto">
          <li v-for="a in stats.recent_activity" :key="a.id" class="py-2 text-sm flex justify-between items-center">
            <div>
              <span class="font-semibold text-gray-900">{{ a.user_name }}</span>
              <span class="text-gray-600"> {{ a.description }}</span>
            </div>
            <span class="text-xs text-gray-400 whitespace-nowrap ml-3">{{ timeAgo(a.timestamp) }}</span>
          </li>
        </ul>
        <p v-else class="text-sm text-gray-500 italic">No activity recorded yet.</p>
      </div>
    </div>
  </div>
</template>
