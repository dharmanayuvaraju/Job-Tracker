from collections import Counter
import csv
from datetime import date, datetime, timedelta
from functools import wraps
import io
import math
import os
import re
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from database import close_db, get_db, init_db

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Production environment detection
IS_PRODUCTION = (
    os.getenv("FLASK_ENV") == "production"
    or os.getenv("RENDER") is not None
    or os.getenv("ENVIRONMENT") == "production"
)

# Security: Load secret key from environment variable (fail immediately if missing in production)
flask_secret = os.getenv("FLASK_SECRET_KEY")
if not flask_secret:
    if IS_PRODUCTION:
        raise RuntimeError("CRITICAL: FLASK_SECRET_KEY environment variable MUST be set in production!")
    flask_secret = "dev-fallback-secret-key-change-in-production"
app.secret_key = flask_secret

# Production Cookie Security (Secure cookies only over real HTTPS)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = False if not IS_PRODUCTION else True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Security: Enable CSRF protection for all POST requests
csrf = CSRFProtect(app)

# Security: Rate limiting to protect endpoints against abuse
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Register database teardown to close connections cleanly
app.teardown_appcontext(close_db)

# Allowed application statuses
VALID_STATUSES = ["Applied", "Interview", "Offer", "Rejected"]

# Common English stopwords to ignore in keyword matching
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours", "yourself", "yourselves", "will",
    "job", "role", "work", "team", "experience", "years", "candidate", "responsibilities"
}

# High-priority technical skills given 3x weight multiplier
TECH_SKILLS = {
    "python", "sql", "sqlite", "postgresql", "mysql", "javascript", "typescript", "html", "css",
    "flask", "django", "fastapi", "react", "vue", "angular", "node", "nodejs", "express", "git",
    "github", "docker", "kubernetes", "aws", "azure", "gcp", "linux", "unix", "rest", "api",
    "apis", "graphql", "redis", "mongodb", "java", "c++", "c#", "golang", "go", "ruby", "rust",
    "php", "bash", "shell", "ci/cd", "ci", "cd", "agile", "scrum", "pytest", "unit", "tdd",
    "devops", "cloud", "backend", "frontend", "fullstack", "oop", "algorithms", "data", "json"
}


@app.after_request
def add_security_headers(response):
    """Adds HTTP security headers to protect against XSS, clickjacking, and MIME sniffing."""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# Custom Error Handlers (No stack traces in production)
@app.errorhandler(404)
def page_not_found(e):
    """Renders custom 404 page without exposing internal errors."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Renders custom 500 page without exposing stack traces."""
    return render_template("500.html"), 500


