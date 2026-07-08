import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

import auth
import admin
import models
import students
import fees
import staff
import academics
import attendance
import finance
import dashboard
import timetable
import leave
import sms_routes
import subjects
import exams
import library
import events
import discipline
from database import engine, SessionLocal
from limiter import limiter

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# Absolute path to the Vue build output — works regardless of CWD
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")

app = FastAPI(title="CBC School Management System API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Security headers ──────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:;"
    )
    return response


# ── CORS ─────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174")
origins = [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


# ── Startup: validate env, sync DB schema ────────────────────────────────────
@app.on_event("startup")
async def startup():
    required_vars = ["SECRET_KEY", "DATABASE_URL"]
    missing = [k for k in required_vars if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Cannot start — missing environment variables: {missing}")

    # Create new tables (create_all is a no-op for tables that already exist)
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database schema synced.")

    # Safely add columns that may be missing from tables created before these
    # columns were introduced (create_all does not ALTER existing tables).
    _safe_add_columns = [
        "ALTER TABLE users      ADD COLUMN IF NOT EXISTS created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS is_deleted     BOOLEAN     NOT NULL DEFAULT FALSE",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS guardian_name  VARCHAR(100)",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS guardian_phone VARCHAR(20)",
        "ALTER TABLE fees       ADD COLUMN IF NOT EXISTS receipt_number VARCHAR(20)",
        # term was added to the FeePayment model after the fees table existed on
        # older deploys; without this the entire finance ledger 500s in prod.
        "ALTER TABLE fees        ADD COLUMN IF NOT EXISTS term VARCHAR(10) NOT NULL DEFAULT 'Term 1'",
        "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS term VARCHAR(10) NOT NULL DEFAULT 'Term 1'",
        # Per-payment waterfall allocation breakdown (JSON) shown on receipts.
        "ALTER TABLE fees        ADD COLUMN IF NOT EXISTS allocation TEXT",
        "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS updated_at   TIMESTAMPTZ DEFAULT NOW()",
        # timetable & leave tables created via create_all; extra safety cols below
        "ALTER TABLE timetable       ADD COLUMN IF NOT EXISTS created_by   VARCHAR(100) NOT NULL DEFAULT 'system'",
        "ALTER TABLE leave_requests  ADD COLUMN IF NOT EXISTS reviewed_at  TIMESTAMPTZ",
        # extended student fields
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS date_of_birth   DATE",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS gender          VARCHAR(10)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian2_name  VARCHAR(100)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian2_phone VARCHAR(20)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS address         VARCHAR(200)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS previous_school VARCHAR(200)",
        # HR fields on users table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title         VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS contract_type     VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS date_of_hire      DATE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS kra_pin           VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nssf_number       VARCHAR(30)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nhif_number       VARCHAR(30)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS accrued_leave_days INTEGER NOT NULL DEFAULT 21",
        # payroll & expenses — backfill ALL cols that may be missing from older Render deploys
        "ALTER TABLE payroll  ADD COLUMN IF NOT EXISTS allowances   NUMERIC(10,2) NOT NULL DEFAULT 0",
        "ALTER TABLE payroll  ADD COLUMN IF NOT EXISTS deductions   NUMERIC(10,2) NOT NULL DEFAULT 0",
        "ALTER TABLE payroll  ADD COLUMN IF NOT EXISTS recorded_by  VARCHAR(100)  NOT NULL DEFAULT 'system'",
        "ALTER TABLE payroll  ADD COLUMN IF NOT EXISTS created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()",
        "ALTER TABLE expenses ADD COLUMN IF NOT EXISTS expense_date TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        # subjects table — created via create_all on newer deploys
        "ALTER TABLE subjects ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        # new feature tables — create_all handles structure; guard against col additions
        "ALTER TABLE exam_results       ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE library_books      ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE library_borrows    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE school_events      ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE disciplinary_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE budgets            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE petty_cash         ADD COLUMN IF NOT EXISTS transaction_date TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        # CBC assessment model — add academic_year and strand
        "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS academic_year VARCHAR(9) NOT NULL DEFAULT '2024'",
        "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS strand VARCHAR(100) NOT NULL DEFAULT ''",
        # Staff salary fields for automatic payroll
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS basic_salary NUMERIC(10,2) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS allowances   NUMERIC(10,2) NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS deductions   NUMERIC(10,2) NOT NULL DEFAULT 0",
        # Portal access flag — teachers and non-portal roles cannot log in
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_login BOOLEAN NOT NULL DEFAULT TRUE",
        # ── Performance indexes (safe to run multiple times) ──────────────────
        "CREATE INDEX IF NOT EXISTS idx_students_grade      ON students(grade_level)",
        "CREATE INDEX IF NOT EXISTS idx_students_deleted    ON students(is_deleted)",
        "CREATE INDEX IF NOT EXISTS idx_fees_student        ON fees(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_assessments_stterm  ON assessments(student_id, term, academic_year)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_student  ON attendance(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date     ON attendance(date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_std_date ON attendance(student_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_staff       ON payroll(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_staff_month ON payroll(staff_id, payment_month)",
        "CREATE INDEX IF NOT EXISTS idx_leave_staff         ON leave_requests(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_student        ON exam_results(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_std_term_year  ON exam_results(student_id, term, academic_year)",
        "CREATE INDEX IF NOT EXISTS idx_discipline_student  ON disciplinary_records(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp     ON audit_logs(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_fees_payment_date   ON fees(payment_date DESC)",
        # Atomic sequence for receipt numbers — replaces race-prone Python counter
        "CREATE SEQUENCE IF NOT EXISTS receipt_number_seq START 1",
        # Advance the sequence past any receipts that were inserted before the sequence existed.
        # setval(..., max_seq, false) means next nextval() returns max_seq+1.
        # The SPLIT_PART extracts the numeric suffix from 'BNS-YYYY-NNNNN'.
        """
        SELECT setval(
            'receipt_number_seq',
            COALESCE((
                SELECT MAX(
                    CAST(SPLIT_PART(receipt_number, '-', 3) AS INTEGER)
                )
                FROM fees
                WHERE receipt_number ~ '^BNS-[0-9]+-[0-9]+$'
            ), 0),
            false
        )
        """,
        # ── Unique constraints (will fail silently if duplicates exist) ────────
        # Use CREATE UNIQUE INDEX so the constraint is advisory; duplicates cause a
        # warning, not a server crash. Application-level checks prevent new dupes.
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_payroll_staff_month "
        "  ON payroll(staff_id, payment_month) WHERE staff_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fee_structure_entry "
        "  ON fee_structure(grade_level, term, fee_type, academic_year)",
        # audit_logs.detail: ALTER TYPE not needed — Text is compatible with VARCHAR
        "ALTER TABLE audit_logs ALTER COLUMN detail TYPE TEXT",
    ]
    # Run each migration statement independently so one failure doesn't block others.
    with engine.connect() as conn:
        for stmt in _safe_add_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.warning("Migration step skipped (may be harmless): %.80s — %s", stmt, exc)

        # One-time: revoke portal access for any existing non-portal role accounts
        try:
            conn.execute(text(
                "UPDATE users SET can_login = FALSE "
                "WHERE role NOT IN ('principal','secretary','accountant','admin','senior_teacher') "
                "AND can_login = TRUE"
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("Portal-access update skipped: %s", exc)

    logger.info("Schema migration checks complete.")

    # First boot: seed a default admin account when no users exist yet so a
    # fresh deployment is immediately usable. Change the password after login.
    try:
        with SessionLocal() as db:
            if db.query(models.User).count() == 0:
                admin_username = os.getenv("ADMIN_USERNAME", "admin")
                admin_password = os.getenv("ADMIN_INITIAL_PASSWORD", "ChangeMe@1234")
                db.add(models.User(
                    username=admin_username,
                    hashed_password=auth.get_password_hash(admin_password),
                    name="System Administrator",
                    role="admin",
                ))
                db.commit()
                logger.info("Seeded default admin account '%s'.", admin_username)
    except Exception as exc:
        logger.warning("Admin seed skipped: %s", exc)

    if os.path.exists(FRONTEND_DIST):
        logger.info("Frontend dist found at %s", FRONTEND_DIST)
    else:
        logger.warning("Frontend dist NOT found at %s — SPA will not be served", FRONTEND_DIST)


# ── API routers (must be registered BEFORE the SPA catch-all) ────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(students.router)
app.include_router(fees.router)
app.include_router(staff.router)
app.include_router(academics.router)
app.include_router(attendance.router)
app.include_router(finance.router)
app.include_router(dashboard.router)
app.include_router(timetable.router)
app.include_router(leave.router)
app.include_router(sms_routes.router)
app.include_router(subjects.router)
app.include_router(exams.router)
app.include_router(library.router)
app.include_router(events.router)
app.include_router(events.cal_router)
app.include_router(discipline.router)
app.include_router(admin.router)


# ── Health check (used by Render's healthCheckPath) ───────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    db_status = "unknown"
    db_error = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)
    return {
        "status": "online",
        "system": "Bona School Backend API",
        "db": db_status,
        **({"db_error": db_error} if db_error else {}),
    }


# ── Serve Vite-built frontend static assets ───────────────────────────────────
_assets_dir = os.path.join(FRONTEND_DIST, "assets")
if os.path.exists(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="static-assets")


# ── SPA catch-all: serve index.html for every non-API route ──────────────────
# This MUST be the last route registered so it doesn't shadow any API endpoint.
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # Let unmatched /api/* calls return 404 instead of HTML
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built. Run npm run build.")
