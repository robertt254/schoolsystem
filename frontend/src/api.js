import axios from 'axios';

const API_URL = 'http://localhost:8000';

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

export default {
  // Auth
  login(data) {
    return axios.post(`${API_URL}/token`, data, {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    });
  },
  getMe() {
    return api.get('/users/me/');
  },

  // Courses
  getCourses() {
    return api.get('/courses/');
  },
  createCourse(course) {
    return api.post('/courses/', course);
  },

  // Teachers
  getTeachers() {
    return api.get('/teachers/');
  },
  createTeacher(teacher) {
    return api.post('/teachers/', teacher);
  },

  // Students
  getStudents() {
    return api.get('/students/');
  },
  createStudent(student) {
    return api.post('/students/', student);
  },

  // Assessments
  getStudentAssessments(studentId) {
      return api.get(`/students/${studentId}/assessments/`);
  },
  createAssessment(assessment) {
      return api.post('/assessments/', assessment);
  },

  // Finance
  getFinanceDashboard() {
      return api.get('/finance/dashboard/');
  },
  createInvoice(invoice) {
      return api.post('/finance/invoices/', invoice);
  },
  processPayment(payment) {
      return api.post('/finance/payments/', payment);
  }
};
