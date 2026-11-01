import pytest

def test_signup_successful(client, auth):
    """Test valid user registration and redirect to login."""
    res = auth.signup("newuser", "newuser@example.com", "SecurePass123!", "SecurePass123!")
    assert b"Account created successfully! Please log in." in res.data

def test_signup_validation_short_password(client, auth):
    """Test rejection of passwords shorter than 8 characters."""
    res = auth.signup("shortpass", "short@example.com", "12345", "12345")
    assert b"Password must be at least 8 characters long." in res.data

def test_signup_validation_bad_email(client, auth):
    """Test rejection of malformed email addresses."""
    res = auth.signup("bademail", "invalid-email-format", "SecurePass123!", "SecurePass123!")
    assert b"Please enter a valid email address." in res.data

def test_signup_duplicate_rejection(client, auth):
    """Test rejection of duplicate username or email."""
    auth.signup("duplicate", "duplicate@example.com", "SecurePass123!", "SecurePass123!")
    res = auth.signup("duplicate", "duplicate@example.com", "SecurePass123!", "SecurePass123!")
    assert b"Username or email already exists." in res.data

def test_login_and_logout(client, auth):
    """Test login with correct credentials and logout."""
    auth.signup("testlogin", "login@example.com", "SecurePass123!", "SecurePass123!")
    
    # Successful login
    res = auth.login("login@example.com", "SecurePass123!")
    assert b"Welcome back, testlogin!" in res.data

    # Logout
    res_logout = auth.logout()
    assert b"You have been logged out." in res_logout.data

def test_login_invalid_credentials(client, auth):
    """Test generic error response for invalid password or nonexistent email."""
    auth.signup("testbad", "bad@example.com", "SecurePass123!", "SecurePass123!")
    
    # Wrong password
    res = auth.login("bad@example.com", "WrongPassword!")
    assert b"Invalid email or password." in res.data

    # Nonexistent email
    res2 = auth.login("nobody@example.com", "SecurePass123!")
    assert b"Invalid email or password." in res2.data

@pytest.mark.parametrize("protected_url", [
    "/dashboard",
    "/applications",
    "/applications/add",
    "/jobs",
    "/match",
    "/api/stats",
])
def test_protected_routes_redirect_when_logged_out(client, protected_url):
    """Verify unauthenticated users cannot access protected views."""
    res = client.get(protected_url, follow_redirects=True)
    assert b"Please log in to access this page." in res.data

