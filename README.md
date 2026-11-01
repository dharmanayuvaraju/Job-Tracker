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
  - Deployable as a cloud web service (Render, Vercel) and installable as a standalone app (PWA).

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Client["Frontend / Client Tier"]
        Browser["Web Browser / PWA App"]
        ChartJS["Chart.js (Local Bundle)"]
        VanillaJS["Dashboard JS (fetch /api/stats)"]
    end

    subgraph Security["Security & Middleware Tier"]
        CSP["Content-Security-Policy & Headers"]
        CSRF["Flask-WTF (CSRF Validation)"]
        Limiter["Flask-Limiter (Rate Limiting)"]
        AuthDecor["@login_required Session Guard"]
    end

    subgraph Server["Application Server Tier"]
        Flask["Flask Application (app.py)"]
        Routes["Routes (Auth, CRUD, Analytics, Matcher)"]
        Matcher["NLP Keyword Engine (Pure Python)"]
    end

    subgraph Database["Persistence & Ingestion Tier"]
        DBAdapter["database.py (Dual Dialect Adapter)"]
        SQLite["SQLite (Local: job_tracker.db)"]
        Postgres["PostgreSQL (Production: Neon / Supabase)"]
        Fetcher["fetch_jobs.py (Ingestion Script)"]
        Cron["GitHub Actions (6-hour Schedule)"]
    end

    Browser -->|HTTPS Requests| Security
    Security --> Routes
    Routes --> Matcher
    Routes --> DBAdapter
    DBAdapter --> SQLite
    DBAdapter --> Postgres
    Cron --> Fetcher
    Fetcher -->|Deduplicate & Ingest| Postgres
    VanillaJS -->|Async /api/stats| Routes
```

### Architecture Highlights
1. **Decoupled Job Ingestion**: Public user searches query local database tables rather than calling slow 3rd-party APIs on request. Background jobs ingest and deduplicate records on a 6-hour cron schedule.
2. **Unified Database Layer**: `database.py` dynamically normalizes SQLite (`?`) and PostgreSQL (`%s`) parameter placeholders, serial types, and column access (`DictCursor` / `sqlite3.Row`), making the application 100% cloud-portable without code changes.
3. **Stateless Scalability**: The application relies on encrypted client-side signed session cookies, allowing seamless horizontal scaling across serverless functions or container replicas.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.9+ / 3.11 |
| **Web Framework** | Flask, Flask-WTF, Flask-Limiter |
| **WSGI Server** | Gunicorn (Production) |
| **Database** | PostgreSQL (`psycopg2-binary`) in Production, SQLite3 locally |
| **Frontend** | Vanilla HTML5, Vanilla CSS (zero heavy JS frameworks), Web App Manifest (PWA) |
| **Visualizations** | Chart.js UMD (hosted locally in `static/js/`) |
| **Testing & CI/CD** | Pytest, Pip-Audit, Gitleaks, GitHub Actions |
| **Cloud Hosting** | Vercel (Serverless) / Render (Web Service), Neon (Serverless Postgres) |

---

## 🛡️ Security Measures Summary

| Threat / Vulnerability | Defense Implemented in Job Tracker |
|---|---|
| **SQL Injection (SQLi)** | 100% Parameterized queries using `?` placeholders (translated to `%s` on PostgreSQL). String formatting is never used in SQL. |
| **Cross-Site Scripting (XSS)** | Jinja2 auto-escaping on all dynamic output; strict prohibition of the `\|safe` filter; strict CSP header (`default-src 'self'; script-src 'self'; style-src 'self'; form-action 'self'`). |
| **Cross-Site Request Forgery (CSRF)** | Flask-WTF `CSRFProtect` verifying cryptographically signed tokens on every `POST` request, including deletes. |
| **Insecure Direct Object Reference (IDOR)** | Every query (`SELECT`, `UPDATE`, `DELETE`) filters by `WHERE id = ? AND user_id = ?`, returning a generic 404 if not owned by the session user. |
| **Server-Side Request Forgery (SSRF)** | The job fetcher only connects to hardcoded, static API domains with company slugs validated against an internal allowlist (`companies.json`). |
| **CSV Formula Injection** | Cells starting with `=`, `+`, `-`, or `@` are sanitized by prefixing with an apostrophe (`'`) so spreadsheet software treats them as literal strings. |
| **Brute Force / Abuse** | Flask-Limiter rate limits sensitive endpoints (`10/min` on login and signup, `60/min` on jobs board, `20/min` on match score). |
| **Denial of Service (DoS) via Payload** | Strict length bounds on all inputs (usernames $\le 50$, passwords $\le 128$, search $\le 50$, resume/job texts $\le 10,000$). |
| **Credential & Secret Leaks** | Secrets loaded from environment variables (`.env`); `.env` and `*.db` excluded via `.gitignore`; automated Gitleaks scan in CI. |
| **Information Disclosure** | Custom 404 and 500 error templates suppress stack traces and database error messages in production. |
| **Cookie Hijacking** | Session cookies configured with `HttpOnly=True`, `SameSite=Lax`, and `Secure=True` in production. |

---

## 🚀 Local Quickstart Guide

