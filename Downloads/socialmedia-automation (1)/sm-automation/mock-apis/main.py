"""
Mock Social Media APIs — Instagram Graph API, X API v2, LinkedIn Posts+Images API

Run:  uvicorn mock-apis.main:app --host 0.0.0.0 --port 8100 --reload
Docs: http://localhost:8100/docs
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse, Response

# ── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
PERSISTENCE_FILE = BASE_DIR / "published_posts.json"
MOCK_DELAY_STEPS = int(os.environ.get("MOCK_DELAY_STEPS", "2"))
CONTAINER_EXPIRY_MS = 24 * 60 * 60 * 1000  # 24 hours
IG_CAPTION_MAX = 2200
IG_HASHTAG_MAX = 30

app = FastAPI(
    title="Mock Social Media APIs",
    description="Mock Instagram Graph API, X API v2, and LinkedIn Posts+Images API for testing auto-publishing.",
    version="1.0.0",
)


# ── Persistence ─────────────────────────────────────────────────────────────

def _load_published() -> dict:
    if PERSISTENCE_FILE.exists():
        try:
            return json.loads(PERSISTENCE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"instagram": [], "x": [], "linkedin": []}


def _save_published(data: dict):
    PERSISTENCE_FILE.write_text(json.dumps(data, indent=2, default=str))


published_posts: dict = _load_published()


# ── ID Generators ──────────────────────────────────────────────────────────

def _ig_id() -> str:
    return str(uuid.uuid4().int)[:19]


def _x_id() -> str:
    return str(uuid.uuid4().int)[:19]


def _linkedin_id() -> str:
    return str(uuid.uuid4().int)[:18]


def _urn(kind: str, id_val: str) -> str:
    return f"urn:li:{kind}:{id_val}"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _count_hashtags(text: str) -> int:
    return len(re.findall(r"#\w+", text))


# ── Auth Dependency ────────────────────────────────────────────────────────

async def require_bearer_auth(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    # Accept both "Bearer <token>" and "OAuth 2.0 Bearer <token>"
    if not (authorization.lower().startswith("bearer ") or authorization.lower().startswith("oauth 2.0 bearer ")):
        raise HTTPException(status_code=401, detail="Invalid Authorization header. Expected: Bearer <token>")
    return authorization


# ── Rate Limit Headers ────────────────────────────────────────────────────

def _rate_limit_headers(platform: str, limit: int, remaining: int) -> dict:
    reset_at = int(time.time()) + 3600
    headers = {
        "x-rate-limit-limit": str(limit),
        "x-rate-limit-remaining": str(max(0, remaining)),
        "x-rate-limit-reset": str(reset_at),
    }
    if platform == "instagram":
        headers["x-app-usage"] = json.dumps({"call_count": 0, "total_cputime": 0, "total_time": 0})
    return headers


# ── Error Simulation State ─────────────────────────────────────────────────

error_simulation: dict = {}  # platform -> {"error_type": str, "remaining": int}


def _check_error_sim(platform: str):
    sim = error_simulation.get(platform)
    if sim and sim["remaining"] > 0:
        sim["remaining"] -= 1
        if sim["remaining"] <= 0:
            error_simulation.pop(platform, None)
        raise HTTPException(status_code=429, detail=f"Simulated {sim['error_type']} for {platform}")


# ══════════════════════════════════════════════════════════════════════════════
#  INSTAGRAM GRAPH API MOCK
# ══════════════════════════════════════════════════════════════════════════════

ig_containers: dict = {}   # container_id -> {status, call_count, ...metadata}
ig_media: dict = {}        # media_id -> {image_url, caption, user_id, published_at}


def _ig_error(message: str, code: int, error_subcode: int = 33, error_type: str = "OAuthException"):
    return JSONResponse(
        status_code=400 if code != 10 else 429,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "code": code,
                "error_subcode": error_subcode,
                "fbtrace_id": str(uuid.uuid4().hex[:16]),
            }
        },
    )


@app.post("/ig/v25.0/{ig_user_id}/media")
async def ig_create_container(
    ig_user_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Instagram: Create media container (Step 1).
    Accepts application/x-www-form-urlencoded (real API) or query params.
    """
    _check_error_sim("instagram")

    # Accept both form-encoded body and query params for flexibility
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        image_url = form.get("image_url", "")
        caption = form.get("caption", "")
        access_token = form.get("access_token", "")
        media_type = form.get("media_type", "")
        children = form.get("children", "")
        user_tags = form.get("user_tags", "")
        alt_text = form.get("alt_text", "")
        location_id = form.get("location_id", "")
    else:
        image_url = request.query_params.get("image_url", "")
        caption = request.query_params.get("caption", "")
        access_token = request.query_params.get("access_token", "")
        media_type = request.query_params.get("media_type", "")
        children = request.query_params.get("children", "")
        user_tags = request.query_params.get("user_tags", "")
        alt_text = request.query_params.get("alt_text", "")
        location_id = request.query_params.get("location_id", "")

    if not access_token:
        return _ig_error("An access token is required", 190, 102)

    if not image_url and media_type != "CAROUSEL":
        return _ig_error("Invalid image URL", 100, 33)

    if image_url and not image_url.startswith("http"):
        return _ig_error("Invalid image URL", 100, 33)

    # Caption validation
    if len(caption) > IG_CAPTION_MAX:
        return _ig_error(f"Caption exceeds maximum length of {IG_CAPTION_MAX} characters", 100, 33)

    if _count_hashtags(caption) > IG_HASHTAG_MAX:
        return _ig_error(f"Caption exceeds maximum of {IG_HASHTAG_MAX} hashtags", 100, 33)

    # Parse user_tags JSON if provided
    parsed_user_tags = None
    if user_tags:
        try:
            parsed_user_tags = json.loads(user_tags)
        except (json.JSONDecodeError, TypeError):
            return _ig_error("Invalid user_tags JSON", 100, 33)

    container_id = _ig_id()
    ig_containers[container_id] = {
        "status": "IN_PROGRESS",
        "call_count": 0,
        "image_url": image_url,
        "caption": caption,
        "media_type": media_type,
        "children": children.split(",") if children else [],
        "user_tags": parsed_user_tags,
        "alt_text": alt_text,
        "location_id": location_id,
        "created_at": _now_ms(),
        "user_id": ig_user_id,
    }

    return JSONResponse(
        status_code=200,
        content={"id": container_id},
        headers=_rate_limit_headers("instagram", 200, 195),
    )


