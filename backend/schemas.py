import json
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class GradeLevel(str, Enum):
    play_group = "Play Group"
    pp1 = "PP1"
    pp2 = "PP2"
    grade_1 = "Grade 1"
    grade_2 = "Grade 2"
    grade_3 = "Grade 3"
    grade_4 = "Grade 4"
    grade_5 = "Grade 5"
    grade_6 = "Grade 6"


class StudentStatus(str, Enum):
    active = "Active"
    graduated = "Graduated"
    transferred = "Transferred"


PORTAL_ROLES = {"principal", "secretary", "accountant", "admin", "senior_teacher"}

class UserRole(str, Enum):
    admin = "admin"
    principal = "principal"
    accountant = "accountant"
    secretary = "secretary"
    senior_teacher = "senior_teacher"
    teacher = "teacher"
    support_staff = "support_staff"


class AssessmentScore(str, Enum):
    ee = "EE"
    me = "ME"
    ae = "AE"
    be = "BE"


class Term(str, Enum):
    term_1 = "Term 1"
    term_2 = "Term 2"
    term_3 = "Term 3"


class PaymentType(str, Enum):
    tuition = "Tuition"
    uniforms = "Uniforms"
    transport = "Transport"
    exam_fees = "Exam Fees"


class StudentBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    admission_number: str = Field(..., min_length=1, max_length=20)
    grade_level: GradeLevel
    status: StudentStatus = StudentStatus.active
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    guardian_name: Optional[str] = Field(None, max_length=100)
    guardian_phone: Optional[str] = Field(None, max_length=20)
    guardian2_name: Optional[str] = Field(None, max_length=100)
    guardian2_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=200)
    previous_school: Optional[str] = Field(None, max_length=200)


class StudentCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    admission_number: Optional[str] = Field(None, max_length=20)
    grade_level: GradeLevel
    status: StudentStatus = StudentStatus.active
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    guardian_name: Optional[str] = Field(None, max_length=100)
    guardian_phone: Optional[str] = Field(None, max_length=20)
    guardian2_name: Optional[str] = Field(None, max_length=100)
    guardian2_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=200)
    previous_school: Optional[str] = Field(None, max_length=200)


class StudentResponse(StudentBase):
    id: int

    class Config:
        from_attributes = True


class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    grade_level: Optional[GradeLevel] = None
    status: Optional[StudentStatus] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    guardian_name: Optional[str] = Field(None, max_length=100)
    guardian_phone: Optional[str] = Field(None, max_length=20)
    guardian2_name: Optional[str] = Field(None, max_length=100)
    guardian2_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=200)
    previous_school: Optional[str] = Field(None, max_length=200)


class FeeBase(BaseModel):
    student_id: int
    amount: float = Field(..., gt=0, description="Payment amount must be positive")
    payment_type: PaymentType
    term: Term


class FeeCreate(FeeBase):
    current_term: Optional[str] = None  # school's active term — used for future-term validation


class BulkPaymentItem(BaseModel):
    student_id: int
    amount: float = Field(..., gt=0, description="Payment amount must be positive")
    payment_type: PaymentType = PaymentType.tuition
    term: Term


class FeeAllocationItem(BaseModel):
    term: str
    amount: float
    kind: str  # 'arrears' (prior term) | 'current' (current term) | 'advance' (prepayment)


class FeeResponse(FeeBase):
    id: int
    payment_date: datetime
    recorded_by: str
    receipt_number: Optional[str] = None
    # Parsed from the FeePayment.allocation JSON column when present.
    allocation: Optional[List[FeeAllocationItem]] = None

    @field_validator("allocation", mode="before")
    @classmethod
    def _parse_allocation(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return None
        return v

    class Config:
        from_attributes = True


class TermDateItem(BaseModel):
    term: str
    start_date: date
    end_date: date


class TermDatesPayload(BaseModel):
    academic_year: int = Field(..., ge=2020, le=2100)
    terms: List[TermDateItem]


class TermDatesResponse(BaseModel):
    academic_year: int
    is_default: bool
    terms: List[TermDateItem]


class CurrentTermResponse(BaseModel):
    academic_year: int
    term: str
    source: str  # 'configured' | 'default'


class AllocationPreview(BaseModel):
    student_id: int
    student_name: str
    grade_level: str
    current_term: str
    amount: float
    allocation: List[FeeAllocationItem]
    total_outstanding_before: float
    remaining_after: float  # advance/credit left as prepayment on the current term


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10)


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    role: UserRole


