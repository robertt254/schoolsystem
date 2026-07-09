// CBC grading scale — same thresholds as the Bona School system.
// Maps a numeric exam mark to its CBC evaluation band.
export function gradeLabel(marks, maxMarks = 100) {
  const pct = (Number(marks) / Number(maxMarks || 100)) * 100;
  if (pct >= 80) return { label: 'Exceeding Expectation', abbr: 'EE', cls: 'bg-green-100 text-green-800' };
  if (pct >= 70) return { label: 'Meeting Expectation', abbr: 'ME', cls: 'bg-blue-100 text-blue-800' };
  if (pct >= 60) return { label: 'Approaching Expectation', abbr: 'AE', cls: 'bg-yellow-100 text-yellow-800' };
  return { label: 'Below Expectation', abbr: 'BE', cls: 'bg-red-100 text-red-800' };
}
