import { describe, it, expect } from 'vitest';
import { wasEnrolledForTerm } from './enrollment';

describe('wasEnrolledForTerm (mid-year joiner eligibility)', () => {
  it('treats a student with no admission_year as enrolled for every term', () => {
    const student = { admission_year: null, admission_term: null };
    expect(wasEnrolledForTerm(student, 'Term 1', 2026)).toBe(true);
    expect(wasEnrolledForTerm(student, 'Term 3', 2026)).toBe(true);
  });

  it('excludes a mid-year joiner from terms before their admission term', () => {
    const student = { admission_year: 2026, admission_term: 'Term 2' };
    expect(wasEnrolledForTerm(student, 'Term 1', 2026)).toBe(false);
    expect(wasEnrolledForTerm(student, 'Term 2', 2026)).toBe(true);
    expect(wasEnrolledForTerm(student, 'Term 3', 2026)).toBe(true);
  });

  it('excludes every term of a future admission year', () => {
    const student = { admission_year: 2027, admission_term: 'Term 1' };
    expect(wasEnrolledForTerm(student, 'Term 3', 2026)).toBe(false);
  });

  it('includes every term of a past admission year', () => {
    const student = { admission_year: 2024, admission_term: 'Term 3' };
    expect(wasEnrolledForTerm(student, 'Term 1', 2026)).toBe(true);
  });

  it('defaults a missing admission_term to Term 1 for the admission year', () => {
    const student = { admission_year: 2026, admission_term: null };
    expect(wasEnrolledForTerm(student, 'Term 1', 2026)).toBe(true);
  });
});
