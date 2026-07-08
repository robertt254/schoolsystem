import models
from database import SessionLocal
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
db = SessionLocal()

admin = models.User(username="admin", hashed_password=pwd_context.hash("password"), name="Admin", role="admin")
db.add(admin)
db.commit()
db.close()
