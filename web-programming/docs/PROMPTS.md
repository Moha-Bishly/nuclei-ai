# NucleiAI — Full Development Prompt Documentation

> This document records every major prompt used to design, architect, and build the NucleiAI
> web platform from the ground up. Prompts are ordered by development phase and cover every
> layer of the stack: backend, frontend, authentication, AI integration, security, testing,
> and deployment.

---

## Phase 1 — Project Architecture & Planning

### Prompt 1.1 — System Architecture Design

```
Design a full-stack web application called NucleiAI that wraps an existing PyTorch U-Net
deep learning model (ResNet-18 encoder, trained on histopathology microscopy images) into
a production-ready multi-user web platform.

Requirements:
- Backend: FastAPI (Python 3.12) with SQLModel ORM, Pydantic validation, and Uvicorn ASGI
- Frontend: React 18 with TypeScript, Vite 5 build tool, React Router v6
- Database: PostgreSQL (Neon managed cloud) with SQLAlchemy connection pooling
- Authentication: JWT-based auth, TOTP 2FA, Email OTP, and 3 OAuth providers
- Authorization: Role-based access control with 4 roles (manager, admin, researcher, viewer)
- AI: The existing U-Net model must run as a backend service — not exposed directly
- Deployment: DigitalOcean Ubuntu 24.04 droplet behind nginx with Let's Encrypt TLS

Produce:
1. A complete directory structure for both backend and frontend
2. A list of all API endpoints with HTTP methods, paths, auth requirements, and descriptions
3. A data model diagram showing all database tables and their relationships
4. The request lifecycle for a typical image analysis job
```

---

### Prompt 1.2 — Database Schema Design

```
Design the complete PostgreSQL database schema for NucleiAI using SQLModel (which combines
SQLAlchemy ORM and Pydantic in one class definition). The schema must support:

Tables required:
1. User — id, username (unique), email (unique), hashed_password, role (enum), totp_secret,
   totp_enabled, email_otp_hash, email_otp_expires_at, reset_token_hash, reset_token_expires_at,
   created_at
2. AnalysisJob — id, job_id (12-char unique string), user_id (FK), status, cell_count, mode
   (unet/otsu), original_filename, input_url, mask_url, overlay_url, processing_ms, threshold,
   min_area, image_size, device, created_at
3. Annotation — id, job_id (FK), user_id (FK), note (max 1000 chars), created_at
4. Publication — id, job_id (FK unique), user_id (FK), headline (max 150), description
   (max 2000), created_at
5. Favourite — id, publication_id (FK), user_id (FK), created_at
6. Comment — id, publication_id (FK), user_id (FK), text (max 1000), created_at
7. Notification — id, user_id (recipient FK), actor_id (FK), kind (favourite/comment),
   publication_id (FK), read (bool), created_at
8. RevokedToken — id, token_hash (unique SHA-256 of JWT), expires_at, created_at

Use SQLModel field definitions with proper constraints (unique, index, max_length, ge).
Include all SQLModel Relationship() back-references. Use UserRole as a str enum with values:
manager, admin, researcher, viewer (in descending privilege order).
```

---

## Phase 2 — Backend Core

### Prompt 2.1 — FastAPI Application Entry Point

```
Create backend/main.py — the FastAPI entry point for NucleiAI with the following:

Middleware stack (in order):
1. SessionMiddleware (for OAuth state management) with SECRET_KEY
2. CORSMiddleware — allow origins: FRONTEND_URL and any preview subdomain matching
   r"https://[a-zA-Z0-9-]+\.nip\.io" — allow credentials, all methods, all headers
3. SecurityHeadersMiddleware (custom — sets X-Frame-Options, X-Content-Type-Options,
   Referrer-Policy, Content-Security-Policy)
4. Rate limiter via slowapi (Limiter keyed on get_remote_address, add handler for
   RateLimitExceeded → 429)

Startup lifespan:
- create_db_and_tables() on startup
- Load U-Net model into memory during startup (so first request is fast)
- Log model status

Auth endpoints (prefix /auth):
POST /auth/register          — rate limit 10/min
POST /auth/login             — rate limit 20/min
POST /auth/logout            — JWT required
GET  /auth/me                — JWT required
PATCH /auth/me               — JWT required (update username/email)
POST /auth/change-password   — JWT required
POST /auth/totp/setup        — JWT required
POST /auth/totp/verify-setup — JWT required
POST /auth/2fa/verify        — temp JWT required
POST /auth/email-otp/send    — rate limit 10/min
POST /auth/email-otp/verify  — rate limit 10/min
POST /auth/forgot-password   — rate limit 5/min
POST /auth/verify-reset-code
POST /auth/reset-password
GET  /auth/google  /auth/google/callback
GET  /auth/github  /auth/github/callback
GET  /auth/dropbox /auth/dropbox/callback
POST /auth/oauth/exchange    — exchange short-lived code for JWT

API endpoints (prefix /api):
POST /api/analyze            — JWT required, rate limit 20/min, multipart image upload
GET  /api/jobs               — JWT required, paginated
GET  /api/jobs/export.csv    — JWT required
GET  /api/jobs/{job_id}      — JWT required
DELETE /api/jobs/{job_id}    — JWT required
POST /api/jobs/{job_id}/publish   — researcher+ role
POST /api/jobs/{job_id}/reanalyze — JWT required
GET  /api/explore            — JWT required, search + filter
POST /api/publications/{id}/favourite — JWT required
POST /api/publications/{id}/comments  — JWT required
GET  /api/favourites         — JWT required
GET  /api/notifications      — JWT required

Admin endpoints (prefix /admin):
GET    /admin/users          — admin+ role
PATCH  /admin/users/{id}/role — admin+ role
DELETE /admin/users/{id}    — admin+ role
GET    /admin/stats          — admin+ role
POST   /admin/users          — manager role only

Static file serving:
GET /files/{filename}        — serve from backend/storage/

Health endpoints:
GET /health   — simple 200 {"status":"ok"}
GET /api/health — full health with model status, db connectivity, uptime

Disable /docs and /redoc in production (ENV == "production").
```

