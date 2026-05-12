# NucleiAI — Final Project Report

**AI-Powered Microscopy Analysis System for Nuclei Segmentation and Cell Counting**

**Live URL:** https://165.227.139.185.nip.io  
**Repository:** https://github.com/Moha-Bishly/nuclei-ai  
**University:** Istinye University | **Course:** Web Programming | **Date:** May 2026

---

## 1. Executive Summary

NucleiAI is a fully deployed, production-ready web platform that uses artificial intelligence to automatically segment and count cell nuclei in histopathology microscopy images. A researcher uploads a microscopy image and receives within seconds a precise cell nucleus count, a segmentation mask, a colour-coded overlay, and a downloadable PDF report — all powered by a custom-trained U-Net deep learning model running on a DigitalOcean cloud server.

The platform is live at **https://165.227.139.185.nip.io** with full HTTPS, role-based access control, three OAuth providers, TOTP two-factor authentication, automated CI/CD, and Playwright end-to-end tests.

---

## 2. Grading Criteria Coverage

### 2.1 Code Correctness and Topic Inclusions (25%)

The project implements every core web programming topic:

**Full-stack architecture:**
- React 18 + TypeScript frontend (Vite build tool, React Router v6)
- FastAPI Python backend with SQLModel ORM and Pydantic validation
- PostgreSQL database hosted on Neon (managed cloud Postgres)
- REST API with proper HTTP methods, status codes, and JSON responses

**Authentication system (complete):**
- User registration with strong password validation (uppercase, lowercase, digit, special character required)
- JWT-based login returning signed access tokens (HS256, 60-minute expiry)
- Token revocation on logout via in-memory blacklist
- Password change with current-password verification
- Password reset via secure token email flow

**AI integration:**
- U-Net model (ResNet-18 encoder, trained on histopathology data) performs real segmentation
- Full inference pipeline: load → preprocess → predict → threshold → connected-component labelling → count → overlay generation
- Results persisted to database and files served back to the frontend

**Data persistence:**
- Every analysis is stored as an `AnalysisJob` record (job ID, cell count, file URLs, metadata)
- Users, publications, comments, favourites, annotations, and notifications all stored in PostgreSQL
- CSV export of full job history

**Frontend features:**
- Dashboard with 7-day trend chart (pure SVG, no charting library)
- Explore page — community-published analyses with search and filter
- Favourites, comments, publish-to-community workflow
- Admin panel with real-time user management

---

### 2.2 Code Robustness — Error Handling, Edge Cases, and Attack Resistance (25%)

**Input validation:**
- All request bodies validated by Pydantic before reaching business logic — invalid data returns structured 422 errors, never crashes
- Image uploads validated by both `Content-Type` header AND magic-bytes check (reads first bytes of file) — a renamed `.exe` disguised as `.png` is rejected
- File path traversal prevented: filenames checked for `/`, `\`, `..` before any file I/O

**Authentication hardening:**
- bcrypt with cost factor 12 for password hashing — plaintext never stored or logged
- JWT tokens are signed (HS256) and validated on every request; expired or malformed tokens return 401
- Revoked tokens added to blacklist — a stolen token cannot be used after logout
- TOTP 2FA uses time-based codes via pyotp; temp tokens issued mid-login are scoped (`"scope": "2fa"`) and cannot access normal endpoints
- Identical error message for "wrong email" and "wrong password" — prevents user enumeration

**Rate limiting (slowapi):**
- Login endpoint: 20 requests/minute per IP
- Registration: 10 requests/minute
- Analysis: 20 requests/minute
- All auth endpoints rate-limited to prevent brute-force

**Role-based access control:**
- `require_role()` dependency injected into every protected endpoint
- Viewers cannot access researcher or admin endpoints; attempts return 403
- Admin cannot delete another admin; manager cannot be deleted by anyone

**Database robustness:**
- `pool_pre_ping=True` on SQLAlchemy engine — stale Neon connections are detected and reconnected automatically
- `pool_recycle=300` — connections recycled every 5 minutes to prevent SSL timeout errors
- All DB operations in SQLModel sessions with automatic rollback on exception

**HTTPS and headers:**
- nginx enforces HTTPS redirect — HTTP is rejected with 301
- `SecurityHeadersMiddleware` sets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Content-Security-Policy`
- API docs (`/docs`, `/redoc`) disabled in production (`ENV=production`)
- `pip-audit` dependency scan runs in CI on every push to catch known CVEs

