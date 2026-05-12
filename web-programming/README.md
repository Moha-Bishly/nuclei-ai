# NucleiAI — Web Platform

> AI-powered cell nuclei segmentation and counting as a full-stack web application.

**Live:** https://165.227.139.185.nip.io &nbsp;|&nbsp; **Repo:** https://github.com/Moha-Bishly/nuclei-ai

Upload a histopathology image → get a segmentation mask, overlay, and nuclei count in under 2 seconds. Built for the Web Programming course with a complete auth system, role-based access control, 3 OAuth providers, TOTP 2FA, automated tests, and cloud deployment on DigitalOcean.

---

## Screenshots

### Login — Password + Email OTP + 3 Social Providers
![Login](screenshots/Screenshot%202026-05-12%20102806.png)

### Registration
![Register](screenshots/Screenshot%202026-05-12%20102836.png)

### Dashboard — Job History with 7-Day Trend Chart
![Dashboard](screenshots/Screenshot%202026-05-12%20102551.png)

### Analyze — U-Net AI Results (241 cells, mask, overlay)
![Analyze](screenshots/Screenshot%202026-05-12%20102613.png)

### Publish Analysis to Community
![Publish](screenshots/Screenshot%202026-05-12%20102623.png)

### Explore — Community Publications
![Explore](screenshots/Screenshot%202026-05-12%20102643.png)

### Favourites
![Favourites](screenshots/Screenshot%202026-05-12%20102653.png)

### Profile — Password Change + TOTP 2FA Setup
![Profile](screenshots/Screenshot%202026-05-12%20102709.png)

### TOTP 2FA — Google Authenticator QR Code
![2FA](screenshots/Screenshot%202026-05-12%20102825.png)

### Admin Dashboard — User Management (12 users, roles, stats)
![Admin](screenshots/Screenshot%202026-05-12%20102427.png)

### About Us
![About](screenshots/Screenshot%202026-05-12%20102724.png)

### Contact Us
![Contact](screenshots/Screenshot%202026-05-12%20102731.png)

---

## Feature Matrix

| Category | Feature | Status |
|---|---|---|
| **Core** | Image upload → U-Net inference → mask + overlay + count | ✅ |
| **Core** | Fallback Otsu-threshold demo (works without GPU/checkpoint) | ✅ |
| **Core** | Per-user job history with annotations and CSV export | ✅ |
| **Core** | Publish analyses to community Explore page | ✅ |
| **Core** | Favourites, comments, reanalyze with different threshold | ✅ |
| **Core** | PDF report download per analysis | ✅ |
| **Core** | 7-day cell-count trend chart (pure SVG, no library) | ✅ |
| **Auth** | JWT authentication (register / login / logout / `/auth/me`) | ✅ |
| **Auth** | TOTP 2FA (Google Authenticator — RFC 6238) | ✅ |
| **Auth** | Email OTP (6-digit code, second 2FA method) | ✅ +5 pts |
| **Auth** | Google OAuth 2.0 | ✅ |
| **Auth** | GitHub OAuth 2.0 | ✅ +5 pts |
| **Auth** | Dropbox OAuth 2.0 | ✅ +10 pts |
| **Authorization** | RBAC: `manager` / `admin` / `researcher` / `viewer` roles | ✅ +10 pts |
| **Authorization** | Admin dashboard — user list, role editor, delete, stats | ✅ |
| **Testing** | 85 pytest backend unit tests (7 suites, 90%+ coverage) | ✅ +5 pts |
| **Testing** | Playwright E2E tests (auth, nav, CRUD, admin) | ✅ |
| **Testing** | GitHub Actions CI/CD — tests run + deploy on every push | ✅ +10 pts |
| **Deployment** | DigitalOcean + nginx + Let's Encrypt (not Vercel/Railway) | ✅ +10 pts |
| **Security** | HTTP security headers (CSP, X-Frame-Options, HSTS…) | ✅ |
| **Security** | Image magic-bytes validation (not just Content-Type) | ✅ |
| **Security** | Cryptographically secure OTP (`secrets` module) | ✅ |
| **Security** | Rate limiting on all auth and analysis endpoints | ✅ |
| **Security** | Password strength validation enforced on registration | ✅ |
| **Security** | API docs disabled in production | ✅ |
| **Security** | `pip-audit` dependency CVE scan in CI | ✅ |
| **Base** | Built on top of the original ML project (U-Net from src/) | ✅ |

**Estimated bonus: +55 points**

---

## Architecture