---

### Prompt 2.2 — Configuration Module

```
Create backend/config.py that reads all configuration from environment variables with
sensible development defaults.

Variables to expose:
- SECRET_KEY: str — used for JWT signing and session middleware
- ALGORITHM: str = "HS256"
- ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
- TEMP_TOKEN_EXPIRE_MINUTES: int = 5  (for mid-login 2FA temp tokens)
- DATABASE_URL: str = "sqlite:///./nuclei.db"
- ENV: str = "development"  ("production" disables API docs)
- FRONTEND_URL: str = "http://localhost:5173"
- BACKEND_URL: str = "http://localhost:8000"
- SMTP_HOST: str = "smtp.gmail.com"
- SMTP_PORT: int = 587
- SMTP_USER: Optional[str] = None
- SMTP_PASSWORD: Optional[str] = None
- EMAIL_FROM: str = same as SMTP_USER
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
- DROPBOX_CLIENT_ID, DROPBOX_CLIENT_SECRET

Use python-dotenv to load .env automatically.
```

---

### Prompt 2.3 — Database Engine and Session

```
Create backend/database.py with:
- SQLAlchemy engine created from DATABASE_URL
- For PostgreSQL: pool_pre_ping=True, pool_recycle=300, connect_args={"sslmode":"require"}
- For SQLite (development): connect_args={"check_same_thread": False}
- create_db_and_tables() function using SQLModel.metadata.create_all(engine)
- get_session() FastAPI dependency that yields a Session and auto-closes it

pool_pre_ping ensures stale connections to Neon (which aggressively drops idle connections)
are detected and reconnected before executing a query. pool_recycle=300 prevents SSL timeout
errors on long-running instances.
```

---

### Prompt 2.4 — Authentication Utilities

```
Create backend/auth_utils.py with the following utilities:

1. Password strength validation:
   validate_password_strength(password: str) — raises ValueError if:
   - Less than 8 characters
   - Contains non-ASCII or space characters
   - Missing uppercase letter (ASCII only)
   - Missing lowercase letter (ASCII only)
   - Missing digit
   - Missing special character from: !@#$%^&*()-_=+[]{}|;:'",.<>?/`~\

2. Password hashing:
   hash_password(plain: str) → bcrypt hash with cost factor 12
   verify_password(plain: str, hashed: str) → bool (constant-time via bcrypt)

3. JWT operations:
   create_access_token(subject, extra=None) → signed HS256 JWT with 60-min expiry
   create_temp_token(subject) → scoped JWT with {"scope":"2fa"} and 5-min expiry
   decode_token(token) → payload dict or raises JWTError

4. Email OTP:
   generate_otp() → 6-digit string using secrets.randbelow(1_000_000)
   hash_otp(code) → SHA-256 hex digest
   verify_otp_hash(code, stored_hash) → bool using hmac.compare_digest (timing-safe)

5. Password reset token:
   generate_reset_token() → secrets.token_urlsafe(32)

6. Token revocation blacklist (in-memory, thread-safe with threading.Lock):
   revoke_token(token) — adds to dict keyed by token, expires at JWT exp, prunes expired
   is_token_revoked(token) → bool

7. Email sending:
   send_otp_email(to_email, code) — 6-digit OTP via SMTP/STARTTLS port 587
   send_reset_code_email(to_email, code) — password reset code email
   If SMTP_USER/PASSWORD not configured: print code to console (dev fallback) and return.
```

---

### Prompt 2.5 — Security Middleware and Image Validation

```
Create backend/security.py with:

1. SecurityHeadersMiddleware(BaseHTTPMiddleware):
   Add to every response:
   - X-Frame-Options: DENY
   - X-Content-Type-Options: nosniff
   - Referrer-Policy: strict-origin-when-cross-origin
   - Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:;
     script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
   - Permissions-Policy: camera=(), microphone=(), geolocation=()

