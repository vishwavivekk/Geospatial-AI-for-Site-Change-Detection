import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    SESSION_COOKIE,
    create_user,
    delete_user,
    get_user_record,
    list_users,
    require_canva_access,
    update_user,
    user_can_use_canva,
    create_session_token,
    get_user,
    require_approver,
    require_editor,
    require_user,
    verify_login,
)
from app.chat_handler import chat_edit
from app.chunker import chunk_document
from app.config import (
    ASSETS_DIR,
    BANK_DIR,
    DESIGN_EXPORTS_DIR,
    BASE_DIR,
    PAGES_DIR,
    PUBLISHED_DIR,
    TEMPLATES_DIR,
)
from app.database import async_session, get_db, init_db
from app.document_loader import Document
from app.embedder import embed_batch
from app.enhancement import enhance_layout
from app.generator import generate_post
from app.image_store import get_image_path, save_images
from app.layout_generator import generate_layout, generate_layout_variations
from app.models import Chunk as ChunkModel
from app.publisher import build_caption, publish_design as publish_design_mock
from app.repositories.category_repo import BRAND_TEMPLATES, CategoryRepo, _sanitize_name
from app.repositories.chunk_repo import ChunkRepo
from app.repositories.design_repo import DesignRepo
from app.repositories.image_repo import ImageRepo
from app.repositories.post_repo import PostRepo
from app.repositories.story_repo import StoryRepo
from app.retriever import retrieve
from app.social import post_to_social
from app.vector_store import store
from app.zernio import upload_image


class Repos:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.category = CategoryRepo(session)
        self.design = DesignRepo(session)
        self.story = StoryRepo(session)
        self.image = ImageRepo(session)
        self.chunk = ChunkRepo(session)
        self.post = PostRepo(session)


async def get_repos(session: AsyncSession = Depends(get_db)) -> "Repos":
    return Repos(session)


async def _seed_default_categories():
    seeds = [("News", "authoritative"), ("Events", "celebratory"), ("Hiring", "opportunity-driven")]
    async with async_session() as session:
        repo = CategoryRepo(session)
        if await repo.list():
            return
        for name, template in seeds:
            try:
                await repo.create(name, template)
            except ValueError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # additive schema migrations for tables that predate new columns
    from sqlalchemy import text as _sql_text
    from app.database import engine as _engine
    async with _engine.begin() as conn:
        for ddl in (
            "ALTER TABLE bank_posts ADD COLUMN canva_design_id VARCHAR",
            "ALTER TABLE bank_posts ADD COLUMN canva_edit_url VARCHAR",
        ):
            try:
                await conn.execute(_sql_text(ddl))
            except Exception:
                pass  # column already exists
    await _seed_default_categories()
    # vectors.npy + metadata.json are written together and stay row-aligned;
    # the DB chunk table is the fallback source for chunk metadata.
    if not store.load():
        async with async_session() as session:
            meta = await ChunkRepo(session).get_all_metadata()
        store.load_from_metadata(meta)
    yield


app = FastAPI(title="NICDC Social Studio", lifespan=lifespan)


# ── Request models ────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class QueryRequest(BaseModel):
    query: str
    k: int = 5


class GenerateRequest(BaseModel):
    topic: str
    k: int = 5


class LayoutRequest(BaseModel):
    topic: str
    text: str
    category: str = "News"
    images: list[str] = []


class EnhanceLayoutRequest(BaseModel):
    design_state: dict
    brand: dict
    content: dict = {}


class DesignStatusUpdate(BaseModel):
    status: str
    reviewer_note: str = ""


class ApproveRequest(BaseModel):
    caption: str = ""
    note: str = ""
    png_data_url: str = ""  # fallback for designs submitted without a stored PNG


class CaptionUpdate(BaseModel):
    caption: str


class CommentRequest(BaseModel):
    element_id: str | None = None
    element_type: str | None = None
    text: str


class ChatEditRequest(BaseModel):
    topic: str
    message: str
    design_state: dict
    history: list[dict] = []


class CategoryCreateRequest(BaseModel):
    name: str
    template: str
    layout_instructions: str = ""


class CategoryUpdateRequest(BaseModel):
    name: str | None = None
    tone: str | None = None
    layout_instructions: str | None = None


# ── Pages ─────────────────────────────────────────────

def load_page(name: str) -> str:
    with open(os.path.join(PAGES_DIR, name), encoding="utf-8") as f:
        return f.read()


def _json_for_script(value) -> str:
    return json.dumps(value).replace("</script>", "<\\/script>")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_user(request)
    if user:
        return RedirectResponse("/review" if user["role"] == "approver" else "/", status_code=302)
    return HTMLResponse(load_page("login.html"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] == "approver":
        return RedirectResponse("/review", status_code=302)
    return HTMLResponse(load_page("editor_home.html").replace("__USER_NAME__", user["display_name"]))


@app.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, topic: str = Query(""), category: str = Query("News")):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "editor":
        return RedirectResponse("/review", status_code=302)
    topic_escaped = topic.replace("\\", "\\\\").replace('"', "&quot;").replace("<", "&lt;")
    category_escaped = category.replace("\\", "\\\\").replace('"', "&quot;").replace("<", "&lt;")
    return HTMLResponse(
        load_page("editor.html")
        .replace("__TOPIC__", topic_escaped)
        .replace("__CATEGORY__", category_escaped)
        .replace("__USER_NAME__", user["display_name"])
    )


