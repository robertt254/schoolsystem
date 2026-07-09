# Bona School Kenya — School Management System

Full-stack CBC school management system for Bona School Kenya. FastAPI +
PostgreSQL backend, Vue 3 + Tailwind frontend. In production a single Docker
container serves both the API and the compiled SPA.

## Features

- **Authentication** — JWT login with rate limiting, role-based access
  (admin, principal, secretary, accountant, senior teacher; teachers and support
  staff are HR records without portal access), password change and reset.
- **Students** — admission (auto-generated admission numbers), search/filter,
  per-grade class rosters with headcounts and gender split, student profiles
  (attendance %, fee balance, assessments, payment history), soft delete with
  archive/restore, grade promotion and academic-year transition.
- **Academics (CBC)** — subjects per grade, strand-level assessment scores
  (EE/ME/AE/BE), grade/term score sheets, report card generation.
- **Exams** — bulk numeric exam results (CAT/mid/end-term), per-grade and
  per-student views, performance summaries.
- **Attendance** — bulk daily marking, per-student history, summaries.
- **Fees** — configurable per-grade/per-term fee structure (with yearly
  template), payment recording with atomic receipt numbers and waterfall
  allocation (oldest arrears first), carry-forward charges/credits, balances,
  defaulter lists, term and monthly collection reports, payment SMS
  notifications.
- **Finance** — payroll runs with payslips, expenses, budgets vs. actuals,
  petty cash ledger, finance dashboard.
- **HR** — staff records with contracts and statutory numbers (KRA/NSSF/NHIF),
  leave requests and approvals with entitlement tracking.
- **Library** — book catalogue, borrow/return with fines.
- **More** — school event calendar with configurable term dates, disciplinary
  records, SMS broadcasts, audit log of every write, dashboards, admin data
  reset.

## Local development

Backend (Python 3.11+, PostgreSQL):

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # set DATABASE_URL and SECRET_KEY
uvicorn main:app --reload --port 8000
```

On first boot with an empty database, a default admin account is seeded from
`ADMIN_USERNAME` / `ADMIN_INITIAL_PASSWORD`. If `ADMIN_INITIAL_PASSWORD` is
not set, a random password is generated and printed once in the server log —
there is no hardcoded default. Change the password immediately after logging in.

Frontend:

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, talks to the API on :8000
```

## Deploying to Render

The repo ships with [`render.yaml`](render.yaml) (Blueprint) and a multi-stage
[`Dockerfile`](Dockerfile) that builds the Vue frontend and serves it from the
FastAPI backend on one web service.

1. Push this repository to GitHub.
2. In Render: **New → Blueprint**, select the repo. Render provisions the
   `cbc-school-system` web service and the `cbc-school-db` PostgreSQL database
   from `render.yaml`.
3. `SECRET_KEY` and `ADMIN_INITIAL_PASSWORD` are auto-generated — read the
   admin password from the service's **Environment** tab, log in as `admin`,
   then change it.
4. If you rename the service, update the `ALLOWED_ORIGINS` env var to match
   the new `https://<service>.onrender.com` URL.

Health check endpoint: `GET /health`. API docs: `/docs`.

## Backups & moving to local hosting

The system snapshots **every table to a JSON backup every 24 hours** (last 7
kept) and the system administrator can create/download snapshots any time from
**Admin Tools → Data Backups**. Configure with `BACKUP_INTERVAL_HOURS`,
`BACKUP_KEEP`, `BACKUP_DIR`, `BACKUP_ENABLED`.

To migrate from Render to a locally hosted database:

1. Log in as the system admin and download the latest snapshot from
   Admin Tools → Data Backups.
2. On the local machine, point `DATABASE_URL` at the local database and run:

   ```bash
   DATABASE_URL=postgresql://user:pass@localhost/bona_local \
       python backend/restore_backup.py bns_backup_XXXXXXXXTXXXXXXZ.json --wipe
   ```

3. Start the backend against that same `DATABASE_URL` — all students, fees,
   staff, results and logs carry over, and PostgreSQL id sequences are advanced
   automatically.

Note: Render's free-tier disk is ephemeral, so snapshots on the server vanish
on redeploy — download the ones you want to keep. The live data itself is
always safe in Postgres.

## Security model notes

- There is exactly **one system administrator** (seeded at first boot). No
  user — including the admin — can create another admin, promote anyone to
  admin, change or terminate the admin account, or reset the admin's password.
  The admin changes their own password via Change Password.
- Admission numbers (`BNS-0001`, …) are system-generated, unique and immutable.
- Idle sessions are signed out automatically after 15 minutes.