2. is_valid_image_bytes(data: bytes) → bool:
   Validate actual magic bytes (not just Content-Type header).
   Accept: JPEG (FF D8 FF), PNG (89 50 4E 47), GIF (47 49 46 38),
           WebP (52 49 46 46 ... 57 45 42 50 at bytes 8-12)
   Reject everything else — a renamed .exe cannot pass this check.

3. validate_filename(filename: str) → str:
   Reject filenames containing /, \, or .. (path traversal prevention).
   Raise HTTPException 400 if invalid.
```

---

### Prompt 2.6 — Dependencies (Auth Guards)

```
Create backend/dependencies.py with FastAPI dependency functions:

1. get_current_user(credentials, session) → User:
   - Extract Bearer token from Authorization header
   - Decode JWT, check is_token_revoked() — raise 401 if revoked
   - Look up user by id from token "sub" claim — raise 401 if not found
   - Reject tokens with a "scope" field (temp tokens cannot access normal endpoints)
   - Return User object

2. require_role(*roles: UserRole) → Callable:
   Returns a FastAPI dependency that calls get_current_user() and raises 403 if
   user's role is not in the allowed list.
   Usage: Depends(require_role(UserRole.admin, UserRole.manager))

3. get_temp_token_user_id(credentials, session) → int:
   Used only for POST /auth/2fa/verify
   Decode token, verify scope == "2fa", return user_id as int.
   Raise 401 if scope is wrong or token is invalid/expired.
```

---

### Prompt 2.7 — CRUD Services

```
Create backend/crud.py with two service classes:

JobService:
- create(session, user_id, analysis_result) → AnalysisJob
  Generate 12-char alphanumeric job_id with secrets.token_hex(6)
  Set status="done", persist all fields from analysis result dict
- get_user_jobs(session, user_id, skip, limit) → list[AnalysisJob]
- get_job(session, job_id, user_id) → AnalysisJob or raise 404
  Only return if job belongs to the requesting user
- delete_job(session, job_id, user_id) — also delete associated files from disk
- get_7day_trend(session, user_id) → list[{date, cell_count}]
  Group by date, sum cell counts, fill missing days with 0

AnnotationService:
- create(session, job_id, user_id, note) → Annotation
  Verify job exists and belongs to user first
- list_for_job(session, job_id, user_id) → list[Annotation]
- delete(session, annotation_id, user_id) — verify ownership before deleting
```

---

### Prompt 2.8 — Analysis Service (AI Integration)

```
Create backend/services/analysis_service.py wrapping the existing U-Net PyTorch model:

1. Load model ONCE at startup via _ensure_model_loaded() with a threading.Lock:
   Model: segmentation_models_pytorch.Unet(encoder_name="resnet18", in_channels=3, classes=1)
   Load checkpoint from src/unet_best.pth
   Set model.eval(), move to CPU (or CUDA if available)

2. analyze(image_bytes: bytes, threshold=0.5, min_area=10) → dict:
   a. Decode with cv2.imdecode
   b. Resize to 256×256
   c. Normalize to [0,1], BGR→RGB, reshape to (1,3,256,256) tensor
   d. Run inference under torch.no_grad()
   e. Apply sigmoid, threshold to binary mask
   f. Apply cv2.morphologyEx (morphological opening) to remove noise
   g. Label connected components with skimage.measure.label()
   h. Filter by area >= min_area
   i. Generate colour overlay: draw each nucleus contour in a distinct colour
   j. Save input, mask, overlay as PNG to backend/storage/results/
   k. Return: cell_count, input_url, mask_url, overlay_url, processing_ms,
      mode, threshold, min_area, image_size=256, device

3. Fallback: if checkpoint not found, use Otsu thresholding (cv2.THRESH_OTSU).
   Set mode="otsu" in result. Application still works without the model weights.

4. Thread safety: wrap model inference in threading.Lock() — concurrent requests
   must not corrupt shared model state.
```

---

### Prompt 2.9 — OAuth Integration

```
Create backend/oauth.py using Authlib's Starlette OAuth integration.

Register three providers:

1. Google OAuth 2.0:
   - server_metadata_url: https://accounts.google.com/.well-known/openid-configuration
   - scope: "openid email profile"

2. GitHub OAuth 2.0:
   - access_token_url: https://github.com/login/oauth/access_token
   - authorize_url: https://github.com/login/oauth/authorize
   - scope: "read:user user:email"
   - Fetch email separately via GET /user/emails if not in profile

3. Dropbox OAuth 2.0:
   - access_token_url: https://api.dropboxapi.com/oauth2/token
   - authorize_url: https://www.dropbox.com/oauth2/authorize
   - token_endpoint_auth_method: "client_secret_post"
   - Fetch account via POST https://api.dropboxapi.com/2/users/get_current_account

OAuth flow:
- GET /auth/{provider}: redirect to provider, store CSRF state in session
- GET /auth/{provider}/callback: exchange code for token, fetch user profile
- Create or find User by email, auto-generate username from profile if new
- Generate single-use exchange code with secrets.token_urlsafe(16), store in memory
  dict with 60-second TTL and associated user_id
