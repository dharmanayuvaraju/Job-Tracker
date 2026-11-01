import json
import os
import sqlite3
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import requests

from database import get_connection, init_db

# Load environment variables
load_dotenv()


def is_valid_http_url(url):
    """Ensure URL strictly starts with http:// or https://."""
    if not url or not isinstance(url, str):
        return False
    return url.startswith("http://") or url.startswith("https://")


def fetch_adzuna_jobs():
    """Fetch tech jobs from Adzuna (India). Skips gracefully if keys are missing."""
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        print("[Adzuna] API keys not found in .env; skipping Adzuna fetch.")
        return []

    jobs = []
    # Fixed base URL (prevents SSRF)
    url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 20,
        "what": "software developer",
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("results", []):
                job_url = item.get("redirect_url", "")
                if not is_valid_http_url(job_url):
                    continue

                jobs.append({
                    "title": item.get("title", "Software Developer"),
                    "company": item.get("company", {}).get("display_name", "Unknown"),
                    "location": item.get("location", {}).get("display_name", "India"),
                    "url": job_url,
                    "source": "Adzuna",
                    "external_id": str(item.get("id", "")),
                    "posted_date": (item.get("created") or "")[:10] or str(date.today()),
                })
            print(f"[Adzuna] Successfully fetched {len(jobs)} jobs.")
        else:
            print(f"[Adzuna] API returned status {response.status_code}")
    except Exception as e:
        print(f"[Adzuna] Error fetching jobs: {e}")

    return jobs


def fetch_greenhouse_jobs(slugs):
    """Fetch jobs from Greenhouse for an allowlist of company slugs."""
    jobs = []
    for slug in slugs:
        # Fixed API endpoint with allowlisted slug
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                fetched_count = 0
                for item in data.get("jobs", []):
                    job_url = item.get("absolute_url", "")
                    if not is_valid_http_url(job_url):
                        continue

                    location_name = (item.get("location") or {}).get("name") or "Remote"
                    jobs.append({
                        "title": item.get("title", "Role"),
                        "company": slug.capitalize(),
                        "location": location_name,
                        "url": job_url,
                        "source": "Greenhouse",
                        "external_id": f"gh_{slug}_{item.get('id')}",
                        "posted_date": (item.get("updated_at") or "")[:10] or str(date.today()),
                    })
                    fetched_count += 1
                print(f"[Greenhouse:{slug}] Fetched {fetched_count} jobs.")
            else:
                print(f"[Greenhouse:{slug}] Returned status {response.status_code}")
        except Exception as e:
            # One failing company or network glitch must not stop others
            print(f"[Greenhouse:{slug}] Error: {e}")

    return jobs


def fetch_lever_jobs(slugs):
    """Fetch jobs from Lever for an allowlist of company slugs."""
    jobs = []
    for slug in slugs:
        # Fixed API endpoint with allowlisted slug
        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                fetched_count = 0
                for item in data:
                    job_url = item.get("hostedUrl", "")
                    if not is_valid_http_url(job_url):
                        continue

                    location_name = (item.get("categories") or {}).get("location") or "Remote"
                    created_at_ms = item.get("createdAt")
                    if created_at_ms:
                        posted_date = datetime.fromtimestamp(created_at_ms / 1000).strftime("%Y-%m-%d")
                    else:
                        posted_date = str(date.today())

                    jobs.append({
                        "title": item.get("text", "Role"),
                        "company": slug.capitalize(),
                        "location": location_name,
                        "url": job_url,
                        "source": "Lever",
                        "external_id": f"lever_{slug}_{item.get('id')}",
                        "posted_date": posted_date,
                    })
                    fetched_count += 1
                print(f"[Lever:{slug}] Fetched {fetched_count} jobs.")
            else:
                print(f"[Lever:{slug}] Returned status {response.status_code}")
        except Exception as e:
            # One failing company or network glitch must not stop others
            print(f"[Lever:{slug}] Error: {e}")

    return jobs


def save_jobs(jobs):
    """Save fetched jobs with deduplication and 30-day purge (PostgreSQL & SQLite compatible)."""
    db = get_connection()

    # 1. Deduplication using ON CONFLICT (supported in SQLite 3.24+ and PostgreSQL)
    new_jobs_count = 0
    for job in jobs:
        cur = db.execute(
            """
            INSERT INTO jobs (title, company, location, url, source, external_id, posted_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, external_id) DO NOTHING
            """,
            (
                job["title"],
                job["company"],
                job["location"],
                job["url"],
                job["source"],
                job["external_id"],
                job["posted_date"],
            ),
        )
        if cur.rowcount > 0:
            new_jobs_count += 1

    # 2. Delete jobs older than 30 days using parameter to stay portable
    cutoff_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    cur_del = db.execute(
        """
        DELETE FROM jobs 
        WHERE posted_date IS NOT NULL 
          AND posted_date != '' 
          AND posted_date < ?
        """,
        (cutoff_date,),
    )
    purged_count = cur_del.rowcount

    db.commit()

    # Count total jobs remaining in the database
    row = db.execute("SELECT COUNT(*) as count FROM jobs").fetchone()
    total_in_db = row["count"] if row else 0

    db.close()

    print("\n--- Summary ---")
    print(f"Total fetched from sources: {len(jobs)}")
    print(f"New jobs added:             {new_jobs_count}")
    print(f"Duplicates ignored:         {len(jobs) - new_jobs_count}")
    print(f"Old jobs purged (>30 days): {purged_count}")
    print(f"Total jobs currently in DB: {total_in_db}")


def main():
    """Main job fetcher entry point."""
    print("Starting automated job fetcher...")

    # Ensure tables exist
    init_db()

    # Read company slug allowlists
    allowlist_file = "companies.json"
    greenhouse_slugs = []
    lever_slugs = []

    if os.path.exists(allowlist_file):
        with open(allowlist_file, "r", encoding="utf-8") as f:
            companies = json.load(f)
            greenhouse_slugs = companies.get("greenhouse", [])
            lever_slugs = companies.get("lever", [])
    else:
        print(f"Warning: {allowlist_file} not found.")

    all_jobs = []

    # 1. Fetch Adzuna
    all_jobs.extend(fetch_adzuna_jobs())

    # 2. Fetch Greenhouse
    all_jobs.extend(fetch_greenhouse_jobs(greenhouse_slugs))

    # 3. Fetch Lever
    all_jobs.extend(fetch_lever_jobs(lever_slugs))

    # Save to SQLite with deduplication
    save_jobs(all_jobs)


if __name__ == "__main__":
    main()

