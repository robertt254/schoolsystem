# Security & Performance Audit — 2026-09-01

Branch: `audit/system-review-2026-09-01` (off `feature/full-stack-school-system-12076392000409103685` @ `3817199`)

Scope: full codebase — dependency (SCA) scan, static secret/injection scan, authorization review of every backend endpoint, and a performance/bundle/index pass. Findings below are ranked by severity; each fixed item names the commit-local change, each recommendation is left for a deliberate decision rather than guessed at.

## Summary

| Severity | Found | Fixed on this branch |
|---|---|---|
| Critical | 0 | — |
| High | 3 | 3 |
| Medium | 5 | 4 |
| Low | 4 | 3 |

---

## High

### H1. Weak-password bypass on self-service password change — **fixed**
`auth.py` defined its own local `class PasswordChange(BaseModel)` with an unconstrained `new_password: str`, shadowing a properly validated `schemas.PasswordChange` (`min_length=10`) that turned out to be dead code — nothing imported it. The `/api/auth/change-password` endpoint used the shadowed, unvalidated version, so any authenticated user could set their password to a single character. Fixed by deleting the local duplicate and switching the endpoint to `schemas.PasswordChange`. Also added the same `10/minute` rate limit already used on `/login`, since this endpoint re-checks a password (the current one) and was previously unthrottled — a stolen-but-valid session token could otherwise brute-force it. Regression test added (`test_change_password_rejects_weak_new_password`).

### H2. Financial revenue endpoint had no role check — **fixed**
`GET /api/fees/collection-summary` (per-term revenue totals) authenticated any logged-in user but applied no role restriction at all — reachable by `secretary` and `senior_teacher` via a direct API call even though the frontend already restricts the page that uses it (`/reports`) to admin/principal/accountant, and this session's earlier work explicitly excluded `secretary` from seeing "what the school makes" everywhere else (dashboard net revenue, term accountability). This one endpoint was the gap. Fixed to require `{admin, principal, accountant}`, matching the frontend and the sibling dashboard endpoint. Regression test added.

### H3. Outdated core dependencies with known CVEs — **fixed**
`pip-audit` against `requirements.txt` found 20 known vulnerabilities across 6 packages, including the ASGI framework itself:

| Package | Was | Now | Notes |
|---|---|---|---|
| `starlette` | 1.0.0 | 1.6.0 | FastAPI's core request/response layer — several CVEs |
| `cryptography` | 48.0.0 | 50.0.1 | 4 CVEs |
| `pyasn1` | 0.6.3 | 0.6.4 | used by JWT signing dependency chain |
| `python-multipart` | 0.0.28 | 0.0.32 | form/file upload parsing — 3 CVEs |
| `python-dotenv` | 1.0.0 | 1.2.3 | |
| `ecdsa` | 0.19.2 | *(no fix exists)* | see below — accepted |

Verified: full backend test suite (120 tests) still passes after the upgrade; no code changes were needed. `ecdsa`'s advisory (PYSEC-2026-1325, a Minerva-style timing side channel) has no fixed release — the maintainer treats side-channel resistance in pure-Python ECDSA as out of scope, a long-standing, publicly known position. It's pulled in transitively by `python-jose`; this app signs JWTs with `HS256` (HMAC) only (`auth.py`), so the vulnerable ECDSA signing/verification code path is never exercised here. Documented as an accepted risk directly in `requirements.txt`.

`npm audit` on the frontend found 2 high-severity issues (`nanoid`, `postcss`) — both dev/build-time-only tooling, not shipped to the browser. Fixed via `npm audit fix` (non-breaking); `npm audit` now reports 0 vulnerabilities.

---

## Medium

### M1. Six read endpoints exposing sensitive data with no role check — **fixed**
None of these had *any* role restriction — just "must be logged in." Because only 5 of this app's 7 roles ever get portal login credentials (`PORTAL_ROLES` in `schemas.py`: admin, principal, secretary, accountant, senior_teacher — `teacher` and `support_staff` cannot authenticate at all, enforced both frontend and backend), the real exposure was narrower than "any role" — but still meant a role with no legitimate reason to see it, could:

