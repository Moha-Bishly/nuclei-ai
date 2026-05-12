"""Central configuration — all values read from environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

ENV: str = os.getenv("ENV", "development")

# Guard against accidentally deploying with development settings.
# Rate limits, docs exposure, and dev endpoints all depend on this being correct.
if ENV not in ("development", "staging", "production"):
    print(f"FATAL: ENV='{ENV}' is not a recognised value. Use development, staging, or production.", file=sys.stderr)
    sys.exit(1)

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./nuclei.db")

_raw_secret = os.getenv("SECRET_KEY", "")
_INSECURE_DEFAULTS = {"dev-secret-change-in-production", "", "change-me", "secret"}

if not _raw_secret or _raw_secret in _INSECURE_DEFAULTS:
    if ENV == "production":
        print("FATAL: SECRET_KEY is missing or uses an insecure default. Set a strong random value.", file=sys.stderr)
        sys.exit(1)
    _raw_secret = "dev-secret-change-in-production"

if len(_raw_secret) < 32 and ENV != "development":
    print("FATAL: SECRET_KEY must be at least 32 characters.", file=sys.stderr)
    sys.exit(1)

SECRET_KEY: str = _raw_secret
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
TEMP_TOKEN_EXPIRE_MINUTES: int = 5

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

# OAuth providers (empty string = provider disabled)
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
DROPBOX_CLIENT_ID: str = os.getenv("DROPBOX_CLIENT_ID", "")
DROPBOX_CLIENT_SECRET: str = os.getenv("DROPBOX_CLIENT_SECRET", "")

# Email (SMTP) — for Email OTP
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", "noreply@nuclei.app"))
