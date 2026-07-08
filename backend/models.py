from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Date, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    job_title = Column(String(100), nullable=True)
    contract_type = Column(String(50), nullable=True)
    date_of_hire = Column(Date, nullable=True)
    kra_pin = Column(String(20), nullable=True)
    nssf_number = Column(String(30), nullable=True)
    nhif_number = Column(String(30), nullable=True)
    accrued_leave_days = Column(Integer, nullable=False, default=21, server_default="21")
    basic_salary = Column(Numeric(10, 2), nullable=False, server_default="0")
    allowances = Column(Numeric(10, 2), nullable=False, server_default="0")
    deductions = Column(Numeric(10, 2), nullable=False, server_default="0")
    can_login = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), index=True, nullable=False)
    last_name = Column(String(100), index=True, nullable=False)
    admission_number = Column(String(20), unique=True, index=True, nullable=False)
    grade_level = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="Active")
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    guardian_name = Column(String(100), nullable=True)
    guardian_phone = Column(String(20), nullable=True)
    guardian2_name = Column(String(100), nullable=True)
    guardian2_phone = Column(String(20), nullable=True)
    address = Column(String(200), nullable=True)
    previous_school = Column(String(200), nullable=True)
    # Soft delete — never hard-delete student records
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FeePayment(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    # Numeric(10, 2) avoids floating-point rounding errors for currency
    amount = Column(Numeric(10, 2), nullable=False)
    payment_type = Column(String(50), nullable=False)
    term = Column(String(10), nullable=False)
    payment_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recorded_by = Column(String(100), nullable=False)
    # Sequential receipt number — format BNS-{YEAR}-{seq:05d}
    receipt_number = Column(String(20), unique=True, nullable=True, index=True)
    # JSON breakdown of how this payment was applied across terms (waterfall:
    # oldest arrears first, remainder to the current term). For receipt display.
    # e.g. [{"term": "Term 1", "amount": 5000, "kind": "arrears"},
    #       {"term": "Term 2", "amount": 3000, "kind": "current"}]
    allocation = Column(Text, nullable=True)


class FeeStructure(Base):
    """Configurable per-grade/per-term fee schedule. Replaces hardcoded dictionary in fees.py."""
    __tablename__ = "fee_structure"

    id = Column(Integer, primary_key=True, index=True)
    grade_level = Column(String(20), nullable=False)
    term = Column(String(10), nullable=False)
    fee_type = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    academic_year = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('grade_level', 'term', 'fee_type', 'academic_year',
                         name='uq_fee_structure_entry'),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year = Column(String(9), nullable=False, server_default="2024")
    term = Column(String(10), nullable=False)
    learning_area = Column(String(100), nullable=False)
    strand = Column(String(100), nullable=False, server_default="")
    score = Column(String(5), nullable=False)
    remarks = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_assessments_student_term_year', 'student_id', 'term', 'academic_year'),
    )


class FeeCarryForward(Base):
    """Explicit cross-year balance carry-forward for a student."""
    __tablename__ = "fee_carry_forwards"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)   # positive = owes, negative = credit
    academic_year = Column(String(9), nullable=False)
    term = Column(String(10), nullable=False)
    note = Column(String(200), nullable=True)
    recorded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, server_default=func.current_date(), nullable=False, index=True)
    is_present = Column(Boolean, default=True, nullable=False)
    remarks = Column(String(500), nullable=True)

    __table_args__ = (
        Index('idx_attendance_student_date', 'student_id', 'date'),
    )


