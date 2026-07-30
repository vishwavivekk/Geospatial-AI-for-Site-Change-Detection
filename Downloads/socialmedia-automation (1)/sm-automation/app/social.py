"""Real social media posting via the Zernio SDK.

Posts the approved design image to the Instagram / LinkedIn accounts
connected in the Zernio dashboard. Raises RuntimeError when no key is
configured or no accounts are connected — callers fall back to the
mock publisher so the approval flow never breaks.
"""

import asyncio

from app.config import ZERNIO_API_KEY


def _post_sync(image_path: str, caption: str) -> dict:
    from zernio import Zernio

    if not ZERNIO_API_KEY:
        raise RuntimeError("ZERNIO_API_KEY is not configured")

    client = Zernio(api_key=ZERNIO_API_KEY)

    accounts_resp = client.accounts.list()
    ig_accounts = [a for a in accounts_resp.accounts if a.platform.value == "instagram"]
    li_accounts = [a for a in accounts_resp.accounts if a.platform.value == "linkedin"]

    if not ig_accounts and not li_accounts:
        raise RuntimeError("No Instagram or LinkedIn accounts connected in Zernio")

    upload = client.media.upload(image_path)
    image_url = str(upload.files[0].url)

    platforms = []
    if ig_accounts:
        platforms.append({"platform": "instagram", "accountId": ig_accounts[0].field_id})
    if li_accounts:
        platforms.append({"platform": "linkedin", "accountId": li_accounts[0].field_id})

    result = client.posts.create_post(
        content=caption,
        media_items=[{"url": image_url, "type": "image"}],
        platforms=platforms,
        publish_now=True,
    )

    post = result["post"]
    post_urls = {}
    for p in post.get("platforms", []):
        url = p.get("platformPostUrl")
        if url:
            post_urls[p.get("platform", "unknown")] = url

    return {
        "post_id": post["_id"],
        "status": post["status"],
        "platforms": post.get("platforms", []),
        "post_urls": post_urls,
        "image_url": image_url,
    }


async def post_to_social(image_path: str, caption: str) -> dict:
    """Async wrapper — the Zernio SDK is synchronous."""
    return await asyncio.to_thread(_post_sync, image_path, caption)
