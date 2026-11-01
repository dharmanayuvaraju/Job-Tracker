import pytest

def test_add_application_validation(client, auth):
    """Test validation rules when adding a job application."""
    auth.signup("appuser", "appuser@example.com")
    auth.login("appuser@example.com")

    # 1. Invalid status
    res_status = client.post("/applications/add", data={
        "company": "Acme Corp",
        "role": "Developer",
        "status": "InvalidStatus",
        "applied_date": "2026-11-01"
    })
    assert b"Status must be one of: Applied, Interview, Offer, Rejected" in res_status.data

    # 2. Invalid date
    res_date = client.post("/applications/add", data={
        "company": "Acme Corp",
        "role": "Developer",
        "status": "Applied",
        "applied_date": "not-a-date"
    })
    assert b"Applied date must be a valid date in YYYY-MM-DD format" in res_date.data

    # 3. Invalid URL (not http/https)
    res_url = client.post("/applications/add", data={
        "company": "Acme Corp",
        "role": "Developer",
        "status": "Applied",
        "applied_date": "2026-11-01",
        "job_link": "javascript:alert(1)"
    })
    assert b"Job link must start with http:// or https://" in res_url.data

def test_idor_protection_between_users(client, auth):
    """Verify that User A's application cannot be viewed, edited, or deleted by User B (returns 404)."""
    # User A logs in and creates an application
    auth.signup("userA", "userA@example.com")
    auth.login("userA@example.com")

    client.post("/applications/add", data={
        "company": "Private Corp A",
        "role": "Lead Architect",
        "status": "Offer",
        "applied_date": "2026-11-01"
    }, follow_redirects=True)

    auth.logout()

    # User B logs in
    auth.signup("userB", "userB@example.com")
    auth.login("userB@example.com")

    # User B tries to view/edit User A's application (ID: 1) -> Expect 404
    res_get = client.get("/applications/1/edit")
    assert res_get.status_code == 404

    # User B tries to submit an edit to User A's application -> Expect 404
    res_post = client.post("/applications/1/edit", data={
        "company": "Hacked Corp",
        "role": "Hacker",
        "status": "Rejected",
        "applied_date": "2026-11-01"
    })
    assert res_post.status_code == 404

    # User B tries to delete User A's application -> Expect 404
    res_del = client.post("/applications/1/delete")
    assert res_del.status_code == 404

    auth.logout()

    # Log back into User A to confirm data is untouched
    auth.login("userA@example.com")
    res_check = client.get("/applications")
    assert b"Private Corp A" in res_check.data

