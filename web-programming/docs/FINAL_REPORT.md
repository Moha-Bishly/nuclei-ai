# NucleiAI — Final Project Report

**AI-Powered Microscopy Analysis System for Nuclei Segmentation and Cell Counting**

---

## 1. Cover Page

| Field | Value |
|---|---|
| Project Title | NucleiAI — AI-Powered Microscopy Analysis System |
| Course | Web Programming |
| University | Istinye University |
| Submission Date | May 2026 |
| Live URL | https://165.227.139.185.nip.io |
| Repository | https://github.com/Moha-Bishly/nuclei-ai |

---

## 2. Executive Summary

NucleiAI is a fully deployed, production-ready web platform that uses artificial intelligence to automatically segment and count cell nuclei in histopathology microscopy images. A researcher uploads a microscopy image through the web interface and receives within seconds a precise cell nucleus count, a segmentation mask, a colour-coded overlay visualisation, and a downloadable PDF report — all powered by a custom-trained U-Net deep learning model.

The project solves a real problem in biomedical research: manual nuclei counting is slow, subjective, inconsistent, and does not scale. By replacing the manual process with an AI pipeline, NucleiAI delivers consistent, reproducible measurements and frees researchers to focus on interpretation rather than counting.

The platform is live and accessible at **https://165.227.139.185.nip.io**, deployed on a DigitalOcean cloud server with a Neon managed PostgreSQL database, automated CI/CD via GitHub Actions, and full HTTPS via Let's Encrypt.

---

## 3. Problem Statement

Nuclei counting on microscopy images is a foundational measurement in histopathology and cell biology. In practice, it is still performed manually or with semi-automated tools that require heavy operator tuning. This creates three critical problems:

1. **Manual counting is slow.** Annotating a single image can take 20–30 minutes. Studies that produce hundreds of images become impractical at this pace.

2. **Manual analysis is inconsistent.** Counts vary between different observers and even between sessions of the same observer, which weakens statistical confidence in downstream results.

3. **Researchers need faster and more reliable results** to iterate on experiments and meet publication timelines.

NucleiAI addresses all three problems with a single, web-accessible AI platform that processes an image in under 2 seconds with consistent, operator-independent results.

---

## 4. Solution Overview

NucleiAI is a multi-tier web application with four interacting layers:

1. **Frontend** — A React + TypeScript single-page application with a dark, modern UI that allows users to upload images, run analyses, view results, and manage their account.

2. **Backend API** — A FastAPI (Python) REST API that handles authentication, file uploads, analysis orchestration, user management, and result storage.

3. **AI Processing Layer** — A PyTorch U-Net model with a ResNet-18 encoder trained on annotated histopathology datasets. It performs image preprocessing, semantic segmentation, post-processing, connected-component counting, and result generation.

4. **Database & Storage** — A PostgreSQL database (hosted on Neon) stores users, analysis jobs, and results. Image files and output artefacts are stored on the server's filesystem.

---

## 5. Technology Stack

### 5.1 Frontend

| Technology | Version | Purpose |
|---|---|---|
| React | 18 | UI component framework |
| TypeScript | 5 | Type-safe JavaScript |
| Vite | 5 | Build tool and dev server |
| React Router | 6 | Client-side routing |
| Playwright | Latest | End-to-end testing |

### 5.2 Backend

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Backend language |
| FastAPI | 0.136 | REST API framework |
| Uvicorn | 0.46 | ASGI server |
| SQLModel | 0.0.38 | ORM (built on SQLAlchemy + Pydantic) |
| Pydantic | 2.13 | Data validation and serialisation |
| psycopg2-binary | 2.9 | PostgreSQL driver |
| python-jose | 3.5 | JWT token creation and validation |
| bcrypt | 5.0 | Password hashing |
| pyotp | 2.9 | TOTP two-factor authentication |
| authlib | 1.7 | OAuth 2.0 client (Google, GitHub, Dropbox) |
| slowapi | 0.1.9 | API rate limiting |
| httpx | 0.28 | Async HTTP client |
| pytest | 9 | Backend unit and integration testing |

### 5.3 AI / Machine Learning

