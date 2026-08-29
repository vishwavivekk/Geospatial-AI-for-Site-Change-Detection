"""Canva Connect API integration.

Editors link their Canva account once (OAuth + PKCE). After that a bank
post can be opened as a Canva design (current image becomes the starting
layer), edited in Canva itself, and pulled back as a PNG — then shared
with the approver through the normal flow.

Requires a Canva integration (developer.canva.com) configured via env:
CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REDIRECT_URI.
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time

import httpx

from app.config import (
    CANVA_CLIENT_ID,
    CANVA_CLIENT_SECRET,
    CANVA_REDIRECT_URI,
    CANVA_TOKENS_PATH,
)

AUTH_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
API = "https://api.canva.com/rest/v1"
SCOPES = "asset:read asset:write design:content:read design:content:write design:meta:read"

# state -> {username, verifier, ts} for in-flight OAuth flows
_pending: dict[str, dict] = {}


def configured() -> bool:
    return bool(CANVA_CLIENT_ID and CANVA_CLIENT_SECRET and CANVA_REDIRECT_URI)


# ── Token store (per app user) ────────────────────────

def _load_tokens() -> dict:
    try:
        with open(CANVA_TOKENS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_tokens(tokens: dict) -> None:
    os.makedirs(os.path.dirname(CANVA_TOKENS_PATH), exist_ok=True)
    with open(CANVA_TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def connected(username: str) -> bool:
    return username in _load_tokens()


def disconnect(username: str) -> None:
    tokens = _load_tokens()
    if tokens.pop(username, None) is not None:
        _save_tokens(tokens)


# ── OAuth (authorization code + PKCE) ─────────────────

def authorize_url(username: str) -> str:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    # keep only fresh flows
    now = time.time()
    for k in [k for k, v in _pending.items() if now - v["ts"] > 900]:
        _pending.pop(k, None)
    _pending[state] = {"username": username, "verifier": verifier, "ts": now}
    from urllib.parse import urlencode
    return AUTH_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": CANVA_CLIENT_ID,
        "redirect_uri": CANVA_REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })


async def handle_callback(state: str, code: str) -> str:
    """Exchanges the code; returns the app username that connected."""
    flow = _pending.pop(state, None)
    if not flow:
        raise ValueError("Unknown or expired OAuth state — start the connection again.")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            auth=(CANVA_CLIENT_ID, CANVA_CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": flow["verifier"],
                "redirect_uri": CANVA_REDIRECT_URI,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    tokens = _load_tokens()
    tokens[flow["username"]] = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + data.get("expires_in", 3600) - 60,
    }
    _save_tokens(tokens)
    return flow["username"]


async def _access_token(username: str) -> str:
    tokens = _load_tokens()
    tok = tokens.get(username)
    if not tok:
        raise LookupError("Canva account not connected")
    if time.time() < tok["expires_at"]:
        return tok["access_token"]
    # refresh
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            auth=(CANVA_CLIENT_ID, CANVA_CLIENT_SECRET),
            data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]},
        )
        if resp.status_code != 200:
            tokens.pop(username, None)
            _save_tokens(tokens)
            raise LookupError("Canva session expired — connect again")
        data = resp.json()
    tokens[username] = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", tok["refresh_token"]),
        "expires_at": time.time() + data.get("expires_in", 3600) - 60,
    }
    _save_tokens(tokens)
    return tokens[username]["access_token"]


# ── API operations ────────────────────────────────────

async def _poll(client: httpx.AsyncClient, url: str, headers: dict, key: str, tries: int = 30) -> dict:
    for _ in range(tries):
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        job = resp.json().get("job", {})
        if job.get("status") == "success":
            return job
        if job.get("status") == "failed":
            raise RuntimeError(f"Canva {key} job failed: {job.get('error', {}).get('message', 'unknown')}")
        await asyncio.sleep(1.0)
    raise RuntimeError(f"Canva {key} job timed out")


async def upload_asset(username: str, data: bytes, name: str) -> str:
    token = await _access_token(username)
    meta = base64.b64encode(name.encode()).decode()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{API}/asset-uploads",
            content=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Asset-Upload-Metadata": json.dumps({"name_base64": meta}),
            },
        )
        resp.raise_for_status()
        job = resp.json()["job"]
        if job.get("status") == "success":
            return job["asset"]["id"]
        job = await _poll(
            client, f"{API}/asset-uploads/{job['id']}",
            {"Authorization": f"Bearer {token}"}, "asset upload",
        )
        return job["asset"]["id"]


async def create_design(username: str, title: str, asset_id: str | None = None) -> dict:
    """Creates a 1080x1080 design (optionally starting from an asset).
    Returns {id, edit_url, view_url}."""
    token = await _access_token(username)
    body: dict = {
        "type": "type_and_asset",
        "design_type": {"type": "custom", "width": 1080, "height": 1080},
        "title": title[:255],
    }
    if asset_id:
        body["asset_id"] = asset_id
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{API}/designs",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        design = resp.json()["design"]
    return {
        "id": design["id"],
        "edit_url": design.get("urls", {}).get("edit_url", ""),
        "view_url": design.get("urls", {}).get("view_url", ""),
    }


async def export_design_png(username: str, design_id: str) -> bytes:
    """Exports the design as a 1080px PNG and downloads it."""
    token = await _access_token(username)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{API}/exports",
            json={"design_id": design_id, "format": {"type": "png", "width": 1080, "height": 1080}},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        job = resp.json()["job"]
        if job.get("status") != "success":
            job = await _poll(
                client, f"{API}/exports/{job['id']}",
                {"Authorization": f"Bearer {token}"}, "export",
            )
        urls = job.get("urls") or []
        if not urls:
            raise RuntimeError("Canva export returned no download URL")
        dl = await client.get(urls[0])
        dl.raise_for_status()
        return dl.content