class AuditLog(Base):
    """Immutable record of every create/update/delete action in the system."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(10), nullable=False)       # CREATE | UPDATE | DELETE
    resource = Column(String(50), nullable=False)     # student | fee | assessment | attendance | staff
    resource_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)               # JSON string for extra context
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Payroll(Base):
    """Monthly salary disbursement record per staff member."""
    __tablename__ = "payroll"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_month = Column(String(7), nullable=False, index=True)          # YYYY-MM
    basic_salary = Column(Numeric(10, 2), nullable=False)
    allowances = Column(Numeric(10, 2), nullable=False, server_default="0")
    deductions = Column(Numeric(10, 2), nullable=False, server_default="0")
    net_pay = Column(Numeric(10, 2), nullable=False)
    recorded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_payroll_staff_month', 'staff_id', 'payment_month'),
        UniqueConstraint('staff_id', 'payment_month', name='uq_payroll_staff_month'),
    )


class Expense(Base):
    """School operational expense record."""
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(100), nullable=True)
    justification = Column(String(500), nullable=False)
    recorded_by = Column(String(100), nullable=False)
    expense_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Timetable(Base):
    """Weekly class schedule entry per grade."""
    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, index=True)
    grade_level = Column(String(20), nullable=False, index=True)
    day_of_week = Column(String(10), nullable=False)
    period = Column(Integer, nullable=False)
    subject = Column(String(100), nullable=False)
    teacher_name = Column(String(100), nullable=True)
    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)
    term = Column(String(10), nullable=False)
    academic_year = Column(Integer, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subject(Base):
    """CBC subject per grade level with optional teacher assignment."""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    grade_level = Column(String(20), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    color = Column(String(7), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LeaveRequest(Base):
    """Staff leave application and approval record."""
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExamResult(Base):
    """Numeric exam mark per student/subject/exam type."""
    __tablename__ = "exam_results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_level = Column(String(20), nullable=False, index=True)
    subject = Column(String(100), nullable=False)
    exam_type = Column(String(20), nullable=False)   # CAT1 | CAT2 | MidTerm | EndTerm
    marks = Column(Numeric(5, 1), nullable=False)
    max_marks = Column(Integer, nullable=False, server_default="100")
    term = Column(String(10), nullable=False)
    academic_year = Column(Integer, nullable=False)
    recorded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_exam_results_student_term_year', 'student_id', 'term', 'academic_year'),
    )


class LibraryBook(Base):
    """Book in the school library catalogue."""
    __tablename__ = "library_books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(200), nullable=True)
    isbn = Column(String(20), unique=True, nullable=True)
    category = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False, server_default="1")
    available = Column(Integer, nullable=False, server_default="1")
    condition = Column(String(20), nullable=False, server_default="'Good'")
    acquired_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LibraryBorrow(Base):
    """Book borrow/return transaction."""
    __tablename__ = "library_borrows"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("library_books.id", ondelete="CASCADE"), nullable=False)
    borrower_type = Column(String(10), nullable=False)   # student | staff
    borrower_id = Column(Integer, nullable=False)
    borrower_name = Column(String(200), nullable=False)
    borrowed_date = Column(Date, server_default=func.current_date(), nullable=False)
    due_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    fine_amount = Column(Numeric(8, 2), nullable=False, server_default="0")
    recorded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SchoolEvent(Base):
    """School calendar event."""
    __tablename__ = "school_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False)   # exam | holiday | meeting | sports | other
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    all_day = Column(Boolean, nullable=False, server_default="true")
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DisciplinaryRecord(Base):
    """Student disciplinary incident record."""
    __tablename__ = "disciplinary_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_date = Column(Date, nullable=False)
    incident_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    action_taken = Column(String(500), nullable=True)
    action_date = Column(Date, nullable=True)
    severity = Column(String(20), nullable=False, server_default="'Minor'")   # Minor | Moderate | Serious
    status = Column(String(20), nullable=False, server_default="'Open'")      # Open | Resolved
    recorded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Budget(Base):
    """Expense budget per category/term/year."""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)
    academic_year = Column(Integer, nullable=False)
    term = Column(String(10), nullable=False)
    budgeted_amount = Column(Numeric(12, 2), nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PettyCashTransaction(Base):
    """Petty cash fund transaction (IN = top-up, OUT = expenditure)."""
    __tablename__ = "petty_cash"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String(5), nullable=False)    # IN | OUT
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    recorded_by = Column(String(100), nullable=False)
    transaction_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class TermDate(Base):
    """Configurable academic term start/end dates per year. Drives the
    auto-detected 'current term' used across fees and reporting."""
    __tablename__ = "term_dates"

    id = Column(Integer, primary_key=True, index=True)
    academic_year = Column(Integer, nullable=False, index=True)
    term = Column(String(10), nullable=False)   # Term 1 | Term 2 | Term 3
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("academic_year", "term", name="uq_term_dates_year_term"),
    )