- Redirect frontend to /oauth-callback?code=<exchange_code>
- POST /auth/oauth/exchange: validate code (single-use, not expired), delete from dict,
  issue JWT — prevents token appearing in URL history or browser logs
```

---

### Prompt 2.10 — Pydantic Schemas

```
Create backend/schemas.py with all request/response models:

Request schemas:
- RegisterRequest: username (3-50 chars), email (EmailStr), password (validated strength)
- LoginRequest: email (EmailStr), password
- TwoFactorVerifyRequest: code (6 digits string)
- ChangePasswordRequest: current_password, new_password
- RoleUpdateRequest: role (UserRole enum)
- AnnotationCreate: note (max 1000 chars)
- EmailOTPRequest: email (EmailStr)
- EmailOTPVerifyRequest: email, code
- ForgotPasswordRequest: email (EmailStr)
- VerifyResetCodeRequest: email, code
- ResetPasswordRequest: email, code, new_password
- CreateAdminRequest: username, email, password

Response schemas:
- TokenResponse: access_token, token_type="bearer", user (UserResponse)
- UserResponse: id, username, email, role, totp_enabled, created_at
- TwoFactorRequiredResponse: requires_2fa=True, temp_token
- TwoFactorSetupResponse: secret, qr_uri
- JobSummary: job_id, cell_count, mode, original_filename, created_at
- JobResponse: all JobSummary fields + input_url, mask_url, overlay_url,
  processing_ms, threshold, min_area, annotations list
- AnnotationResponse: id, note, created_at, username
- HealthResponse: status, model_loaded, db_ok, uptime_seconds
- PublicationResponse, FavouriteResponse, CommentResponse, NotificationResponse

All response models: model_config = {"from_attributes": True} for ORM compatibility.
```

---

## Phase 3 — Frontend

### Prompt 3.1 — React Application Structure

```
Create a React 18 + TypeScript + Vite 5 frontend for NucleiAI.

Route configuration (App.tsx):
/ → redirect to /dashboard
/login → LoginPage (public)
/register → RegisterPage (public)
/forgot-password → ForgotPasswordPage (public)
/reset-password → ResetPasswordPage (public)
/oauth-callback → OAuthCallbackPage (public)
/2fa → TwoFactorVerifyPage (public — needs temp token in state)
/dashboard → Dashboard (ProtectedRoute)
/analyze → AnalyzePage (ProtectedRoute)
/explore → ExplorePage (ProtectedRoute)
/favourites → FavouritesPage (ProtectedRoute)
/profile → ProfilePage (ProtectedRoute)
/2fa-setup → TwoFactorSetupPage (ProtectedRoute)
/jobs/:jobId → JobDetailPage (ProtectedRoute)
/admin → AdminPage (AdminRoute — admin and manager only)
/about → AboutPage (public)
/contact → ContactPage (public)

ProtectedRoute: if not authenticated, redirect to /login
AdminRoute: if not admin/manager, redirect to /dashboard
```

---

### Prompt 3.2 — Auth Context and API Layer

```
Create src/contexts/AuthContext.tsx:
- State: user (UserResponse | null), token (string | null), loading (bool)
- Persist token in localStorage under key "nuclei_token"
- On mount: if token exists, call GET /auth/me to hydrate user — clear if 401
- login(token, user): store in state and localStorage
- logout(): call POST /auth/logout, clear state and localStorage, navigate to /login
- isAdmin: computed — true if role is "admin" or "manager"

Create src/api.ts:
- BASE_URL from import.meta.env.VITE_API_URL
- apiFetch(path, options): adds Authorization header from localStorage token,
  throws Error with backend "detail" message on non-2xx responses
- Typed function for every endpoint:
  auth: register, login, logout, getMe, updateMe, changePassword
  totp: setupTotp, verifyTotpSetup, verify2fa
  email otp: sendEmailOtp, verifyEmailOtp
  password reset: forgotPassword, verifyResetCode, resetPassword
  jobs: analyzeImage, getJobs, getJob, deleteJob, exportCsv, publishJob, reanalyzeJob
  social: getExplore, favouritePublication, addComment, getFavourites, getNotifications
  admin: getAdminUsers, updateUserRole, deleteUser, getAdminStats, createAdminUser
  oauth: exchangeOauthCode
```

---

### Prompt 3.3 — Login Page

```
Create src/pages/LoginPage.tsx with three authentication methods:

1. Password login form:
   - Email (type=email), Password (type=password), "Sign in" button
   - On success with access_token: AuthContext.login() → navigate /dashboard
   - On success with requires_2fa=true: navigate to /2fa passing temp_token in state
   - On error: show message in div.error

2. Email OTP section:
   - Email input + "Send Code" button → sendEmailOtp(email)
   - After code sent: 6-digit code input + "Verify" button → verifyEmailOtp(email, code)
   - On success: login and navigate to /dashboard

