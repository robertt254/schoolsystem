from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from . import models, schemas, auth
import uuid
from datetime import datetime

# Users
async def get_user_by_username(db: AsyncSession, username: str):
    stmt = select(models.User).filter(models.User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password, role=user.role)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

# Students
async def get_students(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(models.Student).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_student(db: AsyncSession, student: schemas.StudentCreate):
    db_student = models.Student(**student.model_dump())
    db.add(db_student)
    await db.commit()
    await db.refresh(db_student)
    return db_student

# Teachers
async def get_teachers(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(models.Teacher).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_teacher(db: AsyncSession, teacher: schemas.TeacherCreate):
    db_teacher = models.Teacher(**teacher.model_dump())
    db.add(db_teacher)
    await db.commit()
    await db.refresh(db_teacher)
    return db_teacher

# Courses
async def get_courses(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(models.Course).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_course(db: AsyncSession, course: schemas.CourseCreate):
    db_course = models.Course(**course.model_dump())
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course

# Assessments
async def create_assessment(db: AsyncSession, assessment: schemas.AssessmentCreate):
    db_assessment = models.Assessment(**assessment.model_dump())
    db.add(db_assessment)
    await db.commit()
    await db.refresh(db_assessment)
    return db_assessment

async def get_student_assessments(db: AsyncSession, student_id: int):
    stmt = select(models.Assessment).filter(models.Assessment.student_id == student_id)
    result = await db.execute(stmt)
    return result.scalars().all()

# Finance
async def create_fee_structure(db: AsyncSession, fee: schemas.FeeStructureCreate):
    db_fee = models.FeeStructure(**fee.model_dump())
    db.add(db_fee)
    await db.commit()
    await db.refresh(db_fee)
    return db_fee

async def generate_invoice(db: AsyncSession, invoice: schemas.InvoiceCreate):
    db_invoice = models.Invoice(**invoice.model_dump())
    db.add(db_invoice)
    await db.commit()
    await db.refresh(db_invoice)
    return db_invoice

async def process_payment(db: AsyncSession, payment: schemas.PaymentCreate):
    # Fetch invoice
    stmt = select(models.Invoice).filter(models.Invoice.id == payment.invoice_id)
    result = await db.execute(stmt)
    db_invoice = result.scalar_one_or_none()

    if not db_invoice:
        return None

    # Update invoice paid amount
    db_invoice.paid_amount += payment.amount

    # Create payment record
    receipt = f"RCPT-{uuid.uuid4().hex[:8].upper()}"
    db_payment = models.Payment(
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        receipt_number=receipt
    )
    db.add(db_payment)
    await db.commit()
    await db.refresh(db_payment)
    return db_payment

async def get_finance_dashboard_stats(db: AsyncSession):
    # Get total expected (sum of all invoices)
    invoices_stmt = select(models.Invoice)
    invoices_result = await db.execute(invoices_stmt)
    invoices = invoices_result.scalars().all()

    total_expected = sum(inv.total_amount for inv in invoices)
    total_collected = sum(inv.paid_amount for inv in invoices)
    outstanding_balance = total_expected - total_collected

    return {
        "total_expected": total_expected,
        "total_collected": total_collected,
        "outstanding_balance": outstanding_balance
    }
