# NucleiAI — Deployment Guide

Full step-by-step instructions to deploy the backend + frontend to DigitalOcean and wire up automatic CI/CD via GitHub Actions.

---

## Infrastructure Overview

| Component | Service | URL |
|---|---|---|
| Backend (FastAPI) | DigitalOcean Droplet | `https://165.227.139.185.nip.io/api` |
| Frontend (React) | DigitalOcean Droplet (nginx) | `https://165.227.139.185.nip.io` |
| Database (PostgreSQL) | Neon.tech | Managed Postgres |
| CI/CD | GitHub Actions | Auto-deploy on push to `main` |

---

## Prerequisites

- A [DigitalOcean](https://digitalocean.com) account
- A [Neon](https://neon.tech) account (free Postgres)
- Python 3.12+ installed locally
- Node.js 20+ installed locally

---

## Part 1 — Database on Neon

### Step 1: Create a Neon project

1. Go to [neon.tech](https://neon.tech) and sign up
2. Create a new project — name it `nuclei-ai`
3. Copy the **connection string** (starts with `postgresql://...`)

---

## Part 2 — DigitalOcean Droplet

### Step 1: Create the droplet

In DigitalOcean → Create → Droplets:

| Setting | Value |
|---|---|
| Region | Frankfurt (fra1) |
| OS | Ubuntu 24.04 LTS |
| Size | Basic · Regular · **$6/month (1GB RAM)** |
| Authentication | Password or SSH Key |
| Hostname | `nuclei-ai` |

### Step 2: Add swap space (required for PyTorch)

```bash
dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Step 3: Install system dependencies

```bash
apt-get update -y
apt-get install -y git python3 python3-pip python3-venv nginx certbot python3-certbot-nginx libgl1 libglib2.0-0 libgomp1
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
```

### Step 4: Clone the repository

```bash
git clone https://github.com/Moha-Bishly/nuclei-ai.git /app
```

### Step 5: Install Python dependencies

```bash
cd /app/web-programming
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r backend/requirements.txt
```

### Step 6: Create the .env file

```bash
cat > /app/web-programming/backend/.env << 'EOF'
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(64))">
DATABASE_URL=<your-neon-connection-string>
ENV=production
FRONTEND_URL=https://<your-droplet-ip>.nip.io
BACKEND_URL=https://<your-droplet-ip>.nip.io
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<your-gmail>
SMTP_PASSWORD=<your-16-char-app-password>
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GITHUB_CLIENT_ID=<your-github-client-id>
GITHUB_CLIENT_SECRET=<your-github-client-secret>
DROPBOX_CLIENT_ID=<your-dropbox-client-id>
DROPBOX_CLIENT_SECRET=<your-dropbox-client-secret>
EOF
```

> `BACKEND_URL` must match the domain used in OAuth provider redirect URIs.

### Step 7: Create the systemd service

```bash
cat > /etc/systemd/system/nuclei-ai.service << 'EOF'
[Unit]
Description=NucleiAI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/app/web-programming
Environment="PATH=/app/web-programming/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/app/web-programming/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips="*"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable nuclei-ai && systemctl start nuclei-ai
```

### Step 8: Build the frontend

```bash
cd /app/web-programming/frontend
npm ci
VITE_API_URL=https://<your-droplet-ip>.nip.io/api npm run build
```

### Step 9: Configure nginx + SSL

```bash
cat > /etc/nginx/sites-available/nuclei-ai << 'EOF'
server {
    server_name <your-droplet-ip>.nip.io;
    root /app/web-programming/frontend/dist;
    index index.html;
    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }

    location /auth/ {
        proxy_pass http://127.0.0.1:8000/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/<your-droplet-ip>.nip.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<your-droplet-ip>.nip.io/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if ($host = <your-droplet-ip>.nip.io) { return 301 https://$host$request_uri; }
    listen 80;
    server_name <your-droplet-ip>.nip.io;
    return 404;
}
EOF

ln -sf /etc/nginx/sites-available/nuclei-ai /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

certbot --nginx -d <your-droplet-ip>.nip.io --non-interactive --agree-tos -m <your-email>
```

### Step 10: Create the first manager account

```bash
cd /app/web-programming && source venv/bin/activate && python -m backend.seed
```

---

## Part 3 — OAuth Provider Setup

After the server is live, add the production callback URLs in each provider's dashboard.

### Google

[console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → your OAuth client:
- **Authorized JavaScript origins**: `https://<your-droplet-ip>.nip.io`
- **Authorized redirect URIs**: `https://<your-droplet-ip>.nip.io/auth/google/callback`

### GitHub

[github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps → New OAuth App:
- **Homepage URL**: `https://<your-droplet-ip>.nip.io`
- **Authorization callback URL**: `https://<your-droplet-ip>.nip.io/auth/github/callback`

### Dropbox

[dropbox.com/developers/apps](https://www.dropbox.com/developers/apps) → your app → Redirect URIs:
- `https://<your-droplet-ip>.nip.io/auth/dropbox/callback`

---

## Part 4 — CI/CD via GitHub Actions

Add these secrets in **GitHub → Settings → Secrets → Actions**:

| Secret | Value |
|---|---|
| `DO_SSH_HOST` | Your droplet IP |
| `DO_SSH_KEY` | Private SSH key for root access |
| `VITE_API_URL` | `https://<your-droplet-ip>.nip.io/api` |
| `CLOUDFLARE_API_TOKEN` | (optional, for Cloudflare Pages mirror) |
| `CLOUDFLARE_ACCOUNT_ID` | (optional, for Cloudflare Pages mirror) |

On every push to `main`, GitHub Actions will:
1. Run backend tests (pytest)
2. Run frontend type-check and build
3. Run E2E tests (Playwright)
4. SSH into the droplet → pull latest code → restart backend
5. SSH into the droplet → rebuild frontend → reload nginx

---

## Troubleshooting

**Backend not starting:**
```bash
journalctl -u nuclei-ai -n 50 --no-pager
```

**Check backend health:**
```bash
curl https://<your-droplet-ip>.nip.io/api/health
```

**Restart backend:**
```bash
systemctl restart nuclei-ai
```

**Rebuild frontend:**
```bash
cd /app/web-programming/frontend && npm ci && VITE_API_URL=https://<your-droplet-ip>.nip.io/api npm run build && systemctl reload nginx
```

**Database connection error:**
Check the Neon dashboard — the connection string in `.env` must match exactly.
