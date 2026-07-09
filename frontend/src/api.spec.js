import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock axios before the module under test is imported. `api.js` creates one
// axios instance at import time and also calls the top-level axios.post for
// login, so both surfaces are mocked.
const mocks = vi.hoisted(() => {
  const instance = {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  };
  return {
    instance,
    create: vi.fn(() => instance),
    post: vi.fn().mockResolvedValue({ data: {} }),
  };
});

vi.mock('axios', () => ({
  default: { create: mocks.create, post: mocks.post },
}));

// Minimal localStorage for the auth interceptor (vitest runs in Node)
const store = {};
globalThis.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};

const api = (await import('./api.js')).default;
const BASE = 'http://localhost:8000';

beforeEach(() => {
  mocks.instance.get.mockClear();
  mocks.instance.post.mockClear();
  mocks.instance.put.mockClear();
  mocks.instance.delete.mockClear();
  mocks.post.mockClear();
  for (const k of Object.keys(store)) delete store[k];
});

describe('axios setup', () => {
  it('creates the instance with the dev base URL when VITE_API_URL is unset', () => {
    expect(mocks.create).toHaveBeenCalledWith({ baseURL: BASE });
  });

  it('registers a request interceptor that attaches the bearer token', () => {
    expect(mocks.instance.interceptors.request.use).toHaveBeenCalledTimes(1);
    const interceptor = mocks.instance.interceptors.request.use.mock.calls[0][0];

    // No token stored → header untouched
    expect(interceptor({ headers: {} }).headers.Authorization).toBeUndefined();

    // Token stored → Authorization: Bearer <token>
    localStorage.setItem('token', 'jwt-abc');
    expect(interceptor({ headers: {} }).headers.Authorization).toBe('Bearer jwt-abc');
  });

  it('registers a response interceptor that ends the session on 401', async () => {
    expect(mocks.instance.interceptors.response.use).toHaveBeenCalledTimes(1);
    const onError = mocks.instance.interceptors.response.use.mock.calls[0][1];

    localStorage.setItem('token', 'stale-jwt');
    localStorage.setItem('user_info', '{"role":"admin"}');

    const err = { response: { status: 401 } };
    await expect(onError(err)).rejects.toBe(err);
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('user_info')).toBeNull();

    // Non-401 errors leave the session untouched
    localStorage.setItem('token', 'valid-jwt');
    await expect(onError({ response: { status: 500 } })).rejects.toBeTruthy();
    expect(localStorage.getItem('token')).toBe('valid-jwt');
  });
});

describe('auth', () => {
  it('login posts form-encoded credentials to /api/auth/login', () => {
    const form = new URLSearchParams({ username: 'admin', password: 'pw' });
    api.login(form);
    expect(mocks.post).toHaveBeenCalledWith(
      `${BASE}/api/auth/login`,
      form,
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    );
  });

  it('changePassword posts to the change-password endpoint', () => {
    api.changePassword({ current_password: 'a', new_password: 'b' });
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/auth/change-password',
      { current_password: 'a', new_password: 'b' },
    );
  });
});

describe('students', () => {
  it('getStudents passes search/grade filters as query params', () => {
    api.getStudents({ search: 'jane', grade: 'Grade 1' });
    expect(mocks.instance.get).toHaveBeenCalledWith(
      '/api/students/',
      { params: { search: 'jane', grade: 'Grade 1' } },
    );
  });

  it('createStudent posts the student payload', () => {
    const student = { first_name: 'Jane', last_name: 'W', grade_level: 'PP1' };
    api.createStudent(student);
    expect(mocks.instance.post).toHaveBeenCalledWith('/api/students/', student);
  });

  it('getStudentProfile targets the profile subresource', () => {
    api.getStudentProfile(7);
    expect(mocks.instance.get).toHaveBeenCalledWith('/api/students/7/profile');
  });

  it('getClassRoster URL-encodes the grade', () => {
    api.getClassRoster('Grade 1');
    expect(mocks.instance.get).toHaveBeenCalledWith('/api/students/classes/Grade%201');
  });

  it('promoteStudents wraps ids and target grade in the expected body', () => {
    api.promoteStudents([1, 2], 'Grade 3');
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/students/promote',
      { student_ids: [1, 2], to_grade: 'Grade 3' },
    );
  });
});

