import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLEnum, Float, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Role(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    FINANCE_OFFICER = "finance_officer"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(Role), nullable=False)

    teacher_profile = relationship("Teacher", back_populates="user", uselist=False)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    department = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="teacher_profile")
    courses = relationship("Course", back_populates="teacher")

class Grade(str, enum.Enum):
    PLAY_GROUP = "Play Group"
    PP1 = "PP1"
    PP2 = "PP2"
    GRADE_1 = "Grade 1"
    GRADE_2 = "Grade 2"
    GRADE_3 = "Grade 3"
    GRADE_4 = "Grade 4"
    GRADE_5 = "Grade 5"
    GRADE_6 = "Grade 6"

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    admission_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True)
    grade = Column(SQLEnum(Grade), nullable=False)
    guardian_contact = Column(String)

    courses = relationship("Course", secondary="student_course", back_populates="students")
    assessments = relationship("Assessment", back_populates="student")
    invoices = relationship("Invoice", back_populates="student")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    grade_level = Column(SQLEnum(Grade), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"))

    teacher = relationship("Teacher", back_populates="courses")
    students = relationship("Student", secondary="student_course", back_populates="courses")

class StudentCourse(Base):
    __tablename__ = 'student_course'
    student_id = Column(Integer, ForeignKey('students.id'), primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), primary_key=True)

# CBC Assessment Model
class CBCLevel(str, enum.Enum):
    EE = "Exceeding Expectation"
    ME = "Meeting Expectation"
    AE = "Approaching Expectation"
    BE = "Below Expectation"

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    term = Column(Integer, nullable=False)  # 1, 2, or 3
    outcome = Column(String, nullable=False) # e.g., "Identifies shapes correctly"
    level = Column(SQLEnum(CBCLevel), nullable=False)

    student = relationship("Student", back_populates="assessments")
    course = relationship("Course")

# Finance Models
class FeeStructure(Base):
    __tablename__ = "fee_structures"
    id = Column(Integer, primary_key=True, index=True)
    grade = Column(SQLEnum(Grade), nullable=False)
    term = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    term = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    receipt_number = Column(String, unique=True, index=True)

    invoice = relationship("Invoice", back_populates="payments")
