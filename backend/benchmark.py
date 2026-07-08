import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Student, FeeStructure
from students import get_student_profile

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def setup_data(db):
    student = Student(first_name="Test", last_name="Student", admission_number="BONA-0001", gender="M", date_of_birth=datetime.strptime("2010-01-01", "%Y-%m-%d").date(), grade_level="Grade 1", guardian_name="Parent", guardian_phone="123")
    db.add(student)
    db.commit()
    db.refresh(student)

    for term in ["Term 1", "Term 2", "Term 3"]:
        fs = FeeStructure(grade_level="Grade 1", term=term, fee_type="Tuition", academic_year=time.localtime().tm_year, amount=100.0)
        db.add(fs)
    db.commit()
    return student

class DummyUser:
    id = 1

def run_benchmark():
    db = SessionLocal()
    student = setup_data(db)

    # warmup
    get_student_profile(student.id, db, DummyUser())

    start = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        get_student_profile(student.id, db, DummyUser())
    end = time.perf_counter()

    duration = end - start
    print(f"Time for {iterations} iterations: {duration:.4f} seconds")
    print(f"Time per iteration: {duration / iterations * 1000:.4f} ms")

run_benchmark()