| Technology | Version | Purpose |
|---|---|---|
| PyTorch | 2.11 | Deep learning framework |
| torchvision | 0.26 | Image transforms and pretrained encoders |
| segmentation-models-pytorch | 0.5 | U-Net architecture with ResNet-18 encoder |
| timm | 1.0 | Pretrained model library |
| OpenCV (headless) | 4.13 | Image preprocessing and postprocessing |
| scikit-image | 0.26 | Connected-component labelling and morphology |
| NumPy | 2.4 | Array operations |
| Pillow | 12 | Image I/O |
| albumentations | 2.0 | Training data augmentation |
| scipy | 1.17 | Scientific computing utilities |
| scikit-learn | 1.8 | Metrics and evaluation |

### 5.4 Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| DigitalOcean (Ubuntu 24.04, 1GB RAM) | Cloud server hosting backend + frontend |
| Neon.tech | Managed PostgreSQL database |
| nginx | Reverse proxy, static file serving, SSL termination |
| Let's Encrypt + Certbot | Free HTTPS/TLS certificates |
| GitHub Actions | CI/CD pipeline (tests → deploy) |
| nip.io | DNS wildcard service for IP-based domain |

---

## 6. System Architecture

```
┌─────────────────────────────────────────────┐
│         Browser (React + TypeScript)         │
│   https://165.227.139.185.nip.io            │
└─────────────────────────────────────────────┘
                     │ HTTPS
┌─────────────────────────────────────────────┐
│              nginx (reverse proxy)           │
│  /        → frontend static files (dist/)   │
│  /api/    → FastAPI backend (port 8000)     │
│  /auth/   → FastAPI OAuth callbacks         │
└─────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────┐
│         FastAPI Backend (Python 3.12)        │
│  • REST API endpoints                        │
│  • JWT authentication                        │
│  • OAuth 2.0 (Google, GitHub, Dropbox)      │
│  • Rate limiting (slowapi)                   │
│  • AI analysis orchestration                 │
└─────────────────────────────────────────────┘
          │                        │
┌──────────────────┐   ┌──────────────────────┐
│   AI Processing  │   │  PostgreSQL (Neon)    │
│   Layer          │   │  • Users              │
│   • U-Net model  │   │  • Analysis jobs      │
│   • Segmentation │   │  • Results            │
│   • Counting     │   │  • Notifications      │
└──────────────────┘   └──────────────────────┘
          │
┌──────────────────┐
│  File Storage    │
│  • Uploads       │
│  • Masks         │
│  • Overlays      │
│  • Reports       │
└──────────────────┘
```

---

## 7. AI Model — U-Net Architecture

### 7.1 Model Architecture

The core of NucleiAI is a **U-Net** convolutional neural network with a **ResNet-18 encoder** (pretrained on ImageNet). U-Net was selected because it was originally designed for biomedical image segmentation and excels in situations where training data is limited.

- **Encoder**: ResNet-18 (pretrained on ImageNet) — extracts hierarchical features from the input image
- **Decoder**: Symmetric upsampling path with skip connections from the encoder
- **Output**: Binary segmentation mask (nucleus vs. background)
- **Loss function**: Combined Dice Loss + Binary Cross-Entropy (BCE)
- **Framework**: PyTorch + segmentation-models-pytorch

### 7.2 Training

- **Dataset**: Annotated histopathology microscopy images with ground-truth XML annotations marking individual nuclei
- **Augmentation**: Random flips, rotations, brightness/contrast changes (albumentations)
- **Input resolution**: 256×256 pixels (images are tiled/resized as needed)
- **Output**: Binary mask at the same resolution

### 7.3 Inference Pipeline

When a user submits an image for analysis, the following pipeline executes:

1. **Load & preprocess** — Image is loaded, resized to 256×256, normalised to ImageNet statistics
2. **U-Net inference** — Model produces a probability map (0–1 per pixel)
3. **Thresholding** — Probability map is binarised to produce a binary mask
4. **Morphological cleanup** — Small holes are filled, small noise regions are removed
5. **Connected-component labelling** — scikit-image labels individual connected regions (nuclei)
6. **Cell count** — Number of connected components = estimated nucleus count
7. **Overlay generation** — Colour-coded overlay of the mask on the original image
8. **Result storage** — Count, mask, and overlay are saved; job record is updated in the database

### 7.4 Performance

- **Processing time**: Under 2 seconds per image on CPU
- **Hardware**: CPU inference (no GPU required in production)
- **Limitation**: Connected-component counting can under-count in dense regions where nuclei touch — this is the primary source of error in the current implementation