def login_required(view):
    """Decorator that protects routes from unauthorized access."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


def validate_application_input(company, role, status, applied_date, job_link, notes):
    """Validates job application fields according to Day 2 rules."""
    errors = []

    if not company or len(company) > 100:
        errors.append("Company name is required and must be under 100 characters.")
    if not role or len(role) > 100:
        errors.append("Role is required and must be under 100 characters.")

    if status not in VALID_STATUSES:
        errors.append(f"Status must be one of: {', '.join(VALID_STATUSES)}.")

    try:
        datetime.strptime(applied_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        errors.append("Applied date must be a valid date in YYYY-MM-DD format.")

    if job_link:
        if len(job_link) > 500:
            errors.append("Job link must be under 500 characters.")
        elif not (job_link.startswith("http://") or job_link.startswith("https://")):
            errors.append("Job link must start with http:// or https://")

    if notes and len(notes) > 2000:
        errors.append("Notes must be under 2000 characters.")

    return errors


def sanitize_csv_cell(value):
    """Neutralizes formula injection by prefixing dangerous symbols with a single quote."""
    if value is None:
        return ""
    str_val = str(value)
    if str_val and str_val[0] in ("=", "+", "-", "@"):
        return "'" + str_val
    return str_val


def extract_keywords(text):
    """Tokenizes text, strips punctuation, and removes common stopwords."""
    tokens = re.findall(r"\b[a-zA-Z0-9\+#\.-]+\b", text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def calculate_resume_match(resume_text, job_desc):
    """Calculates keyword match score out of 100, matched words, and top 10 missing."""
    resume_tokens = set(extract_keywords(resume_text))
    job_tokens = extract_keywords(job_desc)

    if not job_tokens:
        return {
            "score": 0,
            "matched_count": 0,
            "missing_count": 0,
            "total_job_keywords": 0,
            "matched_keywords": [],
            "top_missing": [],
        }

    job_counts = Counter(job_tokens)

    total_weighted = 0
    matched_weighted = 0
    matched_keywords = []
    missing_keywords = []

    for word, freq in job_counts.items():
        weight = 3 if word in TECH_SKILLS else 1
        item_score = weight * freq
        total_weighted += item_score
        is_tech = word in TECH_SKILLS

        if word in resume_tokens:
            matched_weighted += item_score
            matched_keywords.append({
                "word": word,
                "is_tech": is_tech,
                "weight": item_score,
            })
        else:
            missing_keywords.append({
                "word": word,
                "is_tech": is_tech,
                "weight": item_score,
            })

    score = min(100, round((matched_weighted / total_weighted) * 100)) if total_weighted > 0 else 0

    matched_keywords.sort(key=lambda x: (not x["is_tech"], -x["weight"], x["word"]))
    missing_keywords.sort(key=lambda x: (not x["is_tech"], -x["weight"], x["word"]))

    return {
        "score": score,
        "matched_count": len(matched_keywords),
        "missing_count": len(missing_keywords),
        "total_job_keywords": len(job_counts),
        "matched_keywords": matched_keywords,
        "top_missing": missing_keywords[:10],
    }


@app.route("/")
def index():
    """Redirect home visitors based on their login status."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def signup():
    """Handle new user registration with rate limiting."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("signup.html", username=username, email=email)

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            flash("Please enter a valid email address.", "danger")
            return render_template("signup.html", username=username, email=email)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("signup.html", username=username, email=email)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("signup.html", username=username, email=email)

        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()

        if existing_user:
            flash("Username or email already exists.", "danger")
            return render_template("signup.html", username=username, email=email)

        hashed_password = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed_password),
        )
        db.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    """Handle user login with rate limiting."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log the current user out by clearing the session."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard showing profile details, total applications, and status counts."""
    db = get_db()
    user_id = session["user_id"]

    user = db.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    counts = {"Total": 0, "Applied": 0, "Interview": 0, "Offer": 0, "Rejected": 0}
    status_rows = db.execute(
        "SELECT status, COUNT(*) as count FROM applications WHERE user_id = ? GROUP BY status",
        (user_id,),
    ).fetchall()

    for row in status_rows:
        if row["status"] in counts:
            counts[row["status"]] = row["count"]
            counts["Total"] += row["count"]

    return render_template("dashboard.html", user=user, counts=counts)


@app.route("/api/stats")
@login_required
def api_stats():
    """Returns JSON analytics (weekly trend, status counts, success rate) for current user."""
    db = get_db()
    user_id = session["user_id"]

    today = date.today()
    current_monday = today - timedelta(days=today.weekday())

    weeks = []
    for i in range(7, -1, -1):
        monday = current_monday - timedelta(weeks=i)
        weeks.append({
            "key": monday.strftime("%Y-%W"),
            "label": monday.strftime("%b %d"),
        })

    start_date_str = (current_monday - timedelta(weeks=7)).strftime("%Y-%m-%d")

    # Fetch applied dates and compute weekly distribution in Python (Postgres & SQLite portable)
    app_rows = db.execute(
        "SELECT applied_date FROM applications WHERE user_id = ? AND applied_date >= ?",
        (user_id, start_date_str),
    ).fetchall()

    counts_by_key = Counter()
    for r in app_rows:
        val = r["applied_date"]
        if val and len(val) >= 10:
            try:
                dt = datetime.strptime(val[:10], "%Y-%m-%d").date()
                counts_by_key[dt.strftime("%Y-%W")] += 1
            except (ValueError, TypeError):
                pass

    weekly_labels = [w["label"] for w in weeks]
    weekly_counts = [counts_by_key.get(w["key"], 0) for w in weeks]

    status_counts = {"Applied": 0, "Interview": 0, "Offer": 0, "Rejected": 0}
    status_rows = db.execute(
        "SELECT status, COUNT(*) as count FROM applications WHERE user_id = ? GROUP BY status",
        (user_id,),
    ).fetchall()

    for row in status_rows:
        if row["status"] in status_counts:
            status_counts[row["status"]] = row["count"]

    total = sum(status_counts.values())
    if total > 0:
        success_rate = round(
            ((status_counts["Interview"] + status_counts["Offer"]) / total) * 100, 1
        )
    else:
        success_rate = 0.0

    return jsonify({
        "total": total,
        "success_rate": success_rate,
        "status_counts": status_counts,
        "weekly_labels": weekly_labels,
        "weekly_counts": weekly_counts,
    })


@app.route("/applications")
@login_required
def applications_list():
    """List applications for the logged-in user with search and status filtering."""
    db = get_db()
    user_id = session["user_id"]

    q = request.args.get("q", "").strip()
    selected_status = request.args.get("status", "").strip()

    query = "SELECT * FROM applications WHERE user_id = ?"
    params = [user_id]

    if q:
        query += " AND company LIKE ?"
        params.append(f"%{q}%")

    if selected_status and selected_status in VALID_STATUSES:
        query += " AND status = ?"
        params.append(selected_status)

    query += " ORDER BY applied_date DESC, id DESC"
    applications = db.execute(query, tuple(params)).fetchall()

    return render_template(
        "applications_list.html",
        applications=applications,
        valid_statuses=VALID_STATUSES,
        q=q,
        selected_status=selected_status,
    )


@app.route("/applications/export")
@login_required
def applications_export():
    """Export only the logged-in user's applications as CSV with formula injection defense."""
    db = get_db()
    user_id = session["user_id"]

    applications = db.execute(
        """
        SELECT company, role, status, applied_date, job_link, notes, created_at
        FROM applications
        WHERE user_id = ?
        ORDER BY applied_date DESC, id DESC
        """,
        (user_id,),
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Company", "Role", "Status", "Applied Date", "Job Link", "Notes", "Created At"
    ])

    for app_row in applications:
        writer.writerow([
            sanitize_csv_cell(app_row["company"]),
            sanitize_csv_cell(app_row["role"]),
            sanitize_csv_cell(app_row["status"]),
            sanitize_csv_cell(app_row["applied_date"]),
            sanitize_csv_cell(app_row["job_link"]),
            sanitize_csv_cell(app_row["notes"]),
            sanitize_csv_cell(app_row["created_at"]),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=applications.csv"},
    )


@app.route("/applications/add", methods=["GET", "POST"])
@login_required
def application_add():
    """Add a new job application for the logged-in user."""
    today_str = datetime.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        role = request.form.get("role", "").strip()
        status = request.form.get("status", "").strip()
        applied_date = request.form.get("applied_date", "").strip()
        job_link = request.form.get("job_link", "").strip()
        notes = request.form.get("notes", "").strip()

        form_data = {
            "company": company,
            "role": role,
            "status": status,
            "applied_date": applied_date,
            "job_link": job_link,
            "notes": notes,
        }

        errors = validate_application_input(company, role, status, applied_date, job_link, notes)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "application_add.html",
                valid_statuses=VALID_STATUSES,
                form_data=form_data,
                default_date=today_str,
            )

        db = get_db()
        db.execute(
            """
            INSERT INTO applications (user_id, company, role, status, applied_date, job_link, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                company,
                role,
                status,
                applied_date,
                job_link or None,
                notes or None,
            ),
        )
        db.commit()

        flash("Application added successfully!", "success")
        return redirect(url_for("applications_list"))

    return render_template(
        "application_add.html",
        valid_statuses=VALID_STATUSES,
        form_data=None,
        default_date=today_str,
    )


@app.route("/applications/<int:id>/edit", methods=["GET", "POST"])
@login_required
def application_edit(id):
    """Edit an application owned by the logged-in user (prevents IDOR)."""
    db = get_db()
    user_id = session["user_id"]

    application = db.execute(
        "SELECT * FROM applications WHERE id = ? AND user_id = ?",
        (id, user_id),
    ).fetchone()

    if application is None:
        abort(404)

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        role = request.form.get("role", "").strip()
        status = request.form.get("status", "").strip()
        applied_date = request.form.get("applied_date", "").strip()
        job_link = request.form.get("job_link", "").strip()
        notes = request.form.get("notes", "").strip()

        form_data = {
            "company": company,
            "role": role,
            "status": status,
            "applied_date": applied_date,
            "job_link": job_link,
            "notes": notes,
        }

        errors = validate_application_input(company, role, status, applied_date, job_link, notes)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "application_edit.html",
                application=application,
                valid_statuses=VALID_STATUSES,
                form_data=form_data,
            )

        db.execute(
            """
            UPDATE applications
            SET company = ?, role = ?, status = ?, applied_date = ?, job_link = ?, notes = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                company,
                role,
                status,
                applied_date,
                job_link or None,
                notes or None,
                id,
                user_id,
            ),
        )
        db.commit()

        flash("Application updated successfully!", "success")
        return redirect(url_for("applications_list"))

    return render_template(
        "application_edit.html",
        application=application,
        valid_statuses=VALID_STATUSES,
        form_data=None,
    )