describe('academics & exams', () => {
  it('recordScores posts the score list unmodified', () => {
    const scores = [{ student_id: 1, term: 'Term 1', learning_area: 'Math', score: 'ME' }];
    api.recordScores(scores);
    expect(mocks.instance.post).toHaveBeenCalledWith('/api/academics/scores', scores);
  });

  it('getReportCard encodes path segments and forwards the year', () => {
    api.getReportCard(4, 'Term 2', '2026');
    expect(mocks.instance.get).toHaveBeenCalledWith(
      '/api/academics/report-card/4/Term%202',
      { params: { academic_year: '2026' } },
    );
  });

  it('getGradeExamResults sends year and optional exam type', () => {
    api.getGradeExamResults('Grade 2', 'Term 1', 2026, 'EndTerm');
    expect(mocks.instance.get).toHaveBeenCalledWith(
      '/api/exams/grade/Grade%202/Term%201',
      { params: { academic_year: 2026, exam_type: 'EndTerm' } },
    );
  });
});

describe('fees & finance', () => {
  it('recordFeePayment posts the payment payload', () => {
    const payment = { student_id: 1, amount: 5000, payment_type: 'Tuition', term: 'Term 1', current_term: 'Term 1' };
    api.recordFeePayment(payment);
    expect(mocks.instance.post).toHaveBeenCalledWith('/api/fees/', payment);
  });

  it('getAllocationPreview passes student, amount and current term as params', () => {
    api.getAllocationPreview(3, 2500, 'Term 2');
    expect(mocks.instance.get).toHaveBeenCalledWith(
      '/api/fees/allocation-preview',
      { params: { student_id: 3, amount: 2500, current_term: 'Term 2' } },
    );
  });

  it('getStudentFeeBalance URL-encodes the term segment', () => {
    api.getStudentFeeBalance(9, 'Term 3');
    expect(mocks.instance.get).toHaveBeenCalledWith('/api/fees/balance/9/Term%203');
  });

  it('getDefaulters omits academic_year when not given', () => {
    api.getDefaulters('Term 1');
    expect(mocks.instance.get).toHaveBeenCalledWith(
      '/api/fees/defaulters',
      { params: { term: 'Term 1' } },
    );
  });

  it('runMonthPayroll wraps month and entries in one body', () => {
    api.runMonthPayroll('2026-07', [{ staff_id: 2, allowances: 0, deductions: 0 }]);
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/finance/payroll/run-month',
      { month: '2026-07', entries: [{ staff_id: 2, allowances: 0, deductions: 0 }] },
    );
  });

  it('voidPayrollMonth sends the month as a query param on DELETE', () => {
    api.voidPayrollMonth('2026-07');
    expect(mocks.instance.delete).toHaveBeenCalledWith(
      '/api/finance/payroll/monthly',
      { params: { month: '2026-07' } },
    );
  });
});

describe('leave, library, sms, admin', () => {
  it('reviewLeaveRequest puts with the action as a query param and no body', () => {
    api.reviewLeaveRequest(5, 'approve');
    expect(mocks.instance.put).toHaveBeenCalledWith(
      '/api/leave/5/review',
      null,
      { params: { action: 'approve' } },
    );
  });

  it('returnBook targets the return subresource', () => {
    api.returnBook(11);
    expect(mocks.instance.put).toHaveBeenCalledWith('/api/library/borrows/11/return');
  });

  it('smsBroadcast omits grade when broadcasting to everyone', () => {
    api.smsBroadcast('School reopens Monday.');
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/sms/broadcast',
      { message: 'School reopens Monday.' },
    );
  });

  it('smsBroadcast includes grade when one is selected', () => {
    api.smsBroadcast('PP1 trip tomorrow.', 'PP1');
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/sms/broadcast',
      { message: 'PP1 trip tomorrow.', grade: 'PP1' },
    );
  });

  it('resetData sends the confirmation text and finance flag', () => {
    api.resetData('RESET', true);
    expect(mocks.instance.post).toHaveBeenCalledWith(
      '/api/admin/reset-data',
      { confirm: 'RESET', with_finance: true },
    );
  });
});
