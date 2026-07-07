from pydantic import BaseModel
from typing import List, Optional

# Shared properties
class TeacherBase(BaseModel):
    name: str
    department: str

class TeacherCreate(TeacherBase):
    pass

class Teacher(TeacherBase):
    id: int

    class Config:
        from_attributes = True

# --- Course ---
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    teacher_id: int

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int

    class Config:
        from_attributes = True

# --- Student ---
class StudentBase(BaseModel):
    name: str
    email: str

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: int

    class Config:
        from_attributes = True

class TeacherWithCourses(Teacher):
    courses: List[Course] = []

class CourseWithDetails(Course):
    teacher: Teacher
    students: List[Student] = []

class StudentWithCourses(Student):
    courses: List[Course] = []