@app.get("/review", response_class=HTMLResponse)
async def review_queue_page(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "approver":
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(load_page("approver_home.html").replace("__USER_NAME__", user["display_name"]))


@app.get("/review/{design_id}", response_class=HTMLResponse)
async def review_detail_page(request: Request, design_id: str, repos: Repos = Depends(get_repos)):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "approver":
        return RedirectResponse("/", status_code=302)
    design = await repos.design.get_one_dict_with_comments(design_id)
    if not design:
        return HTMLResponse("<h3>Design not found</h3>", status_code=404)

    variants = []
    if design.get("variant_group"):
        variants = await repos.design.get_variant_group_with_comments(design["variant_group"])

    meta = {
        "topic": design["topic"],
        "category": design["category"],
        "status": design["status"],
        "revision": design.get("revision", 1),
        "caption": design.get("caption", ""),
        "reviewer_note": design.get("reviewer_note", ""),
        "feedback_history": design.get("feedback_history", []),
        "publish_results": design.get("publish_results"),
        "published_image_url": design.get("published_image_url", ""),
        "has_png": bool(design.get("design_png")),
        "variants": [
            {"id": v["id"], "variant_index": v.get("variant_index", 0), "status": v["status"]}
            for v in variants
        ],
    }
    return HTMLResponse(
        load_page("review.html")
        .replace("__DESIGN_ID__", design_id)
        .replace("__DESIGN_JSON__", _json_for_script(design["design_state"]))
        .replace("__COMMENTS_JSON__", _json_for_script(design.get("comments", [])))
        .replace("__META_JSON__", _json_for_script(meta))
        .replace("__USER_NAME__", user["display_name"])
    )


@app.get("/feedback")
async def feedback_page_redirect(design_id: str = Query("")):
    if not design_id:
        return RedirectResponse("/review", status_code=302)
    return RedirectResponse(f"/review/{design_id}", status_code=302)


@app.get("/static/app.css")
async def static_css():
    return FileResponse(
        os.path.join(PAGES_DIR, "shared.css"), media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/static/app.js")
async def static_js():
    return FileResponse(
        os.path.join(PAGES_DIR, "shared.js"), media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# ── Auth API ──────────────────────────────────────────

@app.post("/api/login")
async def api_login(req: LoginRequest):
    user = verify_login(req.username.strip(), req.password)
    if not user:
        raise HTTPException(401, detail="Invalid username or password")
    token = create_session_token(user)
    resp = JSONResponse({"status": "ok", "role": user["role"], "display_name": user["display_name"]})
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
    return resp


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/api/me")
async def api_me(user: dict = Depends(require_user)):
    record = get_user_record(user["username"]) or {}
    return {**user, "can_use_canva": record.get("can_use_canva", True)}


# ── Health / files ────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "chunks": store.size}


@app.get("/images/{filename}")
async def serve_image(filename: str):
    fpath = get_image_path(os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "Image not found")
    return FileResponse(fpath)


@app.get("/assets/{filename}")
async def serve_asset(filename: str):
    fpath = os.path.join(ASSETS_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "Asset not found")
    return FileResponse(fpath)


@app.get("/published/{filename}")
async def serve_published(filename: str):
    fpath = os.path.join(PUBLISHED_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "File not found")
    return FileResponse(fpath)


@app.get("/design-exports/{filename}")
async def serve_design_export(filename: str, user: dict = Depends(require_user)):
    fpath = os.path.join(DESIGN_EXPORTS_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "File not found")
    return FileResponse(fpath)


# ── Post templates (brand designs) ────────────────────

@app.get("/api/templates")
async def list_templates(user: dict = Depends(require_user)):
    try:
        with open(os.path.join(TEMPLATES_DIR, "templates.json"), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@app.get("/templates/{filename}")
async def serve_template_image(filename: str):
    fpath = os.path.join(TEMPLATES_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath) or not fpath.endswith(".png"):
        raise HTTPException(404, "Template image not found")
    return FileResponse(fpath)


# ── RAG utilities ─────────────────────────────────────

@app.post("/query")
async def query_endpoint(req: QueryRequest, user: dict = Depends(require_user)):
    results = await retrieve(req.query, k=req.k)
    return {"results": results}


@app.post("/generate")
async def generate_endpoint(req: GenerateRequest, user: dict = Depends(require_editor)):
    return await generate_post(req.topic, k=req.k)


# ── Stories ───────────────────────────────────────────

async def _ingest_story_data(
    repos: "Repos", topic: str, information: str, category: str,
    image_filenames: list[str], story_date: str,
):
    doc = Document(
        title=topic,
        date=story_date,
        source="user-submitted",
        prid=None,
        url=None,
        body=information,
        filepath="user-submitted",
    )
    chunks = chunk_document(doc, extra_meta={
        "type": "story",
        "topic": topic,
        "category": category,
        "images": image_filenames,
    })
    embeddings = await embed_batch([c.text for c in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
    store.add(chunks)
    store.save()

    story = await repos.story.create_story(
        topic=topic,
        title=topic,
        date=story_date,
        source="user-submitted",
        body_text=information,
        category_name=category,
        image_filenames=image_filenames,
    )
    await repos.chunk.add_chunks([
        ChunkModel(story_id=story.id, text=c.text, chunk_index=i, metadata_json=c.metadata)
        for i, c in enumerate(chunks)
    ])
    return len(chunks)


@app.post("/ingest/story")
async def ingest_story(
    topic: str = Form(...),
    information: str = Form(...),
    category: str = Form("News"),
    images: list[UploadFile] = File(default=[]),
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    if await repos.story.get_story(topic):
        raise HTTPException(400, detail="A story with this topic already exists")
    saved_filenames = await save_images(images, image_repo=repos.image)
    try:
        n_chunks = await _ingest_story_data(
            repos, topic, information, category, saved_filenames, date.today().isoformat()
        )
    except Exception:
        from app.image_store import delete_images
        delete_images(saved_filenames)
        raise
    return {
        "status": "ok",
        "chunks": n_chunks,
        "images_saved": len(saved_filenames),
        "topic": topic,
        "category": category,
    }


@app.get("/api/stories")
async def list_stories(user: dict = Depends(require_user), repos: Repos = Depends(get_repos)):
    return await repos.story.list_stories()


@app.get("/api/stories/{topic}")
async def get_story(topic: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)):
    story = await repos.story.get_story(topic)
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@app.delete("/api/stories/{topic}")
async def delete_story(topic: str, user: dict = Depends(require_editor), repos: Repos = Depends(get_repos)):
    images = await repos.story.delete_story(topic)
    from app.image_store import delete_images
    delete_images(images)
    store.delete_by_topic(topic)
    store.save()
    return {"status": "ok", "topic": topic, "images_deleted": len(images)}


@app.put("/api/stories/{topic}")
async def update_story(
    topic: str,
    new_topic: str = Form(...),
    information: str = Form(...),
    category: str = Form("News"),
    keep_images: str = Form("[]"),
    images: list[UploadFile] = File(default=[]),
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    existing = await repos.story.get_story(topic)
    if not existing:
        raise HTTPException(404, "Story not found")

    keep: list[str] = json.loads(keep_images) if keep_images else []
    to_delete = [img for img in existing["images"] if img not in keep]
    from app.image_store import delete_images
    delete_images(to_delete)

    new_filenames = await save_images(images, image_repo=repos.image)
    all_images = keep + new_filenames

    try:
        await repos.story.delete_story(topic)
        store.delete_by_topic(topic)
        n_chunks = await _ingest_story_data(
            repos, new_topic, information, category, all_images, existing["date"] or date.today().isoformat()
        )
    except Exception:
        delete_images(new_filenames)
        raise
    return {
        "status": "ok",
        "chunks": n_chunks,
        "images_saved": len(all_images),
        "topic": new_topic,
        "category": category,
    }


# ── Layout generation / AI ────────────────────────────

@app.post("/api/generate-layout")
async def generate_layout_endpoint(req: LayoutRequest, user: dict = Depends(require_editor)):
    return await generate_layout(
        topic=req.topic, text=req.text, images=req.images, category=req.category
    )


@app.post("/api/generate-layouts")
async def generate_layouts_endpoint(req: LayoutRequest, user: dict = Depends(require_editor)):
    return await generate_layout_variations(
        topic=req.topic, text=req.text, images=req.images, category=req.category
    )


@app.post("/api/enhance-layout")
async def enhance_layout_endpoint(req: EnhanceLayoutRequest, user: dict = Depends(require_editor)):
    return await enhance_layout(
        design_state=req.design_state, brand=req.brand, content=req.content
    )


@app.post("/api/chat-edit")
async def chat_edit_endpoint(req: ChatEditRequest, user: dict = Depends(require_editor)):
    return await chat_edit(
        design_state=req.design_state, message=req.message, history=req.history
    )


# ── Design workflow ───────────────────────────────────

def _rel_path(path: str) -> str:
    return path[len(BASE_DIR) + 1:] if path.startswith(BASE_DIR) else path


async def _save_design_png(design_png: UploadFile, design_id: str) -> str:
    os.makedirs(DESIGN_EXPORTS_DIR, exist_ok=True)
    abs_png = os.path.join(DESIGN_EXPORTS_DIR, design_id + ".png")
    contents = await design_png.read()
    with open(abs_png, "wb") as f:
        f.write(contents)
    return _rel_path(abs_png)


@app.post("/api/designs/submit")
async def submit_design(
    topic: str = Form(...),
    category: str = Form(""),
    design_state: str = Form(...),
    design_png: UploadFile | None = File(None),
    variant_group: str = Form(""),
    variant_index: int = Form(0),
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    state = json.loads(design_state)
    story = await repos.story.get_story(topic)
    if not story:
        raise HTTPException(404, detail="Story not found for topic: " + topic)

    has_png = bool(design_png and design_png.filename)

    if variant_group:
        existing_variants = await repos.design.get_variant_group(variant_group)
        existing_map = {v["variant_index"]: v for v in existing_variants}
        if any(v["status"] == "published" for v in existing_map.values()):
            raise HTTPException(400, detail="This design is already published and cannot be resubmitted.")
        png_path = ""
        design_id = existing_map[variant_index]["id"] if variant_index in existing_map else "design-" + uuid.uuid4().hex
        if has_png:
            png_path = await _save_design_png(design_png, design_id)
        if variant_index in existing_map:
            design = await repos.design.update_variant(variant_group, variant_index, state, png_path)
        else:
            design = await repos.design.add(
                topic=topic, category=category, story_text=story["text"],
                story_images=story["images"], design_state=state, design_png=png_path,
                variant_group=variant_group, variant_index=variant_index,
                submitted_by=user["display_name"],
            )
    else:
        existing = await repos.design.get_by_topic_dict(topic)
        if existing and existing["status"] == "published":
            raise HTTPException(400, detail="This design is already published and cannot be resubmitted.")
        png_path = ""
        design_id = existing["id"] if existing else "design-" + uuid.uuid4().hex
        if has_png:
            old_png = os.path.join(BASE_DIR, existing["design_png"]) if existing and existing.get("design_png") else ""
            if old_png and os.path.exists(old_png) and not old_png.endswith(design_id + ".png"):
                os.remove(old_png)
            png_path = await _save_design_png(design_png, design_id)
        if existing:
            design = await repos.design.update_state(
                existing["id"], state, png_path, submitted_by=user["display_name"]
            )
        else:
            design = await repos.design.add(
                topic=topic, category=category, story_text=story["text"],
                story_images=story["images"], design_state=state, design_png=png_path,
                submitted_by=user["display_name"],
            )
    return {"status": "ok", "id": design["id"]}


@app.get("/api/designs")
async def list_designs(
    status: str | None = Query(None),
    user: dict = Depends(require_user),
    repos: Repos = Depends(get_repos),
):
    return await repos.design.get_all(status)


@app.get("/api/designs/check")
async def check_designs(
    topics: str = Query(""),
    user: dict = Depends(require_user),
    repos: Repos = Depends(get_repos),
):
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    found = {}
    for t in topic_list:
        d = await repos.design.get_by_topic_dict(t)
        if d:
            found[t] = {"id": d["id"], "status": d.get("status", "pending")}
    return found


@app.get("/api/designs/variant-group/{group_id}")
async def get_variant_group(
    group_id: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)
):
    designs = await repos.design.get_variant_group_with_comments(group_id)
    if not designs:
        raise HTTPException(404, detail="No designs found for variant group")
    return sorted(designs, key=lambda d: d.get("variant_index", 0))


@app.get("/api/designs/by-topic/{topic}")
async def get_design_by_topic(
    topic: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)
):
    design = await repos.design.get_by_topic(topic)
    if not design:
        raise HTTPException(404, detail="No design found for this topic")
    result = await repos.design.get_one_dict_with_comments(design.id)
    return result


@app.get("/api/designs/{design_id}")
async def get_design(
    design_id: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)
):
    design = await repos.design.get_one_dict_with_comments(design_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    return design


@app.patch("/api/designs/{design_id}/status")
async def update_design_status(
    design_id: str,
    req: DesignStatusUpdate,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    if req.status not in ("pending", "rejected", "feedback"):
        raise HTTPException(400, detail="Invalid status. Use the approve endpoint to approve designs.")
    design = await repos.design.update_status(
        design_id, req.status, req.reviewer_note, reviewed_by=user["display_name"]
    )
    if not design:
        raise HTTPException(404, detail="Design not found")
    return design


@app.patch("/api/designs/{design_id}/caption")
async def update_design_caption(
    design_id: str,
    req: CaptionUpdate,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    design = await repos.design.update_caption(design_id, req.caption)
    if not design:
        raise HTTPException(404, detail="Design not found")
    return design


def _derive_caption(design: dict) -> str:
    if design.get("caption"):
        return design["caption"]
    headline, body = "", ""
    for el in design.get("design_state", {}).get("elements", []):
        if el.get("type") == "text":
            el_id = el.get("id", "")
            el_text = (el.get("attrs") or {}).get("text", "")
            if "headline" in el_id and not headline:
                headline = el_text
            elif "body" in el_id and not body:
                body = el_text
    derived = (headline + "\n\n" + body).strip()
    if derived:
        return derived
    return build_caption(design["topic"], design.get("story_text", ""), 2200)


@app.post("/api/designs/{design_id}/approve")
async def approve_design(
    design_id: str,
    req: ApproveRequest,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    """Final approval: posts to the connected social accounts via Zernio;
    falls back to the mock platform APIs when real posting isn't available."""
    design = await repos.design.get_one_dict(design_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if design["status"] == "published":
        raise HTTPException(400, detail="Design is already published")

    # Resolve the final PNG: stored at submit time, or provided by the client
    os.makedirs(PUBLISHED_DIR, exist_ok=True)
    abs_png = os.path.join(PUBLISHED_DIR, design_id + ".png")
    stored = os.path.join(BASE_DIR, design["design_png"]) if design.get("design_png") else ""
    if stored and os.path.isfile(stored):
        shutil.copyfile(stored, abs_png)
    elif req.png_data_url:
        from app.publisher import save_published_png
        save_published_png(design_id, req.png_data_url)
    else:
        raise HTTPException(400, detail="No design PNG available. Re-submit the design from the editor.")

    if req.caption:
        await repos.design.update_caption(design_id, req.caption)
        design["caption"] = req.caption
    caption = _derive_caption(design)

    await repos.design.update_status(
        design_id, "approved", req.note, reviewed_by=user["display_name"]
    )

    # 1) Real posting via Zernio — only when explicitly enabled (SOCIAL_MODE=real)
    from app.config import SOCIAL_MODE
    mode = "real" if SOCIAL_MODE == "real" else "mock"
    image_url = ""
    real_err = None
    if mode == "real":
        try:
            results = await post_to_social(abs_png, caption)
            image_url = results.get("image_url", "")
            all_ok = True
        except Exception as e:
            real_err = e
            mode = "mock"
    if mode == "mock":
        # 2) Mock platform APIs + Zernio-hosted image
        results, image_url = await publish_design_mock(design, design_id + ".png")
        if real_err is not None:
            results["note"] = f"Real posting unavailable ({real_err}); published to mock platforms."
        elif SOCIAL_MODE != "real":
            results["note"] = "SOCIAL_MODE=mock — published to mock platforms only."
        all_ok = all(
            r.get("status") == "published"
            for k, r in results.items() if isinstance(r, dict) and "status" in r
        )

    results["mode"] = mode
    design = await repos.design.set_published(design_id, results, image_url=image_url, all_ok=all_ok)

    # Sibling variants are superseded by the approved one
    if design.get("variant_group"):
        for v in await repos.design.get_variant_group(design["variant_group"]):
            if v["id"] != design_id and v["status"] not in ("published", "rejected"):
                await repos.design.update_status(
                    v["id"], "rejected", "Another variant was approved",
                    reviewed_by=user["display_name"],
                )

    return {
        "status": design["status"],
        "publish_results": results,
        "image": image_url or f"/published/{design_id}.png",
        "caption": caption,
    }


# ── Comments ──────────────────────────────────────────

@app.post("/api/designs/{design_id}/comments")
async def add_comment(
    design_id: str,
    req: CommentRequest,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    comment = await repos.design.add_comment(
        design_id, req.element_id, req.element_type, req.text, author=user["display_name"]
    )
    if comment is None:
        raise HTTPException(404, detail="Design not found")
    return comment


@app.get("/api/designs/{design_id}/comments")
async def get_comments(
    design_id: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)
):
    result = await repos.design.get_comments(design_id)
    if result is None:
        raise HTTPException(404, detail="Design not found")
    return result


@app.delete("/api/designs/{design_id}/comments/{comment_id}")
async def delete_comment(
    design_id: str, comment_id: str,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    result = await repos.design.delete_comment(design_id, comment_id)
    if result is None:
        raise HTTPException(404, detail="Design not found")
    return {"comments": result}


# ── Categories ────────────────────────────────────────

@app.get("/api/categories")
async def api_list_categories(user: dict = Depends(require_user), repos: Repos = Depends(get_repos)):
    return await repos.category.list()


@app.get("/api/categories/templates")
async def api_category_templates(user: dict = Depends(require_user)):
    return CategoryRepo.get_templates()


@app.post("/api/categories")
async def api_create_category(
    req: CategoryCreateRequest,
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    try:
        return await repos.category.create(req.name, req.template, req.layout_instructions)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@app.put("/api/categories/{slug}")
async def api_update_category(
    slug: str,
    req: CategoryUpdateRequest,
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None and k != "name"}
    try:
        return await repos.category.update(slug, data)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@app.delete("/api/categories/{slug}")
async def api_delete_category(
    slug: str,
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    if not await repos.category.delete(slug):
        raise HTTPException(404, detail=f"Category '{slug}' not found")
    return {"status": "ok", "deleted": slug}


# ══════════════════════════════════════════════════════
#  POST BANK — upload/create designs, share, review, publish
# ══════════════════════════════════════════════════════

class ShareRequest(BaseModel):
    caption: str = ""
    platforms: list[str] = []


class CaptionGenRequest(BaseModel):
    title: str = ""
    description: str = ""
    platforms: list[str] = []
    current: str = ""


class PostCommentRequest(BaseModel):
    region: dict | None = None
    text: str


class PostApproveRequest(BaseModel):
    caption: str = ""
    note: str = ""


class HtmlPostRequest(BaseModel):
    title: str
    description: str = ""
    html_source: str = ""
    png_data_url: str


ALLOWED_POST_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


async def _save_bank_image(upload: UploadFile, post_id: str) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_POST_EXTS:
        raise HTTPException(400, detail=f"Unsupported image type '{ext}'. Allowed: png, jpg, jpeg, webp")
    os.makedirs(BANK_DIR, exist_ok=True)
    contents = await upload.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(400, detail="Image exceeds 15 MB")
    fname = post_id + ext
    with open(os.path.join(BANK_DIR, fname), "wb") as f:
        f.write(contents)
    return fname


def _save_bank_data_url(png_data_url: str, post_id: str) -> str:
    import base64
    if "," in png_data_url:
        png_data_url = png_data_url.split(",", 1)[1]
    os.makedirs(BANK_DIR, exist_ok=True)
    fname = post_id + ".png"
    with open(os.path.join(BANK_DIR, fname), "wb") as f:
        f.write(base64.b64decode(png_data_url))
    return fname


@app.get("/bank/{filename}")
async def serve_bank_image(filename: str):
    fpath = os.path.join(BANK_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "File not found")
    return FileResponse(fpath)


@app.get("/api/posts")
async def list_posts(
    status: str | None = Query(None),
    user: dict = Depends(require_user),
    repos: Repos = Depends(get_repos),
):
    posts = await repos.post.get_all(status)
    # approvers only see posts that have been shared with them
    if user["role"] == "approver":
        posts = [p for p in posts if p["status"] != "draft"]
    return posts


@app.get("/api/posts/{post_id}")
async def get_post(post_id: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)):
    post = await repos.post.get_one_dict(post_id)
    if not post:
        raise HTTPException(404, detail="Post not found")
    return post


@app.post("/api/posts/upload")
async def upload_post(
    title: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(...),
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    post_id = "post-" + uuid.uuid4().hex
    fname = await _save_bank_image(image, post_id)
    post = await repos.post.add(
        title=title, kind="upload", image_path=fname,
        description=description, created_by=user["display_name"],
    )
    return post


@app.post("/api/posts/create-html")
async def create_html_post(
    req: HtmlPostRequest,
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    post_id = "post-" + uuid.uuid4().hex
    try:
        fname = _save_bank_data_url(req.png_data_url, post_id)
    except Exception:
        raise HTTPException(400, detail="Invalid PNG data")
    post = await repos.post.add(
        title=req.title, kind="html", image_path=fname,
        description=req.description, html_source=req.html_source,
        created_by=user["display_name"],
    )
    return post


@app.put("/api/posts/{post_id}")
async def update_post(
    post_id: str,
    title: str = Form(""),
    description: str = Form(""),
    html_source: str = Form(""),
    png_data_url: str = Form(""),
    image: UploadFile | None = File(None),
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    existing = await repos.post.get_one_dict(post_id)
    if not existing:
        raise HTTPException(404, detail="Post not found")
    if existing["status"] == "published":
        raise HTTPException(400, detail="Published posts cannot be edited")
    image_path = ""
    if image and image.filename:
        old = os.path.join(BANK_DIR, existing["image_path"])
        image_path = await _save_bank_image(image, post_id)
        if os.path.isfile(old) and os.path.basename(old) != image_path:
            os.remove(old)
    elif png_data_url:
        image_path = _save_bank_data_url(png_data_url, post_id)
    post = await repos.post.update_content(
        post_id, title=title, description=description if description else None,
        image_path=image_path, html_source=html_source if html_source else None,
    )
    return post


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: str, user: dict = Depends(require_editor), repos: Repos = Depends(get_repos)):
    existing = await repos.post.get_one_dict(post_id)
    if not existing:
        raise HTTPException(404, detail="Post not found")
    if existing["status"] not in ("draft", "rejected"):
        raise HTTPException(400, detail="Only drafts can be deleted")
    image_path = await repos.post.delete(post_id)
    if image_path:
        fpath = os.path.join(BANK_DIR, image_path)
        if os.path.isfile(fpath):
            os.remove(fpath)
    return {"status": "ok"}


@app.post("/api/generate-caption")
async def generate_caption_endpoint(req: CaptionGenRequest, user: dict = Depends(require_editor)):
    from app.captioner import generate_caption
    try:
        caption = await generate_caption(req.title, req.description, req.platforms, req.current)
    except Exception as e:
        raise HTTPException(502, detail=f"Caption generation failed: {e}")
    return {"caption": caption}


@app.post("/api/posts/{post_id}/share")
async def share_post(
    post_id: str,
    req: ShareRequest,
    user: dict = Depends(require_editor),
    repos: Repos = Depends(get_repos),
):
    existing = await repos.post.get_one_dict(post_id)
    if not existing:
        raise HTTPException(404, detail="Post not found")
    if existing["status"] == "published":
        raise HTTPException(400, detail="Post is already published")
    platforms = [p for p in req.platforms if p in ("linkedin", "x", "instagram")]
    if not platforms and not existing["platforms"]:
        raise HTTPException(400, detail="Pick at least one platform")
    post = await repos.post.share(post_id, req.caption, platforms, user["display_name"])
    return post


@app.patch("/api/posts/{post_id}/status")
async def update_post_status(
    post_id: str,
    req: DesignStatusUpdate,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    if req.status not in ("pending", "rejected", "feedback"):
        raise HTTPException(400, detail="Invalid status. Use the approve endpoint to approve posts.")
    post = await repos.post.update_status(
        post_id, req.status, req.reviewer_note, reviewed_by=user["display_name"]
    )
    if not post:
        raise HTTPException(404, detail="Post not found")
    return post


@app.post("/api/posts/{post_id}/comments")
async def add_post_comment(
    post_id: str,
    req: PostCommentRequest,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    region = None
    if req.region and all(k in req.region for k in ("x", "y", "w", "h")):
        region = {k: max(0.0, min(1.0, float(req.region[k]))) for k in ("x", "y", "w", "h")}
    comment = await repos.post.add_comment(post_id, region, req.text, author=user["display_name"])
    if comment is None:
        raise HTTPException(404, detail="Post not found")
    return comment


@app.get("/api/posts/{post_id}/comments")
async def get_post_comments(post_id: str, user: dict = Depends(require_user), repos: Repos = Depends(get_repos)):
    result = await repos.post.get_comments(post_id)
    if result is None:
        raise HTTPException(404, detail="Post not found")
    return result


@app.delete("/api/posts/{post_id}/comments/{comment_id}")
async def delete_post_comment(
    post_id: str, comment_id: str,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    result = await repos.post.delete_comment(post_id, comment_id)
    if result is None:
        raise HTTPException(404, detail="Post not found")
    return {"comments": result}


@app.post("/api/posts/{post_id}/approve")
async def approve_post(
    post_id: str,
    req: PostApproveRequest,
    user: dict = Depends(require_approver),
    repos: Repos = Depends(get_repos),
):
    """Final approval of a bank post: publishes to the selected platforms."""
    post = await repos.post.get_one_dict(post_id)
    if not post:
        raise HTTPException(404, detail="Post not found")
    if post["status"] == "published":
        raise HTTPException(400, detail="Post is already published")
    if post["status"] == "draft":
        raise HTTPException(400, detail="Post has not been shared for review yet")

    src = os.path.join(BANK_DIR, post["image_path"])
    if not os.path.isfile(src):
        raise HTTPException(400, detail="Post image is missing")
    os.makedirs(PUBLISHED_DIR, exist_ok=True)
    abs_png = os.path.join(PUBLISHED_DIR, post_id + ".png")
    shutil.copyfile(src, abs_png)

    if req.caption:
        await repos.post.update_caption(post_id, req.caption)
        post["caption"] = req.caption
    caption = post.get("caption") or post["title"]
    platforms = post.get("platforms") or ["linkedin", "x", "instagram"]

    await repos.post.update_status(post_id, "approved", req.note, reviewed_by=user["display_name"])

    from app.config import SOCIAL_MODE
    mode = "real" if SOCIAL_MODE == "real" else "mock"
    image_url = ""
    real_err = None
    if mode == "real":
        try:
            results = await post_to_social(abs_png, caption, platforms)
            image_url = results.get("image_url", "")
            all_ok = True
        except Exception as e:
            real_err = e
            mode = "mock"
    if mode == "mock":
        results, image_url = await publish_design_mock(post, post_id + ".png", platforms)
        if real_err is not None:
            results["note"] = f"Real posting unavailable ({real_err}); published to mock platforms."
        elif SOCIAL_MODE != "real":
            results["note"] = "SOCIAL_MODE=mock — published to mock platforms only."
        all_ok = all(
            r.get("status") == "published"
            for k, r in results.items() if isinstance(r, dict) and "status" in r
        )

    results["mode"] = mode
    post = await repos.post.set_published(post_id, results, image_url=image_url, all_ok=all_ok)
    return {
        "status": post["status"],
        "publish_results": results,
        "image": image_url or f"/published/{post_id}.png",
        "caption": caption,
    }


# ── Post bank pages ───────────────────────────────────

@app.get("/html-editor", response_class=HTMLResponse)
async def html_editor_page(request: Request, post_id: str = Query("")):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "editor":
        return RedirectResponse("/review", status_code=302)
    return HTMLResponse(
        load_page("html_editor.html")
        .replace("__POST_ID__", post_id)
        .replace("__USER_NAME__", user["display_name"])
    )


@app.get("/post/{post_id}", response_class=HTMLResponse)
async def post_detail_page(request: Request, post_id: str, repos: Repos = Depends(get_repos)):
    """Editor's view of a bank post: feedback pins, replace image, re-share."""
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "editor":
        return RedirectResponse(f"/review-post/{post_id}", status_code=302)
    post = await repos.post.get_one_dict(post_id)
    if not post:
        return HTMLResponse("<h3>Post not found</h3>", status_code=404)
    return HTMLResponse(
        load_page("post_edit.html")
        .replace("__POST_JSON__", _json_for_script(post))
        .replace("__USER_NAME__", user["display_name"])
    )


@app.get("/review-post/{post_id}", response_class=HTMLResponse)
async def review_post_page(request: Request, post_id: str, repos: Repos = Depends(get_repos)):
    """Approver's review view: region-pinned comments on the post image."""
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "approver":
        return RedirectResponse(f"/post/{post_id}", status_code=302)
    post = await repos.post.get_one_dict(post_id)
    if not post:
        return HTMLResponse("<h3>Post not found</h3>", status_code=404)
    return HTMLResponse(
        load_page("post_review.html")
        .replace("__POST_JSON__", _json_for_script(post))
        .replace("__USER_NAME__", user["display_name"])
    )


# ══════════════════════════════════════════════════════
#  CANVA CONNECT — edit bank posts in Canva
# ══════════════════════════════════════════════════════

from app import canva as canva_api


class CanvaNewRequest(BaseModel):
    title: str
    description: str = ""


def _canva_placeholder_png(title: str) -> bytes:
    """1080x1080 'design in progress' placeholder for Canva-first drafts."""
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1080, 1080), (238, 246, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 1040, 1040], outline=(67, 118, 31), width=4)
    d.text((90, 480), "Design in progress in Canva", fill=(67, 118, 31))
    d.text((90, 540), title[:60], fill=(90, 105, 125))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@app.get("/api/canva/status")
async def canva_status(user: dict = Depends(require_canva_access)):
    return {
        "configured": canva_api.configured(),
        "connected": canva_api.configured() and canva_api.connected(user["username"]),
    }


@app.get("/canva/connect")
async def canva_connect(request: Request):
    user = get_user(request)
    if not user or user["role"] != "editor":
        return RedirectResponse("/login", status_code=302)
    if not canva_api.configured():
        return HTMLResponse(
            "<div style='font-family:sans-serif;max-width:560px;margin:80px auto;'>"
            "<h2>Canva is not configured yet</h2>"
            "<p>An administrator needs to create an integration at "
            "<a href='https://www.canva.com/developers/'>developer.canva.com</a> and set "
            "<code>CANVA_CLIENT_ID</code>, <code>CANVA_CLIENT_SECRET</code> and "
            "<code>CANVA_REDIRECT_URI</code> in the server's <code>.env</code>, then restart.</p>"
            "<a href='/'>&larr; Back</a></div>",
            status_code=200,
        )
    return RedirectResponse(canva_api.authorize_url(user["username"]), status_code=302)


@app.get("/canva/callback")
async def canva_callback(state: str = Query(""), code: str = Query(""), error: str = Query("")):
    if error:
        return HTMLResponse(
            f"<div style='font-family:sans-serif;max-width:560px;margin:80px auto;'>"
            f"<h2>Canva connection cancelled</h2><p>{error}</p><a href='/'>&larr; Back</a></div>"
        )
    try:
        await canva_api.handle_callback(state, code)
    except Exception as e:
        return HTMLResponse(
            f"<div style='font-family:sans-serif;max-width:560px;margin:80px auto;'>"
            f"<h2>Canva connection failed</h2><p>{e}</p><a href='/canva/connect'>Try again</a></div>",
            status_code=400,
        )
    return HTMLResponse(
        "<div style='font-family:sans-serif;max-width:560px;margin:80px auto;text-align:center;'>"
        "<h2>&#10003; Canva connected</h2>"
        "<p>You can now open designs in Canva from your post bank.</p>"
        "<a href='/' style='display:inline-block;margin-top:12px;padding:10px 22px;"
        "background:#43761f;color:white;border-radius:9px;text-decoration:none;'>Back to post bank</a></div>"
    )


@app.post("/api/canva/new-design")
async def canva_new_design(
    req: CanvaNewRequest,
    user: dict = Depends(require_canva_access),
    repos: Repos = Depends(get_repos),
):
    if not canva_api.configured():
        raise HTTPException(501, detail="Canva is not configured on this server")
    if not canva_api.connected(user["username"]):
        raise HTTPException(409, detail="canva_not_connected")

    post_id = "post-" + uuid.uuid4().hex
    os.makedirs(BANK_DIR, exist_ok=True)
    fname = post_id + ".png"
    with open(os.path.join(BANK_DIR, fname), "wb") as f:
        f.write(_canva_placeholder_png(req.title))
    post = await repos.post.add(
        title=req.title, kind="canva", image_path=fname,
        description=req.description, created_by=user["display_name"],
    )
    try:
        design = await canva_api.create_design(user["username"], req.title)
    except LookupError:
        raise HTTPException(409, detail="canva_not_connected")
    except Exception as e:
        raise HTTPException(502, detail=f"Canva design creation failed: {e}")
    post = await repos.post.set_canva(post["id"], design["id"], design["edit_url"])
    return {"post_id": post["id"], "edit_url": design["edit_url"]}


@app.post("/api/posts/{post_id}/canva/open")
async def canva_open_post(
    post_id: str,
    user: dict = Depends(require_canva_access),
    repos: Repos = Depends(get_repos),
):
    """Ensures the post has a linked Canva design (seeding it with the
    current image on first open) and returns the edit URL."""
    if not canva_api.configured():
        raise HTTPException(501, detail="Canva is not configured on this server")
    if not canva_api.connected(user["username"]):
        raise HTTPException(409, detail="canva_not_connected")
    post = await repos.post.get_one_dict(post_id)
    if not post:
        raise HTTPException(404, detail="Post not found")
    if post["status"] == "published":
        raise HTTPException(400, detail="Published posts cannot be edited")

    if post.get("canva_design_id") and post.get("canva_edit_url"):
        return {"edit_url": post["canva_edit_url"], "design_id": post["canva_design_id"]}

    try:
        asset_id = None
        if post["kind"] != "canva":  # seed the design with the current image
            fpath = os.path.join(BANK_DIR, post["image_path"])
            with open(fpath, "rb") as f:
                asset_id = await canva_api.upload_asset(user["username"], f.read(), post["title"])
        design = await canva_api.create_design(user["username"], post["title"], asset_id)
    except LookupError:
        raise HTTPException(409, detail="canva_not_connected")
    except Exception as e:
        raise HTTPException(502, detail=f"Canva design creation failed: {e}")
    await repos.post.set_canva(post_id, design["id"], design["edit_url"])
    return {"edit_url": design["edit_url"], "design_id": design["id"]}


@app.post("/api/posts/{post_id}/canva/pull")
async def canva_pull_post(
    post_id: str,
    user: dict = Depends(require_canva_access),
    repos: Repos = Depends(get_repos),
):
    """Exports the latest state of the linked Canva design and makes it
    the post's image."""
    if not canva_api.configured():
        raise HTTPException(501, detail="Canva is not configured on this server")
    post = await repos.post.get_one_dict(post_id)
    if not post:
        raise HTTPException(404, detail="Post not found")
    if not post.get("canva_design_id"):
        raise HTTPException(400, detail="This post has no linked Canva design")
    if post["status"] == "published":
        raise HTTPException(400, detail="Published posts cannot be changed")
    try:
        png = await canva_api.export_design_png(user["username"], post["canva_design_id"])
    except LookupError:
        raise HTTPException(409, detail="canva_not_connected")
    except Exception as e:
        raise HTTPException(502, detail=f"Canva export failed: {e}")
    os.makedirs(BANK_DIR, exist_ok=True)
    fname = post_id + ".png"
    with open(os.path.join(BANK_DIR, fname), "wb") as f:
        f.write(png)
    post = await repos.post.update_content(post_id, image_path=fname)
    return post


# ══════════════════════════════════════════════════════
#  TEAM MANAGEMENT — admins create editor/approver accounts
# ══════════════════════════════════════════════════════

class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "editor"
    can_use_canva: bool = False


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    can_use_canva: bool | None = None


@app.get("/api/users")
async def api_list_users(user: dict = Depends(require_approver)):
    return list_users()


@app.post("/api/users")
async def api_create_user(req: UserCreateRequest, user: dict = Depends(require_approver)):
    try:
        return create_user(
            req.username, req.password, req.display_name, req.role,
            req.can_use_canva, created_by=user["display_name"],
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@app.patch("/api/users/{username}")
async def api_update_user(username: str, req: UserUpdateRequest, user: dict = Depends(require_approver)):
    try:
        return update_user(
            username, display_name=req.display_name, password=req.password,
            role=req.role, can_use_canva=req.can_use_canva,
        )
    except LookupError as e:
        raise HTTPException(404, detail=str(e))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@app.delete("/api/users/{username}")
async def api_delete_user(username: str, user: dict = Depends(require_approver)):
    try:
        delete_user(username, acting_username=user["username"])
    except LookupError as e:
        raise HTTPException(404, detail=str(e))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"status": "ok", "deleted": username}
