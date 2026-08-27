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


def _write_users(users: list[dict]) -> None:
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=2)


def _public_user(u: dict) -> dict:
    return {
        "username": u["username"],
        "display_name": u["display_name"],
        "role": u["role"],
        # older accounts predate the flag — they keep Canva access
        "can_use_canva": u.get("can_use_canva", True),
        "created_at": u.get("created_at", ""),
        "created_by": u.get("created_by", ""),
    }


def list_users() -> list[dict]:
    return [_public_user(u) for u in _load_users().values()]


def get_user_record(username: str) -> dict | None:
    user = _load_users().get(username)
    return _public_user(user) if user else None


def create_user(
    username: str, password: str, display_name: str, role: str,
    can_use_canva: bool, created_by: str = "",
) -> dict:
    username = username.strip().lower()
    if not username or not username.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise ValueError("Username may only contain letters, numbers, '.', '-' and '_'")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if role not in ("editor", "approver"):
        raise ValueError("Role must be editor or approver")
    users = _load_users()
    if username in users:
        raise ValueError(f"Username '{username}' already exists")
    import datetime
    salt = secrets.token_hex(8)
    record = {
        "username": username,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "role": role,
        "display_name": display_name.strip() or username,
        "can_use_canva": bool(can_use_canva),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "created_by": created_by,
    }
    all_users = list(users.values()) + [record]
    _write_users(all_users)
    return _public_user(record)


def update_user(
    username: str, display_name: str | None = None, password: str | None = None,
    role: str | None = None, can_use_canva: bool | None = None,
) -> dict:
    users = _load_users()
    user = users.get(username)
    if not user:
        raise LookupError(f"User '{username}' not found")
    if display_name is not None and display_name.strip():
        user["display_name"] = display_name.strip()
    if password:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        user["salt"] = secrets.token_hex(8)
        user["password_hash"] = _hash_password(password, user["salt"])
    if role is not None:
        if role not in ("editor", "approver"):
            raise ValueError("Role must be editor or approver")
        if user["role"] == "approver" and role != "approver":
            approvers = [u for u in users.values() if u["role"] == "approver"]
            if len(approvers) <= 1:
                raise ValueError("At least one approver account must remain")
        user["role"] = role
    if can_use_canva is not None:
        user["can_use_canva"] = bool(can_use_canva)
    _write_users(list(users.values()))
    return _public_user(user)


def delete_user(username: str, acting_username: str) -> None:
    users = _load_users()
    user = users.get(username)
    if not user:
        raise LookupError(f"User '{username}' not found")
    if username == acting_username:
        raise ValueError("You cannot delete your own account")
    if user["role"] == "approver":
        approvers = [u for u in users.values() if u["role"] == "approver"]
        if len(approvers) <= 1:
            raise ValueError("At least one approver account must remain")
    _write_users([u for u in users.values() if u["username"] != username])


def user_can_use_canva(username: str) -> bool:
    user = _load_users().get(username)
    return bool(user and user.get("can_use_canva", True))


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
    user = parse_session_token(token)
    # a deleted account's token must stop working immediately
    if user and user["username"] not in _load_users():
        return None
    return user


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


def require_canva_access(request: Request) -> dict:
    user = require_editor(request)
    if not user_can_use_canva(user["username"]):
        raise HTTPException(
            403, detail="Canva access is not enabled for your account — ask the admin to allow it."
        )
    return user
