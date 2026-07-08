# Fallback per-grade tuition (Term 1 values) used only when no FeeStructure row
# exists for a grade/term/year. Real values come from the configured structure.
CBC_TERMLY_FEES = {
    "Play Group": 8500.00,
    "PP1": 10500.00,
    "PP2": 10500.00,
    "Grade 1": 13500.00,
    "Grade 2": 13500.00,
    "Grade 3": 13500.00,
    "Grade 4": 14500.00,
    "Grade 5": 14500.00,
    "Grade 6": 14500.00,
}

# ── Fee-structure template (The Bona School, 2026 sheet) ──────────────────────
# Preloaded each year as the editable starting point; the principal confirms or
# adjusts and saves. Termly tuition is keyed grade -> {term: amount}. Non-grade
# items are stored under grade_level="General" with a term category label.
_TERMLY_TEMPLATE = {
    "Play Group": {"Term 1": 8500,  "Term 2": 8000,  "Term 3": 7500},
    "PP1":        {"Term 1": 10500, "Term 2": 10000, "Term 3": 10000},
    "PP2":        {"Term 1": 10500, "Term 2": 10000, "Term 3": 10000},
    "Grade 1":    {"Term 1": 13500, "Term 2": 13000, "Term 3": 13000},
    "Grade 2":    {"Term 1": 13500, "Term 2": 13000, "Term 3": 13000},
    "Grade 3":    {"Term 1": 13500, "Term 2": 13000, "Term 3": 13000},
    "Grade 4":    {"Term 1": 14500, "Term 2": 14500, "Term 3": 14000},
    "Grade 5":    {"Term 1": 14500, "Term 2": 14500, "Term 3": 14000},
    "Grade 6":    {"Term 1": 14500, "Term 2": 14500, "Term 3": 14000},
}
_ADMISSION_TEMPLATE = 1500
_DAILY_UNDER2_TEMPLATE = 400
_OTHER_TEMPLATE = {"School Diary": 500, "Ream Paper": 800, "Assessment Book": 350}
_COCURRICULAR_TEMPLATE = {
    "French (Grade 1)": 2000, "Skating": 3500, "Ballet": 3000, "Modern Dance": 3000,
    "Swimming": 0, "Computer": 0, "Coding": 0, "Martial Art": 0, "Scouts": 0, "Football": 0,
}

# term-category labels for non-grade items (stored in FeeStructure.term)
GENERAL_GRADE = "General"
CAT_ADMISSION = "Once"
CAT_DAILY = "Daily"
CAT_OTHER = "Termly"
CAT_COCURRICULAR = "Optional"


def fee_structure_template_rows(year: int):
    """Flat FeeStructure-shaped rows for a year's default template."""
    rows = []
    for grade, terms in _TERMLY_TEMPLATE.items():
        for term, amount in terms.items():
            rows.append({"grade_level": grade, "term": term, "fee_type": "Tuition",
                         "amount": float(amount), "academic_year": year})
    rows.append({"grade_level": GENERAL_GRADE, "term": CAT_ADMISSION, "fee_type": "Admission",
                 "amount": float(_ADMISSION_TEMPLATE), "academic_year": year})
    rows.append({"grade_level": GENERAL_GRADE, "term": CAT_DAILY, "fee_type": "Daycare (Under 2)",
                 "amount": float(_DAILY_UNDER2_TEMPLATE), "academic_year": year})
    for name, amount in _OTHER_TEMPLATE.items():
        rows.append({"grade_level": GENERAL_GRADE, "term": CAT_OTHER, "fee_type": name,
                     "amount": float(amount), "academic_year": year})
    for name, amount in _COCURRICULAR_TEMPLATE.items():
        rows.append({"grade_level": GENERAL_GRADE, "term": CAT_COCURRICULAR, "fee_type": name,
                     "amount": float(amount), "academic_year": year})
    return rows

CBC_GRADES = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6",
]

TERM_ORDER = {"Term 1": 1, "Term 2": 2, "Term 3": 3}
TERM_BY_NUM = {1: "Term 1", 2: "Term 2", 3: "Term 3"}


# ── Academic calendar ─────────────────────────────────────────────────────────
# Standard Kenyan school-term pattern, used as the fallback when no term dates
# have been configured for a year. (month, day) tuples for (start, end).
DEFAULT_TERM_PATTERN = {
    "Term 1": ((1, 2),  (4, 11)),
    "Term 2": ((4, 28), (8, 8)),
    "Term 3": ((9, 1),  (11, 7)),
}


def default_term_dates(year: int):
    """Return {term: (start_date, end_date)} for a given year using the standard
    Kenyan calendar pattern."""
    from datetime import date
    return {
        term: (date(year, sm, sd), date(year, em, ed))
        for term, ((sm, sd), (em, ed)) in DEFAULT_TERM_PATTERN.items()
    }
