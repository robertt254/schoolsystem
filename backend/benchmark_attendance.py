import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models, schemas, attendance

# patch database.py so it uses sqlite for testing instead of postgres
import database
database.engine = create_engine("sqlite:///:memory:")
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
models.Base.metadata.create_all(bind=database.engine)

db = database.SessionLocal()

admin_user = models.User(id=1, username="admin", hashed_password="pw", name="Admin", role="admin")
db.add(admin_user)
db.commit()

for i in range(1, 10001):
    student = models.Student(id=i, first_name=f"First{i}", last_name=f"Last{i}", admission_number=f"ADM-{i}", grade_level="Grade 1", status="Active")
    db.add(student)
db.commit()

records = [
    schemas.AttendanceCreate(student_id=i, is_present=True, remarks="On time")
    for i in range(1, 10001)
]

start = time.time()
attendance.log_bulk_attendance(records=records, db=db, current_user=admin_user)
end = time.time()

print(f"BASELINE - Time taken to insert 10000 records: {end - start:.4f} seconds")

# test updates
records_update = [
    schemas.AttendanceCreate(student_id=i, is_present=False, remarks="Late")
    for i in range(1, 10001)
]

start2 = time.time()
attendance.log_bulk_attendance(records=records_update, db=db, current_user=admin_user)
end2 = time.time()
print(f"BASELINE - Time taken to update 10000 records: {end2 - start2:.4f} seconds")
