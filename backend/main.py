from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import os
import sys
from datetime import timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import models, schemas, crud, auth
from backend.database import engine, get_db

app = FastAPI(title="CBC School Management System API")

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # For development we sync create all. In production, use alembic
        await conn.run_sync(models.Base.metadata.create_all)

        # Create default admin user if none exists
        async with engine.connect() as conn:
            from sqlalchemy.orm import Session
            from backend.database import SessionLocal
            async with SessionLocal() as db:
                admin = await crud.get_user_by_username(db, "admin")
                if not admin:
                    await crud.create_user(db, schemas.UserCreate(username="admin", password="password", role=models.Role.ADMIN))

@app.get("/")
def read_root():
    return {"message": "Welcome to CBC School API"}

# --- Auth ---
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_username(db, form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

# --- Students ---
@app.post("/students/", response_model=schemas.Student)
async def create_student(
    student: schemas.StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.TEACHER]))
):
    return await crud.create_student(db=db, student=student)

@app.get("/students/", response_model=list[schemas.Student])
async def read_students(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.get_students(db, skip=skip, limit=limit)

# --- Teachers ---
@app.post("/teachers/", response_model=schemas.Teacher)
async def create_teacher(
    teacher: schemas.TeacherCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN]))
):
    return await crud.create_teacher(db=db, teacher=teacher)

@app.get("/teachers/", response_model=list[schemas.Teacher])
async def read_teachers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.get_teachers(db, skip=skip, limit=limit)

# --- Courses ---
@app.post("/courses/", response_model=schemas.Course)
async def create_course(
    course: schemas.CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.TEACHER]))
):
    return await crud.create_course(db=db, course=course)

@app.get("/courses/", response_model=list[schemas.Course])
async def read_courses(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.get_courses(db, skip=skip, limit=limit)

# --- Assessments ---
@app.post("/assessments/", response_model=schemas.Assessment)
async def create_assessment(
    assessment: schemas.AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.TEACHER]))
):
    return await crud.create_assessment(db=db, assessment=assessment)

@app.get("/students/{student_id}/assessments/", response_model=list[schemas.Assessment])
async def read_student_assessments(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return await crud.get_student_assessments(db=db, student_id=student_id)

# --- Finance ---
@app.post("/finance/fee_structures/", response_model=schemas.FeeStructure)
async def create_fee_structure(
    fee: schemas.FeeStructureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.FINANCE_OFFICER]))
):
    return await crud.create_fee_structure(db=db, fee=fee)

@app.post("/finance/invoices/", response_model=schemas.Invoice)
async def create_invoice(
    invoice: schemas.InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.FINANCE_OFFICER]))
):
    return await crud.generate_invoice(db=db, invoice=invoice)

@app.post("/finance/payments/", response_model=schemas.Payment)
async def process_payment(
    payment: schemas.PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.FINANCE_OFFICER]))
):
    db_payment = await crud.process_payment(db=db, payment=payment)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db_payment

@app.get("/finance/dashboard/")
async def get_finance_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_role([models.Role.ADMIN, models.Role.FINANCE_OFFICER]))
):
    return await crud.get_finance_dashboard_stats(db=db)
