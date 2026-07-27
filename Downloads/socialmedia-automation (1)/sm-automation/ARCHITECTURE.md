# SM-Automation: Architectural Deep Dive & User Flow Guide

> **System:** Social Media Post Automation Platform for NICDC  
> **Version:** 1.0  
> **Last Updated:** 2026-07-13

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Directory Structure](#4-directory-structure)
5. [Core Modules & Responsibilities](#5-core-modules--responsibilities)
6. [User Flow: End-to-End Journey](#6-user-flow-end-to-end-journey)
7. [API Reference](#7-api-reference)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Design Approval Workflow](#9-design-approval-workflow)
10. [AI Integration Architecture](#10-ai-integration-architecture)
11. [Mock Social Media APIs](#11-mock-social-media-apis)
12. [Data Persistence Strategy](#12-data-persistence-strategy)
13. [Configuration & Environment](#13-configuration--environment)

---

## 1. System Overview

SM-Automation is an intelligent social media content creation platform designed for **NICDC (National Industrial Corridor Development Corporation)**. The system automates the end-to-end workflow of converting government press releases into visually compelling social media posts for Instagram, X (Twitter), and LinkedIn.

### Key Capabilities

- **Automated Content Ingestion:** Parses PIB (Press Information Bureau) press releases from structured markdown files
- **RAG-Powered Content Generation:** Uses retrieval-augmented generation to create contextually relevant posts
- **AI Layout Generation:** Creates 1080×1080 pixel social media post designs using brand guidelines
- **Visual Canvas Editor:** Full-featured Konva.js editor with drag-and-drop, layers, properties, and undo/redo
- **Conversational AI Editing:** Natural language chat interface to iteratively refine designs
- **Approval Workflow:** Complete review cycle with element-level commenting and feedback loops
- **Multi-Platform Publishing:** Mock APIs simulating Instagram, X, and LinkedIn publishing flows

### Core Value Proposition

The system eliminates the manual bottleneck of turning government news into social media content by providing an AI-assisted pipeline that:
1. Ingests and indexes press releases
2. Generates structured social media posts
3. Creates visual layouts following brand guidelines
4. Enables iterative refinement through conversation
5. Manages the approval lifecycle

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend Framework** | FastAPI (Python 3.14) | API endpoints, HTML serving, async operations |
| **ASGI Server** | Uvicorn | Development server with hot-reload |
| **Local LLM** | llama.cpp + Gemma 4 (GGUF) | Embeddings generation, simple post text generation |
| **Cloud LLM** | OpenCode API (`big-pickle` model) | Layout generation, conversational AI editing |
| **Frontend Canvas** | Konva.js 9 | 2D canvas rendering, element manipulation |
| **Vector Store** | NumPy (custom) | In-memory cosine similarity search |
| **Image Processing** | Pillow (PIL) | Image dimension extraction, format validation |
| **HTTP Client** | httpx (async) | LLM API communication |
| **Persistence** | JSON files + NumPy arrays | Metadata, designs, embeddings |
| **Environment** | python-dotenv | API key management |

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │   Stories     │  │  Konva.js Editor │  │    Feedback Review Page      │  │
│  │   Dashboard   │  │  (1080×1080)     │  │    (Read-only + Comments)    │  │
│  └──────┬───────┘  └────────┬─────────┘  └──────────────┬───────────────┘  │
│         │                   │                            │                  │
│         └───────────────────┼────────────────────────────┘                  │
│                             │                                               │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │ HTTP Requests
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI BACKEND (port 8000)                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         API ROUTES (25+ endpoints)                     ││
│  │  • /ingest/*  • /api/stories/*  • /api/generate-layout                ││
│  │  • /api/chat-edit  • /api/designs/*  • /api/designs/*/comments        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │  Document   │  │  Chunker    │  │  Embedder   │  │  Vector Store   │   │
│  │  Loader     │  │  (500 char) │  │  (llama.cpp)│  │  (NumPy)        │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │  Layout     │  │  Chat       │  │  Design     │  │  Image Store    │   │
│  │  Generator  │  │  Handler    │  │  Store      │  │  (UUID files)   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐                                          │
│  │  Retriever  │  │  Generator  │                                          │
│  │  (RAG)      │  │  (llama.cpp)│                                          │
│  └─────────────┘  └─────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   llama.cpp     │ │  OpenCode API   │ │  File System    │
│   (port 8080)   │ │  (cloud LLM)    │ │  (images, JSON) │
│   Gemma 4 model │ │  big-pickle     │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 4. Directory Structure

```
sm-automation/
│
├── run.py                          # Entry point: starts Uvicorn on 0.0.0.0:8000
├── .env                            # Gemini API key (currently unused by main flow)
├── requirements.txt                # Python dependencies (6 packages)
├── metadata.json                   # Persisted chunk metadata (RAG index)
├── vectors.npy                     # Persisted embedding vectors (NumPy binary)
├── server.log                      # Uvicorn startup logs
├── editor-plan.md                  # Konva.js editor design document
├── ingestion-architecture.md       # Ingestion pipeline architecture doc
├── nicdc-content.md                # Index of 10 NICDC news articles
│
├── app/                            # Main application package
│   ├── __init__.py                 # Package marker
│   ├── config.py                   # Central configuration (paths, constants)
│   ├── main.py                     # FastAPI app + all routes + embedded HTML (3183 lines)
│   ├── document_loader.py          # Markdown file parser (67 lines)
│   ├── chunker.py                  # Text chunking for embeddings (41 lines)
│   ├── embedder.py                 # llama.cpp embedding client (20 lines)
│   ├── vector_store.py             # NumPy-based vector store (158 lines)
│   ├── retriever.py                # RAG retrieval logic (16 lines)
│   ├── generator.py                # Post text generation via llama.cpp (80 lines)
│   ├── image_store.py              # Image upload/delete/serve (58 lines)
│   ├── cloud_llm.py                # OpenCode cloud LLM client (46 lines)
│   ├── layout_generator.py         # AI layout generation (211 lines)
│   ├── chat_handler.py             # Conversational AI editing (123 lines)
│   ├── design_store.py             # Design approval workflow persistence (130 lines)
│   └── templates/
│       └── system_prompt.txt       # System prompt for post generation
│
├── data/                           # Runtime data storage
│   ├── brands/                     # Brand guideline JSON files
│   │   ├── news.json               # News: navy/blue palette, Georgia font
│   │   ├── hiring.json             # Hiring: teal/green palette
│   │   └── events.json             # Events: navy/gold palette
│   ├── designs.json                # Persisted design submissions
│   └── images/                     # Uploaded story images (UUID filenames)
│       ├── *.jpg
│       ├── *.png
│       └── *.jpeg
│
├── nicdc-content/                  # Press release source documents (10 files)
│   ├── 01-2026-07-03-board-of-trade-meeting.md
│   ├── 02-2026-06-08-bhavya-portal-launch.md
│   ├── 03-2026-05-29-bhavya-workshop-nth-bis.md
│   ├── 04-2026-05-23-dpiit-bhavya-guidelines.md
│   ├── 05-2026-03-18-cabinet-approves-bhavya.md
│   ├── 06-2026-03-18-stakeholder-consultation.md
│   ├── 07-2026-02-01-east-coast-industrial-corridor-budget.md
│   ├── 08-2026-02-01-budget-revival-legacy-clusters.md
│   ├── 09-2025-10-16-pm-modi-kurnool.md
│   └── 10-2025-09-20-iprs-3.0-launch.md
│
├── mock-apis/                      # Mock social media API server
│   ├── main.py                     # FastAPI mock server (1026 lines)
│   └── requirements.txt            # Mock server dependencies
│
├── models/                         # Local LLM model files
│   └── gemma-4-E2B-it-Q4_K_M.gguf # Quantized Gemma 4 model (GGUF)
│
├── llama-server                    # Pre-compiled llama.cpp server binary
├── llama.cpp/                      # Full llama.cpp source repository
│
└── venv/                           # Python 3.14 virtual environment
```

---

## 5. Core Modules & Responsibilities

### 5.1 Document Loader (`app/document_loader.py`)

**Purpose:** Parses structured markdown files from `nicdc-content/` into `Document` objects.

**Parsing Logic:**
1. Reads each `.md` file from the content directory
2. Extracts the title from the `# heading` line
3. Parses metadata from bold-prefixed lines (`**Date:**`, `**Source:**`, `**PRID:**`, `**URL:**`)
4. Splits body text after the `---` separator
5. Returns a list of `Document` dataclass instances

**Output Structure:**
```python
@dataclass
class Document:
    title: str
    date: str
    source: str
    prid: str
    url: str
    body: str
    file_path: str
```

---

### 5.2 Chunker (`app/chunker.py`)

**Purpose:** Splits documents into fixed-size text chunks for embedding and retrieval.

**Algorithm:**
- Splits by paragraphs (double newline)
- Accumulates text up to `CHUNK_SIZE` (500 characters)
- Supports `CHUNK_OVERLAP` (50 characters) for context continuity
- Attaches metadata from the source document
- Supports `extra_meta` for user-submitted stories (sets `type: "story"` vs `type: "document"`)

**Output Structure:**
```python
@dataclass
class Chunk:
    text: str
    metadata: dict   # title, date, source, type, etc.
    embedding: Optional[np.ndarray] = None
```

---

### 5.3 Embedder (`app/embedder.py`)

**Purpose:** Generates text embeddings via llama.cpp's `/v1/embeddings` endpoint.

**Key Functions:**
- `embed_text(text: str) -> List[float]`: Embeds a single text string
- `embed_batch(texts: List[str]) -> List[List[float]]`: Embeds multiple texts sequentially

**Endpoint:** `POST {LLAMA_CPP_BASE_URL}/v1/embeddings` (default: `http://localhost:8080`)

---

### 5.4 Vector Store (`app/vector_store.py`)

**Purpose:** In-memory vector store with cosine similarity search.

**Core Operations:**
- **Add:** Appends chunks and stacks embedding vectors into a NumPy array
- **Search:** Normalizes vectors, computes cosine similarity via matrix multiplication, returns top-k results
- **Save/Load:** Persists to `vectors.npy` (embeddings) + `metadata.json` (chunk metadata)
- **Story Management:** Groups/queries/deletes story chunks by topic

**Search Algorithm:**
```python
# Normalize query and stored vectors
query_norm = query / np.linalg.norm(query)
matrix_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

# Cosine similarity via dot product
similarities = matrix_norm @ query_norm

# Return top-k indices
top_indices = np.argsort(similarities)[-top_k:][::-1]
```

**Singleton Instance:** A single `store` instance is shared across the application (line 158).

---

### 5.5 Retriever (`app/retriever.py`)

**Purpose:** RAG retrieval layer that combines embedding + vector search.

**Flow:**
1. Embeds the user query via `embedder.embed_text()`
2. Searches the vector store via `store.search()`
3. Returns chunks with similarity scores

---

### 5.6 Generator (`app/generator.py`)

**Purpose:** LLM-powered social media post generation via llama.cpp.

**Generation Flow:**
1. Retrieves relevant chunks via RAG
2. Formats context with titles and dates
3. Loads system prompt from `app/templates/system_prompt.txt`
4. Calls llama.cpp `/v1/chat/completions` with Gemma model
5. Parses JSON response into structured output

**Output Structure:**
```python
{
    "headline": "...",
    "body": "...",
    "hashtags": ["#NICDC", "#IndustrialDevelopment", ...]
}
```

---

### 5.7 Layout Generator (`app/layout_generator.py`)

**Purpose:** AI-powered visual layout generation for 1080×1080 Instagram posts.

**Generation Flow:**
1. **Load Brand Guidelines:** Reads category-specific JSON from `data/brands/{category}.json`
2. **Extract Image Info:** Uses Pillow to get image dimensions for accurate placement
3. **Build Prompt:** Combines topic, text content, image dimensions, and brand rules
4. **Call Cloud LLM:** Sends to OpenCode API (`big-pickle` model)
5. **Parse Response:** Extracts JSON layout from LLM output
6. **Normalize:** Standardizes element types (e.g., `"heading"` → `"text"`)
7. **Auto-Place Images:** Ensures all uploaded images appear in the layout

**Brand Guidelines Structure:**
```json
{
    "primary_color": "#002147",
    "secondary_color": "#1565C0",
    "accent_color": "#FFD700",
    "text_color": "#FFFFFF",
    "heading_font": "Georgia",
    "body_font": "Arial",
    "tone": "authoritative",
    "logo_position": "top-right"
}
```

**Available Categories:**
| Category | Palette | Tone |
|----------|---------|------|
| News | Navy/Blue/Gold | Authoritative |
| Hiring | Teal/Green | Opportunity-driven |
| Events | Navy/Gold | Celebratory |

---

### 5.8 Chat Handler (`app/chat_handler.py`)

**Purpose:** Conversational AI design editing interface.

**Interaction Pattern:**
1. User describes desired changes in natural language
2. System constructs message array with:
   - System prompt (NICDC designer persona)
   - Current design JSON (full layout state)
   - Conversation history (last 10 turns)
   - User's new message
3. Cloud LLM generates response with optional design update
4. Response is parsed: text explanation + `---DESIGN---` marker + updated JSON
5. Frontend applies the new design state to the canvas

**Response Format:**
```
Here's the updated design with your requested changes...

---DESIGN---
{
    "width": 1080,
    "height": 1080,
    "elements": [...]
}
```

---

### 5.9 Design Store (`app/design_store.py`)

**Purpose:** Manages the design approval workflow lifecycle.

**State Machine:**
```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  approved   │  │  rejected   │  │  feedback   │
   └─────────────┘  └─────────────┘  └─────────────┘
```

**Operations:**
- `add()`: Creates new design with `pending` status, UUID, timestamps
- `get_all()`: Lists all designs (filterable by status)
- `get_one()`: Retrieves by design ID
- `get_by_topic()`: Retrieves by story topic
- `update_state()`: Replaces design layout, resets to `pending`
- `update_status()`: Transitions approval status
- `add_comment()`: Attaches element-level or general comments
- `get_comments()`: Retrieves comments for a design
- `delete_comment()`: Removes a specific comment

**Design Document Structure:**
```json
{
    "design_id": "uuid",
    "topic": "Board of Trade Meeting",
    "category": "news",
    "state": { "width": 1080, "height": 1080, "elements": [...] },
    "status": "pending",
    "created_at": "2026-07-13T10:00:00",
    "updated_at": "2026-07-13T10:00:00",
    "comments": []
}
```

---

### 5.10 Image Store (`app/image_store.py`)

**Purpose:** Handles image file upload, validation, and storage.

**Validation Rules:**
- Allowed extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`
- Maximum size: 10 MB per image
- UUID-based filenames to prevent collisions

**Operations:**
- `save_images(files, extra_meta)`: Validates + saves to `data/images/`
- `delete_images(filenames)`: Removes images from disk
- `get_image_path(filename)`: Returns full filesystem path for serving

---

## 6. User Flow: End-to-End Journey

### 6.1 Complete User Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY MAP                                    │
│                                                                             │
│  1. CONTENT INGESTION                                                       │
│     ┌──────────────┐                                                        │
│     │ Startup or   │──► load_documents() ──► chunk_document()              │
│     │ Manual Ingest│──► embed_batch() ──► store.add() ──► store.save()     │
│     └──────────────┘                                                        │
│                              │                                              │
│                              ▼                                              │
│  2. CONTENT DISCOVERY                                                       │
│     ┌──────────────┐                                                        │
│     │ Stories      │──► Browse categories (News/Hiring/Events)             │
│     │ Dashboard    │──► View story text + images                           │
│     │ (/)          │──► Choose action: Generate / Edit / Delete            │
│     └──────────────┘                                                        │
│                              │                                              │
│              ┌───────────────┴───────────────┐                             │
│              ▼                               ▼                              │
│  3a. POST GENERATION          3b. CUSTOM STORY INGESTION                   │
│     ┌──────────────┐            ┌──────────────┐                           │
│     │ Click        │            │ Add Story    │──► save_images()          │
│     │ "Generate"   │            │ Modal        │──► chunk_document()       │
│     │              │            │              │──► embed_batch()          │
│     │ POST         │            │ POST         │──► store.add()            │
│     │ /api/generate│            │ /ingest/story│                           │
│     │              │            └──────────────┘                           │
│     │ Returns:     │                                                       │
│     │ headline     │                                                       │
│     │ body         │                                                       │
│     │ hashtags     │                                                       │
│     └──────────────┘                                                        │
│              │                                                              │
│              ▼                                                              │
│  4. VISUAL DESIGN                                                           │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │                     KONVA.JS EDITOR (/create)                    │   │
│     │                                                                  │   │
│     │  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐    │   │
│     │  │  Toolbar    │  │  Canvas          │  │  Sidebar        │    │   │
│     │  │  • Generate │  │  (1080×1080)     │  │  • Properties   │    │   │
│     │  │  • Export   │  │  • Drag elements │  │  • Layers       │    │   │
│     │  │  • Undo/Redo│  │  • Resize        │  │  • Chat (AI)    │    │   │
│     │  │  • Delete   │  │  • Rotate        │  │  • Feedback     │    │   │
│     │  │  • Add Elem │  │  • Select        │  │                 │    │   │
│     │  └─────────────┘  └──────────────────┘  └─────────────────┘    │   │
│     │                                                                  │   │
│     │  ┌──────────────────────────────────────────────────────────┐   │   │
│     │  │  CONVERSATIONAL AI EDITING (Chat Panel)                  │   │   │
│     │  │                                                          │   │   │
│     │  │  User: "Make the headline bigger and blue"              │   │   │
│     │  │  AI: "I've updated the headline to 72px in blue..."    │   │   │
│     │  │       [Updated layout applied to canvas]                │   │   │
│     │  └──────────────────────────────────────────────────────────┘   │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│              │                                                              │
│              ▼                                                              │
│  5. SUBMISSION & APPROVAL                                                   │
│     ┌──────────────┐                                                        │
│     │ Click        │──► POST /api/designs/submit                          │
│     │ "Send for    │──► design_store.add() [status: "pending"]            │
│     │  Approval"   │                                                       │
│     └──────────────┘                                                        │
│              │                                                              │
│              ▼                                                              │
│  6. ADMIN REVIEW                                                            │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │                     ADMIN PANEL (Admin tab)                      │   │
│     │                                                                  │   │
│     │  ┌─────────────┐  ┌──────────────────┐                          │   │
│     │  │  Design     │  │  Preview Canvas   │                          │   │
│     │  │  List       │  │  (Mini Konva.js)  │                          │   │
│     │  │  • Filter   │  │                   │                          │   │
│     │  │  • Status   │  │  Actions:         │                          │   │
│     │  │             │  │  • Approve        │                          │   │
│     │  │             │  │  • Feedback       │                          │   │
│     │  └─────────────┘  └──────────────────┘                          │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│              │                                                              │
│     ┌────────┴────────┐                                                    │
│     ▼                 ▼                                                     │
│  7a. APPROVED       7b. FEEDBACK                                           │
│     ┌──────────────┐  ┌──────────────────────────────────────────────┐    │
│     │ Status →     │  │  FEEDBACK PAGE (/feedback)                   │    │
│     │ "approved"   │  │                                              │    │
│     │              │  │  • Read-only canvas rendering                │    │
│     │ Ready for    │  │  • Click elements to attach comments         │    │
│     │ publishing   │  │  • Add general or element-specific comments  │    │
│     │              │  │  • "Submit Feedback" → status: "feedback"    │    │
│     └──────────────┘  │                                              │    │
│                        │  ┌─────────────────────────────────────┐    │    │
│                        │  │  Back in Editor:                     │    │    │
│                        │  │  • Feedback tab shows comments       │    │    │
│                        │  │  • "Send to Agent" sends comment     │    │    │
│                        │  │    text to AI for automated changes  │    │    │
│                        │  └─────────────────────────────────────┘    │    │
│                        └──────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  8. ITERATION LOOP                                                          │
│     ┌──────────────────────────────────────────────────────────────────┐   │
│     │  Designer refines based on feedback                              │   │
│     │  → Resubmits → Admin re-reviews → Cycle repeats                 │   │
│     └──────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  9. PUBLISHING (Future)                                                     │
│     ┌──────────────┐                                                        │
│     │ Export PNG    │──► Local download                                    │
│     │ Publish to   │──► Mock APIs (Instagram/X/LinkedIn)                  │
│     │ Social Media │                                                       │
│     └──────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Detailed Flow: Story Ingestion

**Trigger:** Application startup or manual re-ingestion

**Steps:**

1. **Load Documents** (`document_loader.load_documents`)
   - Scans `nicdc-content/` for `.md` files
   - Parses title, metadata, and body from each file
   - Returns list of `Document` objects

2. **Chunk Documents** (`chunker.chunk_document`)
   - Splits each document into ~500-character chunks
   - Preserves metadata (title, date, source)
   - Attaches chunk type (`"document"` for PIB content)

3. **Generate Embeddings** (`embedder.embed_batch`)
   - Sends each chunk text to llama.cpp `/v1/embeddings`
   - Receives float32 embedding vectors
   - Attaches embeddings to chunk objects

4. **Store Vectors** (`vector_store.store.add`)
   - Appends chunks to metadata list
   - Stacks embedding vectors into NumPy array
   - Saves to `vectors.npy` + `metadata.json`

**Persistence:** Cached on disk. Subsequent startups skip ingestion if files exist.

---

### 6.3 Detailed Flow: Post Generation

**Trigger:** User clicks "Generate Post" on a story

**Steps:**

1. **Retrieve Context** (`retriever.retrieve`)
   - Embeds the story topic/query
   - Searches vector store for top-5 similar chunks
   - Returns chunks with similarity scores

2. **Format Context**
   - Extracts text, titles, and dates from retrieved chunks
   - Formats as structured context string

3. **Load Prompt Template**
   - Reads system prompt from `app/templates/system_prompt.txt`
   - Instructs model to generate JSON with `headline`, `body`, `hashtags`

4. **Generate via LLM** (`generator.generate_post`)
   - Calls llama.cpp `/v1/chat/completions` with Gemma model
   - Temperature: 0.7 (configurable)
   - Max tokens: 1024

5. **Parse Response**
   - Extracts JSON from LLM output (handles markdown code blocks)
   - Returns structured post data

**Output Example:**
```json
{
    "headline": "NICDC Board of Trade Meeting Reviews Export Targets",
    "body": "The National Industrial Corridor Development Corporation convened...",
    "hashtags": ["#NICDC", "#Trade", "#Exports", "#India"]
}
```

---

### 6.4 Detailed Flow: Layout Generation

**Trigger:** User clicks "Generate" in the Konva.js editor

**Steps:**

1. **Fetch Story Data** (`GET /api/stories/{topic}`)
   - Retrieves story text, images, and metadata

2. **Load Brand Guidelines** (`layout_generator.load_brand`)
   - Reads `data/brands/{category}.json`
   - Extracts colors, fonts, tone, logo position

3. **Extract Image Info** (`layout_generator._get_image_info`)
   - Uses Pillow to read image dimensions
   - Formats as descriptive text for LLM prompt

4. **Build Prompt**
   - Combines: topic + story text + image dimensions + brand rules
   - Includes detailed layout JSON schema in system prompt

5. **Call Cloud LLM** (`cloud_llm.generate`)
   - Sends to OpenCode API (`big-pickle` model)
   - Timeout: 180 seconds
   - Returns JSON layout specification

6. **Post-Process**
   - Normalize element types (e.g., `"heading"` → `"text"`)
   - Auto-place any missing images via `_auto_place_images()`
   - Return final layout state

**Layout JSON Schema:**
```json
{
    "width": 1080,
    "height": 1080,
    "background": "#002147",
    "elements": [
        {
            "type": "text",
            "id": "elem-uuid",
            "x": 50,
            "y": 50,
            "width": 980,
            "height": 100,
            "text": "NICDC Board of Trade Meeting",
            "fontSize": 48,
            "fontFamily": "Georgia",
            "fill": "#FFFFFF",
            "align": "center"
        },
        {
            "type": "image",
            "id": "elem-uuid",
            "x": 50,
            "y": 200,
            "width": 980,
            "height": 600,
            "src": "data/images/uuid.jpg"
        },
        {
            "type": "rect",
            "id": "elem-uuid",
            "x": 0,
            "y": 980,
            "width": 1080,
            "height": 100,
            "fill": "#FFD700"
        }
    ]
}
```

---

### 6.5 Detailed Flow: Conversational AI Editing

**Trigger:** User types a message in the Chat panel

**Steps:**

1. **Build Message Array** (`chat_handler._build_messages`)
   - System prompt: NICDC designer persona
   - Design context: Current layout JSON (full state)
   - Conversation history: Last 10 turns (user + assistant)
   - User message: New request

2. **Call Cloud LLM** (`cloud_llm.generate`)
   - Sends messages array to OpenCode API
   - Model: `big-pickle`
   - Timeout: 180 seconds

3. **Parse Response** (`chat_handler._parse_response`)
   - Splits on `---DESIGN---` marker
   - Left side: Text explanation
   - Right side: Updated JSON layout

4. **Apply to Canvas**
   - Frontend receives `{text, design}` response
   - Updates Konva.js stage with new layout state
   - User sees both the explanation and visual change

**Example Interaction:**
```
User: "Move the logo to the bottom-right and make the headline red"

AI: "I've made the following changes:
     - Moved the logo element to bottom-right (x: 880, y: 900)
     - Changed headline fill color to #FF0000

---DESIGN---
{
    "width": 1080,
    "height": 1080,
    "elements": [...updated elements...]
}"
```

---

### 6.6 Detailed Flow: Design Approval

**Trigger:** User clicks "Send for Approval"

**Steps:**

1. **Submit Design** (`POST /api/designs/submit`)
   - Frontend sends: `{topic, category, state}`
   - Backend creates design document with UUID
   - Status: `pending`
   - Timestamps: `created_at`, `updated_at`

2. **Admin Views Design** (Admin tab)
   - Lists all designs with mini Konva.js previews
   - Filters by status: All / Pending / Approved / Rejected / Feedback

3. **Admin Action: Approve**
   - `PATCH /api/designs/{id}/status` → `{status: "approved"}`
   - Design marked as ready for publishing

4. **Admin Action: Feedback**
   - Redirects to `/feedback?design_id=...`
   - Read-only canvas with element selection
   - Admin clicks elements to attach comments
   - "Submit Feedback" → status: `feedback`

5. **Designer Reviews Feedback**
   - Back in editor, Feedback tab shows all comments
   - Each comment is linked to a specific element (or general)
   - "Send to Agent" button sends comment text to AI chat
   - AI automatically applies the requested changes

6. **Iteration Loop**
   - Designer resubmits → Admin re-reviews
   - Cycle repeats until approved

---

## 7. API Reference

### 7.1 Main Application API (port 8000)

#### Content Management

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/health` | Health check | — | `{status, chunk_count}` |
| `POST` | `/ingest` | Re-ingest all markdown docs | — | `{message, chunks_added}` |
| `POST` | `/ingest/story` | Ingest user story with images | multipart: `topic`, `text`, `category`, `images[]` | `{message, chunks_added}` |
| `GET` | `/images/{filename}` | Serve stored image | — | Image file |
| `POST` | `/query` | RAG query | `{query: string}` | `{results: [chunks]}` |
| `POST` | `/generate` | Generate post text | `{topic: string}` | `{headline, body, hashtags, sources}` |

#### Stories API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/api/stories` | List all stories | — | `{stories: [{topic, category, text, images}]}` |
| `GET` | `/api/stories/{topic}` | Get story by topic | — | `{topic, category, text, images}` |
| `PUT` | `/api/stories/{topic}` | Update story | multipart: `text`, `category`, `images[]` | `{message}` |
| `DELETE` | `/api/stories/{topic}` | Delete story + images | — | `{message}` |

#### Design API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/generate-layout` | AI layout generation | `{topic, category, text, images[]}` | `{layout: {...}}` |
| `POST` | `/api/chat-edit` | Conversational AI editing | `{design, messages, history}` | `{text, design}` |
| `POST` | `/api/designs/submit` | Submit design for approval | `{topic, category, state}` | `{design_id, status}` |
| `GET` | `/api/designs` | List designs | `?status=pending` | `{designs: [...]}` |
| `GET` | `/api/designs/check` | Check design existence | `?topics=[...]` | `{existing: {topic: design_id}}` |
| `GET` | `/api/designs/by-topic/{topic}` | Get design by topic | — | `{design}` |
| `GET` | `/api/designs/{id}` | Get design by ID | — | `{design}` |
| `PATCH` | `/api/designs/{id}/status` | Update approval status | `{status: "approved"\|"rejected"\|"feedback"}` | `{message}` |
| `POST` | `/api/designs/{id}/comments` | Add comment | `{element_id?, text, author}` | `{comment}` |
| `GET` | `/api/designs/{id}/comments` | Get comments | — | `{comments: [...]}` |
| `DELETE` | `/api/designs/{id}/comments/{cid}` | Delete comment | — | `{message}` |

#### Frontend Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main frontend (Stories + Admin tabs) |
| `GET` | `/create?topic=...&category=...` | Konva.js post editor |
| `GET` | `/feedback?design_id=...` | Design feedback review page |

---

### 7.2 Mock Social Media API (port 8100)

#### Instagram Graph API Mock (`/ig/v25.0/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/{user_id}/media` | Create media container |
| `GET` | `/{container_id}` | Check container status (simulated delay) |
| `POST` | `/{user_id}/media_publish` | Publish container |
| `GET` | `/{user_id}/content_publishing_limit` | Check publishing quota |

#### X (Twitter) API Mock (`/x/v2/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/media/upload` | Upload media (simple + chunked INIT) |
| `POST` | `/media/upload/{id}/append` | Append chunk |
| `POST` | `/media/upload/{id}/finalize` | Finalize chunked upload |
| `GET` | `/media/upload?command=STATUS` | Poll processing status |
| `POST` | `/tweets` | Create tweet |

#### LinkedIn API Mock (`/linkedin/rest/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/images?action=initializeUpload` | Initialize image upload |
| `PUT` | `/images/upload/{image_id}` | Upload image binary |
| `GET` | `/images/{image_urn}` | Check image status |
| `POST` | `/posts` | Create post with image |

#### Cross-Platform Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/published` | List all published posts |
| `GET` | `/published/{platform}` | List posts for specific platform |
| `POST` | `/reset/{platform}` | Reset platform state |
| `POST` | `/simulate/{platform}/rate-limit` | Inject rate limit error |
| `POST` | `/simulate/{platform}/error` | Inject custom error |

---

## 8. Data Flow Diagrams

### 8.1 Ingestion Pipeline

```
                    ┌─────────────────────────────────────┐
                    │         STARTUP / MANUAL INGEST      │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────┐
                    │     nicdc-content/*.md (10 files)    │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │     document_loader.load_documents() │
                    │     • Parse title, metadata, body   │
                    │     • Return Document objects        │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │     chunker.chunk_document()         │
                    │     • Split by paragraphs            │
                    │     • 500-char chunks, 50-char overlap│
                    │     • Attach metadata                │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │     embedder.embed_batch()           │
                    │     • llama.cpp /v1/embeddings       │
                    │     • Gemma 4 model                  │
                    │     • float32 vectors                │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │     vector_store.store.add()         │
                    │     • Stack vectors into NumPy array │
                    │     • Append metadata                │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │     vector_store.store.save()        │
                    │     • vectors.npy (embeddings)       │
                    │     • metadata.json (chunk metadata) │
                    └─────────────────────────────────────┘
```

### 8.2 Layout Generation Pipeline

```
                    ┌─────────────────────────────────────┐
                    │   User: "Generate" in editor         │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   POST /api/generate-layout          │
                    │   {topic, category, text, images}    │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   layout_generator.generate_layout() │
                    │   ├─ load_brand(category)            │
                    │   │  └─ data/brands/{cat}.json       │
                    │   ├─ _get_image_info(images)         │
                    │   │  └─ Pillow: dimensions + paths   │
                    │   ├─ Build prompt                    │
                    │   │  └─ topic + text + brand + dims  │
                    │   └─ cloud_llm.generate()            │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   OpenCode API (big-pickle model)    │
                    │   POST opencode.ai/zen/v1/chat/...   │
                    │   Timeout: 180s                      │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   Parse JSON response                │
                    │   • Normalize element types           │
                    │   • _auto_place_images()             │
                    │   • Return layout state              │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   Frontend: Apply to Konva.js stage  │
                    │   • Render elements on canvas        │
                    │   • Update properties panel          │
                    │   • Enable editing controls          │
                    └─────────────────────────────────────┘
```

### 8.3 Conversational Editing Pipeline

```
                    ┌─────────────────────────────────────┐
                    │   User types in Chat panel           │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   POST /api/chat-edit                │
                    │   {design, messages, history}        │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   chat_handler.chat_edit()           │
                    │   ├─ _build_messages()               │
                    │   │  • System prompt                  │
                    │   │  • Current design JSON            │
                    │   │  • History (last 10 turns)        │
                    │   │  • User message                   │
                    │   └─ cloud_llm.generate()            │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   OpenCode API (big-pickle model)    │
                    │   Returns: text + ---DESIGN--- + JSON│
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   _parse_response()                  │
                    │   • Split on ---DESIGN--- marker     │
                    │   • Extract text explanation         │
                    │   • Parse layout JSON                │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │   Frontend: Update canvas            │
                    │   • Apply new layout state           │
                    │   • Show AI's explanation            │
                    │   • Add to conversation history      │
                    └─────────────────────────────────────┘
```

---

## 9. Design Approval Workflow

### 9.1 State Transitions

```
                           ┌─────────────┐
                           │   (new)     │
                           └──────┬──────┘
                                  │
                                  ▼
                           ┌─────────────┐
                           │   pending   │ ◄── submit design
                           └──────┬──────┘
                                  │
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                 ▼
         ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
         │  approved   │  │  rejected   │  │  feedback   │
         └─────────────┘  └─────────────┘  └──────┬──────┘
                                                   │
                                                   │ (designer reviews
                                                   │  comments, updates
                                                   │  design, resubmits)
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   pending   │
                                            └─────────────┘
```

### 9.2 Comment System

**Element-Level Comments:**
- Admin clicks a specific canvas element in the feedback page
- Comment is attached to that element's ID
- Designer sees the comment overlaid on that element

**General Comments:**
- Admin adds a comment without selecting an element
- Comment is attached to the design generally
- Designer sees it in the Feedback tab

**"Send to Agent" Feature:**
- Designer clicks "Send to Agent" on a comment
- Comment text is sent to the AI chat as a user message
- AI automatically applies the requested change
- Updated design is rendered on canvas

---

## 10. AI Integration Architecture

### 10.1 Dual LLM Architecture

The system uses two separate LLM backends for different purposes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DUAL LLM ARCHITECTURE                               │
│                                                                             │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  llama.cpp (Local)                  │  │  OpenCode API (Cloud)       │  │
│  │  Port: 8080                         │  │  Endpoint: opencode.ai      │  │
│  │  Model: Gemma 4 E2B (GGUF)         │  │  Model: big-pickle          │  │
│  │                                     │  │                             │  │
│  │  Use Cases:                         │  │  Use Cases:                 │  │
│  │  • Text embeddings                  │  │  • Layout generation        │  │
│  │  • Simple post text generation      │  │  • Conversational editing   │  │
│  │                                     │  │                             │  │
│  │  Endpoints:                         │  │  Endpoint:                  │  │
│  │  • POST /v1/embeddings              │  │  • POST /chat/completions   │  │
│  │  • POST /v1/chat/completions        │  │                             │  │
│  │                                     │  │  Timeout: 180 seconds       │  │
│  │  Model File:                        │  │                             │  │
│  │  models/gemma-4-E2B-it-Q4_K_M.gguf │  │                             │  │
│  └─────────────────────────────────────┘  └─────────────────────────────┘  │
│                                                                             │
│  Rationale: Local LLM for high-frequency, low-latency tasks (embeddings).  │
│  Cloud LLM for complex, creative tasks requiring larger context windows.   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 RAG Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAG (Retrieval-Augmented Generation)                │
│                                                                             │
│  INGESTION PHASE:                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Markdown │  │ Chunk    │  │ Embed    │  │ Store    │  │ Persist  │   │
│  │ Files    │──► Splitter │──► Model    │──► Vectors  │──► to Disk  │   │
│  │ (10 PIB) │  │ (500 ch) │  │ (Gemma)  │  │ (NumPy)  │  │ (.npy +  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  .json)  │   │
│                                                            └──────────┘   │
│  RETRIEVAL PHASE:                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ User     │  │ Embed    │  │ Cosine   │  │ Top-K    │                  │
│  │ Query    │──► Query    │──► Similarity│──► Chunks   │──► Context       │
│  │          │  │ (Gemma)  │  │ Search   │  │ (k=5)    │  │ for LLM       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                  │
│                                                                             │
│  GENERATION PHASE:                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Context  │  │ System   │  │ LLM      │  │ Parsed   │                  │
│  │ + Query  │──► Prompt   │──► Generate │──► JSON     │──► Output         │
│  │          │  │ Template │  │ (Gemma)  │  │ Extract  │  │ (headline +    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  body + tags)  │
│                                                            └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Layout Generation System

**System Prompt (summarized):**
- Defines the AI as a NICDC social media designer
- Specifies the 1080×1080 canvas constraints
- Defines supported element types: `text`, `image`, `rect`, `circle`
- Requires brand color palette adherence
- Mandates logo placement per brand guidelines
- Enforces readability and visual hierarchy

**Brand Guidelines (per category):**
```json
{
    "news": {
        "primary_color": "#002147",
        "secondary_color": "#1565C0",
        "accent_color": "#FFD700",
        "text_color": "#FFFFFF",
        "heading_font": "Georgia",
        "body_font": "Arial",
        "tone": "authoritative",
        "logo_position": "top-right"
    },
    "hiring": {
        "primary_color": "#00796B",
        "secondary_color": "#4DB6AC",
        "accent_color": "#B2DFDB",
        "text_color": "#FFFFFF",
        "heading_font": "Roboto",
        "body_font": "Open Sans",
        "tone": "opportunity-driven",
        "logo_position": "top-left"
    },
    "events": {
        "primary_color": "#1A237E",
        "secondary_color": "#FFD700",
        "accent_color": "#FFC107",
        "text_color": "#FFFFFF",
        "heading_font": "Montserrat",
        "body_font": "Lato",
        "tone": "celebratory",
        "logo_position": "top-center"
    }
}
```

---

## 11. Mock Social Media APIs

### 11.1 Purpose

The mock API server (`mock-apis/main.py`) provides a realistic simulation of Instagram, X (Twitter), and LinkedIn publishing APIs for development and testing without requiring actual social media credentials.

### 11.2 Instagram Graph API Mock

**Flow:**
1. `POST /ig/v25.0/{user_id}/media` → Creates a media container
2. `GET /ig/v25.0/{container_id}` → Polls status (simulates processing delay)
3. `POST /ig/v25.0/{user_id}/media_publish` → Publishes the container

**Features:**
- Bearer token auth validation
- Rate limit headers
- Simulated processing delays
- Publishing quota tracking

### 11.3 X (Twitter) API Mock

**Flow:**
1. `POST /x/v2/media/upload` → Initialize upload (simple or chunked)
2. `POST /x/v2/media/upload/{id}/append` → Append chunk (chunked mode)
3. `POST /x/v2/media/upload/{id}/finalize` → Finalize upload
4. `GET /x/v2/media/upload?command=STATUS` → Poll processing status
5. `POST /x/v2/tweets` → Create tweet with media

**Features:**
- Simple and chunked upload modes
- Media processing simulation
- Tweet creation with media attachment

### 11.4 LinkedIn API Mock

**Flow:**
1. `POST /linkedin/rest/images?action=initializeUpload` → Initialize image upload
2. `PUT /linkedin/rest/images/upload/{image_id}` → Upload image binary
3. `GET /linkedin/rest/images/{image_urn}` → Check image status
4. `POST /linkedin/rest/posts` → Create post with image

**Features:**
- Binary image upload
- Image processing simulation
- Post creation with image URN

### 11.5 Cross-Platform Features

- **Inspection Endpoints:** List, get, and delete published posts
- **Reset Endpoints:** Clear platform state for testing
- **Error Simulation:** Inject rate limits or custom errors
- **Persistence:** Published posts saved to `published_posts.json`

---

## 12. Data Persistence Strategy

### 12.1 Storage Mechanisms

| Data Type | Storage | File | Format |
|-----------|---------|------|--------|
| Embedding Vectors | NumPy array | `vectors.npy` | Binary float32 |
| Chunk Metadata | JSON file | `metadata.json` | JSON array |
| Design Submissions | JSON file | `data/designs.json` | JSON object |
| Uploaded Images | Filesystem | `data/images/` | Binary (UUID filenames) |
| Brand Guidelines | JSON files | `data/brands/*.json` | JSON objects |
| Published Posts (Mock) | JSON file | `mock-apis/published_posts.json` | JSON object |

### 12.2 Persistence Characteristics

**Strengths:**
- Simple, no external database dependency
- Easy to inspect and debug (human-readable JSON)
- Fast read/write for single-process applications
- Portable across environments

**Limitations:**
- No concurrent access protection (single-process only)
- No transactional guarantees
- File locking not implemented
- Full rewrite on every save (not append-only)

**Recommended for:** Prototypes, single-user systems, development environments.

---

## 13. Configuration & Environment

### 13.1 Configuration File (`app/config.py`)

```python
BASE_DIR = "/home/prnv/nicdc/sm-automation"
CONTENT_DIR = "nicdc-content"
PROMPT_TEMPLATE_PATH = "app/templates/system_prompt.txt"
VECTORS_PATH = "vectors.npy"
METADATA_PATH = "metadata.json"
DESIGNS_PATH = "data/designs.json"

LLAMA_CPP_BASE_URL = "http://localhost:8080"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5

IMAGES_DIR = "data/images"
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
MAX_IMAGE_SIZE_MB = 10
```

### 13.2 Environment Variables (`.env`)

```
GOOGLE_API_KEY=AIzaSyCYnqTRno9cycGK2wmNUD5SE-1HDt1OAhs
```

**Note:** The Gemini API key is currently unused. The system uses OpenCode's cloud LLM API instead.

### 13.3 Running the Application

```bash
# Main application
python run.py
# Starts Uvicorn on 0.0.0.0:8000 with hot-reload

# llama.cpp server (required for embeddings + post generation)
./llama-server -m models/gemma-4-E2B-it-Q4_K_M.gguf --port 8080

# Mock social media APIs (optional, for testing publishing)
cd mock-apis && python main.py
# Starts on port 8100
```

---

## Appendix A: Key Code Locations

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Entry Point | `run.py` | 1-4 | Uvicorn startup |
| Configuration | `app/config.py` | 1-25 | All paths and constants |
| Main App | `app/main.py` | 1-3183 | Routes + embedded HTML |
| Document Loader | `app/document_loader.py` | 1-67 | Markdown parsing |
| Chunker | `app/chunker.py` | 1-41 | Text chunking |
| Embedder | `app/embedder.py` | 1-20 | llama.cpp client |
| Vector Store | `app/vector_store.py` | 1-158 | NumPy cosine search |
| Retriever | `app/retriever.py` | 1-16 | RAG retrieval |
| Generator | `app/generator.py` | 1-80 | Post text generation |
| Layout Generator | `app/layout_generator.py` | 1-211 | AI layout generation |
| Chat Handler | `app/chat_handler.py` | 1-123 | Conversational editing |
| Design Store | `app/design_store.py` | 1-130 | Approval workflow |
| Image Store | `app/image_store.py` | 1-58 | Image management |
| Cloud LLM | `app/cloud_llm.py` | 1-46 | OpenCode API client |
| Mock APIs | `mock-apis/main.py` | 1-1026 | Social media mocks |
| Konva.js Editor | `app/main.py` | 393-1836 | Embedded HTML/JS |
| Main Frontend | `app/main.py` | 1837-2809 | Stories + Admin UI |
| Feedback Page | `app/main.py` | 2812-3178 | Design review UI |

---

## Appendix B: Architectural Decisions

1. **Monolithic Backend + Embedded Frontend:** The entire application is a single FastAPI server with HTML pages embedded as Python strings. This simplifies deployment but makes the codebase harder to maintain.

2. **Dual LLM Strategy:** Using local llama.cpp for embeddings (high-frequency, low-latency) and cloud API for creative tasks (layout generation, conversational editing) balances cost and quality.

3. **File-Based Persistence:** Chosen for simplicity and zero external dependencies. Suitable for prototype/single-user deployment but would need replacement for production multi-user scenarios.

4. **Konva.js for Canvas:** Provides a robust 2D canvas library with built-in support for drag, resize, rotate, and layer management. The editor supports undo/redo via history stack.

5. **Brand-Guided AI Generation:** Each content category (News/Hiring/Events) has its own brand JSON that guides the AI's color palette, fonts, and tone, ensuring visual consistency.

6. **Element-Level Feedback:** The comment system supports attaching feedback to specific canvas elements, enabling precise, actionable design revisions.

---

*This document provides a comprehensive architectural overview of the SM-Automation system. For implementation details, refer to the source code files listed in Appendix A.*
