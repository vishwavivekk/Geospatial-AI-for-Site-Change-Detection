"""Auto-publish approved designs to the mock social media APIs.

Runs the real multi-step flows against the mock server:
  Instagram : create container -> poll status -> publish
  X         : upload media -> create tweet
  LinkedIn  : initialize upload -> upload binary -> poll -> create post
"""

import asyncio
import base64
import os

import httpx

from app.config import (
    IG_USER_ID,
    LINKEDIN_AUTHOR,
    MOCK_API_BASE,
    PUBLIC_BASE_URL,
    PUBLISHED_DIR,
    SOCIAL_ACCESS_TOKEN,
)

POLL_TRIES = 10
POLL_DELAY = 0.3

X_TEXT_MAX = 280
IG_CAPTION_MAX = 2200
LINKEDIN_TEXT_MAX = 3000


def save_published_png(design_id: str, data_url: str) -> str:
    """Persist the approved design PNG; returns the filename."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    png_bytes = base64.b64decode(data_url)
    os.makedirs(PUBLISHED_DIR, exist_ok=True)
    filename = f"{design_id}.png"
    with open(os.path.join(PUBLISHED_DIR, filename), "wb") as f:
        f.write(png_bytes)
    return filename


def build_caption(topic: str, story_text: str, limit: int) -> str:
    hashtags = "#NICDC #IndustrialCorridors #MakeInIndia"
    body = story_text.strip().replace("\r\n", "\n")
    caption = f"{topic}\n\n{body}\n\n{hashtags}"
    if len(caption) <= limit:
        return caption
    room = limit - len(topic) - len(hashtags) - 6  # newlines + ellipsis
    if room > 40:
        return f"{topic}\n\n{body[:room].rstrip()}…\n\n{hashtags}"
    return caption[: limit - 1] + "…"


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {SOCIAL_ACCESS_TOKEN}"}


async def _publish_instagram(client: httpx.AsyncClient, image_url: str, caption: str) -> dict:
    # Step 1: create media container
    resp = await client.post(
        f"{MOCK_API_BASE}/ig/v25.0/{IG_USER_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": SOCIAL_ACCESS_TOKEN,
        },
        headers=_auth_headers(),
    )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        raise RuntimeError(f"IG container failed: {data}")
    container_id = data["id"]

    # Step 1b: poll container status until FINISHED
    for _ in range(POLL_TRIES):
        resp = await client.get(
            f"{MOCK_API_BASE}/ig/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": SOCIAL_ACCESS_TOKEN},
            headers=_auth_headers(),
        )
        status = resp.json().get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("IG container processing failed")
        await asyncio.sleep(POLL_DELAY)
    else:
        raise RuntimeError("IG container never finished processing")

    # Step 2: publish
    resp = await client.post(
        f"{MOCK_API_BASE}/ig/v25.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": SOCIAL_ACCESS_TOKEN},
        headers=_auth_headers(),
    )
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        raise RuntimeError(f"IG publish failed: {data}")
    return {"platform": "instagram", "post_id": data["id"], "status": "published"}


async def _publish_x(client: httpx.AsyncClient, png_bytes: bytes, text: str) -> dict:
    # Step 1: simple media upload
    resp = await client.post(
        f"{MOCK_API_BASE}/x/v2/media/upload",
        files={"media": ("post.png", png_bytes, "image/png")},
        data={"media_category": "tweet_image", "media_type": "image/png"},
        headers=_auth_headers(),
    )
    data = resp.json()
    media_id = (data.get("data") or {}).get("id")
    if resp.status_code not in (200, 201) or not media_id:
        raise RuntimeError(f"X media upload failed: {data}")

    # Step 2: create tweet
    resp = await client.post(
        f"{MOCK_API_BASE}/x/v2/tweets",
        json={"text": text, "media": {"media_ids": [media_id]}},
        headers=_auth_headers(),
    )
    data = resp.json()
    tweet_id = (data.get("data") or {}).get("id")
    if resp.status_code not in (200, 201) or not tweet_id:
        raise RuntimeError(f"X tweet failed: {data}")
    return {"platform": "x", "post_id": tweet_id, "status": "published"}


async def _publish_linkedin(client: httpx.AsyncClient, png_bytes: bytes, text: str) -> dict:
    # Step 1: initialize upload
    resp = await client.post(
        f"{MOCK_API_BASE}/linkedin/rest/images",
        params={"action": "initializeUpload"},
        json={"initializeUploadRequest": {"owner": LINKEDIN_AUTHOR}},
        headers={**_auth_headers(), "Linkedin-Version": "202506"},
    )
    data = resp.json()
    image_urn = (data.get("value") or {}).get("image")
    if resp.status_code != 200 or not image_urn:
        raise RuntimeError(f"LinkedIn init upload failed: {data}")
    image_id = image_urn.split(":")[-1]

    # Step 2: upload binary (mock routes the dynamic uploadUrl locally)
    resp = await client.put(
        f"{MOCK_API_BASE}/linkedin/rest/images/upload/{image_id}",
        content=png_bytes,
        headers=_auth_headers(),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"LinkedIn image upload failed: {resp.text}")

    # Step 2b: poll until AVAILABLE
    for _ in range(POLL_TRIES):
        resp = await client.get(
            f"{MOCK_API_BASE}/linkedin/rest/images/{image_urn}",
            headers=_auth_headers(),
        )
        if resp.json().get("status") == "AVAILABLE":
            break
        await asyncio.sleep(POLL_DELAY)
    else:
        raise RuntimeError("LinkedIn image never became AVAILABLE")

    # Step 3: create post
    resp = await client.post(
        f"{MOCK_API_BASE}/linkedin/rest/posts",
        json={
            "author": LINKEDIN_AUTHOR,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED"},
            "content": {"media": {"id": image_urn, "altText": text[:100]}},
            "lifecycleState": "PUBLISHED",
        },
        headers={**_auth_headers(), "Linkedin-Version": "202506"},
    )
    if resp.status_code != 201:
        raise RuntimeError(f"LinkedIn post failed: {resp.text}")
    post_urn = resp.headers.get("x-restli-id", "")
    return {"platform": "linkedin", "post_id": post_urn, "status": "published"}


async def publish_design(design: dict, png_filename: str) -> dict:
    """Publish to all three platforms. Returns per-platform results;
    each entry is either a success record or {status: failed, error}."""
    topic = design["topic"]
    story_text = design.get("story_text", "")
    image_url = f"{PUBLIC_BASE_URL}/published/{png_filename}"
    with open(os.path.join(PUBLISHED_DIR, png_filename), "rb") as f:
        png_bytes = f.read()

    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = {
            "instagram": _publish_instagram(
                client, image_url, build_caption(topic, story_text, IG_CAPTION_MAX)
            ),
            "x": _publish_x(
                client, png_bytes, build_caption(topic, story_text, X_TEXT_MAX)
            ),
            "linkedin": _publish_linkedin(
                client, png_bytes, build_caption(topic, story_text, LINKEDIN_TEXT_MAX)
            ),
        }
        outcomes = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for platform, outcome in zip(tasks.keys(), outcomes):
            if isinstance(outcome, Exception):
                results[platform] = {
                    "platform": platform,
                    "status": "failed",
                    "error": str(outcome),
                }
            else:
                results[platform] = outcome
    return results
