import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.models import Design, DesignComment


class DesignRepo:
    def __init__(self, session):
        self.session = session

    async def get_all(self, status: str | None = None) -> list[dict]:
        q = select(Design)
        if status:
            q = q.where(Design.status == status)
        q = q.order_by(Design.submitted_at.desc())
        result = await self.session.execute(q)
        return [row[0].to_dict() for row in result.all()]

    async def get_one(self, design_id: str) -> Design | None:
        result = await self.session.execute(
            select(Design).where(Design.id == design_id)
        )
        return result.scalar_one_or_none()

    async def get_one_dict(self, design_id: str) -> dict | None:
        design = await self.get_one(design_id)
        return design.to_dict() if design else None

    async def get_one_with_comments(self, design_id: str) -> Design | None:
        result = await self.session.execute(
            select(Design)
            .where(Design.id == design_id)
            .options(selectinload(Design.comments))
        )
        return result.scalar_one_or_none()

    async def get_one_dict_with_comments(self, design_id: str) -> dict | None:
        design = await self.get_one_with_comments(design_id)
        return design.to_dict_with_comments() if design else None

    async def get_variant_group_with_comments(self, group_id: str) -> list[dict]:
        result = await self.session.execute(
            select(Design)
            .where(Design.variant_group == group_id)
            .order_by(Design.variant_index)
            .options(selectinload(Design.comments))
        )
        return [row[0].to_dict_with_comments() for row in result.all()]

    async def get_by_topic(self, topic: str) -> Design | None:
        result = await self.session.execute(
            select(Design).where(Design.topic == topic)
            .order_by(Design.submitted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_topic_dict(self, topic: str) -> dict | None:
        design = await self.get_by_topic(topic)
        return design.to_dict() if design else None

    async def get_variant_group(self, group_id: str) -> list[dict]:
        result = await self.session.execute(
            select(Design).where(Design.variant_group == group_id)
            .order_by(Design.variant_index)
        )
        return [row[0].to_dict() for row in result.all()]

    async def add(
        self,
        topic: str,
        category: str,
        story_text: str,
        story_images: list[str],
        design_state: dict,
        design_png: str = "",
        variant_group: str = "",
        variant_index: int = 0,
        submitted_by: str = "",
    ) -> dict:
        design = Design(
            topic=topic,
            category=category or None,
            story_text=story_text,
            story_images=story_images or None,
            design_state=design_state,
            design_png=design_png or None,
            status="pending",
            revision=1,
            submitted_by=submitted_by or None,
            variant_group=variant_group or None,
            variant_index=variant_index,
        )
        self.session.add(design)
        await self.session.commit()
        await self.session.refresh(design)
        return design.to_dict()

    async def update_state(
        self, design_id: str, design_state: dict, design_png: str = "",
        submitted_by: str = "",
    ) -> dict | None:
        """Editor resubmits a fixed design: archive the feedback round,
        bump the revision, and put it back in the approval queue."""
        design = await self.get_one_with_comments(design_id)
        if not design:
            return None
        if design.comments or design.reviewer_note:
            history = list(design.feedback_history or [])
            history.append({
                "revision": design.revision or 1,
                "comments": [c.to_dict() for c in design.comments],
                "reviewer_note": design.reviewer_note or "",
                "reviewed_at": design.reviewed_at.isoformat() if design.reviewed_at else None,
                "reviewed_by": design.reviewed_by or "",
            })
            design.feedback_history = history
        design.design_state = design_state
        if design_png:
            design.design_png = design_png
        design.status = "pending"
        design.revision = (design.revision or 1) + 1
        if submitted_by:
            design.submitted_by = submitted_by
        design.submitted_at = datetime.now(timezone.utc)
        design.reviewed_at = None
        design.reviewed_by = None
        design.reviewer_note = None
        design.post_results = None
        design.comments = []
        await self.session.commit()
        return design.to_dict()

    async def update_variant(
        self, variant_group: str, variant_index: int,
        design_state: dict, design_png: str = ""
    ) -> dict | None:
        result = await self.session.execute(
            select(Design).where(
                Design.variant_group == variant_group,
                Design.variant_index == variant_index,
            )
        )
        design = result.scalar_one_or_none()
        if not design:
            return None
        design.design_state = design_state
        if design_png:
            design.design_png = design_png
        design.status = "pending"
        design.submitted_at = datetime.now(timezone.utc)
        design.reviewed_at = None
        design.reviewer_note = None
        design.post_results = None
        await self.session.commit()
        return design.to_dict()

    async def update_caption(
        self, design_id: str, caption: str
    ) -> dict | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        design.caption = caption or None
        await self.session.commit()
        return design.to_dict()

    async def update_status(
        self, design_id: str, status: str, note: str = "",
        post_results: dict | None = None, reviewed_by: str = "",
    ) -> dict | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        design.status = status
        design.reviewed_at = datetime.now(timezone.utc)
        design.reviewer_note = note or None
        if reviewed_by:
            design.reviewed_by = reviewed_by
        if post_results is not None:
            design.post_results = post_results
        await self.session.commit()
        return design.to_dict()

    async def set_published(
        self, design_id: str, publish_results: dict,
        image_url: str = "", all_ok: bool = True,
    ) -> dict | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        design.post_results = publish_results
        if image_url:
            design.published_image_url = image_url
        if all_ok:
            design.status = "published"
            design.published_at = datetime.now(timezone.utc)
        await self.session.commit()
        return design.to_dict()

    async def delete(self, design_id: str) -> bool:
        result = await self.session.execute(
            select(Design).where(Design.id == design_id)
        )
        design = result.scalar_one_or_none()
        if not design:
            return False
        await self.session.delete(design)
        await self.session.commit()
        return True

    async def add_comment(
        self, design_id: str,
        element_id: str | None, element_type: str | None, text: str,
        author: str = "",
    ) -> dict | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        comment = DesignComment(
            design_id=design_id,
            element_id=element_id,
            element_type=element_type,
            text=text,
            author=author or None,
        )
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment.to_dict()

    async def get_comments(self, design_id: str) -> list[dict] | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        result = await self.session.execute(
            select(DesignComment).where(DesignComment.design_id == design_id)
            .order_by(DesignComment.created_at)
        )
        return [row[0].to_dict() for row in result.all()]

    async def delete_comment(self, design_id: str, comment_id: str) -> list[dict] | None:
        design = await self.get_one(design_id)
        if not design:
            return None
        result = await self.session.execute(
            select(DesignComment).where(
                DesignComment.id == comment_id,
                DesignComment.design_id == design_id,
            )
        )
        comment = result.scalar_one_or_none()
        if comment:
            await self.session.delete(comment)
            await self.session.commit()
        return await self.get_comments(design_id)

    @staticmethod
    def get_groups_for_designs(designs: list[dict]) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for d in designs:
            vg = d.get("variant_group", "")
            if vg:
                groups.setdefault(vg, []).append(d)
        return groups
