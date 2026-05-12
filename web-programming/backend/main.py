"""FastAPI entry point for the Nuclei Analysis API.

Run from the project root (web-programming/):
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
"""

import csv
import hashlib
import html as _html
import io
import logging
import secrets
import threading  # used for _oauth_codes_lock
from contextlib import asynccontextmanager

import httpx
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Union

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
_log = logging.getLogger("nuclei")

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, SQLModel, select, text
from starlette.middleware.sessions import SessionMiddleware

from backend.auth_utils import (
    create_access_token,
    create_temp_token,
    decode_token,
    generate_otp,
    generate_reset_token,
    hash_otp,
    hash_password,
    send_otp_email,
    send_reset_code_email,
    verify_otp_hash,
    verify_password,
)
from backend.config import ENV, FRONTEND_URL, BACKEND_URL, SECRET_KEY
from backend.security import SecurityHeadersMiddleware, is_valid_image_bytes
from backend.crud import AnnotationService, JobService
from backend.database import create_db_and_tables, engine, get_session
from backend.dependencies import get_current_user, get_temp_token_user_id, require_role
from backend.models import AnalysisJob, Annotation, Comment, Favourite, Notification, Publication, RevokedToken, User, UserRole
from backend.oauth import oauth
from backend.schemas import (
    AnalysisResponse,
    AnnotationCreate,
    AnnotationResponse,
    ChangePasswordRequest,
    CreateAdminRequest,
    SelfRoleRequest,
    EmailOTPRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyResetCodeRequest,
    VerifyResetCodeResponse,
    EmailOTPVerifyRequest,
    HealthResponse,
    JobResponse,
    JobSummary,
    LoginRequest,
    RegisterRequest,
    RoleUpdateRequest,
    TokenResponse,
    TwoFactorRequiredResponse,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    CommentCreate,
    CommentResponse,
    NotificationResponse,
    PublicationResponse,
    PublishRequest,
    UpdateProfileRequest,
    UserResponse,
)
from backend.services import analysis_service
from backend.totp_utils import generate_totp_secret, get_totp_uri, verify_totp

RESULT_DIR = Path(__file__).resolve().parent / "storage" / "results"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

# Short-lived OAuth code store: code → (token, expires_at)
_oauth_codes: dict[str, tuple[str, datetime]] = {}
_oauth_codes_lock = threading.Lock()


def _store_oauth_code(token: str) -> str:
    code = secrets.token_urlsafe(16)
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    with _oauth_codes_lock:
        _oauth_codes[code] = (token, expires)
        now = datetime.now(timezone.utc)
        for c in [k for k, (_, e) in _oauth_codes.items() if e < now]:
            del _oauth_codes[c]
    return code


# Role groups used throughout admin logic
_ELEVATED = (UserRole.manager, UserRole.admin)       # can access admin endpoints
_MANAGEABLE = (UserRole.viewer, UserRole.researcher)  # roles that can be changed via dropdown


# ── Rate limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
_bearer = HTTPBearer(auto_error=False)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    analysis_service._ensure_model_loaded()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

_docs_url = "/docs" if ENV == "development" else None
_redoc_url = "/redoc" if ENV == "development" else None

