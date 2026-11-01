import pytest
from app import calculate_resume_match

def test_match_score_calculation():
    """Verify keyword extraction, matching, and score out of 100."""
    resume = "Senior Python engineer with SQL, Docker, and Flask experience building REST APIs."
    job_desc = "Seeking a Python Developer with SQL, Docker, Kubernetes, and AWS experience."

    result = calculate_resume_match(resume, job_desc)

    matched = [item["word"] for item in result["matched_keywords"]]
    missing = [item["word"] for item in result["top_missing"]]

    assert "python" in matched
    assert "sql" in matched
    assert "docker" in matched
    assert "kubernetes" in missing
    assert "aws" in missing
    assert 0 <= result["score"] <= 100

def test_match_input_character_limit_rejection(client, auth):
    """Verify input exceeding 10,000 characters is rejected with an error message."""
    auth.signup("matchuser", "match@example.com")
    auth.login("match@example.com")

    oversized_text = "python " * 2000  # > 12,000 characters
    res = client.post("/match", data={
        "resume_text": oversized_text,
        "job_description": "Looking for python developer",
    })
    assert b"Input text exceeds the maximum allowed limit of 10,000 characters." in res.data

