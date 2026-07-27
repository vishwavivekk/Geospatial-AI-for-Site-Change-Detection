import json
import os
from datetime import date

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE,
    create_session_token,
    get_user,
    require_approver,
    require_editor,
    require_user,
    verify_login,
)
from app.chat_handler import chat_edit
from app.chunker import chunk_document
from app.config import PAGES_DIR, PUBLISHED_DIR
from app.design_store import design_store
from app.document_loader import Document, load_documents
from app.embedder import embed_batch
from app.generator import generate_post
from app.image_store import get_image_path, save_images
from app.layout_generator import generate_layout
from app.publisher import publish_design, save_published_png
from app.retriever import retrieve
from app.vector_store import store

app = FastAPI(title="NICDC Social Studio")


class QueryRequest(BaseModel):
    query: str
    k: int = 5


class LoginRequest(BaseModel):
    username: str
    password: str


class GenerateRequest(BaseModel):
    topic: str
    k: int = 5


class LayoutRequest(BaseModel):
    topic: str
    text: str
    category: str = "News"
    images: list[str] = []


class DesignSubmitRequest(BaseModel):
    topic: str
    category: str = "News"
    design_state: dict


class DesignStatusUpdate(BaseModel):
    status: str
    reviewer_note: str = ""


class ApproveRequest(BaseModel):
    png_data_url: str
    note: str = ""


class CommentRequest(BaseModel):
    element_id: str | None = None
    element_type: str | None = None
    text: str


class ChatEditRequest(BaseModel):
    topic: str
    message: str
    design_state: dict
    history: list[dict] = []


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
async def review_detail_page(request: Request, design_id: str):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user["role"] != "approver":
        return RedirectResponse("/", status_code=302)
    design = design_store.get_one(design_id)
    if not design:
        return HTMLResponse("<h3>Design not found</h3>", status_code=404)
    meta = {
        "topic": design["topic"],
        "category": design["category"],
        "status": design["status"],
        "revision": design.get("revision", 1),
        "reviewer_note": design.get("reviewer_note", ""),
        "feedback_history": design.get("feedback_history", []),
        "publish_results": design.get("publish_results"),
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
    # Legacy URL — the review page replaced it
    if not design_id:
        return RedirectResponse("/review", status_code=302)
    return RedirectResponse(f"/review/{design_id}", status_code=302)


@app.get("/static/app.css")
async def static_css():
    return FileResponse(os.path.join(PAGES_DIR, "shared.css"), media_type="text/css")


@app.get("/static/app.js")
async def static_js():
    return FileResponse(os.path.join(PAGES_DIR, "shared.js"), media_type="application/javascript")


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
    return user


# ── Startup / Ingest ──────────────────────────────────

@app.on_event("startup")
async def startup():
    design_store.load()
    if store.load():
        return
    await ingest()


async def ingest():
    docs = load_documents()
    if not docs:
        return

    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))

    texts = [c.text for c in all_chunks]
    embeddings = await embed_batch(texts)

    for chunk, emb in zip(all_chunks, embeddings):
        chunk.embedding = emb

    store.add(all_chunks)
    store.save()


# ── Health / Ingestion API ────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "chunks": store.size}


@app.post("/ingest")
async def ingest_endpoint(user: dict = Depends(require_editor)):
    store.clear()
    await ingest()
    return {"status": "ok", "chunks": store.size}


