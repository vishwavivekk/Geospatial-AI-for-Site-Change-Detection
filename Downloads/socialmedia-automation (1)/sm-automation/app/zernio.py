"""Zernio media hosting.

Uploads the approved post image and returns a public URL, which is
then used as the image URL when publishing to social platforms.
Flow: POST /v1/media/presign -> PUT file to uploadUrl -> use publicUrl.
"""

import httpx

from app.config import ZERNIO_API_BASE, ZERNIO_API_KEY


async def upload_image(data: bytes, filename: str, content_type: str = "image/png") -> str | None:
    """Upload image bytes to Zernio; returns the public URL.
    Returns None when no key is configured or the upload fails —
    callers fall back to the locally served URL."""
    if not ZERNIO_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ZERNIO_API_BASE}/v1/media/presign",
                headers={"Authorization": f"Bearer {ZERNIO_API_KEY}"},
                json={"filename": filename, "contentType": content_type},
            )
            resp.raise_for_status()
            presign = resp.json()
            upload_url = presign["uploadUrl"]
            public_url = presign["publicUrl"]

            resp = await client.put(
                upload_url,
                content=data,
                headers={"Content-Type": content_type},
            )
            resp.raise_for_status()
            return public_url
    except Exception:
        return None