---

## 8. Features Implemented

### 8.1 Authentication & Security

| Feature | Description |
|---|---|
| Password login | Email + password with bcrypt hashing |
| Email OTP login | 6-digit one-time code sent by email |
| Password reset | Secure token-based reset flow |
| JWT tokens | Signed access tokens (60-minute expiry) |
| TOTP 2FA | Google Authenticator-compatible two-factor authentication |
| OAuth — Google | Sign in with Google |
| OAuth — GitHub | Sign in with GitHub |
| OAuth — Dropbox | Sign in with Dropbox |
| Rate limiting | Per-endpoint rate limits to prevent abuse |
| Role-based access | 4-tier role system: manager, admin, researcher, viewer |

### 8.2 Analysis Features

| Feature | Description |
|---|---|
| Image upload | Upload microscopy images (JPEG, PNG, TIFF) |
| AI analysis | U-Net segmentation + nucleus counting |
| Segmentation mask | Black/white mask of detected nuclei |
| Overlay visualisation | Colour-coded overlay on original image |
| Cell count | Exact count of detected nuclei |
| Analysis history | Full history of all past analyses |
| CSV export | Export all analysis results as CSV |
| PDF report | Download a formatted PDF report of any analysis |
| Explore page | Browse published analyses from other users |
| Favourites | Save analyses to a personal favourites list |

### 8.3 User Management

| Feature | Description |
|---|---|
| User profiles | Username, email, avatar, account settings |
| Role management | Managers can promote/demote users |
| User listing | Admins can view and manage all users |
| Notification system | In-app notifications for account events |

### 8.4 Platform Features

| Feature | Description |
|---|---|
| Dark UI | Modern dark-themed responsive interface |
| Mobile-friendly | Responsive layout for all screen sizes |
| HTTPS | Full SSL/TLS encryption via Let's Encrypt |
| Health endpoint | `/api/health` reports model and system status |
| Auto-deploy | GitHub Actions deploys on every push to main |

---

## 9. Database Schema

The PostgreSQL database (Neon) contains the following core tables:

| Table | Purpose |
|---|---|
| `user` | User accounts, credentials, roles, 2FA settings |
| `job` | Analysis job records (status, image path, results) |
| `notification` | User notification records |

The database is automatically created and migrated on application startup using SQLModel's `create_all()`.

---

## 10. API Design

The backend exposes a RESTful API under the `/api/` prefix. Key endpoint groups:

| Prefix | Purpose |
|---|---|
| `/api/auth/` | Registration, login, logout, password reset, 2FA |
| `/auth/google`, `/auth/github`, `/auth/dropbox` | OAuth login flows |
| `/api/analyze` | Submit an image for AI analysis |
| `/api/jobs/` | List, retrieve, and export analysis jobs |
| `/api/files/` | Serve generated result files (masks, overlays) |
| `/api/users/` | User management (admin/manager only) |
| `/api/notifications/` | Notification management |
| `/api/health` | System health and model status |

All endpoints are documented automatically by FastAPI's OpenAPI integration (accessible at `/docs` in development mode).

---

## 11. Security Implementation

Security was treated as a first-class concern throughout the project:

- **Password hashing**: All passwords are hashed with bcrypt (cost factor 12) — plaintext passwords are never stored
- **JWT authentication**: Access tokens are signed with HS256 and expire after 60 minutes
- **Token revocation**: Logged-out tokens are added to an in-memory blacklist until expiry
- **TOTP 2FA**: Users can enable Google Authenticator-compatible TOTP on their account
- **OAuth 2.0**: Secure social login via Authlib with state parameter CSRF protection
- **Rate limiting**: All sensitive endpoints are rate-limited (slowapi) to prevent brute force
- **HTTPS only**: nginx enforces HTTPS redirection; HTTP is rejected
- **CORS policy**: Only the production frontend origin is allowed to make cross-origin requests
- **Input validation**: All request bodies are validated by Pydantic before reaching business logic
- **Role-based access**: Endpoints verify the user's role before performing privileged operations
- **Password strength**: Registration enforces uppercase, lowercase, number, and special character requirements

---

## 12. Testing

### 12.1 Backend Tests (pytest)

The backend includes a pytest test suite covering:
- Authentication flows (register, login, token validation)
- Analysis endpoint behaviour
- Role-based access control
- Input validation edge cases