@app.route("/applications/<int:id>/delete", methods=["POST"])
@login_required
def application_delete(id):
    """Delete an application owned by the logged-in user (POST only, prevents IDOR)."""
    db = get_db()
    user_id = session["user_id"]

    application = db.execute(
        "SELECT id FROM applications WHERE id = ? AND user_id = ?",
        (id, user_id),
    ).fetchone()

    if application is None:
        abort(404)

    db.execute(
        "DELETE FROM applications WHERE id = ? AND user_id = ?",
        (id, user_id),
    )
    db.commit()

    flash("Application deleted successfully.", "info")
    return redirect(url_for("applications_list"))


@app.route("/jobs")
@login_required
@limiter.limit("60 per minute")
def jobs_board():
    """Browse aggregated jobs from database with keyword/location search and pagination."""
    db = get_db()

    q = request.args.get("q", "").strip()[:50]
    location = request.args.get("location", "").strip()[:50]

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    per_page = 20

    base_query = "FROM jobs WHERE 1=1"
    params = []

    if q:
        base_query += " AND (title LIKE ? OR company LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    if location:
        base_query += " AND location LIKE ?"
        params.append(f"%{location}%")

    count_row = db.execute(f"SELECT COUNT(*) as total {base_query}", tuple(params)).fetchone()
    total_jobs = count_row["total"] if count_row else 0
    total_pages = math.ceil(total_jobs / per_page) or 1

    offset = (page - 1) * per_page
    query = f"SELECT * {base_query} ORDER BY posted_date DESC, id DESC LIMIT ? OFFSET ?"
    query_params = params + [per_page, offset]
    jobs = db.execute(query, tuple(query_params)).fetchall()

    return render_template(
        "jobs.html",
        jobs=jobs,
        q=q,
        location=location,
        page=page,
        total_pages=total_pages,
        total_jobs=total_jobs,
    )


