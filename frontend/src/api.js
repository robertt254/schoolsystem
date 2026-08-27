import axios from 'axios';

// Empty string = relative URLs, used in production builds where the SPA is
// served by the FastAPI backend on the same origin (single Render service).
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Any 401 means the token is expired or invalid: end the session immediately
// so a stale login can never keep the UI open for someone else.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user_info');
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        sessionStorage.setItem('logout_reason', 'Your session expired — please sign in again.');
        window.location.assign('/login');
      }
    }
    return Promise.reject(error);
  }
);

export default {
  // ── Auth ──────────────────────────────────────────────────────────────────
  login(data) {
    return axios.post(`${API_URL}/api/auth/login`, data, {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    });
  },
  changePassword(data) {
    return api.post('/api/auth/change-password', data);
  },

  // ── Students ──────────────────────────────────────────────────────────────
  getStudents(params = {}) {
    return api.get('/api/students/', { params });
  },
  createStudent(student) {
    return api.post('/api/students/', student);
  },
  bulkImportStudents(students) {
    return api.post('/api/students/bulk', students);
  },
  updateStudent(studentId, data) {
    return api.put(`/api/students/${studentId}`, data);
  },
  archiveStudent(studentId) {
    return api.delete(`/api/students/${studentId}`);
  },
  restoreStudent(studentId) {
    return api.post(`/api/students/${studentId}/restore`);
  },
  getArchivedStudents() {
    return api.get('/api/students/archived');
  },
  getStudentProfile(studentId) {
    return api.get(`/api/students/${studentId}/profile`);
  },
  getClassesSummary() {
    return api.get('/api/students/classes/summary');
  },
  getClassRoster(grade) {
    return api.get(`/api/students/classes/${encodeURIComponent(grade)}`);
  },
  promoteStudents(studentIds, toGrade) {
    return api.post('/api/students/promote', { student_ids: studentIds, to_grade: toGrade });
  },
  yearTransition() {
    return api.post('/api/students/year-transition');
  },
  getEnrollmentSummary() {
    return api.get('/api/students/enrollment-summary');
  },

  // ── Staff (teachers and other employees) ──────────────────────────────────
  getStaff() {
    return api.get('/api/staff/');
  },
  createStaff(staff) {
    return api.post('/api/staff/', staff);
  },
  updateStaff(userId, data) {
    return api.put(`/api/staff/${userId}`, data);
  },
  terminateStaff(userId) {
    return api.delete(`/api/staff/${userId}`);
  },
  resetStaffPassword(userId, newPassword) {
    return api.post(`/api/staff/${userId}/reset-password`, { new_password: newPassword });
  },
  getAuditLogs(params = {}) {
    return api.get('/api/staff/audit-logs', { params });
  },

  // ── Subjects (learning areas — shown as "Courses" in the UI) ──────────────
  getSubjects(params = {}) {
    return api.get('/api/subjects/', { params });
  },
  createSubject(subject) {
    return api.post('/api/subjects/', subject);
  },
  updateSubject(subjectId, data) {
    return api.put(`/api/subjects/${subjectId}`, data);
  },
  deleteSubject(subjectId) {
    return api.delete(`/api/subjects/${subjectId}`);
  },
  seedSubjects() {
    return api.post('/api/subjects/seed');
  },

  // ── CBC assessments ───────────────────────────────────────────────────────
  recordScores(scores) {
    return api.post('/api/academics/scores', scores);
  },
  getGradeAssessments(grade, term, academicYear) {
    return api.get(`/api/academics/grade/${encodeURIComponent(grade)}/${encodeURIComponent(term)}`,
      { params: academicYear ? { academic_year: academicYear } : {} });
  },
  getReportCard(studentId, term, academicYear) {
    return api.get(`/api/academics/report-card/${studentId}/${encodeURIComponent(term)}`,
      { params: academicYear ? { academic_year: academicYear } : {} });
  },

  // ── Exams ────────────────────────────────────────────────────────────────
  recordExamResults(payload) {
    return api.post('/api/exams/bulk', payload);
  },
  getGradeExamResults(grade, term, academicYear, examType) {
    return api.get(`/api/exams/grade/${encodeURIComponent(grade)}/${encodeURIComponent(term)}`,
      { params: { academic_year: academicYear, ...(examType ? { exam_type: examType } : {}) } });
  },
  getStudentExamResults(studentId) {
    return api.get(`/api/exams/student/${studentId}`);
  },
  getExamPerformanceSummary(params = {}) {
    return api.get('/api/exams/performance-summary', { params });
  },

  // ── Attendance ────────────────────────────────────────────────────────────
  markBulkAttendance(records) {
    return api.post('/api/attendance/bulk', records);
  },
  getTodayAttendance(grade) {
    return api.get(`/api/attendance/today/${encodeURIComponent(grade)}`);
  },
  getAttendanceSummary() {
    return api.get('/api/attendance/summary');
  },
  getStudentAttendance(studentId) {
    return api.get(`/api/attendance/student/${studentId}`);
  },

  // ── Timetable ─────────────────────────────────────────────────────────────
  getTimetable(grade, term, year) {
    return api.get(`/api/timetable/${encodeURIComponent(grade)}/${encodeURIComponent(term)}`,
      { params: year ? { year } : {} });
  },
  upsertTimetableEntry(entry) {
    return api.post('/api/timetable/', entry);
  },
  deleteTimetableEntry(entryId) {
    return api.delete(`/api/timetable/${entryId}`);
  },

  // ── Discipline ────────────────────────────────────────────────────────────
  getDisciplineRecords(params = {}) {
    return api.get('/api/discipline/', { params });
  },
  createDisciplineRecord(record) {
    return api.post('/api/discipline/', record);
  },
  updateDisciplineRecord(recordId, data) {
    return api.put(`/api/discipline/${recordId}`, data);
  },
  deleteDisciplineRecord(recordId) {
    return api.delete(`/api/discipline/${recordId}`);
  },

  // ── Leave ─────────────────────────────────────────────────────────────────
  applyForLeave(request) {
    return api.post('/api/leave/', request);
  },
  getLeaveRequests(status) {
    return api.get('/api/leave/', { params: status ? { status } : {} });
  },
  reviewLeaveRequest(requestId, action) {
    return api.put(`/api/leave/${requestId}/review`, null, { params: { action } });
  },
  cancelLeaveRequest(requestId) {
    return api.delete(`/api/leave/${requestId}`);
  },

  // ── Academic calendar & events ────────────────────────────────────────────
  getCurrentTerm() {
    return api.get('/api/calendar/current-term');
  },
  getTermDates(year) {
    return api.get('/api/calendar/term-dates', { params: year ? { year } : {} });
  },
  setTermDates(payload) {
    return api.put('/api/calendar/term-dates', payload);
  },
  getEvents(params = {}) {
    return api.get('/api/events/', { params });
  },
  createEvent(event) {
    return api.post('/api/events/', event);
  },
  updateEvent(eventId, data) {
    return api.put(`/api/events/${eventId}`, data);
  },
  deleteEvent(eventId) {
    return api.delete(`/api/events/${eventId}`);
  },

  // ── Dashboard ─────────────────────────────────────────────────────────────
  getDashboardStats(term) {
    return api.get('/api/dashboard/stats', { params: { term } });
  },
  getGradeStats() {
    return api.get('/api/dashboard/grade-stats');
  },

  // ── Fees ──────────────────────────────────────────────────────────────────
  recordFeePayment(payment) {
    return api.post('/api/fees/', payment);
  },
  recordBulkPayments(payments) {
    return api.post('/api/fees/bulk', payments);
  },
  getPaymentLog(limit = 500) {
    return api.get('/api/fees/log', { params: { limit } });
  },
  deleteFeePayment(paymentId) {
    return api.delete(`/api/fees/${paymentId}`);
  },
  getStudentPayments(studentId) {
    return api.get(`/api/fees/student/${studentId}`);
  },
  getStudentFeeBalance(studentId, term) {
    return api.get(`/api/fees/balance/${studentId}/${encodeURIComponent(term)}`);
  },
  getSmartTerm(studentId, currentTerm) {
    return api.get(`/api/fees/smart-term/${studentId}`, { params: { current_term: currentTerm } });
  },
  getAllocationPreview(studentId, amount, currentTerm) {
    return api.get('/api/fees/allocation-preview',
      { params: { student_id: studentId, amount, current_term: currentTerm } });
  },
  getTermSummary(term) {
    return api.get('/api/fees/term-summary', { params: { term } });
  },
  getCollectionSummary(params = {}) {
    return api.get('/api/fees/collection-summary', { params });
  },
  getStudentCarryForwards(studentId) {
    return api.get(`/api/fees/carry-forward/${studentId}`);
  },
  deleteCarryForward(cfId) {
    return api.delete(`/api/fees/carry-forward/${cfId}`);
  },
  getMonthlyCollection(year) {
    return api.get('/api/fees/monthly-collection', { params: year ? { year } : {} });
  },
  getDefaulters(term, academicYear) {
    return api.get('/api/fees/defaulters',
      { params: { term, ...(academicYear ? { academic_year: academicYear } : {}) } });
  },
  createCarryForward(charge) {
    return api.post('/api/fees/carry-forward', charge);
  },
  getFeeStructure() {
    return api.get('/api/fees/structure');
  },
  getFeeStructureTemplate(year) {
    return api.get('/api/fees/structure/template', { params: { year } });
  },
  createFeeStructureEntry(entry) {
    return api.post('/api/fees/structure', entry);
  },
  bulkSaveFeeStructure(entries) {
    return api.post('/api/fees/structure/bulk', entries);
  },

  // ── Transport & Co-curricular Activities ─────────────────────────────────
  getActivities(year, category) {
    return api.get('/api/activities/', { params: { ...(year ? { year } : {}), ...(category ? { category } : {}) } });
  },
  getStudentActivityEnrollments(studentId, academicYear) {
    return api.get(`/api/activities/enrollments/${studentId}`,
      { params: academicYear ? { academic_year: academicYear } : {} });
  },
  subscribeToActivity(payload) {
    return api.post('/api/activities/enrollments', payload);
  },
  unsubscribeFromActivity(enrollmentId) {
    return api.delete(`/api/activities/enrollments/${enrollmentId}`);
  },
  getActivityRoster(activityName, term, academicYear) {
    return api.get(`/api/activities/${encodeURIComponent(activityName)}/roster`,
      { params: { term, ...(academicYear ? { academic_year: academicYear } : {}) } });
  },
  recordActivityPayment(payload) {
    return api.post('/api/activities/payments', payload);
  },
  updateFeeStructureEntry(entryId, entry) {
    return api.put(`/api/fees/structure/${entryId}`, entry);
  },
  deleteFeeStructureEntry(entryId) {
    return api.delete(`/api/fees/structure/${entryId}`);
  },

  // ── Finance: payroll, expenses, budget, petty cash ────────────────────────
  getMonthlyPayroll(month) {
    return api.get('/api/finance/payroll/monthly', { params: { month } });
  },
  runMonthPayroll(month, entries) {
    return api.post('/api/finance/payroll/run-month', { month, entries });
  },
  voidPayrollMonth(month) {
    return api.delete('/api/finance/payroll/monthly', { params: { month } });
  },
  getPayslip(payrollId) {
    return api.get(`/api/finance/payslip/${payrollId}`);
  },
  createExpense(expense) {
    return api.post('/api/finance/expenses', expense);
  },
  getExpenses() {
    return api.get('/api/finance/expenses');
  },
  getBudgets(params = {}) {
    return api.get('/api/finance/budget', { params });
  },
  createBudget(budget) {
    return api.post('/api/finance/budget', budget);
  },
  updateBudget(budgetId, data) {
    return api.put(`/api/finance/budget/${budgetId}`, data);
  },
  deleteBudget(budgetId) {
    return api.delete(`/api/finance/budget/${budgetId}`);
  },
  getPettyCash() {
    return api.get('/api/finance/petty-cash');
  },
  getTermAccountability(year) {
    return api.get('/api/finance/term-accountability', { params: year ? { year } : {} });
  },
  createPettyCash(tx) {
    return api.post('/api/finance/petty-cash', tx);
  },
  deletePettyCash(txId) {
    return api.delete(`/api/finance/petty-cash/${txId}`);
  },

  // ── Library ───────────────────────────────────────────────────────────────
  getBooks(params = {}) {
    return api.get('/api/library/books', { params });
  },
  addBook(book) {
    return api.post('/api/library/books', book);
  },
  updateBook(bookId, data) {
    return api.put(`/api/library/books/${bookId}`, data);
  },
  deleteBook(bookId) {
    return api.delete(`/api/library/books/${bookId}`);
  },
  getBorrows(activeOnly = false) {
    return api.get('/api/library/borrows', { params: { active_only: activeOnly } });
  },
  createBorrow(borrow) {
    return api.post('/api/library/borrows', borrow);
  },
  returnBook(borrowId) {
    return api.put(`/api/library/borrows/${borrowId}/return`);
  },

  // ── SMS ───────────────────────────────────────────────────────────────────
  smsBroadcast(message, grade) {
    return api.post('/api/sms/broadcast', { message, ...(grade ? { grade } : {}) });
  },
  smsPreview(grade) {
    return api.get('/api/sms/preview', { params: grade ? { grade } : {} });
  },

  // ── Admin ─────────────────────────────────────────────────────────────────
  resetData(confirm, withFinance = false) {
    return api.post('/api/admin/reset-data', { confirm, with_finance: withFinance });
  },

  // ── Backups (system admin only) ───────────────────────────────────────────
  listBackups() {
    return api.get('/api/admin/backups/');
  },
  createBackup() {
    return api.post('/api/admin/backups/');
  },
  downloadBackup(filename) {
    return api.get(`/api/admin/backups/${filename}`, { responseType: 'blob' });
  }
};
