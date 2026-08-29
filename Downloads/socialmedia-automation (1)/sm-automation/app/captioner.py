"""AI caption generation for bank posts."""

from app.cloud_llm import generate

SYSTEM_PROMPT = """You are a social media manager for NICDC (National Industrial
Corridor Development Corporation, Government of India) writing captions for
official posts about industrial corridors, investment and infrastructure.

Write ONE caption suitable for the given platforms. Rules:
- Professional, confident, institutional tone; no exaggeration
- 2-4 short sentences, then 3-5 relevant hashtags on a new line
- Always include #NICDC among the hashtags
- If X (Twitter) is targeted, stay under 240 characters INCLUDING hashtags
- No emojis unless the description asks for them
- Output ONLY the caption text, nothing else"""


async def generate_caption(title: str, description: str, platforms: list[str], current: str = "") -> str:
    parts = [f"Post title: {title}"]
    if description:
        parts.append(f"What the post shows / notes from the editor: {description}")
    if current:
        parts.append(f"Current draft caption (improve it): {current}")
    parts.append("Target platforms: " + ", ".join(platforms or ["linkedin"]))
    text = await generate(
        prompt="\n".join(parts),
        system_instruction=SYSTEM_PROMPT,
        temperature=0.7,
    )
    return text.strip().strip('"')
