// Mirrors the backend's mid-year-joiner eligibility check (fees._owes_term /
// exams._was_enrolled_for_term): a student admitted mid-year wasn't enrolled
// for terms before their admission term, so there's nothing to show or enter
// for them — fees, exams, whatever — from before they joined.
const TERM_ORDER = { 'Term 1': 1, 'Term 2': 2, 'Term 3': 3 };

export function wasEnrolledForTerm(student, term, academicYear) {
    const admissionYear = student.admission_year;
    if (admissionYear == null || admissionYear < academicYear) return true;
    if (admissionYear > academicYear) return false;
    const admissionTerm = student.admission_term || 'Term 1';
    return (TERM_ORDER[term] || 1) >= (TERM_ORDER[admissionTerm] || 1);
}
