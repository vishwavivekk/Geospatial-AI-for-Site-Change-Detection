import json
import os
import uuid
from datetime import datetime, timezone

from app.config import DESIGNS_PATH

# Status lifecycle:
#   pending   -> submitted by editor, waiting for approver
#   feedback  -> approver requested changes (comments attached)
#   approved  -> approver approved; publishing in progress / failed
#   published -> auto-published to social media
VALID_STATUSES = ("pending", "approved", "rejected", "feedback", "published")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DesignStore:
    def __init__(self):
        self._designs: list[dict] = []

    def load(self) -> bool:
        try:
            with open(DESIGNS_PATH) as f:
                self._designs = json.load(f)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            self._designs = []
            return False

    def save(self) -> None:
        os.makedirs(os.path.dirname(DESIGNS_PATH), exist_ok=True)
        with open(DESIGNS_PATH, "w") as f:
            json.dump(self._designs, f, indent=2)

    def add(
        self,
        topic: str,
        category: str,
        story_text: str,
        story_images: list[str],
        design_state: dict,
        submitted_by: str = "",
    ) -> dict:
        design = {
            "id": "design-" + uuid.uuid4().hex,
            "topic": topic,
            "category": category,
            "story_text": story_text,
            "story_images": story_images,
            "design_state": design_state,
            "status": "pending",
            "revision": 1,
            "submitted_by": submitted_by,
            "submitted_at": _now(),
            "reviewed_at": None,
            "reviewed_by": "",
            "reviewer_note": "",
            "comments": [],
            "feedback_history": [],
            "publish_results": None,
            "published_at": None,
        }
        self._designs.append(design)
        self.save()
        return design

    def get_all(self, status: str | None = None) -> list[dict]:
        if status:
            return [d for d in self._designs if d["status"] == status]
        return list(self._designs)

    def get_one(self, design_id: str) -> dict | None:
        for d in self._designs:
            if d["id"] == design_id:
                return d
        return None

    def get_by_topic(self, topic: str) -> dict | None:
        for d in reversed(self._designs):
            if d["topic"] == topic:
                return d
        return None

    def update_state(self, design_id: str, design_state: dict, submitted_by: str = "") -> dict | None:
        """Editor resubmits a fixed design: archive the feedback round,
        bump the revision, and put it back in the approval queue."""
        design = self.get_one(design_id)
        if not design:
            return None
        if design.get("comments") or design.get("reviewer_note"):
            design.setdefault("feedback_history", []).append({
                "revision": design.get("revision", 1),
                "comments": design.get("comments", []),
                "reviewer_note": design.get("reviewer_note", ""),
                "reviewed_at": design.get("reviewed_at"),
                "reviewed_by": design.get("reviewed_by", ""),
            })
        design["design_state"] = design_state
        design["status"] = "pending"
        design["revision"] = design.get("revision", 1) + 1
        if submitted_by:
            design["submitted_by"] = submitted_by
        design["submitted_at"] = _now()
        design["reviewed_at"] = None
        design["reviewed_by"] = ""
        design["reviewer_note"] = ""
        design["comments"] = []
        self.save()
        return design

    def update_status(self, design_id: str, status: str, note: str = "", reviewed_by: str = "") -> dict | None:
        design = self.get_one(design_id)
        if not design:
            return None
        design["status"] = status
        design["reviewed_at"] = _now()
        design["reviewer_note"] = note
        if reviewed_by:
            design["reviewed_by"] = reviewed_by
        self.save()
        return design

    def set_published(self, design_id: str, publish_results: dict, image_url: str = "") -> dict | None:
        design = self.get_one(design_id)
        if not design:
            return None
        all_ok = all(r.get("status") == "published" for r in publish_results.values())
        design["publish_results"] = publish_results
        if image_url:
            design["published_image_url"] = image_url
        if all_ok:
            design["status"] = "published"
            design["published_at"] = _now()
        self.save()
        return design

    def delete(self, design_id: str) -> bool:
        before = len(self._designs)
        self._designs = [d for d in self._designs if d["id"] != design_id]
        if len(self._designs) < before:
            self.save()
            return True
        return False

    def add_comment(
        self,
        design_id: str,
        element_id: str | None,
        element_type: str | None,
        text: str,
        author: str = "",
    ) -> dict | None:
        design = self.get_one(design_id)
        if not design:
            return None
        comment = {
            "id": "comment-" + uuid.uuid4().hex,
            "element_id": element_id,
            "element_type": element_type,
            "text": text,
            "author": author,
            "created_at": _now(),
        }
        design.setdefault("comments", []).append(comment)
        self.save()
        return comment

    def get_comments(self, design_id: str) -> list[dict] | None:
        design = self.get_one(design_id)
        if not design:
            return None
        return design.get("comments", [])

    def delete_comment(self, design_id: str, comment_id: str) -> list[dict] | None:
        design = self.get_one(design_id)
        if not design:
            return None
        design["comments"] = [c for c in design.get("comments", []) if c["id"] != comment_id]
        self.save()
        return design["comments"]


design_store = DesignStore()