**CORS:**
- Only the production frontend origin is allowed in the CORS policy — no wildcard `*`
- OAuth preview subdomains explicitly allowed via regex pattern

---

### 2.3 Technical Documentation and Prompt Quality (25%)

**This report** covers the full project lifecycle. Additional documentation:

- **`DEPLOYMENT.md`** — step-by-step deployment guide for DigitalOcean + Neon, nginx config, SSL setup, systemd service, CI/CD secrets
- **`README.md`** — feature matrix with bonus point tracking, architecture diagram, API reference, test instructions, environment variable reference
- **Inline code** — functions and modules are named to be self-documenting; non-obvious logic (e.g. OAuth state CSRF, token blacklist cleanup) has explanatory comments
- **OpenAPI docs** — FastAPI auto-generates complete API documentation at `/docs` (available in development)
- **GitHub Actions workflow** — `.github/workflows/test.yml` documents the full CI/CD pipeline with named steps

**API design follows REST conventions:**
- `GET` for reads, `POST` for creates, `PATCH` for partial updates, `DELETE` for removal
- Proper HTTP status codes: 201 for created resources, 204 for no-content responses, 401/403/404/422 for errors
- Consistent JSON error format: `{"detail": "message"}`

---

### 2.4 Technical Depth — Technologies Used (25%)

**AI / Machine Learning:**
- PyTorch 2.11 with segmentation-models-pytorch U-Net (ResNet-18 encoder, pretrained on ImageNet)
- Dice Loss + BCE combined loss for training
- albumentations for data augmentation during training
- scikit-image for connected-component labelling and morphological operations
- OpenCV for image preprocessing and overlay generation
- Full training pipeline in `src/` (infer.py, batch_count_refined.py)

**Backend architecture:**
- FastAPI with async support (Uvicorn ASGI server)
- Layered design: routes → service layer → data access → database
- SQLModel = single model class for both ORM (SQLAlchemy) and validation (Pydantic)
- Authlib for OAuth 2.0 with Google, GitHub, and Dropbox
- python-jose for JWT encoding/decoding
- pyotp for RFC 6238 TOTP implementation
- slowapi (Starlette middleware) for rate limiting
- httpx for async HTTP calls to OAuth providers and Dropbox API

**Frontend:**
- React 18 with TypeScript (strict mode)
- Vite 5 for build — code splitting, tree shaking, asset hashing
- React Router v6 with protected routes (`ProtectedRoute`, `AdminRoute` components)
- Custom `AuthContext` and `ToastContext` with React hooks
- Pure SVG trend chart (no charting library dependency)
- CSS custom properties for theming

**Infrastructure:**
- DigitalOcean Ubuntu 24.04 droplet (1GB RAM + 2GB swap for PyTorch)
- nginx as reverse proxy — path-based routing (`/api/` → uvicorn, `/auth/` → uvicorn, `/` → static files)
- Let's Encrypt + Certbot for free auto-renewing TLS certificates
- systemd service with automatic restart policy
- Neon serverless Postgres with connection pooling
- GitHub Actions CI/CD with SSH key deployment to DigitalOcean

---

## 3. Bonus Points

### Playwright Testing ✅ (full points + +10 bonus)

The project has Playwright E2E tests covering authentication, navigation, analysis CRUD, and admin flows. These tests run automatically in GitHub Actions on every push to `main` — automated with each deployment.

```
frontend/e2e/
├── auth.spec.ts        (6 tests — register, login, logout, OAuth redirect)
├── navigation.spec.ts  (4 tests — all pages load, protected routes redirect)
├── crud.spec.ts        (3 tests — upload image, view jobs, CSV export)
└── admin.spec.ts       (4 tests — user list, role change, delete user)
```

Backend pytest suite: 85 tests across 7 modules with 90%+ coverage.

| Suite | Tests | What it covers |
|---|---|---|
| `test_auth.py` | 14 | Register, login, JWT, error message consistency |
| `test_crud.py` | 15 | Analyze, jobs, annotations, file validation |
| `test_roles.py` | 11 | RBAC, admin endpoints, 403 enforcement |
| `test_totp.py` | 10 | Full 2FA flow, token scope checks |
| `test_export.py` | 8 | CSV export, content-type, RBAC scoping |
| `test_security.py` | 15 | Magic bytes, headers, password strength |
| `test_profile.py` | 12 | Update username/email, change-password |

---

### Social Login: 3 Providers ✅ (+10 bonus)

