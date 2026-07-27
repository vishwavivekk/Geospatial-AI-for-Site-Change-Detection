import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(BASE_DIR, "nicdc-content")
TEMPLATE_PATH = os.path.join(BASE_DIR, "base_design.html")
PROMPT_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
PROMPT_TEMPLATE_PATH = os.path.join(PROMPT_TEMPLATE_DIR, "system_prompt.txt")
PAGES_DIR = os.path.join(os.path.dirname(__file__), "pages")
VECTORS_PATH = os.path.join(BASE_DIR, "vectors.npy")
METADATA_PATH = os.path.join(BASE_DIR, "metadata.json")
DESIGNS_PATH = os.path.join(BASE_DIR, "data", "designs.json")
USERS_PATH = os.path.join(BASE_DIR, "data", "users.json")
SECRET_PATH = os.path.join(BASE_DIR, "data", ".session_secret")

LLAMA_CPP_BASE_URL = os.environ.get("LLAMA_CPP_URL", "http://localhost:8080")
MODEL_NAME = "default"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5

DEFAULT_PROFILE_NAME = "NICDC"
DEFAULT_PROFILE_LOGO = "https://via.placeholder.com/48"
DEFAULT_IMAGE = "https://via.placeholder.com/600x450"

IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
PUBLISHED_DIR = os.path.join(BASE_DIR, "data", "published")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE_MB = 10

# ── Mock social media APIs ────────────────────────────
MOCK_API_BASE = os.environ.get("MOCK_API_BASE", "http://localhost:8100")
# Base URL the mock APIs can use to reference our images (acts as our "CDN")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
SOCIAL_ACCESS_TOKEN = os.environ.get("SOCIAL_ACCESS_TOKEN", "mock-access-token")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841400000000000")
LINKEDIN_AUTHOR = os.environ.get("LINKEDIN_AUTHOR", "urn:li:organization:900001")