class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=8)  # not required for non-portal roles
    job_title: Optional[str] = Field(None, max_length=100)
    contract_type: Optional[str] = Field(None, max_length=50)
    date_of_hire: Optional[date] = None
    kra_pin: Optional[str] = Field(None, max_length=20)
    nssf_number: Optional[str] = Field(None, max_length=30)
    nhif_number: Optional[str] = Field(None, max_length=30)
    accrued_leave_days: Optional[int] = Field(21, ge=0)
    basic_salary: Optional[float] = Field(0.0, ge=0)
    allowances: Optional[float] = Field(0.0, ge=0)
    deductions: Optional[float] = Field(0.0, ge=0)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    password: Optional[str] = None   # validated below only when a value is actually provided
    job_title: Optional[str] = Field(None, max_length=100)
    contract_type: Optional[str] = Field(None, max_length=50)
    date_of_hire: Optional[date] = None
    kra_pin: Optional[str] = Field(None, max_length=20)
    nssf_number: Optional[str] = Field(None, max_length=30)
    nhif_number: Optional[str] = Field(None, max_length=30)
    accrued_leave_days: Optional[int] = Field(None, ge=0)
    basic_salary: Optional[float] = Field(None, ge=0)
    allowances: Optional[float] = Field(None, ge=0)
    deductions: Optional[float] = Field(None, ge=0)

    @field_validator('password')
    @classmethod
    def password_length(cls, v):
        if v is not None and len(v) > 0 and len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v or None  # treat empty string as None


class UserResponse(UserBase):
    id: int
    role: str  # override UserBase enum — accept any role string stored in DB
    job_title: Optional[str] = None
    contract_type: Optional[str] = None
    date_of_hire: Optional[date] = None
    kra_pin: Optional[str] = None
    nssf_number: Optional[str] = None
    nhif_number: Optional[str] = None
    accrued_leave_days: int = 21
    leave_days_used: int = 0
    leave_days_left: int = 21
    basic_salary: float = 0.0
    allowances: float = 0.0
    deductions: float = 0.0
    can_login: bool = True

    class Config:
        from_attributes = True


class PayrollStaffEntry(BaseModel):
    staff_id: int
    allowances: float = Field(0.0, ge=0)
    deductions: float = Field(0.0, ge=0)


class RunPayrollRequest(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    entries: list[PayrollStaffEntry]


class AssessmentBase(BaseModel):
    student_id: int
    academic_year: str = Field(..., min_length=4, max_length=9)
    term: Term
    learning_area: str = Field(..., min_length=1, max_length=100)
    strand: str = Field("", max_length=100)
    score: AssessmentScore
    remarks: Optional[str] = Field(None, max_length=500)


class AssessmentCreate(AssessmentBase):
    pass


class AssessmentResponse(AssessmentBase):
    id: int

    class Config:
        from_attributes = True


class FeeCarryForwardCreate(BaseModel):
    student_id: int
    amount: float = Field(..., description="Positive = student owes; negative = school credit")
    academic_year: str
    term: Term
    note: Optional[str] = Field(None, max_length=200)


class FeeCarryForwardResponse(BaseModel):
    id: int
    student_id: int
    amount: float
    academic_year: str
    term: str
    note: Optional[str]
    recorded_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class FeeStructureCreate(BaseModel):
    # Free strings (not enums) so the structure can hold non-grade items such as
    # Admission, Daycare and co-curricular activities, not just termly tuition.
    grade_level: str = Field(..., max_length=20)
    term: str = Field(..., max_length=10)
    fee_type: str = Field(..., max_length=50)
    amount: float = Field(..., ge=0)   # 0 allowed (e.g. unpriced optional activity)
    academic_year: int = Field(..., ge=2020, le=2100)


class FeeStructureResponse(FeeStructureCreate):
    id: int

    class Config:
        from_attributes = True


class AttendanceCreate(BaseModel):
    student_id: int
    is_present: bool
    remarks: Optional[str] = Field(None, max_length=500)


class AttendanceResponse(AttendanceCreate):
    id: int
    date: date

    class Config:
        from_attributes = True


class PayrollCreate(BaseModel):
    staff_id: int
    payment_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    basic_salary: float = Field(..., ge=0)
    allowances: float = Field(0.0, ge=0)
    deductions: float = Field(0.0, ge=0)
    net_pay: float = Field(..., ge=0)


class PayrollResponse(BaseModel):
    id: int
    staff_id: Optional[int] = None
    payment_month: str
    basic_salary: float
    allowances: float
    deductions: float
    net_pay: float
    recorded_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    category: Optional[str] = Field(None, max_length=100)
    justification: str = Field(..., min_length=1, max_length=500)


class ExpenseResponse(ExpenseCreate):
    id: int
    recorded_by: str
    expense_date: datetime

    class Config:
        from_attributes = True


class TimetableCreate(BaseModel):
    grade_level: GradeLevel
    day_of_week: str = Field(..., pattern=r"^(Monday|Tuesday|Wednesday|Thursday|Friday)$")
    period: int = Field(..., ge=1, le=10)
    subject: str = Field(..., min_length=1, max_length=100)
    teacher_name: Optional[str] = Field(None, max_length=100)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    term: Term
    academic_year: int = Field(..., ge=2020, le=2100)


class TimetableResponse(TimetableCreate):
    id: int
    created_by: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    grade_level: GradeLevel
    teacher_id: Optional[int] = None
    color: Optional[str] = Field(None, max_length=7)


class SubjectUpdate(BaseModel):
    teacher_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=7)


