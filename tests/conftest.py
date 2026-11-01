import os
import pytest
import sqlite3
import sys

# Ensure root folder is in Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app as flask_app, limiter
from database import init_db

TEST_DB_NAME = "test_pytest.db"

class AuthActions:
    def __init__(self, client):
        self.client = client

    def signup(self, username="alice", email="alice@example.com", password="Password123!", confirm="Password123!"):
        return self.client.post("/signup", data={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": confirm,
        }, follow_redirects=True)

    def login(self, email="alice@example.com", password="Password123!"):
        return self.client.post("/login", data={
            "email": email,
            "password": password,
        }, follow_redirects=True)

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

@pytest.fixture
def app():
    # Force test configuration
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
    })
    limiter.enabled = False
    # Use isolated test database
    os.environ["DATABASE_PATH"] = TEST_DB_NAME
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)

    init_db()
    yield flask_app

    # Cleanup after test finishes
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth(client):
    return AuthActions(client)