@app.get("/ig/v25.0/{container_id}")
async def ig_check_container(
    container_id: str,
    fields: str = Query("status_code"),
    access_token: str = Query(""),
    authorization: Optional[str] = Header(None),
):
    """Instagram: Check container status (Step 1b)."""
    container = ig_containers.get(container_id)
    if not container:
        return _ig_error(
            f"Unsupported post request. Object with ID '{container_id}' does not exist, "
            "cannot be loaded due to missing permissions, or does not support this operation.",
            100,
            33,
            "GraphMethodException",
        )

    # Check container expiry
    if _now_ms() - container["created_at"] > CONTAINER_EXPIRY_MS:
        container["status"] = "EXPIRED"

    if container["status"] != "EXPIRED":
        container["call_count"] += 1
        if container["call_count"] >= MOCK_DELAY_STEPS:
            container["status"] = "FINISHED"

    return JSONResponse(
        status_code=200,
        content={"id": container_id, "status_code": container["status"]},
        headers=_rate_limit_headers("instagram", 200, 195),
    )


@app.post("/ig/v25.0/{ig_user_id}/media_publish")
async def ig_publish(
    ig_user_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """Instagram: Publish container (Step 2).
    Accepts application/x-www-form-urlencoded (real API) or query params.
    """
    _check_error_sim("instagram")

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        creation_id = form.get("creation_id", "")
        access_token = form.get("access_token", "")
    else:
        creation_id = request.query_params.get("creation_id", "")
        access_token = request.query_params.get("access_token", "")

    if not access_token:
        return _ig_error("An access token is required", 190, 102)

    if not creation_id:
        return _ig_error("creation_id is required", 100, 33)

    container = ig_containers.get(creation_id)
    if not container:
        return _ig_error(
            f"Unsupported post request. Object with ID '{creation_id}' does not exist, "
            "cannot be loaded due to missing permissions, or does not support this operation.",
            100,
            33,
            "GraphMethodException",
        )

    if container["status"] == "EXPIRED":
        return _ig_error("Container has expired (24h lifetime). Create a new one.", 100, 33)

    if container["status"] != "FINISHED":
        return _ig_error("Container is not ready yet. Status: " + container["status"], 100, 33)

    media_id = _ig_id()
    ig_media[media_id] = {
        "id": media_id,
        "image_url": container["image_url"],
        "caption": container["caption"],
        "media_type": container["media_type"],
        "user_tags": container.get("user_tags"),
        "alt_text": container.get("alt_text"),
        "location_id": container.get("location_id"),
        "user_id": ig_user_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    published_posts["instagram"].append(ig_media[media_id])
    _save_published(published_posts)

    ig_containers.pop(creation_id, None)

    return JSONResponse(
        status_code=200,
        content={"id": media_id},
        headers=_rate_limit_headers("instagram", 200, 194),
    )


@app.get("/ig/v25.0/{ig_user_id}/content_publishing_limit")
async def ig_publishing_limit(
    ig_user_id: str,
    access_token: str = Query(""),
    authorization: Optional[str] = Header(None),
):
    """Instagram: Check publishing quota."""
    usage = len([p for p in published_posts["instagram"] if p.get("user_id") == ig_user_id])
    return JSONResponse(
        status_code=200,
        content={
            "data": [
                {
                    "config": {
                        "quota_total": 50,
                        "quota_duration": 86400,
                    },
                    "quota_usage": usage,
                }
            ]
        },
        headers=_rate_limit_headers("instagram", 200, 195),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  X (TWITTER) API v2 MOCK
# ══════════════════════════════════════════════════════════════════════════════

x_media_store: dict = {}   # media_id -> {status, call_count, ...}
x_tweets: dict = {}        # tweet_id -> {text, media_ids, created_at}


def _x_response(data: dict = None, errors: list = None, status: int = 200, extra_headers: dict = None):
    body = {"data": data or {}, "meta": {}, "errors": errors or []}
    headers = _rate_limit_headers("x", 200, 195)
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(status_code=status, content=body, headers=headers)


def _x_media_response(data: dict, status: int = 200):
    return _x_response(data=data, status=status)


@app.post("/x/v2/media/upload")
async def x_upload_media(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """X: Upload media (simple or chunked INIT).
    Real API: POST https://api.x.com/2/media/upload
    """
    _check_error_sim("x")
    await require_bearer_auth(authorization)

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        command = form.get("command")

        # ── Chunked upload: INIT ──
        if command == "INIT":
            media_id = _x_id()
            media_type = form.get("media_type", "image/jpeg")
            media_category = form.get("media_category", "tweet_image")
            total_bytes = int(form.get("total_bytes", 0))
            additional_owners = form.get("additional_owners", "")
            x_media_store[media_id] = {
                "status": "pending",
                "call_count": 0,
                "media_category": media_category,
                "media_type": media_type,
                "total_bytes": total_bytes,
                "additional_owners": additional_owners.split(",") if additional_owners else [],
                "expires_at": _now_ms() + 86400_000,
                "chunks_received": [],
            }
            return _x_media_response({
                "id": media_id,
                "media_key": f"13_{media_id}",
                "expires_after_secs": 86400,
            }, status=201)

        # ── Simple upload (images < 5MB) ──
        media_file = form.get("media")
        media_category = form.get("media_category", "tweet_image")
        media_type = form.get("media_type", "image/jpeg")
        additional_owners = form.get("additional_owners", "")

        if media_file is None:
            return _x_response(errors=[{"message": "media field is required", "code": 400}], status=400)

        # Validate media_category
        valid_categories = {"tweet_image", "dm_image", "tweet_video", "tweet_gif", "amplify_video", "dm_video", "dm_gif", "subtitles"}
        if media_category not in valid_categories:
            return _x_response(errors=[{"message": f"Invalid media_category: {media_category}", "code": 400}], status=400)

        media_id = _x_id()
        x_media_store[media_id] = {
            "status": "succeeded",
            "call_count": MOCK_DELAY_STEPS,  # images are instant
            "media_category": media_category,
            "media_type": media_type,
            "additional_owners": additional_owners.split(",") if additional_owners else [],
            "expires_at": _now_ms() + 86400_000,
            "chunks_received": [],
        }
        return _x_media_response({
            "id": media_id,
            "media_key": f"3_{media_id}",
            "expires_after_secs": 86400,
            "processing_info": {
                "state": "succeeded",
                "check_after_secs": 0,
                "progress_percent": 100,
            },
        }, status=201)

    return _x_response(errors=[{"message": "Content-Type must be multipart/form-data", "code": 400}], status=400)


@app.post("/x/v2/media/upload/{media_id}/append")
async def x_append_media(
    media_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """X: Append chunk to chunked media upload.
    Real API: POST https://api.x.com/2/media/upload/{id}/append
    """
    await require_bearer_auth(authorization)

    media = x_media_store.get(media_id)
    if not media:
        return _x_response(errors=[{"message": f"Media not found: {media_id}", "code": 404}], status=404)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        segment_index = int(form.get("segment_index", 0))
        media_chunk = form.get("media")
        media["chunks_received"].append(segment_index)
    else:
        return _x_response(errors=[{"message": "Content-Type must be multipart/form-data", "code": 400}], status=400)

    return _x_media_response({
        "media_id": media_id,
        "segment_index": segment_index,
    })


@app.post("/x/v2/media/upload/{media_id}/finalize")
async def x_finalize_media(
    media_id: str,
    authorization: Optional[str] = Header(None),
):
    """X: Finalize chunked media upload.
    Real API: POST https://api.x.com/2/media/upload/{id}/finalize
    """
    await require_bearer_auth(authorization)

    media = x_media_store.get(media_id)
    if not media:
        return _x_response(errors=[{"message": f"Media not found: {media_id}", "code": 404}], status=404)

    media["call_count"] += 1
    if media["call_count"] >= MOCK_DELAY_STEPS:
        media["status"] = "succeeded"

    return _x_media_response({
        "id": media_id,
        "media_key": f"13_{media_id}",
        "size": media.get("total_bytes", 0),
        "expires_after_secs": 86400,
        "processing_info": {
            "state": media["status"],
            "check_after_secs": 1 if media["status"] != "succeeded" else 0,
            "progress_percent": 100 if media["status"] == "succeeded" else 50,
        },
    })


@app.get("/x/v2/media/upload")
async def x_media_status(
    command: str = Query("STATUS"),
    media_id: str = Query(..., alias="media_id"),
    authorization: Optional[str] = Header(None),
):
    """X: Poll media processing status.
    Real API: GET https://api.x.com/2/media/upload?command=STATUS&media_id=X
    """
    await require_bearer_auth(authorization)

    if command != "STATUS":
        return _x_response(errors=[{"message": f"Unknown command: {command}", "code": 400}], status=400)

    media = x_media_store.get(media_id)
    if not media:
        return _x_response(errors=[{"message": f"Media not found: {media_id}", "code": 404}], status=404)

    media["call_count"] += 1
    if media["call_count"] >= MOCK_DELAY_STEPS:
        media["status"] = "succeeded"

    return _x_media_response({
        "id": media_id,
        "media_key": f"3_{media_id}",
        "processing_info": {
            "state": media["status"],
            "check_after_secs": 0 if media["status"] == "succeeded" else 5,
            "progress_percent": 100 if media["status"] == "succeeded" else int(
                min((media["call_count"] / MOCK_DELAY_STEPS), 1.0) * 100
            ),
        },
    })


@app.post("/x/v2/tweets")
async def x_create_tweet(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """X: Create tweet with optional media (Step 2).
    Real API: POST https://api.x.com/2/tweets
    Request: {"text": "...", "media": {"media_ids": ["..."]}}
    Response: {"data": {"id": "...", "text": "...", "created_at": "..."}}
    """
    _check_error_sim("x")
    await require_bearer_auth(authorization)

    try:
        body = await request.json()
    except Exception:
        return _x_response(errors=[{"message": "Invalid JSON body", "code": 400}], status=400)

    text = body.get("text", "")
    media_obj = body.get("media", {})
    media_ids = media_obj.get("media_ids", [])
    tagged_user_ids = media_obj.get("tagged_user_ids", [])
    description = media_obj.get("description", "")
    reply = body.get("reply", {})
    poll = body.get("poll", {})
    geo = body.get("geo", {})
    quote_tweet_id = body.get("quote_tweet_id")

    # Validate: at least text or media required
    if not text and not media_ids:
        return _x_response(errors=[{"message": "At least one of `text` or `media` is required.", "code": 400}], status=400)

    # Validate text length (max 280 for standard, 25000 for Blue)
    if len(text) > 280:
        return _x_response(errors=[{"message": "Value too long. Max length for this field is 280", "code": 400}], status=400)

    # Validate media_ids exist
    for mid in media_ids:
        if mid not in x_media_store:
            return _x_response(
                errors=[{"message": f"Media ID not found: {mid}", "code": 404, "type": "https://api.x.com/2/problems/resource-not-found"}],
                status=404,
            )
        if x_media_store[mid]["status"] != "succeeded":
            return _x_response(
                errors=[{"message": f"Media ID {mid} is still processing", "code": 400, "type": "https://api.x.com/2/problems/invalid-request"}],
                status=400,
            )

    # Validate poll
    if poll:
        poll_options = poll.get("options", [])
        if len(poll_options) < 2 or len(poll_options) > 4:
            return _x_response(errors=[{"message": "Poll must have 2-4 options", "code": 400}], status=400)
        duration = poll.get("duration_minutes", 0)
        if duration < 5 or duration > 10080:
            return _x_response(errors=[{"message": "duration_minutes must be between 5 and 10080", "code": 400}], status=400)

    tweet_id = _x_id()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    x_tweets[tweet_id] = {
        "id": tweet_id,
        "text": text,
        "media_ids": media_ids,
        "tagged_user_ids": tagged_user_ids,
        "description": description,
        "created_at": created_at,
    }
    published_posts["x"].append(x_tweets[tweet_id])
    _save_published(published_posts)

    return _x_response(data={"id": tweet_id, "text": text, "created_at": created_at}, status=201)


# ══════════════════════════════════════════════════════════════════════════════
#  LINKEDIN API MOCK (New Posts + Images API)
# ══════════════════════════════════════════════════════════════════════════════

linkedin_images: dict = {}   # image_id -> {status, call_count, owner, urn, ...}
linkedin_posts: dict = {}    # post_id -> {author, commentary, ...}


def _linkedin_error(message: str, status: int = 400, code: str = "INVALID_INPUT"):
    return JSONResponse(
        status_code=status,
        content={
            "status": status,
            "message": message,
            "code": code,
            "request_id": str(uuid.uuid4().hex[:12]),
        },
        headers={
            "x-restli-protocol-version": "2.0.0",
            "Content-Type": "application/json",
        },
    )


def _linkedin_headers(extra: dict = None) -> dict:
    headers = {
        "x-restli-protocol-version": "2.0.0",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _validate_urn(urn: str, expected_kind: str) -> bool:
    """Validate URN format: urn:li:{kind}:{id}"""
    pattern = rf"^urn:li:{re.escape(expected_kind)}:[A-Za-z0-9_-]+$"
    return bool(re.match(pattern, urn))


@app.post("/linkedin/rest/images")
async def linkedin_initialize_upload(
    request: Request,
    action: str = Query(..., description="Must be 'initializeUpload'"),
    authorization: Optional[str] = Header(None),
    linkedin_version: Optional[str] = Header(None, alias="Linkedin-Version"),
):
    """LinkedIn: Initialize image upload (Step 1).
    Real API: POST https://api.linkedin.com/rest/images?action=initializeUpload
    """
    _check_error_sim("linkedin")
    await require_bearer_auth(authorization)

    if action != "initializeUpload":
        return _linkedin_error(f"Unknown action: {action}. Expected 'initializeUpload'", 400, "INVALID_INPUT")

    try:
        body = await request.json()
    except Exception:
        return _linkedin_error("Invalid JSON body")

    req = body.get("initializeUploadRequest", {})
    owner = req.get("owner", "")
    if not owner:
        return _linkedin_error("'initializeUploadRequest.owner' is required")

    # Validate owner URN format
    if not (_validate_urn(owner, "person") or _validate_urn(owner, "organization")):
        return _linkedin_error(f"Invalid owner URN format: {owner}. Expected urn:li:person:{{id}} or urn:li:organization:{{id}}")

    image_id = _linkedin_id()
    urn = _urn("image", image_id)
    # Real LinkedIn returns a full external URL with query params
    upload_url = f"https://www.linkedin.com/dms-uploads/{image_id}/uploaded-image/0?ca=vector_ads&cn=uploads&sync=0&v=beta&ut={uuid.uuid4().hex[:16]}"

    linkedin_images[image_id] = {
        "id": image_id,
        "urn": urn,
        "owner": owner,
        "status": "WAITING_UPLOAD",
        "call_count": 0,
        "uploaded": False,
        "upload_url": upload_url,
        "expires_at": _now_ms() + 3_600_000,
        "created_at": _now_ms(),
    }

    return JSONResponse(
        status_code=200,
        content={
            "value": {
                "uploadUrl": upload_url,
                "image": urn,
                "uploadUrlExpiresAt": _now_ms() + 3_600_000,
            }
        },
        headers=_linkedin_headers(),
    )


@app.put("/linkedin/rest/images/upload/{image_id}")
async def linkedin_upload_image(
    image_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """LinkedIn: Upload image binary (Step 2).
    Real API: PUT {uploadUrl from Step 1}
    Note: Real API uses a dynamic uploadUrl, we route it through our mock endpoint.
    """
    await require_bearer_auth(authorization)

    img = linkedin_images.get(image_id)
    if not img:
        return _linkedin_error(f"Image not found: {_urn('image', image_id)}", 404, "RESOURCE_NOT_FOUND")

    # Read and discard the body (simulate upload)
    body_bytes = await request.body()
    if len(body_bytes) == 0:
        return _linkedin_error("Empty upload body")

    img["uploaded"] = True
    img["status"] = "PROCESSING"
    img["call_count"] = 0
    img["upload_size"] = len(body_bytes)

    return Response(status_code=200, headers=_linkedin_headers())


@app.get("/linkedin/rest/images/{image_urn:path}")
async def linkedin_check_image_status(
    image_urn: str,
    authorization: Optional[str] = Header(None),
):
    """LinkedIn: Check image upload status (Step 2b).
    Real API: GET https://api.linkedin.com/rest/images/{imageUrn}
    """
    await require_bearer_auth(authorization)

    # Extract image_id from URN like "urn:li:image:C4E10AQFoyyAjHPMQuQ"
    image_id = image_urn.split(":")[-1] if ":" in image_urn else image_urn
    img = linkedin_images.get(image_id)
    if not img:
        return _linkedin_error(f"Image not found: {image_urn}", 404, "RESOURCE_NOT_FOUND")

    img["call_count"] += 1
    if img["call_count"] >= MOCK_DELAY_STEPS:
        img["status"] = "AVAILABLE"

    return JSONResponse(
        status_code=200,
        content={
            "status": img["status"],
            "id": img["urn"],
            "createdAt": img.get("created_at", _now_ms()),
            "downloadUrl": f"https://www.linkedin.com/dms-image/{image_id}",
            "size": img.get("upload_size", 0),
            "initialClipRegion": None,
            "recipe": "urn:li:digitalmediaRecipe:feedshare-image",
        },
        headers=_linkedin_headers(),
    )


@app.post("/linkedin/rest/posts")
async def linkedin_create_post(
    request: Request,
    authorization: Optional[str] = Header(None),
    linkedin_version: Optional[str] = Header(None, alias="Linkedin-Version"),
):
    """LinkedIn: Create a post with image (Step 3).
    Real API: POST https://api.linkedin.com/rest/posts
    """
    _check_error_sim("linkedin")
    await require_bearer_auth(authorization)

    try:
        body = await request.json()
    except Exception:
        return _linkedin_error("Invalid JSON body")

    author = body.get("author", "")
    commentary = body.get("commentary", "")
    visibility = body.get("visibility", "PUBLIC")
    distribution = body.get("distribution", {})
    content = body.get("content", {})
    media = content.get("media", {})
    image_id_urn = media.get("id", "")
    alt_text = media.get("altText", "")
    lifecycle_state = body.get("lifecycleState", "PUBLISHED")
    is_reshare_disabled = body.get("isReshareDisabledByAuthor", False)

    # Validate required fields
    if not author:
        return _linkedin_error("'author' is required")

    if not _validate_urn(author, "person") and not _validate_urn(author, "organization"):
        return _linkedin_error(f"Invalid author URN format: {author}")

    # Validate visibility
    valid_visibility = {"PUBLIC", "CONNECTIONS", "LOGGED_IN"}
    if visibility not in valid_visibility:
        return _linkedin_error(f"Invalid visibility: {visibility}. Must be one of {valid_visibility}")

    # Validate lifecycleState
    if lifecycle_state not in ("PUBLISHED", "DRAFT"):
        return _linkedin_error(f"Invalid lifecycleState: {lifecycle_state}. Must be PUBLISHED or DRAFT")

    # Validate commentary length
    if len(commentary) > 3000:
        return _linkedin_error("Commentary exceeds maximum length of 3000 characters")

    # Validate distribution
    if distribution:
        feed_dist = distribution.get("feedDistribution", "")
        valid_feed_dist = {"MAIN_FEED", "PROFILE_ONLY", "NONE"}
        if feed_dist and feed_dist not in valid_feed_dist:
            return _linkedin_error(f"Invalid feedDistribution: {feed_dist}")

    # Validate image if provided
    if image_id_urn:
        if not _validate_urn(image_id_urn, "image"):
            return _linkedin_error(f"Invalid image URN format: {image_id_urn}")

        image_id = image_id_urn.split(":")[-1]
        img = linkedin_images.get(image_id)
        if img and img["status"] != "AVAILABLE":
            return _linkedin_error("Image is not yet available for use. Wait for status AVAILABLE.", 409, "CONFLICT")

    post_id = _linkedin_id()
    post_urn = _urn("share", post_id)

    linkedin_posts[post_id] = {
        "id": post_urn,
        "author": author,
        "commentary": commentary,
        "visibility": visibility,
        "distribution": distribution,
        "content_media_id": image_id_urn,
        "content_media_alt": alt_text,
        "lifecycleState": lifecycle_state,
        "isReshareDisabledByAuthor": is_reshare_disabled,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "createdAt": _now_ms(),
        "lastModifiedAt": _now_ms(),
    }
    published_posts["linkedin"].append(linkedin_posts[post_id])
    _save_published(published_posts)

    # Real API returns 201 with NO body — post ID is ONLY in x-restli-id header
    return Response(
        status_code=201,
        headers={
            "x-restli-id": post_urn,
            "x-restli-protocol-version": "2.0.0",
            "Content-Type": "application/json",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
#  INSPECTION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/published")
async def list_all_published():
    """List all published posts across all platforms."""
    return published_posts


@app.get("/published/{platform}")
async def list_platform_published(platform: str):
    """List published posts for a specific platform (instagram, x, linkedin)."""
    if platform not in published_posts:
        raise HTTPException(404, detail=f"Unknown platform: {platform}. Use instagram, x, or linkedin")
    return published_posts[platform]


@app.get("/published/{platform}/{post_id}")
async def get_published_post(platform: str, post_id: str):
    """Get a specific published post by ID."""
    if platform not in published_posts:
        raise HTTPException(404, detail=f"Unknown platform: {platform}")

    for post in published_posts[platform]:
        if post.get("id", "").endswith(post_id) or post.get("id") == post_id:
            return post

    raise HTTPException(404, detail=f"Post not found: {post_id} on {platform}")


@app.delete("/published")
async def clear_all_published():
    """Clear all published posts from all platforms."""
    published_posts.clear()
    published_posts.update({"instagram": [], "x": [], "linkedin": []})
    _save_published(published_posts)
    return {"status": "ok", "message": "All published posts cleared"}


@app.post("/reset/{platform}")
async def reset_platform(platform: str):
    """Reset a platform's mock state (containers, media, posts)."""
    if platform == "instagram":
        ig_containers.clear()
        ig_media.clear()
        published_posts["instagram"] = []
    elif platform == "x":
        x_media_store.clear()
        x_tweets.clear()
        published_posts["x"] = []
    elif platform == "linkedin":
        linkedin_images.clear()
        linkedin_posts.clear()
        published_posts["linkedin"] = []
    else:
        raise HTTPException(404, detail=f"Unknown platform: {platform}")

    _save_published(published_posts)
    return {"status": "ok", "platform": platform, "message": f"Reset {platform} mock state"}


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR SIMULATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/simulate/{platform}/rate-limit")
async def simulate_rate_limit(platform: str, requests: int = Query(3, ge=1, le=100)):
    """Enable rate limit simulation for a platform. Returns 429 for the next N requests."""
    if platform not in ("instagram", "x", "linkedin"):
        raise HTTPException(404, detail=f"Unknown platform: {platform}")
    error_simulation[platform] = {"error_type": "rate_limit", "remaining": requests}
    return {"status": "ok", "platform": platform, "remaining": requests, "message": f"Rate limit simulation enabled for {requests} requests"}


@app.post("/simulate/{platform}/error")
async def simulate_error(
    platform: str,
    error_type: str = Query("server_error", description="Error type to simulate"),
    requests: int = Query(1, ge=1, le=100),
):
    """Inject error simulation for a platform."""
    if platform not in ("instagram", "x", "linkedin"):
        raise HTTPException(404, detail=f"Unknown platform: {platform}")
    error_simulation[platform] = {"error_type": error_type, "remaining": requests}
    return {"status": "ok", "platform": platform, "error_type": error_type, "remaining": requests}


@app.get("/simulate/status")
async def simulation_status():
    """Check current error simulation state."""
    return {"active_simulations": error_simulation}


@app.post("/simulate/clear")
async def clear_simulations():
    """Clear all active error simulations."""
    error_simulation.clear()
    return {"status": "ok", "message": "All simulations cleared"}


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH / ROOT
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "service": "Mock Social Media APIs",
        "version": "2.0.0",
        "platforms": {
            "instagram": {"prefix": "/ig/v25.0", "docs": "/docs"},
            "x": {"prefix": "/x/v2", "docs": "/docs"},
            "linkedin": {"prefix": "/linkedin/rest", "docs": "/docs"},
        },
        "inspection": {
            "all_published": "/published",
            "by_platform": "/published/{instagram|x|linkedin}",
            "by_post_id": "/published/{platform}/{post_id}",
        },
        "simulations": {
            "rate_limit": "POST /simulate/{platform}/rate-limit",
            "error": "POST /simulate/{platform}/error",
            "status": "GET /simulate/status",
            "clear": "POST /simulate/clear",
        },
        "reset": "POST /reset/{platform}",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "published_counts": {
            "instagram": len(published_posts["instagram"]),
            "x": len(published_posts["x"]),
            "linkedin": len(published_posts["linkedin"]),
        },
        "active_simulations": len(error_simulation),
        "ig_containers_pending": len(ig_containers),
        "x_media_pending": len([m for m in x_media_store.values() if m["status"] != "succeeded"]),
        "linkedin_images_pending": len([i for i in linkedin_images.values() if i["status"] != "AVAILABLE"]),
    }