| Provider | Status | Callback URL |
|---|---|---|
| Google OAuth 2.0 | ✅ Working | `/auth/google/callback` |
| GitHub OAuth 2.0 | ✅ Working | `/auth/github/callback` |
| Dropbox OAuth 2.0 | ✅ Working | `/auth/dropbox/callback` |

All three use Authlib with proper state parameter CSRF protection. After authentication, the backend creates or finds the user account, generates a short-lived exchange code (single-use, 60-second expiry), and redirects the frontend to `/oauth-callback` to complete the handshake.

---

### Basic Authentication + 2FA: 4 Methods ✅ (+15 bonus)

| Method | Description |
|---|---|
| **Password login** | Email + bcrypt-hashed password, returns JWT |
| **Email OTP** | 6-digit code sent to email, verified for JWT |
| **TOTP 2FA** | Google Authenticator (RFC 6238), enabled per-user in profile settings |
| **OAuth login** | Google, GitHub, Dropbox — social identity mapped to user account |

The TOTP flow is two-step: password login returns a scoped `temp_token` (cannot call normal endpoints), user submits the 6-digit authenticator code to `/auth/2fa/verify` to receive the full JWT.

---

### Authorization: Multi-role with Dynamic Admin Dashboard ✅ (+10 bonus)

**Four user roles with different permissions:**

| Role | Permissions |
|---|---|
| **viewer** | View own jobs, explore community publications, add comments/favourites |
| **researcher** | All viewer permissions + publish analyses to Explore |
| **admin** | All researcher permissions + manage users (view list, change roles, delete) |
| **manager** | All admin permissions + manage admins + view platform stats |

**Admin dashboard** (live at `/admin`):
- Real-time user list with roles, emails, and join dates
- Role dropdown to promote/demote any user instantly
- Delete user (cascades to all their jobs, publications, comments, annotations)
- Platform statistics (total users, total analyses, total cells counted)
- Managers can see and manage admins; admins cannot manage other admins

---

### Alternative Deployment with Security ✅ (+10 bonus)

**We chose DigitalOcean instead of Vercel or Railway.** Here is the justification:

**Why not Vercel/Railway:**
- The backend requires PyTorch (2GB+ RAM at startup) — Railway's free tier is 512MB, which crashes immediately
- Vercel is frontend-only (serverless functions, not a persistent Python server)
- Both platforms are opinionated PaaS solutions that hide infrastructure details

**Why DigitalOcean + manual setup:**
- Full control over the server — we configure nginx, systemd, SSL, and firewall ourselves
- Demonstrates real-world DevOps knowledge (not just clicking "deploy")
- 1GB RAM droplet with 2GB swap handles PyTorch in production
- nip.io provides a domain from the raw IP (`165.227.139.185.nip.io`) without buying a domain

**Security measures applied manually (that PaaS would hide):**
1. **nginx HTTPS enforcement** — all HTTP redirected to HTTPS with 301
2. **Let's Encrypt TLS** — free, auto-renewing certificate via Certbot
3. **nginx as reverse proxy** — uvicorn never exposed directly to the internet
4. **systemd service** — process manager with automatic restart, resource limits
5. **SSH key authentication** — password SSH disabled; CI/CD uses key-based authentication
6. **UFW firewall** — only ports 80, 443, and 22 open
7. **Swap memory** — 2GB swap prevents OOM kills from crashing the server
8. **`pool_pre_ping`** — database connections validated before use to prevent stale connection errors

---

### Using the Old Project as the Base ✅ (full points)

NucleiAI is built **on top of the original ML pipeline** from the previous project. The `src/` directory contains the original training and inference code (`infer.py`, `batch_count_refined.py`) which the backend imports. The U-Net model checkpoint was trained in the original project and deployed unchanged.

The web application wraps this existing AI core with:
- A FastAPI REST API exposing the inference pipeline as HTTP endpoints
- A React frontend for uploading images and viewing results
- Authentication, authorization, and multi-user support
- Cloud deployment with CI/CD

---

## 4. System Architecture

```
Browser (React + TypeScript)
https://165.227.139.185.nip.io
         │
         │ HTTPS (TLS 1.2/1.3)
         ▼
    nginx (reverse proxy)
    ├── /          → frontend static files (dist/)
    ├── /api/      → FastAPI uvicorn (port 8000)
    └── /auth/     → FastAPI OAuth callbacks
         │
         ▼
    FastAPI Backend (Python 3.12, Uvicorn)
    ├── JWT authentication middleware
    ├── Rate limiting (slowapi)
    ├── CORS policy
    ├── Security headers middleware
    ├── AI analysis service (U-Net inference)
    └── REST API endpoints
         │
    ┌────┴────┐
    │         │
    ▼         ▼
PostgreSQL  File Storage
(Neon.tech) /backend/storage/
```