### 12.2 Frontend Tests (Playwright)

End-to-end tests using Playwright cover:
- Login and registration flows
- Image upload and analysis submission
- Result page rendering

### 12.3 CI/CD Integration

All tests run automatically on every push to `main` via GitHub Actions. A push only triggers deployment if all tests pass.

---

## 13. Deployment

### 13.1 Infrastructure

| Component | Service |
|---|---|
| Server | DigitalOcean Droplet — Ubuntu 24.04, 1GB RAM, Frankfurt |
| Database | Neon.tech — managed PostgreSQL (free tier) |
| Web server | nginx — reverse proxy + static file serving |
| SSL | Let's Encrypt + Certbot (auto-renewing) |
| Process manager | systemd — keeps the backend alive across reboots |

### 13.2 Memory Optimisation

PyTorch requires significant RAM. On the 1GB droplet:
- **2GB swap file** is configured to handle PyTorch's memory requirements
- **1 uvicorn worker** (not multiple) to conserve memory
- **CPU-only inference** (no GPU) — this is sufficient for the use case

### 13.3 CI/CD Pipeline

GitHub Actions automates the full deployment pipeline:

```
Push to main
     │
     ├── Backend tests (pytest)
     ├── Frontend type-check (TypeScript)
     ├── Frontend build (Vite)
     └── E2E tests (Playwright)
           │
           ├── Deploy backend → SSH into server → git pull → restart service
           └── Deploy frontend → SSH into server → git pull → npm build → reload nginx
```

---

## 14. Challenges and Solutions

| Challenge | Solution |
|---|---|
| PyTorch OOM on 1GB RAM | Added 2GB swap file; reduced to 1 worker |
| DigitalOcean blocks SMTP | Identified issue; password login and OAuth work fully |
| OAuth redirect URI mismatches | Hardcoded `BACKEND_URL` env var instead of using `request.url_for()` |
| GitHub OAuth under wrong account | Created new OAuth app under the correct GitHub account |
| OAuth double-exchange (useRef bug) | Added `useRef` guard to prevent `useEffect` from running twice |
| pages.dev domain blocked by ISP | Moved frontend to same DigitalOcean server as backend |
| Neon DB connection drops | Added `pool_pre_ping=True` and `pool_recycle=300` to SQLAlchemy engine |

---

## 15. Conclusion

NucleiAI is a complete, production-deployed AI platform that demonstrates the full software engineering lifecycle: problem identification, solution design, AI model development, full-stack web development, security implementation, testing, and cloud deployment.

The platform is live and functional at **https://165.227.139.185.nip.io** with:
- A working AI model that segments and counts nuclei in under 2 seconds
- Secure multi-user authentication including OAuth and 2FA
- A modern, responsive web interface
- Automated CI/CD deployment via GitHub Actions
- A PostgreSQL database on managed cloud infrastructure

The project demonstrates that AI-powered biomedical tools can be built as accessible, secure, and deployable web applications — making scientific analysis faster, more consistent, and available to any researcher with a web browser.

---

## 16. References

1. Ronneberger, O., Fischer, P., & Brox, T. (2015). *U-Net: Convolutional Networks for Biomedical Image Segmentation.* MICCAI, pp. 234–241.
2. Caicedo, J. C., et al. (2019). *Evaluation of Deep Learning Strategies for Nucleus Segmentation in Fluorescence Images.* Cytometry Part A, 95(9), 952–965.
3. Iakubovskii, P. (2019). *Segmentation Models PyTorch.* https://github.com/qubvel/segmentation_models.pytorch
4. Paszke, A., et al. (2019). *PyTorch: An Imperative Style, High-Performance Deep Learning Library.* NeurIPS, 32.
5. Bradski, G. (2000). *The OpenCV Library.* Dr. Dobb's Journal of Software Tools.
6. van der Walt, S., et al. (2014). *scikit-image: Image Processing in Python.* PeerJ, 2, e453.
7. Tiangolo, S. R. (2018–). *FastAPI Documentation.* https://fastapi.tiangolo.com/
8. SQLModel Documentation. https://sqlmodel.tiangolo.com/
9. Neon PostgreSQL Documentation. https://neon.tech/docs
10. DigitalOcean Documentation. https://docs.digitalocean.com/

---

*Report version: v1.0 — May 2026*
*NucleiAI — Istinye University Web Programming Project*