@app.post("/ingest/story")
async def ingest_story(
    topic: str = Form(...),
    information: str = Form(...),
    category: str = Form("News"),
    images: list[UploadFile] = File(default=[]),
    user: dict = Depends(require_editor),
):
    saved_filenames = await save_images(images)

    try:
        doc = Document(
            title=topic,
            date=date.today().isoformat(),
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
            "images": saved_filenames,
        })
        texts = [c.text for c in chunks]
        embeddings = await embed_batch(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
        store.add(chunks)
        store.save()
    except Exception:
        from app.image_store import delete_images
        delete_images(saved_filenames)
        raise

    return {
        "status": "ok",
        "chunks": len(chunks),
        "images_saved": len(saved_filenames),
        "topic": topic,
        "category": category,
    }


@app.get("/images/{filename}")
async def serve_image(filename: str):
    fpath = get_image_path(filename)
    if not os.path.isfile(fpath):
        raise HTTPException(404, "Image not found")
    return FileResponse(fpath)


@app.get("/published/{filename}")
async def serve_published(filename: str):
    fpath = os.path.join(PUBLISHED_DIR, os.path.basename(filename))
    if not os.path.isfile(fpath):
        raise HTTPException(404, "File not found")
    return FileResponse(fpath)


@app.post("/query")
async def query_endpoint(req: QueryRequest, user: dict = Depends(require_user)):
    results = await retrieve(req.query, k=req.k)
    return {"results": results}


@app.post("/generate")
async def generate_endpoint(req: GenerateRequest, user: dict = Depends(require_editor)):
    result = await generate_post(req.topic, k=req.k)
    return result


# ── Stories ───────────────────────────────────────────

@app.get("/api/stories")
async def list_stories(user: dict = Depends(require_user)):
    return store.get_stories()


@app.delete("/api/stories/{topic}")
async def delete_story(topic: str, user: dict = Depends(require_editor)):
    images = store.delete_story(topic)
    from app.image_store import delete_images
    delete_images(images)
    store.save()
    return {"status": "ok", "topic": topic, "images_deleted": len(images)}


@app.get("/api/stories/{topic}")
async def get_story(topic: str, user: dict = Depends(require_user)):
    story = store.get_story(topic)
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@app.put("/api/stories/{topic}")
async def update_story(
    topic: str,
    new_topic: str = Form(...),
    information: str = Form(...),
    category: str = Form("News"),
    keep_images: str = Form("[]"),
    images: list[UploadFile] = File(default=[]),
    user: dict = Depends(require_editor),
):
    existing = store.get_story(topic)
    if not existing:
        raise HTTPException(404, "Story not found")

    old_images = existing["images"]
    keep: list[str] = json.loads(keep_images) if keep_images else []

    to_delete = [img for img in old_images if img not in keep]
    from app.image_store import delete_images
    delete_images(to_delete)

    new_filenames = await save_images(images)
    all_images = keep + new_filenames

    try:
        store.delete_story(topic)
        doc = Document(
            title=new_topic,
            date=existing["date"],
            source="user-submitted",
            prid=None,
            url=None,
            body=information,
            filepath="user-submitted",
        )
        chunks = chunk_document(doc, extra_meta={
            "type": "story",
            "topic": new_topic,
            "category": category,
            "images": all_images,
        })
        texts = [c.text for c in chunks]
        embeddings = await embed_batch(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
        store.add(chunks)
        store.save()
    except Exception:
        delete_images(new_filenames)
        raise

    return {
        "status": "ok",
        "chunks": len(chunks),
        "images_saved": len(all_images),
        "topic": new_topic,
        "category": category,
    }


# ── Layout Generation ────────────────────────────────

@app.post("/api/generate-layout")
async def generate_layout_endpoint(req: LayoutRequest, user: dict = Depends(require_editor)):
    layout = await generate_layout(
        topic=req.topic,
        text=req.text,
        images=req.images,
        category=req.category,
    )
    return layout


@app.post("/api/chat-edit")
async def chat_edit_endpoint(req: ChatEditRequest, user: dict = Depends(require_editor)):
    result = await chat_edit(
        design_state=req.design_state,
        message=req.message,
        history=req.history,
    )
    return result


# ── Design Approval Workflow ──────────────────────────

@app.post("/api/designs/submit")
async def submit_design(req: DesignSubmitRequest, user: dict = Depends(require_editor)):
    story = store.get_story(req.topic)
    if not story:
        raise HTTPException(404, detail="Story not found for topic: " + req.topic)
    existing = design_store.get_by_topic(req.topic)
    if existing:
        if existing["status"] == "published":
            raise HTTPException(400, detail="This design is already published and cannot be resubmitted.")
        design = design_store.update_state(existing["id"], req.design_state, submitted_by=user["display_name"])
    else:
        design = design_store.add(
            topic=req.topic,
            category=req.category,
            story_text=story["text"],
            story_images=story["images"],
            design_state=req.design_state,
            submitted_by=user["display_name"],
        )
    return {"status": "ok", "id": design["id"]}


@app.get("/api/designs")
async def list_designs(status: str | None = Query(None), user: dict = Depends(require_user)):
    return design_store.get_all(status)


@app.get("/api/designs/check")
async def check_designs(topics: str = Query(""), user: dict = Depends(require_user)):
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    found = {}
    for t in topic_list:
        d = design_store.get_by_topic(t)
        if d:
            found[t] = {"id": d["id"], "status": d.get("status", "pending")}
    return found


@app.get("/api/designs/by-topic/{topic}")
async def get_design_by_topic(topic: str, user: dict = Depends(require_user)):
    design = design_store.get_by_topic(topic)
    if not design:
        raise HTTPException(404, detail="No design found for this topic")
    return design


@app.get("/api/designs/{design_id}")
async def get_design(design_id: str, user: dict = Depends(require_user)):
    design = design_store.get_one(design_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    return design


@app.patch("/api/designs/{design_id}/status")
async def update_design_status(design_id: str, req: DesignStatusUpdate, user: dict = Depends(require_approver)):
    if req.status not in ("pending", "rejected", "feedback"):
        raise HTTPException(400, detail="Invalid status. Use the approve endpoint to approve designs.")
    design = design_store.update_status(design_id, req.status, req.reviewer_note, reviewed_by=user["display_name"])
    if not design:
        raise HTTPException(404, detail="Design not found")
    return design


@app.post("/api/designs/{design_id}/approve")
async def approve_design(design_id: str, req: ApproveRequest, user: dict = Depends(require_approver)):
    """Final approval: saves the rendered PNG, then auto-publishes the
    post to Instagram, X and LinkedIn."""
    design = design_store.get_one(design_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if design["status"] == "published":
        raise HTTPException(400, detail="Design is already published")

    try:
        png_filename = save_published_png(design_id, req.png_data_url)
    except Exception:
        raise HTTPException(400, detail="Invalid PNG data")

    design = design_store.update_status(design_id, "approved", req.note, reviewed_by=user["display_name"])
    publish_results = await publish_design(design, png_filename)
    design = design_store.set_published(design_id, publish_results)

    return {
        "status": design["status"],
        "publish_results": publish_results,
        "image": f"/published/{png_filename}",
    }


# ── Comments (approver feedback) ──────────────────────

@app.post("/api/designs/{design_id}/comments")
async def add_comment(design_id: str, req: CommentRequest, user: dict = Depends(require_approver)):
    comment = design_store.add_comment(
        design_id, req.element_id, req.element_type, req.text, author=user["display_name"]
    )
    if comment is None:
        raise HTTPException(404, detail="Design not found")
    return comment


@app.get("/api/designs/{design_id}/comments")
async def get_comments(design_id: str, user: dict = Depends(require_user)):
    result = design_store.get_comments(design_id)
    if result is None:
        raise HTTPException(404, detail="Design not found")
    return result


@app.delete("/api/designs/{design_id}/comments/{comment_id}")
async def delete_comment(design_id: str, comment_id: str, user: dict = Depends(require_approver)):
    result = design_store.delete_comment(design_id, comment_id)
    if result is None:
        raise HTTPException(404, detail="Design not found")
    return {"comments": result}
