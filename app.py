"""
Geospatial AI for Site Change Detection
Main Streamlit Application Entry Point
"""

import streamlit as st

st.set_page_config(
    page_title="Geospatial AI | Site Change Detection",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1a73e8, #34a853);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #5f6368;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem;
        border-left: 4px solid #1a73e8;
    }
    .feature-box {
        background: linear-gradient(135deg, #e8f4fd, #f0fdf4);
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }
    .badge {
        display: inline-block;
        background: #1a73e8;
        color: white;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        margin: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/satellite.png", width=64)
    st.markdown("## 🛰️ Geospatial AI")
    st.markdown("**Site Change Detection**")
    st.divider()

    st.markdown("### 📡 Navigation")
    st.page_link("app.py",                     label="🏠  Home",              icon=None)
    st.page_link("pages/1_Run_Detection.py",    label="🔍  Run Detection",     icon=None)
    st.page_link("pages/2_Results_Viewer.py",   label="📊  Results Viewer",    icon=None)
    st.page_link("pages/3_About.py",            label="ℹ️   About",             icon=None)

    st.divider()
    st.markdown("### ⚙️ Quick Settings")
    st.selectbox("SAM Model", ["vit_h (recommended)", "vit_l", "vit_b"],
                 help="Larger models = higher accuracy but slower")
    st.slider("Confidence Threshold", 100, 200, 145,
              help="Higher = fewer but more certain detections")

    st.divider()
    st.markdown(
        "[![GitHub](https://img.shields.io/badge/GitHub-Source-black?logo=github)]"
        "(https://github.com/vishwavivekk/Geospatial-AI-for-Site-Change-Detection)"
    )

# ── Hero Section ──────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🛰️ Geospatial AI for Site Change Detection</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Instance-level change detection in satellite & aerial imagery '
    'using Segment Anything Model (SAM) + torchange</div>',
    unsafe_allow_html=True,
)

# ── Metric Cards ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Model Backbone", "SAM vit_h", help="Segment Anything Model")
with c2:
    st.metric("Detection Type", "Instance", help="Each change gets a unique ID")
with c3:
    st.metric("Output Formats", "GeoTIFF + PNG", help="Spatially referenced outputs")
with c4:
    st.metric("Confidence Scoring", "✅ Per-mask", help="IoU + Stability scores")

st.divider()

# ── Feature Grid ─────────────────────────────────────────────────────────────
st.markdown("## 🔑 Key Capabilities")
f1, f2 = st.columns(2)

with f1:
    st.markdown("""
<div class="feature-box">
<b>🔍 Instance Segmentation</b><br>
Each change region receives a unique ID, enabling object-level analysis and tracking.
</div>
<div class="feature-box">
<b>📈 Confidence Scoring</b><br>
Per-instance IoU prediction and stability scores help filter low-quality detections.
</div>
<div class="feature-box">
<b>🗺️ GeoTIFF Output</b><br>
All outputs preserve CRS and spatial reference — ready for GIS workflows.
</div>
""", unsafe_allow_html=True)

with f2:
    st.markdown("""
<div class="feature-box">
<b>🖼️ Rich Visualizations</b><br>
Split comparisons, probability maps, instance overlays, and comprehensive reports.
</div>
<div class="feature-box">
<b>⚡ One-Click Analysis</b><br>
Run the full pipeline — detection, export, and visualisation — in a single call.
</div>
<div class="feature-box">
<b>🌍 NAIP / Satellite Ready</b><br>
Tested on NAIP aerial imagery; compatible with any co-registered bi-temporal pair.
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Workflow ──────────────────────────────────────────────────────────────────
st.markdown("## 🔄 Workflow")
w1, w2, w3, w4 = st.columns(4)
steps = [
    ("1️⃣", "Upload Images", "Provide before & after GeoTIFFs (or use sample NAIP data)"),
    ("2️⃣", "Configure Model", "Select SAM model size and confidence threshold"),
    ("3️⃣", "Run Detection", "SAM segments regions; torchange scores changes"),
    ("4️⃣", "Explore Results", "View maps, stats, split comparisons, and download outputs"),
]
for col, (icon, title, desc) in zip([w1, w2, w3, w4], steps):
    with col:
        st.markdown(f"### {icon} {title}")
        st.caption(desc)

st.divider()

# ── CTA ───────────────────────────────────────────────────────────────────────
col_a, col_b, _ = st.columns([1, 1, 3])
with col_a:
    if st.button("🚀 Run Detection", use_container_width=True, type="primary"):
        st.switch_page("pages/1_Run_Detection.py")
with col_b:
    if st.button("📊 View Sample Results", use_container_width=True):
        st.switch_page("pages/2_Results_Viewer.py")

st.divider()
st.caption(
    "Built with [GeoAI](https://github.com/opengeos/geoai) · "
    "[torchange](https://github.com/Z-Zheng/pytorch-change-models) · "
    "[SAM](https://github.com/facebookresearch/segment-anything) · "
    "Streamlit"
)