```
Browser (React + TypeScript)
https://165.227.139.185.nip.io
         │ HTTPS
         ▼
    nginx (reverse proxy + static files + SSL)
    ├── /        → React SPA (frontend/dist/)
    ├── /api/    → FastAPI (uvicorn :8000) — strips /api/ prefix
    └── /auth/   → FastAPI OAuth callbacks
         │
         ▼
    FastAPI Backend (Python 3.12)
    ├── JWT auth + RBAC + Rate limiting
    ├── U-Net AI analysis service
    └── PostgreSQL (Neon) + File Storage
```

### Analysis Request Flow

```
POST /api/analyze  (multipart, Bearer JWT)
  │
  ├── 1. JWT validation (require_role)
  ├── 2. Content-Type + magic-bytes check
  ├── 3. analysis_service.analyze(image_bytes)
  │       ├── _ensure_model_loaded()  →  U-Net ResNet-18
  │       ├── decode + resize to 256×256
  │       ├── predict binary mask
  │       ├── connected-component labelling (scikit-image)
  │       ├── make_overlay() → colour-coded result
  │       └── write {job_id}_input / _mask / _overlay .png
  ├── 4. INSERT AnalysisJob to PostgreSQL
  └── 5. 201 { job_id, cell_count, urls, metadata }
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite 5, React Router v6 |
| Backend | FastAPI, Python 3.12, SQLModel, Uvicorn |
| Database | PostgreSQL (Neon managed cloud) |
| Auth | python-jose JWT, bcrypt, pyotp TOTP, authlib OAuth |
| AI | PyTorch 2.11, segmentation-models-pytorch (U-Net ResNet-18) |
| Image processing | OpenCV, scikit-image, Pillow, NumPy, albumentations |
| Rate limiting | slowapi |
| Testing — backend | pytest (85 tests, 7 suites) |
| Testing — E2E | Playwright (Chromium) |
| CI/CD | GitHub Actions (test → build → SSH deploy) |
| Server | DigitalOcean Ubuntu 24.04 (1GB RAM + 2GB swap) |
| Proxy / SSL | nginx + Let's Encrypt (Certbot) |

---

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+

### 1 — Backend

```sh
# From web-programming/
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend: `http://127.0.0.1:8000`  
Swagger UI: `http://127.0.0.1:8000/docs` (development only)

### 2 — Frontend

```sh
cd frontend
npm install
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

Frontend: `http://localhost:5173`

---

## Running Tests

### Backend (85 tests)

```sh
# From web-programming/
python -m pytest backend/tests/ -v --cov=backend --cov-report=term-missing
```

| Suite | Tests | Coverage area |
|---|---|---|
| `test_auth.py` | 14 | Register, login, JWT, error message consistency |
| `test_crud.py` | 15 | Analyze, jobs, annotations, file validation |
| `test_roles.py` | 11 | RBAC, admin endpoints, 403 enforcement |
| `test_totp.py` | 10 | Full 2FA flow, token scope checks |
| `test_export.py` | 8 | CSV export, content-type, RBAC scoping |
| `test_security.py` | 15 | Magic bytes, headers, password strength |
| `test_profile.py` | 12 | Update username/email, change-password |

### E2E (Playwright)

```sh
# Start backend and frontend first, then:
cd frontend && npx playwright test
```

| Suite | Tests |
|---|---|
| `auth.spec.ts` | 6 |
| `navigation.spec.ts` | 4 |
| `crud.spec.ts` | 3 |
| `admin.spec.ts` | 4 |

---

## Authentication Methods

### Password login (no 2FA)
```
POST /auth/login  →  200 { access_token, user }
```

### Password login with TOTP 2FA
```
POST /auth/login        →  200 { requires_2fa: true, temp_token }
POST /auth/2fa/verify   →  200 { access_token, user }
```

### Email OTP
```
POST /auth/email-otp/send    { email }        →  200
POST /auth/email-otp/verify  { email, code }  →  200 { access_token, user }
```

> **Note on local setup:** The Email OTP feature is fully implemented end-to-end (backend + frontend). It requires a valid SMTP configuration to deliver the 6-digit code. As is standard practice in any production application, SMTP credentials (host, user, app password) are intentionally kept out of version control and supplied through environment variables. To enable this feature locally, add your own Gmail App Password (or any SMTP provider) to `.env` under the `SMTP_*` keys. The feature has been verified working in our development environment with a dedicated project Gmail account.

