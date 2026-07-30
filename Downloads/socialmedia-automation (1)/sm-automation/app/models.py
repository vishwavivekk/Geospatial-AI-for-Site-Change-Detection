import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    palette: Mapped[dict] = mapped_column(JSON, nullable=False)
    fonts: Mapped[dict] = mapped_column(JSON, nullable=False)
    logo: Mapped[Optional[str]] = mapped_column(String)
    dpiit_logo: Mapped[Optional[str]] = mapped_column(String)
    tone: Mapped[Optional[str]] = mapped_column(Text)
    layout_instructions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "palette": self.palette,
            "fonts": self.fonts,
            "logo": self.logo or "",
            "dpiit_logo": self.dpiit_logo or "",
            "tone": self.tone or "",
            "layout_instructions": self.layout_instructions or "",
        }


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    topic: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String)
    source: Mapped[Optional[str]] = mapped_column(String)
    prid: Mapped[Optional[str]] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_name: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="story", cascade="all, delete-orphan")
    story_images: Mapped[list["StoryImage"]] = relationship(back_populates="story", cascade="all, delete-orphan")


class StoryImage(Base):
    __tablename__ = "story_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(String, ForeignKey("stories.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String)

    story: Mapped["Story"] = relationship(back_populates="story_images")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(String, ForeignKey("stories.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    story: Mapped["Story"] = relationship(back_populates="chunks")


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("stories.id"))
    topic: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String)
    story_text: Mapped[Optional[str]] = mapped_column(Text)
    story_images: Mapped[Optional[list]] = mapped_column(JSON)
    design_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    design_png: Mapped[Optional[str]] = mapped_column(String)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    variant_group: Mapped[Optional[str]] = mapped_column(String, index=True)
    variant_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    submitted_by: Mapped[Optional[str]] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text)
    feedback_history: Mapped[Optional[list]] = mapped_column(JSON)
    post_results: Mapped[Optional[dict]] = mapped_column(JSON)
    published_image_url: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    comments: Mapped[list["DesignComment"]] = relationship(
        back_populates="design", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "category": self.category or "",
            "story_text": self.story_text or "",
            "story_images": self.story_images or [],
            "design_state": self.design_state,
            "design_png": self.design_png or "",
            "caption": self.caption or "",
            "variant_group": self.variant_group or "",
            "variant_index": self.variant_index,
            "status": self.status,
            "revision": self.revision or 1,
            "submitted_by": self.submitted_by or "",
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else "",
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by or "",
            "reviewer_note": self.reviewer_note or "",
            "feedback_history": self.feedback_history or [],
            "publish_results": self.post_results,
            "published_image_url": self.published_image_url or "",
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "comments": [],
        }

    def to_dict_with_comments(self) -> dict:
        d = self.to_dict()
        d["comments"] = [c.to_dict() for c in self.comments]
        return d


class DesignComment(Base):
    __tablename__ = "design_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    design_id: Mapped[str] = mapped_column(String, ForeignKey("designs.id"), nullable=False, index=True)
    element_id: Mapped[Optional[str]] = mapped_column(String)
    element_type: Mapped[Optional[str]] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    design: Mapped["Design"] = relationship(back_populates="comments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "element_id": self.element_id,
            "element_type": self.element_type,
            "text": self.text,
            "author": self.author or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class ImageFile(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
