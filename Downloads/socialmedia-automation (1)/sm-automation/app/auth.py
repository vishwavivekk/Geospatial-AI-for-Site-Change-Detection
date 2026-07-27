"""Session-cookie auth with two roles: editor and approver.

Sessions are stateless signed tokens (HMAC-SHA256) so they survive
server reloads. Users live in data/users.json (auto-created with
default demo accounts on first run).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException, Request

from app.config import SECRET_PATH, USERS_PATH

SESSION_COOKIE = "sm_session"
SESSION_TTL = 60 * 60 * 12  # 12 hours

DEFAULT_USERS = [
    {
        "username": "editor",
        "password": "editor123",
        "role": "editor",
        "display_name": "Content Editor",
    },
    {
        "username": "approver",
        "password": "approver123",
        "role": "approver",
        "display_name": "Design Approver",
    },
]


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def _load_secret() -> bytes:
    try:
        with open(SECRET_PATH) as f:
            return f.read().strip().encode()
    except FileNotFoundError:
        os.makedirs(os.path.dirname(SECRET_PATH), exist_ok=True)
        secret = secrets.token_hex(32)
        with open(SECRET_PATH, "w") as f:
            f.write(secret)
        return secret.encode()


_SECRET = _load_secret()


def _load_users() -> dict[str, dict]:
    try:
        with open(USERS_PATH) as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
        for u in DEFAULT_USERS:
            salt = secrets.token_hex(8)
            users.append({
                "username": u["username"],
                "salt": salt,
                "password_hash": _hash_password(u["password"], salt),
                "role": u["role"],
                "display_name": u["display_name"],
            })
        os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
        with open(USERS_PATH, "w") as f:
            json.dump(users, f, indent=2)
    return {u["username"]: u for u in users}


def verify_login(username: str, password: str) -> dict | None:
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    if _hash_password(password, user["salt"]) != user["password_hash"]:
        return None
    return {
        "username": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
    }


def create_session_token(user: dict) -> str:
    payload = {
        "u": user["username"],
        "r": user["role"],
        "n": user["display_name"],
        "exp": int(time.time()) + SESSION_TTL,
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def parse_session_token(token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
        expected = hmac.new(_SECRET, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            return None
        return {
            "username": payload["u"],
            "role": payload["r"],
            "display_name": payload["n"],
        }
    except Exception:
        return None


def get_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return parse_session_token(token)


def require_user(request: Request) -> dict:
    user = get_user(request)
    if not user:
        raise HTTPException(401, detail="Not logged in")
    return user


def require_editor(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "editor":
        raise HTTPException(403, detail="Editor access required")
    return user


def require_approver(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "approver":
        raise HTTPException(403, detail="Approver access required")
    return user
