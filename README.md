# 💼 Job Tracker — Full-Stack Python Web Application

A secure, production-ready Job Application Tracker built from scratch with **Python, Flask, SQLite / PostgreSQL, Vanilla HTML5, and CSS**.

---

## 🌟 Features Overview

- **User Authentication (Day 1)**:
  - Secure registration, login, and session-based logout.
  - Password hashing with PBKDF2 / Werkzeug cryptography (passwords never stored in plain text).
  - Cross-Site Request Forgery (CSRF) tokens on all state-changing forms.
  - Generic authentication errors to prevent account enumeration.

- **Applications Management (Day 2)**:
  - Full CRUD: Add, View, Edit, and Delete job applications.
  - Strict multi-user data isolation (preventing Insecure Direct Object Reference / IDOR).
  - Real-time search by company name and filtering by status (`Applied`, `Interview`, `Offer`, `Rejected`).
  - Parameterized queries to eliminate SQL injection risks.

- **Dashboard Analytics & Data Export (Day 3)**:
  - Interactive **Bar Chart** (applications per week over the last 8 weeks) and **Doughnut Chart** (status breakdown).
  - Dynamically calculated success rate: $\frac{\text{Interviews} + \text{Offers}}{\text{Total}} \times 100$.
  - Local Chart.js bundle (no third-party CDN dependencies).
  - Strict Content Security Policy (CSP), anti-clickjacking, and nosniff headers.
  - One-click CSV Export sanitized against spreadsheet formula injection.

- **Automated Job Fetcher & Resume Matcher (Day 4)**:
  - Background ingestor (`fetch_jobs.py`) collecting live tech jobs from Greenhouse, Lever, and Adzuna.
  - Fixed allowlist of company slugs preventing Server-Side Request Forgery (SSRF).
  - Automatic deduplication using composite unique constraints (`source + external_id`).
  - Automated 30-day expiration purge for outdated listings.
  - Built-in **Resume Match Score**: Pure Python NLP keyword matcher with $3\times$ multipliers for technical skills and extraction of top missing keywords.

- **Production Engineering & CI/CD (Day 5)**:
  - Dual-database architecture: **PostgreSQL** in production, **SQLite** for zero-configuration local development.
  - Automated CI pipeline on GitHub Actions running **Pytest**, **pip-audit** (vulnerability scanner), and **Gitleaks** (secret detection).
  - Scheduled background workflow running `fetch_jobs.py` every 6 hours using GitHub Secrets.
  - Automated dependency updates with Dependabot.
  - Production-hardened with Gunicorn, rate limiting, and custom 404/500 error pages.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.9+ / 3.11 |
| **Web Framework** | Flask, Flask-WTF, Flask-Limiter |
| **WSGI Server** | Gunicorn (Production) |
| **Database** | PostgreSQL (`psycopg2-binary`) in Production, SQLite3 locally |
| **Frontend** | Vanilla HTML5, Vanilla CSS (zero heavy JS frameworks) |
| **Visualizations** | Chart.js UMD (hosted locally in `static/js/`) |
| **Testing & CI/CD** | Pytest, Pip-Audit, Gitleaks, GitHub Actions |
| **Hosting** | Render (Web Service), Neon (Serverless Postgres) |

---

## 🛡️ Security Measures Summary