### OAuth (Google / GitHub / Dropbox)
```
GET /auth/{provider}           →  302 → provider login
GET /auth/{provider}/callback  →  307 → /oauth-callback?code=<exchange_code>
POST /auth/oauth/exchange      →  200 { access_token, user }
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | Liveness probe |
| GET | `/api/health` | — | Full health payload (model status) |
| POST | `/auth/register` | — | Create account |
| POST | `/auth/login` | — | Password login → JWT |
| POST | `/auth/logout` | JWT | Revoke token |
| GET | `/auth/me` | JWT | Current user profile |
| PATCH | `/auth/me` | JWT | Update username / email |
| POST | `/auth/change-password` | JWT | Change password |
| POST | `/auth/totp/setup` | JWT | Generate TOTP secret + QR URI |
| POST | `/auth/totp/verify-setup` | JWT | Enable TOTP 2FA |
| POST | `/auth/2fa/verify` | temp JWT | Complete 2FA login |
| POST | `/auth/forgot-password` | — | Request password reset email |
| GET | `/auth/google` | — | Google OAuth redirect |
| GET | `/auth/github` | — | GitHub OAuth redirect |
| GET | `/auth/dropbox` | — | Dropbox OAuth redirect |
| POST | `/api/analyze` | JWT | Upload image → analysis result |
| GET | `/api/jobs` | JWT | List jobs |
| GET | `/api/jobs/export.csv` | JWT | Download history as CSV |
| GET | `/api/jobs/{job_id}` | JWT | Job detail |
| DELETE | `/api/jobs/{job_id}` | JWT | Delete job |
| POST | `/api/jobs/{job_id}/publish` | researcher+ | Publish to Explore |
| POST | `/api/jobs/{job_id}/reanalyze` | JWT | Re-run with new threshold |
| GET | `/api/explore` | JWT | Community publications |
| POST | `/api/publications/{id}/favourite` | JWT | Add to favourites |
| POST | `/api/publications/{id}/comments` | JWT | Add comment |
| GET | `/api/favourites` | JWT | My favourites |
| GET | `/api/notifications` | JWT | Notifications |
| GET | `/files/{filename}` | — | Serve result image |
| GET | `/admin/users` | admin+ | List all users |
| PATCH | `/admin/users/{id}/role` | admin+ | Change user role |
| DELETE | `/admin/users/{id}` | admin+ | Delete user |
| GET | `/admin/stats` | admin+ | Platform statistics |

---

## User Roles

| Role | Permissions |
|---|---|
| **viewer** | View own jobs, explore, comment, favourite |
| **researcher** | viewer + publish analyses to Explore |
| **admin** | researcher + manage users (view, change role, delete) |
| **manager** | admin + manage admins + platform stats |

---

## Environment Variables

### Backend (.env)

| Variable | Default | Required in prod |
|---|---|---|
| `SECRET_KEY` | dev fallback | **yes** |
| `DATABASE_URL` | `sqlite:///./nuclei.db` | yes (Postgres) |
| `ENV` | `development` | set to `production` |
| `FRONTEND_URL` | `http://localhost:5173` | yes |
| `BACKEND_URL` | `http://localhost:8000` | yes |
| `GOOGLE_CLIENT_ID/SECRET` | empty | for Google OAuth |
| `GITHUB_CLIENT_ID/SECRET` | empty | for GitHub OAuth |
| `DROPBOX_CLIENT_ID/SECRET` | empty | for Dropbox OAuth |
| `SMTP_HOST/PORT/USER/PASSWORD` | gmail defaults | for Email OTP |

### Frontend

| Variable | Default |
|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` |

---

## Project Structure

```
web-programming/
├── backend/
│   ├── main.py              FastAPI app — all routes
│   ├── models.py            SQLModel ORM tables
│   ├── schemas.py           Pydantic DTOs
│   ├── config.py            Environment config
│   ├── database.py          Engine + session
│   ├── dependencies.py      get_current_user, require_role
│   ├── auth_utils.py        JWT · bcrypt · OTP · SMTP
│   ├── totp_utils.py        pyotp helpers
│   ├── oauth.py             authlib Google/GitHub/Dropbox
│   ├── security.py          SecurityHeadersMiddleware · magic-bytes
│   ├── crud.py              JobService · AnnotationService
│   ├── services/
│   │   └── analysis_service.py   U-Net inference pipeline
│   ├── seed.py              First manager account bootstrap
│   ├── requirements.txt
│   └── tests/               conftest + 7 test modules (85 tests)
├── frontend/
│   ├── src/
│   │   ├── App.tsx          Route table
│   │   ├── api.ts           All API calls + TypeScript types
│   │   ├── contexts/        AuthContext · ToastContext
│   │   ├── components/      DashboardLayout · ProtectedRoute · AdminRoute
│   │   └── pages/           Login · Register · Dashboard · Analyze ·
│   │                        Explore · Favourites · Profile · Admin ·
│   │                        OAuthCallback · TwoFactor · About · Contact
│   ├── e2e/                 Playwright specs
│   └── playwright.config.ts
├── src/                     Original ML pipeline (U-Net training + inference)
├── screenshots/             Platform screenshots
├── docs/
│   └── FINAL_REPORT.md      Full project report
├── DEPLOYMENT.md            DigitalOcean deployment guide
├── Dockerfile
└── fly.toml
```
