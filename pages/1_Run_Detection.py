"""
Page 1 – Run Detection
Lets users upload bi-temporal imagery and execute the change-detection pipeline.
"""

import streamlit as st
import os
import tempfile
from pathlib import Path

st.set_page_config(page_title="Run Detection | Geospatial AI", page_icon="🔍", layout="wide")

st.markdown("# 🔍 Run Change Detection")
st.markdown("Upload your **before** and **after** satellite/aerial imagery to detect site changes.")
st.divider()

# ── Sidebar config ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Model Settings")

    sam_model = st.selectbox(
        "SAM Model Type",
        ["vit_h (recommended)", "vit_l", "vit_b"],
        help="vit_h is most accurate; vit_b is fastest",
    )
    sam_key = sam_model.split(" ")[0]

    confidence_threshold = st.slider(
        "Change Confidence Threshold", 100, 200, 145,
        help="Higher values = more conservative detection",
    )
    use_normalized = st.checkbox("Use Normalized Features", value=True)
    bitemporal_match = st.checkbox("Bitemporal Matching", value=True)

    st.divider()
    st.markdown("## 🎯 SAM Parameters")
    points_per_side = st.slider("Points Per Side", 16, 64, 32)
    stability_thresh = st.slider("Stability Score Threshold", 0.80, 1.00, 0.95, step=0.01)

    st.divider()
    st.markdown("## 📤 Export Options")
    export_binary   = st.checkbox("Binary Mask (GeoTIFF)", value=True)
    export_prob     = st.checkbox("Probability Mask (GeoTIFF)", value=True)
    export_instance = st.checkbox("Instance Masks (GeoTIFF)", value=True)

# ── Data Source ───────────────────────────────────────────────────────────────
st.markdown("### 📁 Data Source")
data_source = st.radio(
    "Choose input method",
    ["⬆️  Upload my own imagery", "🌐  Use sample NAIP data (Las Vegas 2019 → 2022)"],
    horizontal=True,
)

before_path = after_path = None

if "Upload" in data_source:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📅 Before Image (T1)")
        before_file = st.file_uploader("Upload GeoTIFF – earlier date", type=["tif", "tiff"])
        if before_file:
            st.success(f"✅ {before_file.name}")

    with col2:
        st.markdown("#### 📅 After Image (T2)")
        after_file = st.file_uploader("Upload GeoTIFF – later date", type=["tif", "tiff"])
        if after_file:
            st.success(f"✅ {after_file.name}")

    if before_file and after_file:
        st.info("Both images uploaded. Adjust settings in the sidebar and click **Run Detection**.")
else:
    st.info(
        "🌐 **Sample NAIP Imagery** (Las Vegas, Nevada)\n\n"
        "- **T1**: 2019 NAIP aerial image\n"
        "- **T2**: 2022 NAIP aerial image\n\n"
        "Images will be downloaded automatically from HuggingFace when detection starts."
    )
    before_file = after_file = "sample"   # sentinel

st.divider()

# ── Run button ────────────────────────────────────────────────────────────────
st.markdown("### 🚀 Execute Pipeline")

col_run, col_info = st.columns([1, 3])
with col_run:
    run_btn = st.button("▶️  Run Detection", type="primary", use_container_width=True)

with col_info:
    st.caption(
        "Running on CPU typically takes 3-10 minutes depending on image size and model. "
        "GPU runtime (Colab/cloud) is 5-15× faster."
    )

if run_btn:
    if before_file is None or after_file is None:
        st.error("⚠️ Please upload both images first, or select the sample data option.")
    else:
        out_folder = "change_detection_results"
        Path(out_folder).mkdir(exist_ok=True)

        progress = st.progress(0, text="Initialising…")
        status   = st.empty()

        try:
            import geoai
            from geoai.change_detection import ChangeDetection

            # ── Step 1: Download / save inputs ───────────────────────────────
            status.info("📥 Step 1/5 — Preparing imagery…")
            progress.progress(10)

            if before_file == "sample":
                naip_2019_url = "https://huggingface.co/datasets/giswqs/geospatial/resolve/main/las_vegas_naip_2019_a.tif"
                naip_2022_url = "https://huggingface.co/datasets/giswqs/geospatial/resolve/main/las_vegas_naip_2022_a.tif"
                before_path = geoai.download_file(naip_2019_url)
                after_path  = geoai.download_file(naip_2022_url)
            else:
                tmp = tempfile.mkdtemp()
                before_path = os.path.join(tmp, before_file.name)
                after_path  = os.path.join(tmp, after_file.name)
                with open(before_path, "wb") as f: f.write(before_file.read())
                with open(after_path,  "wb") as f: f.write(after_file.read())

            progress.progress(20)

            # ── Step 2: Init detector ─────────────────────────────────────────
            status.info("🤖 Step 2/5 — Initialising SAM model…")
            Path("~/.cache/torch/hub/checkpoints/").expanduser().mkdir(parents=True, exist_ok=True)
            detector = ChangeDetection(sam_model_type=sam_key)
            detector.set_hyperparameters(
                change_confidence_threshold=confidence_threshold,
                use_normalized_feature=use_normalized,
                bitemporal_match=bitemporal_match,
            )
            detector.set_mask_generator_params(
                points_per_side=points_per_side,
                stability_score_thresh=stability_thresh,
            )
            progress.progress(40)

            # ── Step 3: Detect ────────────────────────────────────────────────
            status.info("🔍 Step 3/5 — Running change detection…")
            results = detector.detect_changes(
                before_path,
                after_path,
                output_path=f"{out_folder}/binary_mask.tif"           if export_binary   else None,
                export_probability=export_prob,
                probability_output_path=f"{out_folder}/probability_mask.tif" if export_prob else None,
                export_instance_masks=export_instance,
                instance_masks_output_path=f"{out_folder}/instance_masks.tif" if export_instance else None,
                return_detailed_results=True,
                return_results=False,
            )
            progress.progress(70)

            # ── Step 4: Visualise ─────────────────────────────────────────────
            status.info("🎨 Step 4/5 — Generating visualisations…")
            if export_binary and export_prob:
                detector.visualize_results(
                    before_path, after_path,
                    f"{out_folder}/binary_mask.tif",
                    f"{out_folder}/probability_mask.tif",
                )
            progress.progress(85)

            # ── Step 5: Report ────────────────────────────────────────────────
            status.info("📄 Step 5/5 — Creating comprehensive report…")
            detector.create_comprehensive_report(results, f"{out_folder}/comprehensive_report.png")
            progress.progress(100)

            # ── Store results in session ──────────────────────────────────────
            st.session_state["results"]      = results
            st.session_state["out_folder"]   = out_folder
            st.session_state["before_path"]  = before_path
            st.session_state["after_path"]   = after_path
            st.session_state["detector"]     = detector

            status.success("✅ Detection complete!")

            # Quick summary
            total = results.get("summary", {}).get("total_masks", "N/A")
            shape = results.get("summary", {}).get("original_shape", "N/A")
            st.balloons()
            st.success(f"**{total} change instances** detected across an image of shape **{shape}**.")
            st.page_link("pages/2_Results_Viewer.py", label="📊 View Results →")

        except ImportError:
            progress.empty()
            status.error(
                "⚠️ Required packages not installed. "
                "Run `pip install geoai-py torchange` and restart the app."
            )
        except Exception as e:
            progress.empty()
            status.error(f"❌ Detection failed: {e}")
