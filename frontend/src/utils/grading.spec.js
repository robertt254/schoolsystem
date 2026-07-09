import { describe, it, expect } from 'vitest';
import { gradeLabel } from './grading';

describe('CBC grading scale (Bona School thresholds)', () => {
  it('maps 80% and above to Exceeding Expectation', () => {
    expect(gradeLabel(80).abbr).toBe('EE');
    expect(gradeLabel(100).abbr).toBe('EE');
  });

  it('maps 70–79% to Meeting Expectation', () => {
    expect(gradeLabel(70).abbr).toBe('ME');
    expect(gradeLabel(79.5).abbr).toBe('ME');
  });

  it('maps 60–69% to Approaching Expectation', () => {
    expect(gradeLabel(60).abbr).toBe('AE');
    expect(gradeLabel(69).abbr).toBe('AE');
  });

  it('maps below 60% to Below Expectation', () => {
    expect(gradeLabel(59.9).abbr).toBe('BE');
    expect(gradeLabel(0).abbr).toBe('BE');
  });

  it('scales to the exam maximum, not raw marks', () => {
    expect(gradeLabel(40, 50).abbr).toBe('EE');   // 80%
    expect(gradeLabel(21, 30).abbr).toBe('ME');   // 70%
    expect(gradeLabel(15, 30).abbr).toBe('BE');   // 50%
  });

  it('provides full labels for report cards', () => {
    expect(gradeLabel(85).label).toBe('Exceeding Expectation');
    expect(gradeLabel(45).label).toBe('Below Expectation');
  });
});