@app.route("/jobs/<int:id>/save", methods=["POST"])
@login_required
def job_save(id):
    """Save an aggregated job directly into the user's applications."""
    db = get_db()
    user_id = session["user_id"]

    job = db.execute("SELECT * FROM jobs WHERE id = ?", (id,)).fetchone()
    if job is None:
        abort(404)

    existing_app = db.execute(
        """
        SELECT id FROM applications 
        WHERE user_id = ? AND company = ? AND role = ?
        """,
        (user_id, job["company"], job["title"]),
    ).fetchone()

    if existing_app:
        flash(f"You have already saved or applied to '{job['title']}' at {job['company']}.", "warning")
        return redirect(url_for("jobs_board"))

    today_str = date.today().strftime("%Y-%m-%d")
    notes = f"Imported from {job['source']} job board."

    db.execute(
        """
        INSERT INTO applications (user_id, company, role, status, applied_date, job_link, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            job["company"],
            job["title"],
            "Applied",
            today_str,
            job["url"],
            notes,
        ),
    )
    db.commit()

    flash(f"Job at {job['company']} saved to your applications!", "success")
    return redirect(url_for("applications_list"))


@app.route("/match", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute")
def resume_match():
    """Compare resume text against job description using weighted keyword analysis."""
    result = None
    resume_text = ""
    job_description = ""

    if request.method == "POST":
        resume_text = request.form.get("resume_text", "")
        job_description = request.form.get("job_description", "")

        if len(resume_text) > 10000 or len(job_description) > 10000:
            flash("Input text exceeds the maximum allowed limit of 10,000 characters.", "danger")
            return render_template(
                "match.html",
                resume_text=resume_text[:10000],
                job_description=job_description[:10000],
                result=None,
            )

        if not resume_text.strip() or not job_description.strip():
            flash("Please provide both your resume and a job description to analyze.", "warning")
            return render_template(
                "match.html",
                resume_text=resume_text,
                job_description=job_description,
                result=None,
            )

        result = calculate_resume_match(resume_text, job_description)

    return render_template(
        "match.html",
        resume_text=resume_text,
        job_description=job_description,
        result=result,
    )


@app.cli.command("init-db")
def init_db_command():
    """CLI command to initialize database schema: flask init-db"""
    init_db()
    print("Database initialized successfully.")


# Ensure database exists when running directly
if __name__ == "__main__":
    init_db()
    app.run(debug=not IS_PRODUCTION)
