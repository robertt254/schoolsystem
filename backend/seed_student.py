from database import SessionLocal
import models
db = SessionLocal()
if not db.query(models.Student).first():
    db.add(models.Student(first_name="John", last_name="Doe", admission_number="BONA-0001", grade_level="Grade 1"))
    db.commit()
db.close()
