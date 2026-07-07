import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export default {
  // Teachers
  getTeachers() {
    return api.get('/teachers/');
  },
  createTeacher(teacher) {
    return api.post('/teachers/', teacher);
  },

  // Courses
  getCourses() {
    return api.get('/courses/');
  },
  createCourse(course) {
    return api.post('/courses/', course);
  },

  // Students
  getStudents() {
    return api.get('/students/');
  },
  createStudent(student) {
    return api.post('/students/', student);
  }
};