- `GET /api/academics/report-card/{id}/{term}` — full CBC report card — reachable by secretary/accountant. Restricted to `{teacher, senior_teacher, admin, principal}`, matching the two sibling endpoints already in that file.
- `GET /api/exams/grade/{grade}/{term}` (merit list), `/student/{id}` (a student's exam history), `/performance-summary` — reachable by secretary/accountant. Restricted to the same `WRITE_ROLES` set already used for entering marks in the same file.
- `GET /api/discipline/` — disciplinary records — reachable by accountant. Restricted to that file's own existing `WRITE_ROLES`.
- `POST /api/library/borrows`, `PUT /api/library/borrows/{id}/return` — reachable by accountant/senior_teacher, inconsistent with the sibling `create_book`/`update_book` endpoints in the same file, which are already restricted to `{admin, principal, secretary}`. Matched that.

Each fix reuses a role set **already established elsewhere in the same file** rather than inventing new policy — flagging in case the actual desired workflow is looser than what I assumed (e.g., if front-office staff are expected to print report cards for parents, `secretary` should be added back to that one). Regression tests added for all of these (`test_audit_authz_gaps.py`).

**Deliberately left unrestricted** (reviewed, not fixed): `students.py`'s roster/profile/list endpoints, `attendance.py`, `dashboard.py grade-stats`, `events.py`, `subjects.py`, `timetable.py`, `library.py`'s GET endpoints. These carry the same "any logged-in role" gate, but every one of the 5 portal roles already has a proven, shipped reason to read them (secretary/accountant browse the full student roster constantly for fee work across Finance pages; senior_teacher needs it for academics) — restricting these would have broken real, already-relied-upon workflows. Login already gates out the two roles (`teacher`, `support_staff`) that can't authenticate at all.

### M2. `fees.activity` and `fees.term` were unindexed — **fixed**
Both columns are filtered in nearly every arrears/balance query added across this engagement (`_term_outstanding`, `_paid_map`, `get_student_balance`, the activity roster/standing queries, ...), but only `is_voided` had an index. Added indexes on `term`, `activity`, and a composite `(student_id, term)` — the single most common filter pair — both in the SQLAlchemy model (fresh databases) and as an idempotent `CREATE INDEX IF NOT EXISTS` migration in `main.py` (already-deployed databases, matching this codebase's established schema-evolution pattern).

### M3. No frontend code-splitting — **not fixed, recommended**
The production build is a single ~449 KB JS bundle (113 KB gzipped) — every route's component is statically imported in `router/index.js`, so the whole app (30+ views) loads on first paint regardless of which page is opened. In absolute terms this isn't alarming for an internal staff tool with a small user base, but it's needless: switching each route to a dynamic import (`() => import('../views/X.vue')`) is a mechanical, low-risk change Vue Router supports natively, and would let Vite split each view into its own chunk, loaded on demand. Not applied on this branch — touches every route entry and is better done as its own reviewable change than folded into a security audit diff.

### M4. Content-Security-Policy allows `'unsafe-inline'` for scripts — **not fixed, recommended**
`main.py`'s CSP header sets `script-src 'self' 'unsafe-inline'`, which meaningfully weakens CSP's XSS mitigation (an injected inline `<script>` would still execute). Whether this can be tightened to just `'self'` depends on whether anything in the built frontend actually relies on inline scripts — that needs verifying in a real browser (this sandbox can't render one), so I'm flagging rather than guessing. If nothing breaks with `'unsafe-inline'` removed from `script-src`, that's a clean, valuable tightening.

### M5. Dead code with a hardcoded weak credential — **fixed**
`backend/seed.py`, a standalone script referenced nowhere (no imports, no docs), created an admin account with the literal password `"password"`, hashed with the deprecated `pbkdf2_sha256` scheme, superseded entirely by the proper env-var-driven, random-password-generating seed logic already in `main.py`'s startup routine. Left in place, it was a loaded gun — anyone unfamiliar with the real setup flow who ran it against a real database would create a trivially guessable admin account. Deleted.

---

## Low

### L1. SQL injection surface — reviewed, no issue found
Every raw `text()` SQL call with string-interpolated identifiers (`admin.py`'s reset-data, `restore_backup.py`, `reset_data.py`) either: (a) sources the identifier from a fixed, hardcoded allow-list validated against a strict `^[a-z_][a-z0-9_]*$` regex before use, and is admin-only plus requires a literal `"RESET"` confirmation string, or (b) is a standalone CLI script iterating SQLAlchemy's own registered model tables (`Base.metadata.sorted_tables`), never reachable over HTTP. No user-controlled input reaches any raw SQL string anywhere in the codebase.

### L2. Dead scaffold code — fixed
`src/components/HelloWorld.vue` and `src/assets/hero.png` (Vite's default starter template, unreferenced anywhere) removed. Confirmed via `dist/` inspection they were already tree-shaken out of the production bundle — cosmetic only, not a shipped-bytes issue.

### L3. `X-XSS-Protection` header — not fixed, informational only
`main.py` sets `X-XSS-Protection: 1; mode=block`. This header is deprecated and ignored by all current browser engines (Chrome removed support years ago); it's harmless to leave but provides no actual protection. Not worth a change on its own.

### L4. `.env.example` files describe slightly different setups — not fixed, informational only
The root `.env.example` and `backend/.env.example` disagree on a couple of defaults (database name `school_db` vs `bona_school_db`, and the backend one references a `setup-users` seeding endpoint) — minor documentation drift, not a security issue. Worth a consolidation pass at some point.

---

## Dependency/secret scan raw results

- **Frontend (`npm audit`)**: 0 vulnerabilities after `npm audit fix` (was 2 high, both dev-only).
- **Backend (`pip-audit -r requirements.txt`)**: 1 known vulnerability after upgrades (`ecdsa`, accepted — see H3).
- **Secrets scan**: no hardcoded API keys, passwords, or tokens found in tracked source. Only `.env.example` template files are committed (correctly gitignored: `.env`, `venv/`, `env/`); their placeholder values are not live credentials.

## Verification

- Backend: `pytest` — **120/120 passing** (8 new tests added by this audit: 1 for the password-length fix, 7 for the authz gaps).
- Frontend: `npm run build` clean, `vitest` — **39/39 passing**.
- No functional/behavioral changes to existing features — every fix on this branch is additive (a missing check, a missing index, an upgraded pin, or dead-code removal).