| Threat / Vulnerability | Defense Implemented in Job Tracker |
|---|---|
| **SQL Injection (SQLi)** | 100% Parameterized queries using `?` placeholders (translated to `%s` on PostgreSQL). String formatting is never used in SQL. |
| **Cross-Site Scripting (XSS)** | Jinja2 auto-escaping on all dynamic output; strict prohibition of the `\|safe` filter; strict CSP header (`default-src 'self'; script-src 'self'; style-src 'self'`). |
| **Cross-Site Request Forgery (CSRF)** | Flask-WTF `CSRFProtect` verifying cryptographically signed tokens on every `POST` request, including deletes. |
| **Insecure Direct Object Reference (IDOR)** | Every query (`SELECT`, `UPDATE`, `DELETE`) filters by `WHERE id = ? AND user_id = ?`, returning a generic 404 if not owned by the session user. |
| **Server-Side Request Forgery (SSRF)** | The job fetcher only connects to hardcoded, static API domains with company slugs validated against an internal allowlist (`companies.json`). |
| **CSV Formula Injection** | Cells starting with `=`, `+`, `-`, or `@` are sanitized by prefixing with an apostrophe (`'`) so spreadsheet software treats them as literal strings. |
| **Brute Force / Abuse** | Flask-Limiter rate limits sensitive endpoints (`10/min` on login and signup, `60/min` on jobs board, `20/min` on match score). |
| **Credential & Secret Leaks** | Secrets loaded from environment variables (`.env`); `.env` and `*.db` excluded via `.gitignore`; automated Gitleaks scan in CI. |
| **Information Disclosure** | Custom 404 and 500 error templates suppress stack traces and database error messages in production. |
| **Cookie Hijacking** | Session cookies configured with `HttpOnly=True`, `SameSite=Lax`, and `Secure=True` in production. |

---

## 🚀 Local Quickstart Guide

### 1. Clone the repository
```bash
git clone https://github.com/your-username/ai-job-tracker.git
cd ai-job-tracker
```

### 2. Create and activate a virtual environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Copy `.env.example` to `.env`:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```
Open `.env` and configure your development `FLASK_SECRET_KEY` (e.g. `dev-secret-key-12345`).

### 5. Initialize the database
```bash
python -c "import database; database.init_db(); print('Database initialized!')"
```

### 6. (Optional) Ingest tech jobs
```bash
python fetch_jobs.py
```

### 7. Run the development server
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🧪 Running the Test Suite

Run all automated unit and integration tests using `pytest`:

```bash
pytest -v
```

All 16 tests execute in an isolated SQLite database without affecting your local development database.

---

## 🌐 Production Deployment Guide

### Part 1: Provision Free PostgreSQL Database on Neon
1. Go to [Neon.tech](https://neon.tech) and create a free account.
2. Click **Create Project** (Name: `job-tracker`).
3. Under **Connection Details**, copy your connection string (`DATABASE_URL`). It looks like:
   ```text
   postgres://alex:secretpassword@ep-cool-sample.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### Part 2: Deploy Web Service on Render
1. Go to [Render.com](https://render.com) and create an account.
2. Click **New +** $\rightarrow$ **Web Service** $\rightarrow$ Connect your GitHub repository.
3. Configure settings:
   - **Name**: `job-tracker`
   - **Environment**: `Python 3`
   - **Branch**: `main`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python -c "import database; database.init_db()"
     ```
   - **Start Command**:
     ```bash
     gunicorn app:app
     ```
4. Under **Environment Variables**, add:
   - `FLASK_ENV`: `production`
   - `FLASK_SECRET_KEY`: *(Generate a 64-char random string via `python -c "import secrets; print(secrets.token_hex(32))"`)*
   - `DATABASE_URL`: *(Paste your Neon connection string from Part 1)*
   - `PYTHON_VERSION`: `3.11.9`
5. Click **Deploy Web Service**. Render will build the app, execute schema migrations, and launch Gunicorn with HTTPS enabled automatically!

### Part 3: Configure GitHub Secrets (for Scheduled Ingestion)
In your GitHub repository, navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** $\rightarrow$ **New repository secret**:
- `DATABASE_URL`: *(Your Neon PostgreSQL connection string)*
- `ADZUNA_APP_ID`: *(Optional Adzuna app ID)*
- `ADZUNA_APP_KEY`: *(Optional Adzuna app key)*

The GitHub Actions workflow in `.github/workflows/fetch.yml` will now automatically update your production database with fresh job listings every 6 hours!

---

## 🔗 Live Demo & Screenshots

- **Live URL**: `https://your-app-name.onrender.com` *(Replace with your Render URL)*

### Screenshots
*(Upload your application screenshots into a `/docs` directory or link them here)*
- **Dashboard & Analytics**: `docs/dashboard.png`
- **Job Applications Management**: `docs/applications.png`
- **Resume Matcher**: `docs/matcher.png`

---

## 📄 License
MIT License. Built for educational purposes.