### 1. Clone the repository
```bash
git clone https://github.com/dharmanayuvaraju/Job-Tracker.git
cd Job-Tracker
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
Open `.env` and set your `FLASK_SECRET_KEY` (e.g. `dev-secret-key-12345`).

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

All tests execute against an isolated SQLite test database without affecting your development database.

---

## 🌐 Deployment Guide: How to Get Both a Live Link and an Installable App

You can deploy this project to **Vercel** or **Render** for a live URL, and install it as a standalone app on your Phone or Desktop computer.

### Step 1: Provision a Free PostgreSQL Database on Neon
*(Since Vercel and Render are serverless/containerized, an external database ensures your applications and accounts persist permanently).*

1. Go to [Neon.tech](https://neon.tech) and sign up for free.
2. Click **Create Project** $\rightarrow$ Name it `job-tracker`.
3. Copy your connection string (`DATABASE_URL`). It looks like:
   ```text
   postgres://username:password@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

---

### Step 2A: Deploying on Vercel (Fast & Free)

1. Go to [Vercel.com](https://vercel.com) and sign in with your GitHub account.
2. Click **Add New...** $\rightarrow$ **Project** $\rightarrow$ Import your **`Job-Tracker`** repository.
3. In the project settings, under **Environment Variables**, add:
   * `DATABASE_URL`: *(Paste your Neon connection string from Step 1)*
   * `FLASK_SECRET_KEY`: *(Generate a random 64-character secret using `python -c "import secrets; print(secrets.token_hex(32))"`)*
   * `FLASK_ENV`: `production`
4. Click **Deploy**.
5. Once deployment completes, Vercel will give you a **Live Link** (e.g., `https://job-tracker-yourname.vercel.app`)!
6. Initialize the database tables on Neon:
   Run this one-liner on your machine (or in Neon's SQL Editor):
   ```bash
   python -c "import os; os.environ['DATABASE_URL']='your_neon_url_here'; import database; database.init_db(); print('Cloud DB ready!')"
   ```

---

### Step 2B: Deploying on Render (Alternative Web Service)

1. Go to [Render.com](https://render.com) and create an account.
2. Click **New +** $\rightarrow$ **Web Service** $\rightarrow$ Select your GitHub repo.
3. Settings:
   - **Build Command**: `pip install -r requirements.txt && python -c "import database; database.init_db()"`
   - **Start Command**: `gunicorn app:app`
   - **Environment Variables**:
     - `DATABASE_URL`: *(Your Neon PostgreSQL URL)*
     - `FLASK_SECRET_KEY`: *(Your secret key)*
     - `FLASK_ENV`: `production`
4. Click **Deploy Web Service**. Render provides your live HTTPS URL.

---

### Step 3: How to Install It as an "App" on Your Phone or PC 📱💻

Our project includes a Web App Manifest (`static/manifest.json`), meaning you can install it as a standalone app directly from your live link!

#### On Android / iPhone:
1. Open your **Live Link** (e.g., `https://job-tracker-yourname.vercel.app`) in Chrome or Safari.
2. Tap the browser menu (**Share** on iOS, or the **Three Dots ⋮** on Android).
3. Tap **"Add to Home Screen"** or **"Install App"**.
4. The Job Tracker will now appear on your home screen with its own icon and open full-screen like a native mobile app!

#### On Windows / Mac / Linux:
1. Open your Live Link in Chrome, Edge, or Brave.
2. Look at the right side of your address bar for the **Install App icon** (looks like a monitor with an arrow, or click the **Three Dots ⋮** $\rightarrow$ **Save and Share** $\rightarrow$ **Install Job Tracker**).
3. Click **Install**.
4. The app opens in its own clean window without browser tabs and is pinned to your Windows Start Menu or Mac Dock!

---

## 💡 What I Learned Building This Project

1. **Defense-in-Depth Security**:
   - Web security is not a single setting; it is a multi-layered architecture. We combined cryptographic hashing (`werkzeug`), token verification (`Flask-WTF`), rate limiting (`Flask-Limiter`), parameterized SQL, content security headers (`CSP`), input bounding, and CSV formula neutralizing to secure every layer.
2. **True Database Portability**:
   - Abstracting database differences in `database.py` demonstrated how to write portable software. By converting parameter markers (`?` to `%s`), normalizing autoincrement syntaxes, and wrapping cursor dictionaries, the same codebase runs effortlessly on SQLite for development and PostgreSQL for production.
3. **Decoupled Architecture for Performance**:
   - Searching external APIs on live HTTP requests creates poor user experience and fragility. Decoupling ingestion into an offline scheduled script (`fetch_jobs.py`) with deduplication ensures user queries resolve in milliseconds.
4. **CI/CD & Supply Chain Defense**:
   - Modern software engineering requires automated testing and supply chain auditing. Running `pytest`, `pip-audit`, and `Gitleaks` in GitHub Actions on every commit gives developers confidence that code changes won't break existing functionality or introduce leaked credentials.
5. **Progressive Web App Architecture**:
   - Utilizing standard web technologies (HTML5, CSS3, Web App Manifest) allows a single codebase to serve as a fast web application, a desktop app, and a mobile application without maintaining separate native codebases.

---

## 📄 License
MIT License. Built for educational and portfolio demonstration.
