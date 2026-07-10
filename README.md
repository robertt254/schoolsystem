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

## Hosting on your local network (LAN-only, no internet exposure)

Run the whole system on a school server with Docker:

```bash
# on the server, from the repo root — edit the passwords in docker-compose.yml first
docker compose up -d --build
```

Then, to reach it from **every computer on the LAN**:

1. Give the server a fixed address (a DHCP reservation on the router, or a
   static IP such as `192.168.1.50`).
2. Allow inbound TCP port 8000 in the server's firewall for the
   **private/local network profile only**.
3. Every LAN computer uses `http://192.168.1.50:8000` (bookmark it).

It stays **off the internet automatically** as long as you do not create a
port-forwarding/DMZ rule for the server on your router — that's the only way
LAN services become publicly reachable.

For **authorized remote computers** (e.g. the director working from home),
use a VPN instead of exposing the server:

- Install [Tailscale](https://tailscale.com) (free tier) on the server and on
  each authorized remote computer, signed into the same account.
- Remote machines then open `http://<server-tailscale-ip>:8000` — traffic is
  end-to-end encrypted WireGuard, and only devices you approved in the
  Tailscale admin console can connect. Nothing is opened on the router.

To migrate the data from Render: download the latest snapshot from
Admin Tools → Data Backups, then load it into the local database:

```bash
docker compose cp bns_backup_XXXX.json web:/tmp/backup.json
docker compose exec web python backend/restore_backup.py /tmp/backup.json --wipe
```

Local backups are written to a Docker volume every 24 h and survive rebuilds.

## Admin lockout recovery (forgot password)

If the system administrator cannot log in, whoever controls the hosting
environment (Render dashboard or the local server) can reset the password —
no email required:

1. Set the environment variable `ADMIN_RECOVERY_PASSWORD` to a temporary
   password (Render: service → Environment; local: uncomment it in
   `docker-compose.yml`).
2. Restart the service. The log prints the admin **username** and confirms
   the reset.
3. Log in with that temporary password, change it via **Change Password**,
   then **remove the variable** and restart again.

## Security model notes

- There is exactly **one system administrator** (seeded at first boot). No
  user — including the admin — can create another admin, promote anyone to
  admin, change or terminate the admin account, or reset the admin's password.
  The admin changes their own password via Change Password.
- Admission numbers (`BNS-0001`, …) are system-generated, unique and immutable.
- Idle sessions are signed out automatically after 15 minutes.
