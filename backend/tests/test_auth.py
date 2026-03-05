"""Tests for JWT verification and CurrentUser dependency."""
import pytest
import time
from jose import jwt
from fastapi import HTTPException


def make_token(secret: str, sub: str = "user-123", email: str = "test@example.com") -> str:
    """Create a valid Supabase-style JWT."""
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "role": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_valid_token():
    """Valid token with correct secret should decode without error."""
    secret = "test-secret-32-chars-minimum-ok!!"
    token = make_token(secret)
    from auth import _decode_jwt
    payload = _decode_jwt(token, secret)
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"


def test_decode_invalid_token_raises():
    """Invalid token should raise HTTPException 401."""
    from auth import _decode_jwt
    with pytest.raises(HTTPException) as exc:
        _decode_jwt("not.a.valid.token", "secret")
    assert exc.value.status_code == 401


def test_decode_wrong_secret_raises():
    """Token signed with wrong secret raises 401."""
    token = make_token("correct-secret-32-chars-minimum!!")
    from auth import _decode_jwt
    with pytest.raises(HTTPException) as exc:
        _decode_jwt(token, "wrong-secret-32-chars-minimum-n!!")
    assert exc.value.status_code == 401


def test_current_user_dataclass():
    """CurrentUser holds expected fields."""
    from auth import CurrentUser
    u = CurrentUser(user_id="abc", email="x@y.com", plan="starter", scans_used_this_month=3)
    assert u.user_id == "abc"
    assert u.plan == "starter"
    assert u.scans_used_this_month == 3