class SubjectResponse(BaseModel):
    id: int
    name: str
    grade_level: str
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Exam Results ──────────────────────────────────────────────────────────────

class ExamResultEntry(BaseModel):
    student_id: int
    marks: float = Field(..., ge=0)
    max_marks: int = Field(100, ge=1)

class ExamBulkCreate(BaseModel):
    grade_level: str
    term: str
    exam_type: str = Field(..., pattern=r"^(CAT1|CAT2|MidTerm|EndTerm)$")
    subject: str = Field(..., min_length=1, max_length=100)
    academic_year: int = Field(..., ge=2020, le=2100)
    results: List[ExamResultEntry]

class ExamResultResponse(BaseModel):
    id: int
    student_id: int
    grade_level: str
    subject: str
    exam_type: str
    marks: float
    max_marks: int
    term: str
    academic_year: int
    recorded_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Library ────────────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    isbn: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=100)
    quantity: int = Field(1, ge=1)
    condition: str = Field("Good", max_length=20)
    acquired_date: Optional[date] = None

class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    quantity: Optional[int] = Field(None, ge=1)
    condition: Optional[str] = Field(None, max_length=20)

class BookResponse(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    category: Optional[str] = None
    quantity: int
    available: int
    condition: str
    acquired_date: Optional[date] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BorrowCreate(BaseModel):
    book_id: int
    borrower_type: str = Field(..., pattern=r"^(student|staff)$")
    borrower_id: int
    borrower_name: str = Field(..., min_length=1, max_length=200)
    due_date: date

class BorrowResponse(BaseModel):
    id: int
    book_id: int
    book_title: str
    borrower_type: str
    borrower_id: int
    borrower_name: str
    borrowed_date: date
    due_date: date
    return_date: Optional[date] = None
    fine_amount: float
    recorded_by: str
    is_overdue: bool

    class Config:
        from_attributes = True


# ── School Events ──────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    event_type: str = Field(..., max_length=50)
    start_date: date
    end_date: Optional[date] = None
    all_day: bool = True

class EventResponse(EventCreate):
    id: int
    created_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Disciplinary Records ───────────────────────────────────────────────────────

class DisciplineCreate(BaseModel):
    student_id: int
    incident_date: date
    incident_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    action_taken: Optional[str] = Field(None, max_length=500)
    action_date: Optional[date] = None
    severity: str = Field("Minor", pattern=r"^(Minor|Moderate|Serious)$")

class DisciplineUpdate(BaseModel):
    action_taken: Optional[str] = Field(None, max_length=500)
    action_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern=r"^(Open|Resolved)$")
    severity: Optional[str] = Field(None, pattern=r"^(Minor|Moderate|Serious)$")

class DisciplineResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    grade_level: str
    incident_date: date
    incident_type: str
    description: str
    action_taken: Optional[str] = None
    action_date: Optional[date] = None
    severity: str
    status: str
    recorded_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Budget ─────────────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    academic_year: int = Field(..., ge=2020, le=2100)
    term: str
    budgeted_amount: float = Field(..., gt=0)

class BudgetResponse(BaseModel):
    id: int
    category: str
    academic_year: int
    term: str
    budgeted_amount: float
    actual_spent: float = 0.0
    variance: float = 0.0
    created_by: str

    class Config:
        from_attributes = True


# ── Petty Cash ─────────────────────────────────────────────────────────────────

class PettyCashCreate(BaseModel):
    transaction_type: str = Field(..., pattern=r"^(IN|OUT)$")
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=100)

class PettyCashResponse(BaseModel):
    id: int
    transaction_type: str
    amount: float
    description: str
    category: Optional[str] = None
    recorded_by: str
    transaction_date: datetime
    running_balance: float = 0.0

    class Config:
        from_attributes = True


# ── Promotion ──────────────────────────────────────────────────────────────────

class PromotionRequest(BaseModel):
    student_ids: List[int]
    to_grade: str


class LeaveRequestCreate(BaseModel):
    leave_type: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=500)


class LeaveRequestResponse(BaseModel):
    id: int
    staff_id: int
    leave_type: str
    start_date: date
    end_date: date
    reason: str
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    staff_name: Optional[str] = None

    class Config:
        from_attributes = True