3. OAuth buttons:
   - Google, GitHub, Dropbox — each navigates to {VITE_API_URL}/auth/{provider}
   - Styled with provider branding

4. Links to /register and /forgot-password

If already authenticated: redirect to /dashboard immediately.
```

---

### Prompt 3.4 — Dashboard Page

```
Create src/pages/Dashboard.tsx:

1. Stats row (3 cards):
   - Total Jobs, Total Cells Counted, Last Analysis Date

2. 7-Day Trend Chart — pure SVG, no charting library:
   - Line chart with X-axis (last 7 dates) and Y-axis (cell count)
   - SVG <path> for the line, <circle> for data points, <line> for gridlines
   - <text> elements for axis labels
   - Tooltip div on hover showing date + count

3. Job History table:
   - Columns: Filename, Cell Count, Mode (U-Net/Otsu badge), Date, Actions
   - Actions: View → /jobs/:jobId, Delete (confirmation required)
   - Pagination (10 per page), search by filename

4. "New Analysis" button → /analyze

Fetch jobs list and 7-day trend in parallel on mount.
Show loading skeleton while fetching. Show empty state when no jobs.
```

---

### Prompt 3.5 — Analyze Page

```
Create src/pages/AnalyzePage.tsx:

1. Upload zone:
   - Drag-and-drop area + file input (accept image/*)
   - Preview thumbnail of selected image
   - Collapsible advanced options:
     Threshold slider (0.1 – 0.9, step 0.05, default 0.5)
     Min area input (1 – 500, default 10)
   - "Analyze" button — disabled while processing
   - Progress spinner during upload/inference

2. Results (shown after success):
   - Large cell count number
   - Three images: Original | Segmentation Mask | Colour Overlay
   - Each image is clickable to fullscreen
   - Mode badge (U-Net / Otsu), processing time in ms
   - Action buttons:
     Download PDF report
     Publish to Explore (modal with headline + description)
     Reanalyze (same image, different parameters)
     Add Annotation (text note)

3. Annotation list (below results):
   - All notes for this job, chronological
   - Delete button per annotation (own annotations only)
```

---

### Prompt 3.6 — Explore Page

```
Create src/pages/ExplorePage.tsx — community publication feed:

1. Search bar (debounced 300ms) + filter dropdown (All/This Week/This Month/Most Cells)

2. Publication cards grid:
   Each card: author, headline, cell count badge, overlay thumbnail,
   truncated description, date, favourite button (heart + count), comment count

3. Card expansion (click): full description, all 3 analysis images,
   comment thread with timestamps, add-comment input

Fetch on mount, re-fetch on search/filter change.
Optimistically update favourite count on click (revert on API error).
```

---

### Prompt 3.7 — Profile Page

```
Create src/pages/ProfilePage.tsx with three sections:

1. Account Info:
   - Display username, email, role badge, member since
   - Inline edit form with "Save Changes" → PATCH /auth/me

2. Password Change:
   - Current password, new password (with strength indicator), confirm password
   - Client-side match check before submit
   - "Change Password" → POST /auth/change-password

3. Two-Factor Authentication:
   - Show TOTP status (enabled/disabled)
   - If disabled: "Enable Authenticator App" → /2fa-setup
   - If enabled: green Active badge + "Disable 2FA" button
```

---

### Prompt 3.8 — Admin Page

```
Create src/pages/AdminPage.tsx (admin and manager roles only):

1. Stats cards: Total Users, Total Analyses, Total Cells, Users by Role breakdown

2. User Management table:
   Columns: ID, Username, Email, Role, Joined, Actions

   Role column: inline <select> dropdown
   - onChange: immediately PATCH /admin/users/{id}/role
   - Show success toast on change
   - Admins cannot change other admins' roles (disable dropdown if both admin)

   Actions: Delete button → confirm dialog → DELETE /admin/users/{id} → remove row

3. Search bar (client-side filter on username/email)

4. "Create Admin" button (manager only) → modal with username/email/password fields
   → POST /admin/users → refreshes table

Fetch /admin/users and /admin/stats in parallel on mount.
Show manager-only controls only when user.role === "manager".
```

---

### Prompt 3.9 — TOTP 2FA Setup Page

```
Create src/pages/TwoFactorSetupPage.tsx — two-step flow:

Step 1 — Generate:
- Call POST /auth/totp/setup on mount
- Display QR code (render qr_uri as image)
- Display manual secret key for manual entry
- "I've scanned it" button → advance to step 2

Step 2 — Verify:
- 6-digit code input from authenticator app
- "Enable 2FA" → POST /auth/totp/verify-setup
- On success: update user.totp_enabled in AuthContext, show green confirmation
- On error: show inline error, allow retry

Note displayed: "Store your backup codes securely — they are the only way to recover
access if you lose your authenticator device."
```

---

### Prompt 3.10 — OAuth Callback Page

```
Create src/pages/OAuthCallbackPage.tsx:

On mount:
1. Read `code` from URL search params (?code=...)
2. If no code: show error "OAuth login failed — no code received"
3. POST /auth/oauth/exchange with {code}
4. On success: AuthContext.login(token, user), navigate to /dashboard
5. On error: show error message + link back to /login

Show loading spinner while exchange is in progress.
The exchange code is single-use and has a 60-second server-side TTL.
```

---

### Prompt 3.11 — Dashboard Layout and Navigation Sidebar

```
Create src/components/DashboardLayout.tsx:

Sidebar (desktop — always visible):
- Brand logo at top
- Navigation links with icons:
  Dashboard, Analyze, Explore, Favourites, Profile
  Admin (only if role is admin or manager)
  About, Contact
- Active link highlighted by current URL
- Logout button at bottom

Topbar (all sizes):
- Hamburger menu (mobile only)
- Page title
- Username + role badge
- Notification bell with unread count (from GET /api/notifications)
- Avatar circle (first letter of username)

Mobile: sidebar hidden by default, shown as overlay on hamburger click.
Desktop: sidebar fixed on left, content fills remaining width.
```

---

## Phase 4 — Security Hardening

### Prompt 4.1 — Security Audit Checklist

```
Apply and verify the following security measures across the entire NucleiAI stack:

Authentication:
- bcrypt cost factor 12 for all password hashes — never store or log plaintext
- Identical error "Invalid credentials." for wrong email AND wrong password
  (prevents user enumeration — attacker cannot distinguish which field is wrong)
- JWT signed with HS256 using a 64-byte random SECRET_KEY
- Temp tokens for 2FA mid-login flow scoped with {"scope":"2fa"} — cannot call
  normal API endpoints (scope check in get_current_user dependency)
- Token blacklist: revoked JWTs tracked in memory, pruned at each revocation

Rate limiting (slowapi, per IP):
- /auth/register: 10/minute
- /auth/login: 20/minute
- /auth/email-otp/send: 10/minute
- /auth/forgot-password: 5/minute
- /api/analyze: 20/minute

Image upload:
- Validate Content-Type header (must start with image/)
- Validate magic bytes of file content (not just the header)
- Validate filename for path traversal characters: /, \, ..
- Reject files larger than 10MB

CORS:
- Explicit origin allow-list: FRONTEND_URL + OAuth preview subdomains
- No wildcard * in production
- allow_credentials=True required for OAuth session cookies

HTTP security headers on every response:
- X-Frame-Options: DENY (clickjacking prevention)
- X-Content-Type-Options: nosniff (MIME sniffing prevention)
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy (restrict all source types)
- Permissions-Policy: deny camera, microphone, geolocation

OAuth CSRF:
- Generate random state parameter before each OAuth redirect
- Store in server-side session (SessionMiddleware)
- Validate state matches on callback — reject mismatches with 400

Admin safeguards:
- Admins cannot delete other admins (only managers can)
- Manager role cannot be deleted by anyone through the API
- Role promotion to manager not available through any API endpoint

Production:
- /docs and /redoc disabled when ENV=production
- pip-audit runs in CI on every push to catch dependency CVEs
```

---

## Phase 5 — Testing

### Prompt 5.1 — Backend Unit Tests (85 tests across 7 modules)

```
Create backend/tests/ with conftest.py and 7 test modules using pytest + TestClient:

conftest.py:
- client fixture: TestClient with SQLite in-memory database (overrides DATABASE_URL)
- make_user(client, username, email, password, role) helper
- auth_headers(token) helper: {"Authorization": f"Bearer {token}"}

test_auth.py (14 tests):
- Register with valid data → 201
- Register duplicate email → 400
- Register weak password (no special char) → 422
- Login success → 200 with access_token
- Login wrong password → 401 "Invalid credentials."
- Login wrong email → 401 "Invalid credentials." (same message as wrong password)
- GET /auth/me authenticated → 200 with user data
- GET /auth/me unauthenticated → 401
- Logout then reuse token → 401 (blacklist check)
- Change password success → 200
- Change password wrong current → 401
- Expired token → 401
- Update username → 200
- Update to duplicate username → 400

test_crud.py (15 tests):
- Analyze with valid PNG → 201 with cell_count >= 0
- Analyze with non-image file → 400 (magic bytes check)
- Job list returns only requesting user's jobs
- Job list pagination works (skip/limit)
- Get job by ID — own job → 200
- Get job by ID — other user's job → 404
- Delete job removes database record
- Delete job removes files from disk
- Create annotation on own job → 201
- List annotations for job → 200
- Delete own annotation → 204
- Delete other user's annotation → 404
- Reanalyze job → new cell_count
- CSV export returns text/csv
- Publish job → 201 (researcher+ role)

test_roles.py (11 tests):
- Viewer cannot publish → 403
- Researcher can publish → 201
- Viewer cannot access /admin/users → 403
- Admin can access /admin/users → 200
- Admin cannot delete another admin → 403
- Manager can delete admin → 204
- Viewer cannot update any user role → 403
- Admin can update viewer role → 200
- Admin cannot update another admin's role → 403
- Manager can create admin account → 201
- Viewer cannot create admin → 403

test_totp.py (10 tests):
- Setup TOTP returns secret and qr_uri
- Verify setup with valid pyotp-generated code → 200, totp_enabled=True
- Verify setup with invalid code → 400
- Login with TOTP enabled → requires_2fa=True + temp_token
- 2FA verify correct code → 200 with full JWT
- 2FA verify wrong code → 401
- Temp token cannot call /auth/me → 401
- Normal token cannot call /auth/2fa/verify → 401
- Same TOTP code rejected on second use (replay prevention)
- Disable TOTP → totp_enabled=False

test_export.py (8 tests):
- CSV Content-Type is text/csv
- CSV has correct header row (columns)
- CSV row count matches job count for user
- User A cannot see User B's jobs in CSV
- Empty export (no jobs) → header row only
- All required fields present in each CSV row
- CSV is valid UTF-8
- Export requires authentication → 401 without token

test_security.py (15 tests):
- Valid PNG magic bytes accepted
- Valid JPEG magic bytes accepted
- .exe renamed to .png rejected (magic bytes check)
- Filename with "../" rejected → 400
- Filename with "/" rejected → 400
- X-Frame-Options header present on all responses
- X-Content-Type-Options: nosniff present
- Rate limit headers present on auth endpoints
- /docs returns 404 in production ENV
- Oversized image (>10MB) → 413
- Path traversal in job_id parameter → 404 not 500
- SQL injection attempt in username field → 422 (Pydantic rejects)
- CORS: request from unlisted origin → no Access-Control-Allow-Origin header
- Security headers present on 404 responses (middleware applies to all)
- CSRF state mismatch on OAuth callback → 400

test_profile.py (12 tests):
- Update username to new valid value → 200
- Update username to taken value → 400
- Update email to new valid value → 200
- Update email to taken value → 400
- Update email to invalid format → 422
- Change password: success path → 200
- Change password: wrong current password → 401
- Change password: new password same as old → 400
- Change password: new password too weak → 422
- Change password: new password missing special char → 422
- Change password: confirm password mismatch (client-side — tested at API level too)
- Update me with no changes → 200 (idempotent)
```

---

### Prompt 5.2 — Playwright E2E Tests (17 tests across 4 suites)

```
Create frontend/e2e/ with playwright.config.ts and 4 test files.

playwright.config.ts:
- baseURL: http://localhost:5173
- 1 worker (sequential execution to avoid state conflicts)
- 1 retry on failure
- Reporter: github (CI annotations), list (local)
- Timeout: 30s per test
- Chromium browser only

helpers.ts:
- loginAs(page, username, email, role?):
  Register via POST /auth/register API call (not UI),
  Fill login form with email/password, submit,
  Wait for /dashboard URL. Use Date.now() suffix for unique usernames.
- loginAsAdmin(page, username, email):
  Register + promote to admin via API, then log in via UI.
- goto(page, path): navigate and wait for networkidle.

auth.spec.ts (6 tests):
1. Register page renders: heading "Create account", username/email/password fields, sign-in link
2. Login page renders: heading "Sign in", auth options visible
3. Register with valid credentials redirects to /login (current behavior)
4. Login with wrong password: .error element visible
5. Unauthenticated /dashboard visit → redirected to /login
6. Logout clears session and redirects to /login

navigation.spec.ts (4 tests):
1. Authenticated user can reach /dashboard, /analyze, /explore, /favourites without redirect
2. Sidebar nav links navigate to correct pages
3. /admin as viewer → redirected to /dashboard
4. Profile page loads and displays current username

crud.spec.ts (3 tests):
1. Upload a real test PNG → results section appears with cell count
2. After analysis, job appears in dashboard history table
3. CSV export button downloads a file with .csv in the name

admin.spec.ts (4 tests):
1. Admin can navigate to /admin without redirect
2. Admin page shows user table with at least one row
3. Admin can change a user's role via dropdown (verify API called)
4. Admin can delete a user (row disappears from table)
```

---

## Phase 6 — CI/CD and Deployment

### Prompt 6.1 — GitHub Actions Pipeline

```
Create .github/workflows/test.yml — runs on every push to main:

Job 1: backend-tests
- ubuntu-latest
- Python 3.12 setup
- pip install -r web-programming/backend/requirements.txt
- pip-audit (fail on any high/critical CVE)
- pytest backend/tests/ -v --cov=backend --cov-report=xml --cov-fail-under=80
- Upload coverage XML as artifact

Job 2: e2e-tests (needs: backend-tests)
- ubuntu-latest
- Start backend: uvicorn backend.main:app --port 8000 &
- Poll until /health returns 200 (retry loop with sleep 2, max 30 attempts)
- Node.js 20 setup
- npm ci in frontend/
- npx playwright install chromium --with-deps
- npm run build → start preview server
- npx playwright test --reporter=github
- Upload playwright-report/ on failure

Job 3: deploy (needs: e2e-tests, only on push to main)
- SSH to DigitalOcean using DEPLOY_SSH_KEY secret
- Commands on server:
  cd /var/www/nuclei-ai && git pull origin main
  pip install -r web-programming/backend/requirements.txt
  cd web-programming/frontend && npm ci && npm run build
  sudo systemctl restart nuclei-backend
  curl -f https://165.227.139.185.nip.io/health

Secrets required in GitHub repository settings:
DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY, DEPLOY_PORT
```

---

### Prompt 6.2 — DigitalOcean Production Server Setup

```
Set up a DigitalOcean Ubuntu 24.04 droplet (1GB RAM + 2GB swap) to serve NucleiAI:

1. Server hardening:
   - Disable root password SSH login (key only)
   - UFW: ufw allow 22,80,443 && ufw enable
   - Create 2GB swap: fallocate -l 2G /swapfile, mkswap, swapon, add to /etc/fstab
     (PyTorch requires >1GB RAM to load — swap prevents OOM kill)

2. Application:
   - Clone repo to /var/www/nuclei-ai/
   - Python venv: python3 -m venv venv && source venv/bin/activate
   - pip install -r web-programming/backend/requirements.txt
   - Create backend/.env with production values (SECRET_KEY, DATABASE_URL=neon postgres URL,
     ENV=production, FRONTEND_URL=https://165.227.139.185.nip.io, OAuth keys)
   - Build frontend: cd frontend && npm ci && npm run build
   - Run python -m backend.seed to create the first manager account

3. systemd service (/etc/systemd/system/nuclei-backend.service):
   [Unit]
   Description=NucleiAI FastAPI Backend
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/var/www/nuclei-ai/web-programming
   EnvironmentFile=/var/www/nuclei-ai/web-programming/backend/.env
   ExecStart=/var/www/nuclei-ai/venv/bin/uvicorn backend.main:app \
             --host 127.0.0.1 --port 8000 --workers 1
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target

4. nginx config:
   server {
       listen 443 ssl;
       server_name 165.227.139.185.nip.io;

       location /api/ { proxy_pass http://127.0.0.1:8000/api/; }
       location /auth/ { proxy_pass http://127.0.0.1:8000/auth/; }
       location /files/ { proxy_pass http://127.0.0.1:8000/files/; }
       location / {
           root /var/www/nuclei-ai/web-programming/frontend/dist;
           try_files $uri $uri/ /index.html;
       }
   }
   server { listen 80; return 301 https://$host$request_uri; }

5. SSL:
   certbot --nginx -d 165.227.139.185.nip.io --non-interactive --agree-tos
   Certbot adds a systemd timer to auto-renew the certificate.

6. Database:
   Use Neon.tech serverless PostgreSQL (free tier, auto-suspend on idle).
   Connection string format: postgresql://user:pass@host/dbname?sslmode=require
   The pool_pre_ping and pool_recycle=300 settings handle Neon's aggressive
   connection dropping behaviour.
```

---

## Phase 7 — Bootstrapping and Seeding

### Prompt 7.1 — First Manager Seed Script

```
Create backend/seed.py — idempotent one-time bootstrap for the first manager account:

Run with: python -m backend.seed (from web-programming/ directory)

Logic:
1. create_db_and_tables() — ensure all tables exist
2. Query for any existing manager — if found, print message and exit (idempotent)
3. Prompt: username (validate 3-50 chars)
4. Prompt: email (validate format with @ and domain)
5. Prompt: password using getpass.getpass() (hidden input, run through validate_password_strength)
6. Check uniqueness of username and email — exit with error if taken
7. Create User(role=UserRole.manager, hashed_password=hash_password(password))
8. session.add() + session.commit()
9. Print success confirmation

This is the ONLY way to create a manager — the API does not allow it.
Managers can then promote users to admin through the admin dashboard.
```

---

## Phase 8 — Error Handling and API Consistency

### Prompt 8.1 — Consistent Error Messages

```
Audit the entire backend and enforce a consistent error response contract:

Standard error messages:
- 401 "Invalid credentials."          — login failures (same for wrong email AND password)
- 401 "Not authenticated."            — missing or invalid JWT
- 401 "Token has been revoked."       — blacklisted token reuse after logout
- 403 "Insufficient permissions."     — role check failed
- 404 "Job not found."                — job doesn't exist or belongs to another user
- 404 "User not found."               — admin lookup of deleted user
- 409 "Username already taken."
- 409 "Email already registered."
- 422 from Pydantic                   — structured validation error with field path
- 429 "Too many requests."            — rate limit exceeded

Rules:
- Never return Python stack traces to the client
- Never distinguish "wrong email" from "wrong password" (prevents enumeration)
- Database errors → 500 with "Internal server error." (log full traceback server-side)
- File I/O errors → 500 with "Storage error." (log server-side)
- Pydantic 422 errors use FastAPI's default structured format — do not override
- All error responses use JSON: {"detail": "message"} format
```

---

*Document version: v1.0 — May 2026*
*NucleiAI — Istinye University Web Programming Project*