app = FastAPI(
    title="Nuclei Analysis API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers — added first so they apply to every response
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# CORS: allow frontend URL and all Cloudflare Pages preview subdomains
_cors_origins = [FRONTEND_URL, "https://nuclei-ai-frontend.pages.dev"]
_cors_origin_regex = r"https://[a-z0-9]+\.nuclei-ai-frontend\.pages\.dev"
if ENV != "production":
    _cors_origins += ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
@app.get("/api/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    try:
        session.exec(text("SELECT 1"))
    except Exception as e:
        _log.error("DB health check failed: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return HealthResponse(**analysis_service.get_health())


# ── Auth: Register / Login / Me ───────────────────────────────────────────────

@app.post("/auth/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute" if ENV == "production" else "60/minute")
async def register(
    request: Request,
    data: RegisterRequest = Body(...),
    session: Session = Depends(get_session),
) -> UserResponse:
    existing = session.exec(
        select(User).where((User.email == data.email) | (User.username == data.username))
    ).first()
    if existing:
        if existing.email == data.email:
            # Detect OAuth-only accounts: their password is hash_password(f"oauth_{email}")
            if verify_password(f"oauth_{data.email}", existing.hashed_password):
                raise HTTPException(
                    status_code=409,
                    detail="This email is already linked to a social login. Please sign in with Google, GitHub, or Dropbox instead."
                )
            raise HTTPException(status_code=409, detail="An account with this email already exists. Please sign in.")
        raise HTTPException(status_code=409, detail="This username is already taken.")
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.viewer,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse.model_validate(user)


@app.post("/auth/login")
@limiter.limit("5/minute" if ENV == "production" else "60/minute")
async def login(
    request: Request,
    data: LoginRequest = Body(...),
    session: Session = Depends(get_session),
) -> Union[TokenResponse, TwoFactorRequiredResponse]:
    user = session.exec(select(User).where(User.email == data.email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    # Detect OAuth-only accounts trying to log in with password
    if verify_password(f"oauth_{data.email}", user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="This account uses social login. Please sign in with Google, GitHub, or Dropbox."
        )
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if user.totp_enabled:
        return TwoFactorRequiredResponse(temp_token=create_temp_token(user.id))

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@app.get("/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@app.post("/auth/logout", status_code=204)
def logout(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if creds:
        try:
            payload = decode_token(creds.credentials)
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            token_hash = hashlib.sha256(creds.credentials.encode()).hexdigest()
            existing = session.exec(
                select(RevokedToken).where(RevokedToken.token_hash == token_hash)
            ).first()
            if not existing:
                session.add(RevokedToken(token_hash=token_hash, expires_at=exp))
                # Clean up expired tokens while we're here
                now = datetime.now(timezone.utc)
                for expired in session.exec(
                    select(RevokedToken).where(RevokedToken.expires_at < now)
                ).all():
                    session.delete(expired)
                session.commit()
        except Exception:
            pass


@app.patch("/auth/me", response_model=UserResponse)
def update_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    if data.username is not None and data.username != current_user.username:
        clash = session.exec(select(User).where(User.username == data.username)).first()
        if clash:
            raise HTTPException(status_code=409, detail="Username already taken.")
        current_user.username = data.username
    if data.email is not None and data.email != current_user.email:
        clash = session.exec(select(User).where(User.email == data.email)).first()
        if clash:
            raise HTTPException(status_code=409, detail="Email already registered.")
        current_user.email = data.email
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserResponse.model_validate(current_user)


@app.post("/auth/change-password", response_model=UserResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(data.new_password)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserResponse.model_validate(current_user)


@app.patch("/auth/me/role", response_model=UserResponse)
def self_update_role(
    data: SelfRoleRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    """Viewer/researcher can switch their own role between viewer and researcher."""
    if current_user.role not in _MANAGEABLE:
        raise HTTPException(status_code=403, detail="Only viewers and researchers can change their own role.")
    current_user.role = UserRole(data.role)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ── Auth: Forgot / Reset Password ────────────────────────────────────────────

# Prefix stored in reset_token_hash during the code phase.
# Prevents raw 6-digit codes from being accepted by /auth/reset-password.
_RESET_CODE_PREFIX = "RESET_CODE:"


@app.post("/auth/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    user = session.exec(select(User).where(User.email == data.email)).first()
    # Always return the same message — never reveal whether email exists
    if user:
        code = generate_otp()   # 6-digit code, same generator as login OTP
        # Store prefixed hash so /auth/reset-password cannot accept this hash directly
        user.reset_token_hash = _RESET_CODE_PREFIX + hash_otp(code)
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        session.add(user)
        session.commit()
        send_reset_code_email(user.email, code)
    return {"message": "If that email exists, a verification code was sent."}


@app.post("/auth/verify-reset-code", response_model=VerifyResetCodeResponse)
@limiter.limit("5/minute")
async def verify_reset_code(
    request: Request,
    data: VerifyResetCodeRequest = Body(...),
    session: Session = Depends(get_session),
) -> VerifyResetCodeResponse:
    """Validate the 6-digit reset code.

    Returns a short-lived reset_token. This is NOT a login token — it has no
    auth scope, is never stored in the auth context, and only works with
    /auth/reset-password.
    """
    user = session.exec(select(User).where(User.email == data.email)).first()
    now = datetime.now(timezone.utc)
    stored = user.reset_token_hash if user else None
    valid = (
        user is not None
        and stored is not None
        and stored.startswith(_RESET_CODE_PREFIX)
        and user.reset_token_expires_at is not None
        and user.reset_token_expires_at.replace(tzinfo=timezone.utc) > now
        and stored == _RESET_CODE_PREFIX + hash_otp(data.code)
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Code is invalid or has expired.")
    # Code accepted — replace with a short-lived reset token (no prefix = accepted by /reset-password)
    reset_token = generate_reset_token()
    user.reset_token_hash = hash_otp(reset_token)   # type: ignore[union-attr]
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    session.add(user)
    session.commit()
    return VerifyResetCodeResponse(reset_token=reset_token)


@app.post("/auth/reset-password")
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    token_hash = hash_otp(data.token)
    user = session.exec(
        select(User).where(User.reset_token_hash == token_hash)
    ).first()
    now = datetime.now(timezone.utc)
    # Reject if not found, expired, or still in code phase (prefixed hash won't match)
    if (
        not user
        or not user.reset_token_expires_at
        or user.reset_token_expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired.")
    user.hashed_password = hash_password(data.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    session.add(user)
    session.commit()
    return {"message": "Password reset successfully. Please log in with your new password."}


# ── Auth: TOTP 2FA ────────────────────────────────────────────────────────────

@app.post("/auth/2fa/setup", response_model=TwoFactorSetupResponse)
def totp_setup(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TwoFactorSetupResponse:
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    session.add(current_user)
    session.commit()
    return TwoFactorSetupResponse(
        secret=secret,
        uri=get_totp_uri(secret, current_user.email),
    )


@app.post("/auth/2fa/verify-setup", response_model=UserResponse)
def totp_verify_setup(
    data: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /auth/2fa/setup first.")
    if not verify_totp(current_user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code.")
    current_user.totp_enabled = True
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserResponse.model_validate(current_user)


@app.post("/auth/2fa/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
async def totp_verify(
    request: Request,
    data: TwoFactorVerifyRequest,
    user_id: int = Depends(get_temp_token_user_id),
    session: Session = Depends(get_session),
) -> TokenResponse:
    user = session.get(User, user_id)
    if not user or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Invalid session.")
    if not verify_totp(user.totp_secret, data.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code.")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


# ── Auth: Email OTP ───────────────────────────────────────────────────────────

@app.post("/auth/email-otp/send")
@limiter.limit("3/minute")
async def email_otp_send(
    request: Request,
    data: EmailOTPRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    user = session.exec(select(User).where(User.email == data.email)).first()
    if user:
        code = generate_otp()
        user.email_otp_hash = hash_otp(code)
        user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        session.add(user)
        session.commit()
        send_otp_email(user.email, code)
    return {"message": "If that email is registered, a verification code was sent."}


@app.post("/auth/email-otp/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
async def email_otp_verify(
    request: Request,
    data: EmailOTPVerifyRequest = Body(...),
    session: Session = Depends(get_session),
) -> TokenResponse:
    user = session.exec(select(User).where(User.email == data.email)).first()
    now = datetime.now(timezone.utc)
    if not user or (
        not user.email_otp_hash
        or not user.email_otp_expires_at
        or user.email_otp_expires_at.replace(tzinfo=timezone.utc) < now
        or not verify_otp_hash(data.code, user.email_otp_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired code.")
    # Invalidate OTP after use
    user.email_otp_hash = None
    user.email_otp_expires_at = None
    session.add(user)
    session.commit()
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


# ── Auth: Google OAuth ────────────────────────────────────────────────────────

@app.get("/auth/google")
async def google_login(request: Request):
    if not hasattr(oauth, "google"):
        raise HTTPException(status_code=501, detail="Google OAuth not configured.")
    redirect_uri = f"{BACKEND_URL}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request, session: Session = Depends(get_session)):
    if not hasattr(oauth, "google"):
        raise HTTPException(status_code=501, detail="Google OAuth not configured.")
    token_data = await oauth.google.authorize_access_token(request)
    info = token_data.get("userinfo") or {}
    return _oauth_upsert_redirect(session, info.get("email", ""), info.get("name", ""))


# ── Auth: GitHub OAuth ────────────────────────────────────────────────────────

@app.get("/auth/github")
async def github_login(request: Request):
    if not hasattr(oauth, "github"):
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured.")
    redirect_uri = f"{BACKEND_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/github/callback", name="github_callback")
async def github_callback(request: Request, session: Session = Depends(get_session)):
    if not hasattr(oauth, "github"):
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured.")
    token_data = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token_data)
    info = resp.json() if resp else {}
    email = info.get("email") or f"gh_{info.get('id', 'unknown')}@github.invalid"
    return _oauth_upsert_redirect(session, email, info.get("login", ""))


# ── Auth: Dropbox OAuth ───────────────────────────────────────────────────────

@app.get("/auth/dropbox")
async def dropbox_login(request: Request):
    if not hasattr(oauth, "dropbox"):
        raise HTTPException(status_code=501, detail="Dropbox OAuth not configured.")
    redirect_uri = f"{BACKEND_URL}/auth/dropbox/callback"
    return await oauth.dropbox.authorize_redirect(request, redirect_uri)


@app.get("/auth/dropbox/callback", name="dropbox_callback")
async def dropbox_callback(request: Request, session: Session = Depends(get_session)):
    if not hasattr(oauth, "dropbox"):
        raise HTTPException(status_code=501, detail="Dropbox OAuth not configured.")
    token_data = await oauth.dropbox.authorize_access_token(request)
    access_token = token_data.get("access_token", "")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.dropboxapi.com/2/users/get_current_account",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            content=b"null",
        )
        info = r.json() if r.status_code == 200 else {}
    email = info.get("email", "")
    name = info.get("name", {}).get("display_name", "") if isinstance(info.get("name"), dict) else ""
    return _oauth_upsert_redirect(session, email, name)


# ── OAuth shared helper ───────────────────────────────────────────────────────

def _oauth_upsert_redirect(session: Session, email: str, display_name: str) -> RedirectResponse:
    if not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_no_email")
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        # Block if the existing account was registered with a password (not OAuth)
        if not verify_password(f"oauth_{email}", user.hashed_password):
            return RedirectResponse(f"{FRONTEND_URL}/login?error=email_password_account")
        # Existing OAuth account — log in
    else:
        # New user — create an OAuth account
        base = (display_name or email.split("@")[0])[:50].replace(" ", "_") or "user"
        username = base
        suffix = 1
        while session.exec(select(User).where(User.username == username)).first():
            username = f"{base}{suffix}"
            suffix += 1
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(f"oauth_{email}"),  # unusable placeholder
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    token = create_access_token(user.id)
    code = _store_oauth_code(token)
    return RedirectResponse(f"{FRONTEND_URL}/oauth-callback?code={code}")


# ── OAuth code exchange ───────────────────────────────────────────────────────

@app.post("/auth/oauth/exchange")
def oauth_exchange(code: str = Body(..., embed=True)) -> dict:
    """Exchange a short-lived OAuth code for a JWT. The code is single-use."""
    with _oauth_codes_lock:
        entry = _oauth_codes.pop(code, None)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth code.")
    token, expires = entry
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth code.")
    return {"access_token": token, "token_type": "bearer"}


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalysisResponse, status_code=201)
@limiter.limit("20/minute")
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 20 MB.")
    if not is_valid_image_bytes(payload):
        raise HTTPException(status_code=400, detail="File content is not a recognised image format.")
    try:
        result = analysis_service.analyze(payload, file.filename or "upload.png")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    JobService.create_job(session, {
        "job_id": result.job_id,
        "user_id": current_user.id,
        "status": result.status,
        "cell_count": result.cell_count,
        "mode": result.metadata["mode"],
        "original_filename": result.metadata["original_filename"],
        "input_url": result.input_url,
        "mask_url": result.mask_url,
        "overlay_url": result.overlay_url,
        "processing_ms": result.metadata["processing_ms"],
        "threshold": result.metadata.get("threshold"),
        "min_area": result.metadata["min_area"],
        "image_size": result.metadata["image_size"],
        "device": result.metadata["device"],
    })
    return AnalysisResponse(**analysis_service.result_to_dict(result))


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=List[JobSummary])
def list_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[JobSummary]:
    if current_user.role in _ELEVATED:
        jobs = JobService.list_jobs(session, skip=skip, limit=limit)
    else:
        jobs = JobService.list_jobs_by_user(session, current_user.id, skip=skip, limit=limit)
    result = []
    for j in jobs:
        pub = session.exec(select(Publication).where(Publication.job_id == j.id)).first()
        result.append(JobSummary(
            id=j.id, job_id=j.job_id, status=j.status, cell_count=j.cell_count,
            mode=j.mode, original_filename=j.original_filename, created_at=j.created_at,
            annotation_count=len(j.annotations) if j.annotations else 0,
            publication_id=pub.id if pub else None,
        ))
    return result


# NOTE: this route must stay above /{job_id} so "export.csv" is not captured as a job_id
@app.get("/api/jobs/export.csv", include_in_schema=True)
def export_jobs_csv(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download all accessible jobs as a CSV file."""
    if current_user.role in _ELEVATED:
        jobs = JobService.list_jobs(session, skip=0, limit=10_000)
    else:
        jobs = JobService.list_jobs_by_user(session, current_user.id, skip=0, limit=10_000)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "job_id", "original_filename", "cell_count", "mode",
        "device", "processing_ms", "threshold", "min_area",
        "image_size", "status", "created_at",
    ])
    for j in jobs:
        writer.writerow([
            j.job_id, j.original_filename, j.cell_count, j.mode,
            j.device, j.processing_ms, j.threshold, j.min_area,
            j.image_size, j.status,
            j.created_at.isoformat(),
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nuclei-jobs.csv"},
    )


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    job = JobService.get_job_by_job_id(session, job_id)
    if current_user.role not in _ELEVATED and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")
    return job


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = JobService.get_job_by_job_id(session, job_id)
    if current_user.role not in _ELEVATED and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")
    JobService.delete_job(session, job_id)


# ── Annotations ───────────────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/annotations", response_model=AnnotationResponse, status_code=201)
def create_annotation(
    job_id: str,
    data: AnnotationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AnnotationResponse:
    return AnnotationService.create_annotation(session, job_id, data, user_id=current_user.id)


@app.get("/api/jobs/{job_id}/annotations", response_model=List[AnnotationResponse])
def list_annotations(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[AnnotationResponse]:
    return AnnotationService.list_annotations(session, job_id)


@app.delete("/api/annotations/{annotation_id}", status_code=204)
def delete_annotation(
    annotation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    AnnotationService.delete_annotation(session, annotation_id)


# ── File serving ──────────────────────────────────────────────────────────────

@app.get("/files/{filename}")
@limiter.limit("120/minute")
def get_file(request: Request, filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    target = (RESULT_DIR / filename).resolve()
    if not str(target).startswith(str(RESULT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(target)


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.get("/admin/users", response_model=List[UserResponse])
def admin_list_users(
    session: Session = Depends(get_session),
    current: User = Depends(require_role(*_ELEVATED)),
) -> List[UserResponse]:
    """Manager sees everyone. Admin sees non-managers only."""
    users = session.exec(select(User)).all()
    if current.role == UserRole.admin:
        users = [u for u in users if u.role != UserRole.manager]
    return [UserResponse.model_validate(u) for u in users]


@app.post("/admin/users", response_model=UserResponse, status_code=201)
def admin_create_admin(
    data: CreateAdminRequest,
    session: Session = Depends(get_session),
    _manager: User = Depends(require_role(UserRole.manager)),
) -> UserResponse:
    """Manager-only: create a new admin account."""
    clash = session.exec(
        select(User).where((User.email == data.email) | (User.username == data.username))
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="Username or email already registered.")
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse.model_validate(user)


@app.patch("/admin/users/{user_id}/role", response_model=UserResponse)
def admin_update_role(
    user_id: int,
    data: RoleUpdateRequest,
    session: Session = Depends(get_session),
    current: User = Depends(require_role(*_ELEVATED)),
) -> UserResponse:
    """Change a user's role — only viewer↔researcher swaps are allowed here."""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == current.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role.")
    # Managers cannot be touched by anyone
    if target.role == UserRole.manager:
        raise HTTPException(status_code=403, detail="Cannot modify a manager.")
    # Admins cannot touch other admins
    if current.role == UserRole.admin and target.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin cannot modify another admin.")
    # Only manager can promote to admin
    if data.role == "admin" and current.role != UserRole.manager:
        raise HTTPException(status_code=403, detail="Only a manager can assign the admin role.")
    old_role = target.role
    target.role = UserRole(data.role)
    session.add(target)
    session.commit()
    session.refresh(target)
    _log.info("AUDIT role_change actor=%s target=%s %s→%s", current.username, target.username, old_role.value, data.role)
    return UserResponse.model_validate(target)


@app.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role(*_ELEVATED)),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself.")
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    # Nobody can delete a manager
    if target.role == UserRole.manager:
        raise HTTPException(status_code=403, detail="Cannot delete a manager.")
    # Admin can only delete viewers/researchers
    if current.role == UserRole.admin and target.role not in _MANAGEABLE:
        raise HTTPException(status_code=403, detail="Admin cannot delete another admin.")
    # Clean up owned records before deleting the user
    for ann in session.exec(select(Annotation).where(Annotation.user_id == user_id)).all():
        session.delete(ann)
    for fav in session.exec(select(Favourite).where(Favourite.user_id == user_id)).all():
        session.delete(fav)
    for notif in session.exec(select(Notification).where(
        (Notification.user_id == user_id) | (Notification.actor_id == user_id)
    )).all():
        session.delete(notif)
    for comment in session.exec(select(Comment).where(Comment.user_id == user_id)).all():
        session.delete(comment)
    session.delete(target)
    session.commit()
    _log.info("AUDIT user_deleted actor=%s target=%s (role=%s)", current.username, target.username, target.role.value)


@app.get("/admin/stats")
def admin_stats(
    session: Session = Depends(get_session),
    _elevated: User = Depends(require_role(*_ELEVATED)),
) -> dict:
    users = list(session.exec(select(User)).all())
    jobs = list(session.exec(select(AnalysisJob)).all())
    by_role = {role.value: 0 for role in UserRole}
    for u in users:
        by_role[u.role.value] += 1
    return {
        "total_users": len(users),
        "users_by_role": by_role,
        "total_jobs": len(jobs),
        "total_cells": sum(j.cell_count for j in jobs),
    }


# ── Explore / Publish / Favourites ───────────────────────────────────────────

def _pub_to_response(pub: Publication, current_user_id: int, session: Session) -> PublicationResponse:
    job = pub.job
    fav = session.exec(
        select(Favourite).where(Favourite.publication_id == pub.id, Favourite.user_id == current_user_id)
    ).first()
    comment_count = len(session.exec(select(Comment).where(Comment.publication_id == pub.id)).all())
    return PublicationResponse(
        id=pub.id,
        job_id=pub.job_id,
        user_id=pub.user_id,
        job_uid=job.job_id if job else "",
        username=pub.user.username if pub.user else "unknown",
        headline=pub.headline,
        description=pub.description,
        cell_count=job.cell_count if job else 0,
        mode=job.mode if job else "fallback-demo",
        overlay_url=job.overlay_url if job else "",
        mask_url=job.mask_url if job else "",
        input_url=job.input_url if job else "",
        original_filename=job.original_filename if job else "",
        created_at=pub.created_at,
        is_favourited=fav is not None,
        comment_count=comment_count,
    )


@app.post("/api/jobs/{job_id}/publish", response_model=PublicationResponse, status_code=201)
def publish_job(
    job_id: str,
    data: PublishRequest = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PublicationResponse:
    job = JobService.get_job_by_job_id(session, job_id)
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")
    existing = session.exec(select(Publication).where(Publication.job_id == job.id)).first()
    if existing:
        raise HTTPException(status_code=409, detail="This job is already published.")
    pub = Publication(
        job_id=job.id,
        user_id=current_user.id,
        headline=data.headline,
        description=data.description,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)
    return _pub_to_response(pub, current_user.id, session)


@app.delete("/api/publications/{pub_id}", status_code=204)
def unpublish(
    pub_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found.")
    if pub.user_id != current_user.id and current_user.role not in _ELEVATED:
        raise HTTPException(status_code=403, detail="Not your publication.")
    session.exec(select(Favourite).where(Favourite.publication_id == pub_id))
    for fav in session.exec(select(Favourite).where(Favourite.publication_id == pub_id)).all():
        session.delete(fav)
    session.delete(pub)
    session.commit()


@app.get("/api/explore", response_model=List[PublicationResponse])
def explore(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[PublicationResponse]:
    pubs = session.exec(select(Publication).order_by(Publication.created_at.desc())).all()
    return [_pub_to_response(p, current_user.id, session) for p in pubs]


@app.get("/api/jobs/{job_id}/publication", response_model=PublicationResponse)
def get_job_publication(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PublicationResponse:
    job = JobService.get_job_by_job_id(session, job_id)
    pub = session.exec(select(Publication).where(Publication.job_id == job.id)).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Not published.")
    return _pub_to_response(pub, current_user.id, session)


@app.post("/api/publications/{pub_id}/favourite", status_code=201)
def add_favourite(
    pub_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found.")
    existing = session.exec(
        select(Favourite).where(Favourite.publication_id == pub_id, Favourite.user_id == current_user.id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already in favourites.")
    session.add(Favourite(publication_id=pub_id, user_id=current_user.id))
    # Notify publication owner (not self)
    if pub.user_id != current_user.id:
        session.add(Notification(
            user_id=pub.user_id, actor_id=current_user.id,
            kind="favourite", publication_id=pub_id,
        ))
    session.commit()
    return {"status": "added"}


@app.delete("/api/publications/{pub_id}/favourite", status_code=204)
def remove_favourite(
    pub_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    fav = session.exec(
        select(Favourite).where(Favourite.publication_id == pub_id, Favourite.user_id == current_user.id)
    ).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Not in favourites.")
    session.delete(fav)
    session.commit()


@app.get("/api/favourites", response_model=List[PublicationResponse])
def list_favourites(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[PublicationResponse]:
    favs = session.exec(
        select(Favourite).where(Favourite.user_id == current_user.id)
        .order_by(Favourite.created_at.desc())
    ).all()
    result = []
    for fav in favs:
        pub = session.get(Publication, fav.publication_id)
        if pub:
            result.append(_pub_to_response(pub, current_user.id, session))
    return result


# ── Comments ──────────────────────────────────────────────────────────────────

@app.get("/api/publications/{pub_id}/comments", response_model=List[CommentResponse])
def list_comments(pub_id: int, session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)) -> List[CommentResponse]:
    comments = session.exec(select(Comment).where(Comment.publication_id == pub_id)
                            .order_by(Comment.created_at)).all()
    result = []
    for c in comments:
        user = session.get(User, c.user_id)
        result.append(CommentResponse(
            id=c.id, publication_id=c.publication_id, user_id=c.user_id,
            username=user.username if user else "unknown",
            text=c.text, created_at=c.created_at,
        ))
    return result


@app.post("/api/publications/{pub_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(pub_id: int, data: CommentCreate = Body(...),
                session: Session = Depends(get_session),
                current_user: User = Depends(get_current_user)) -> CommentResponse:
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found.")
    comment = Comment(publication_id=pub_id, user_id=current_user.id, text=data.text)
    session.add(comment)
    if pub.user_id != current_user.id:
        session.add(Notification(
            user_id=pub.user_id, actor_id=current_user.id,
            kind="comment", publication_id=pub_id,
        ))
    session.commit()
    session.refresh(comment)
    return CommentResponse(
        id=comment.id, publication_id=comment.publication_id, user_id=comment.user_id,
        username=current_user.username, text=comment.text, created_at=comment.created_at,
    )


@app.delete("/api/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: int, session: Session = Depends(get_session),
                   current_user: User = Depends(get_current_user)):
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if comment.user_id != current_user.id and current_user.role not in _ELEVATED:
        raise HTTPException(status_code=403, detail="Not your comment.")
    session.delete(comment)
    session.commit()


# ── Notifications ─────────────────────────────────────────────────────────────

@app.get("/api/notifications", response_model=List[NotificationResponse])
def list_notifications(session: Session = Depends(get_session),
                       current_user: User = Depends(get_current_user)) -> List[NotificationResponse]:
    notifs = session.exec(
        select(Notification).where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc()).limit(50)
    ).all()
    result = []
    for n in notifs:
        actor = session.get(User, n.actor_id)
        pub = session.get(Publication, n.publication_id)
        result.append(NotificationResponse(
            id=n.id,
            actor_username=actor.username if actor else "unknown",
            kind=n.kind,
            publication_id=n.publication_id,
            publication_headline=pub.headline if pub else "",
            read=n.read,
            created_at=n.created_at,
        ))
    return result


@app.post("/api/notifications/read-all", status_code=204)
def mark_all_read(session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)):
    notifs = session.exec(
        select(Notification).where(Notification.user_id == current_user.id, Notification.read == False)
    ).all()
    for n in notifs:
        n.read = True
        session.add(n)
    session.commit()


@app.get("/api/notifications/unread-count")
def unread_count(session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)) -> dict:
    count = len(session.exec(
        select(Notification).where(Notification.user_id == current_user.id, Notification.read == False)
    ).all())
    return {"count": count}


# ── User profiles ─────────────────────────────────────────────────────────────

@app.get("/api/users/{username}/publications", response_model=List[PublicationResponse])
def user_publications(username: str, session: Session = Depends(get_session),
                      current_user: User = Depends(get_current_user)) -> List[PublicationResponse]:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    pubs = session.exec(
        select(Publication).where(Publication.user_id == user.id)
        .order_by(Publication.created_at.desc())
    ).all()
    return [_pub_to_response(p, current_user.id, session) for p in pubs]


# ── Re-analyze ────────────────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/reanalyze", response_model=AnalysisResponse, status_code=201)
async def reanalyze_job(job_id: str, session: Session = Depends(get_session),
                        current_user: User = Depends(get_current_user)) -> AnalysisResponse:
    job = JobService.get_job_by_job_id(session, job_id)
    if current_user.role not in _ELEVATED and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job.")
    upload_path = RESULT_DIR.parent / "uploads" / Path(job.input_url.split("/")[-1].replace("_input", ""))
    # Fall back to the saved input PNG if original upload not found
    input_png = RESULT_DIR / f"{job.job_id}_input.png"
    source = input_png if input_png.exists() else None
    if not source or not source.exists():
        raise HTTPException(status_code=404, detail="Original image not found for re-analysis.")
    image_bytes = source.read_bytes()
    if not is_valid_image_bytes(image_bytes):
        raise HTTPException(status_code=400, detail="Stored image is not valid.")
    try:
        result = analysis_service.analyze(image_bytes, job.original_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    new_job = JobService.create_job(session, result, user_id=current_user.id)
    return AnalysisResponse(**analysis_service.result_to_dict(result))


# ── PDF Report ────────────────────────────────────────────────────────────────

@app.get("/api/jobs/{job_id}/report.pdf")
def download_pdf_report(
    job_id: str,
    tz_offset: int = Query(default=0, ge=-12, le=14),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet
    import io as _io

    job = JobService.get_job_by_job_id(session, job_id)
    is_owner = job.user_id == current_user.id
    is_elevated = current_user.role in _ELEVATED
    is_published = session.exec(select(Publication).where(Publication.job_id == job.id)).first() is not None
    if not (is_owner or is_elevated or is_published):
        raise HTTPException(status_code=403, detail="Not your job.")

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Escape all user-controlled strings before passing to ReportLab Paragraph,
    # which parses XML markup and would interpret tags like <font> or <b>.
    def _p(text: str) -> str:
        return _html.escape(str(text))

    story.append(Paragraph("NucleiAI — Analysis Report", styles["Title"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(f"Job ID: {_p(job.job_id)}", styles["Normal"]))
    story.append(Paragraph(f"File: {_p(job.original_filename)}", styles["Normal"]))
    local_tz = timezone(timedelta(hours=tz_offset))
    tz_label = f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset}:00"
    story.append(Paragraph(f"Generated: {datetime.now(local_tz).strftime('%Y-%m-%d %H:%M')} ({tz_label})", styles["Normal"]))
    story.append(Spacer(1, 0.6*cm))

    data = [
        ["Metric", "Value"],
        ["Cell Count", str(job.cell_count)],
        ["Mode", _p(job.mode)],
        ["Device", _p(job.device)],
        ["Image Size", f"{job.image_size}×{job.image_size}"],
        ["Processing Time", f"{job.processing_ms} ms"],
        ["Threshold", str(job.threshold) if job.threshold else "N/A (fallback)"],
        ["Min Area Filter", str(job.min_area)],
        ["Status", _p(job.status)],
        ["Created", job.created_at.strftime("%Y-%m-%d %H:%M UTC")],
    ]
    t = Table(data, colWidths=[7*cm, 9*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.8*cm))

    # Add overlay image if it exists
    overlay_path = RESULT_DIR / f"{job.job_id}_overlay.png"
    if overlay_path.exists():
        story.append(Paragraph("Overlay Image", styles["Heading2"]))
        story.append(Spacer(1, 0.3*cm))
        img = RLImage(str(overlay_path), width=12*cm, height=12*cm)
        story.append(img)

    doc.build(story)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.read()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=nuclei-report-{job.job_id}.pdf"},
    )


# ── Dev-only utilities ────────────────────────────────────────────────────────

if ENV != "production":
    @app.post("/reset-db", include_in_schema=False)
    def reset_db(session: Session = Depends(get_session)) -> dict:
        with engine.connect() as conn:
            for table in reversed(SQLModel.metadata.sorted_tables):
                conn.execute(text(f"DELETE FROM {table.name}"))
            conn.commit()
        return {"status": "reset"}

    @app.post("/dev/promote-admin", include_in_schema=False)
    def dev_promote_admin(data: dict = Body(...), session: Session = Depends(get_session)) -> dict:
        """CI/dev only: promote a user to admin by email. Never registered in production."""
        user = session.exec(select(User).where(User.email == data["email"])).first()
        if user:
            user.role = UserRole.admin
            session.add(user)
            session.commit()
        return {"ok": True}
