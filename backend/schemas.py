from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .models import Role, Grade, CBCLevel

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    role: Role

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class Config:
        from_attributes = True

# Teachers
class TeacherBase(BaseModel):
    name: str
    department: str

class TeacherCreate(TeacherBase):
    pass

class Teacher(TeacherBase):
    id: int
    user_id: Optional[int] = None
    class Config:
        from_attributes = True

# Courses
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    grade_level: Grade
    teacher_id: int

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int
    class Config:
        from_attributes = True

# Students
class StudentBase(BaseModel):
    admission_number: str
    name: str
    grade: Grade
    guardian_contact: str

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: int
    class Config:
        from_attributes = True

# Assessments
class AssessmentBase(BaseModel):
    course_id: int
    term: int
    outcome: str
    level: CBCLevel

class AssessmentCreate(AssessmentBase):
    student_id: int

class Assessment(AssessmentBase):
    id: int
    student_id: int
    class Config:
        from_attributes = True

# Finance
class FeeStructureBase(BaseModel):
    grade: Grade
    term: int
    amount: float

class FeeStructureCreate(FeeStructureBase):
    pass

class FeeStructure(FeeStructureBase):
    id: int
    class Config:
        from_attributes = True

class PaymentBase(BaseModel):
    amount: float

class PaymentCreate(PaymentBase):
    invoice_id: int

class Payment(PaymentBase):
    id: int
    invoice_id: int
    date: datetime
    receipt_number: str
    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    term: int
    total_amount: float

class InvoiceCreate(InvoiceBase):
    student_id: int

class Invoice(InvoiceBase):
    id: int
    student_id: int
    paid_amount: float
    created_at: datetime
    payments: List[Payment] = []
    class Config:
        from_attributes = True
