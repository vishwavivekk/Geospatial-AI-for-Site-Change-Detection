from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import BankPost, PostComment


def _now():
    return datetime.now(timezone.utc)


class PostRepo:
    def __init__(self, session):
        self.session = session

    async def get_all(self, status: str | None = None) -> "list[dict]":
        q = select(BankPost).options(selectinload(BankPost.comments))
        if status:
            q = q.where(BankPost.status == status)
        q = q.order_by(BankPost.created_at.desc())
        result = await self.session.execute(q)
        return [row[0].to_dict_with_comments() for row in result.all()]

    async def get_one(self, post_id: str) -> BankPost | None:
        result = await self.session.execute(
            select(BankPost).where(BankPost.id == post_id)
            .options(selectinload(BankPost.comments))
        )
        return result.scalar_one_or_none()

    async def get_one_dict(self, post_id: str) -> dict | None:
        post = await self.get_one(post_id)
        return post.to_dict_with_comments() if post else None

    async def add(
        self, title: str, kind: str, image_path: str,
        description: str = "", html_source: str = "",
        design_state: dict | None = None, created_by: str = "",
    ) -> dict:
        post = BankPost(
            title=title,
            description=description or None,
            kind=kind,
            image_path=image_path,
            html_source=html_source or None,
            design_state=design_state,
            status="draft",
            created_by=created_by or None,
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post.to_dict()

    async def update_content(
        self, post_id: str, title: str = "", description: str | None = None,
        image_path: str = "", html_source: str | None = None,
        design_state: dict | None = None,
    ) -> dict | None:
        post = await self.get_one(post_id)
        if not post:
            return None
        if title:
            post.title = title
        if description is not None:
            post.description = description or None
        if image_path:
            post.image_path = image_path
        if html_source is not None:
            post.html_source = html_source or None
        if design_state is not None:
            post.design_state = design_state
        await self.session.commit()
        return post.to_dict()

    async def share(self, post_id: str, caption: str, platforms: list[str], submitted_by: str) -> dict | None:
        """Editor shares (or re-shares after fixes) a post with the approver.
        Re-sharing archives the previous feedback round and bumps the revision."""
        post = await self.get_one(post_id)
        if not post:
            return None
        if post.comments or post.reviewer_note:
            history = list(post.feedback_history or [])
            history.append({
                "revision": post.revision or 1,
                "comments": [c.to_dict() for c in post.comments],
                "reviewer_note": post.reviewer_note or "",
                "reviewed_at": post.reviewed_at.isoformat() if post.reviewed_at else None,
                "reviewed_by": post.reviewed_by or "",
            })
            post.feedback_history = history
            post.revision = (post.revision or 1) + 1
            post.comments = []
        post.caption = caption or post.caption
        if platforms:
            post.platforms = platforms
        post.status = "pending"
        post.submitted_by = submitted_by or None
        post.submitted_at = _now()
        post.reviewed_at = None
        post.reviewed_by = None
        post.reviewer_note = None
        await self.session.commit()
        return post.to_dict()

    async def update_status(
        self, post_id: str, status: str, note: str = "", reviewed_by: str = "",
    ) -> dict | None:
        post = await self.get_one(post_id)
        if not post:
            return None
        post.status = status
        post.reviewed_at = _now()
        post.reviewer_note = note or None
        if reviewed_by:
            post.reviewed_by = reviewed_by
        await self.session.commit()
        return post.to_dict()

    async def update_caption(self, post_id: str, caption: str) -> dict | None:
        post = await self.get_one(post_id)
        if not post:
            return None
        post.caption = caption or None
        await self.session.commit()
        return post.to_dict()

    async def set_published(
        self, post_id: str, publish_results: dict, image_url: str = "", all_ok: bool = True,
    ) -> dict | None:
        post = await self.get_one(post_id)
        if not post:
            return None
        post.post_results = publish_results
        if image_url:
            post.published_image_url = image_url
        if all_ok:
            post.status = "published"
            post.published_at = _now()
        await self.session.commit()
        return post.to_dict()

    async def delete(self, post_id: str) -> str:
        """Deletes the post; returns its image_path so the caller can unlink."""
        post = await self.get_one(post_id)
        if not post:
            return ""
        image_path = post.image_path
        await self.session.delete(post)
        await self.session.commit()
        return image_path or ""

    async def add_comment(
        self, post_id: str, region: dict | None, text: str, author: str = "",
    ) -> dict | None:
        post = await self.get_one(post_id)
        if not post:
            return None
        comment = PostComment(post_id=post_id, region=region, text=text, author=author or None)
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment.to_dict()

    async def get_comments(self, post_id: str) -> "list[dict] | None":
        post = await self.get_one(post_id)
        if not post:
            return None
        result = await self.session.execute(
            select(PostComment).where(PostComment.post_id == post_id)
            .order_by(PostComment.created_at)
        )
        return [row[0].to_dict() for row in result.all()]

    async def delete_comment(self, post_id: str, comment_id: str) -> "list[dict] | None":
        post = await self.get_one(post_id)
        if not post:
            return None
        result = await self.session.execute(
            select(PostComment).where(
                PostComment.id == comment_id, PostComment.post_id == post_id
            )
        )
        comment = result.scalar_one_or_none()
        if comment:
            await self.session.delete(comment)
            await self.session.commit()
        return await self.get_comments(post_id)