---

## 5. Securing the Servers

The DigitalOcean droplet is secured at multiple layers:

| Layer | Measure |
|---|---|
| **Network** | UFW firewall — only ports 22 (SSH), 80 (HTTP→redirect), 443 (HTTPS) open |
| **SSH** | Key-based authentication only; root password login disabled |
| **TLS** | Let's Encrypt certificate, auto-renewed by Certbot systemd timer |
| **Proxy** | nginx reverse proxy — uvicorn bound to `127.0.0.1:8000`, not exposed externally |
| **Application** | Rate limiting, JWT validation, RBAC on every endpoint |
| **Dependencies** | `pip-audit` scans for known CVEs on every CI run |
| **Secrets** | All secrets in `.env` (gitignored) and GitHub Actions secrets — never hardcoded |
| **API docs** | Swagger UI disabled in production (`ENV=production`) |

---

## 6. Screenshots

### Login Page — Multiple Auth Methods
![Login](../screenshots/Screenshot%202026-05-12%20102806.png)
*Password login + Email OTP tab + Google / GitHub / Dropbox social login buttons*

### Registration Page
![Register](../screenshots/Screenshot%202026-05-12%20102836.png)
*Account creation with strong password requirements*

### Dashboard — Analysis History
![Dashboard](../screenshots/Screenshot%202026-05-12%20102551.png)
*6 total jobs, 1,018 cells counted, 7-day trend chart, job list with search and filter*

### Analyze Page — AI Results
![Analyze](../screenshots/Screenshot%202026-05-12%20102613.png)
*U-Net analysis complete: 241 cells counted, segmentation mask, colour overlay, PDF download*

### Publish to Explore
![Publish](../screenshots/Screenshot%202026-05-12%20102623.png)
*Share analysis with the community — headline and description*

### Explore — Community Publications
![Explore](../screenshots/Screenshot%202026-05-12%20102643.png)
*Browse published analyses from all users with search and filters*

### Favourites
![Favourites](../screenshots/Screenshot%202026-05-12%20102653.png)
*Save analyses to personal favourites list*

### Profile — Password + 2FA Setup
![Profile](../screenshots/Screenshot%202026-05-12%20102709.png)
*Change password and access TOTP 2FA setup*

### TOTP 2FA Setup
![2FA](../screenshots/Screenshot%202026-05-12%20102825.png)
*QR code for Google Authenticator — scan and enter 6-digit code to enable*

### Admin Dashboard — User Management
![Admin](../screenshots/Screenshot%202026-05-12%20102427.png)
*12 total users, role dropdown for each user, delete button, platform stats (1 admin, 1 manager, 10 viewers)*

### About Us Page
![About](../screenshots/Screenshot%202026-05-12%20102724.png)
*Project mission, what we do, and platform capabilities*

### Contact Page
![Contact](../screenshots/Screenshot%202026-05-12%20102731.png)
*Contact information and support categories*

---

## 7. References

1. Ronneberger, O., Fischer, P., & Brox, T. (2015). *U-Net: Convolutional Networks for Biomedical Image Segmentation.* MICCAI, pp. 234–241.
2. Caicedo, J. C., et al. (2019). *Evaluation of Deep Learning Strategies for Nucleus Segmentation in Fluorescence Images.* Cytometry Part A, 95(9), 952–965.
3. Iakubovskii, P. (2019). *Segmentation Models PyTorch.* https://github.com/qubvel/segmentation_models.pytorch
4. Paszke, A., et al. (2019). *PyTorch: An Imperative Style, High-Performance Deep Learning Library.* NeurIPS, 32.
5. Tiangolo, S. R. (2018–). *FastAPI Documentation.* https://fastapi.tiangolo.com/
6. SQLModel Documentation. https://sqlmodel.tiangolo.com/
7. DigitalOcean Documentation. https://docs.digitalocean.com/
8. Neon PostgreSQL Documentation. https://neon.tech/docs
9. Let's Encrypt Documentation. https://letsencrypt.org/docs/

---

*Report version: v2.0 — May 2026*
*NucleiAI — Istinye University Web Programming Project*
