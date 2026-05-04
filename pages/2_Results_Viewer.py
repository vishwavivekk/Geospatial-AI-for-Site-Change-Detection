"""
Page 2 – Results Viewer
Displays change detection outputs: stats, maps, instance analysis, downloads.
"""

import streamlit as st
import os
from pathlib import Path

st.set_page_config(page_title="Results Viewer | Geospatial AI", page_icon="📊", layout="wide")

st.markdown("# 📊 Results Viewer")
st.divider()

# ── Check if results exist ────────────────────────────────────────────────────
results    = st.session_state.get("results")
out_folder = st.session_state.get("out_folder", "change_detection_results")
detector   = st.session_state.get("detector")
before_path = st.session_state.get("before_path")
after_path  = st.session_state.get("after_path")

def img_exists(name):
    return os.path.isfile(os.path.join(out_folder, name))

if results is None:
    st.info(
        "No results yet. Run the detection pipeline first on the **Run Detection** page, "
        "or browse the sample images below."
    )
    st.markdown("### 🖼️ Sample Outputs (from the GeoAI demo notebook)")
    col1, col2 = st.columns(2)
    with col1:
        st.image(
            "https://github.com/user-attachments/assets/e7c00b50-c456-4653-b8ce-0c9ec8f05b7f",
            caption="Probability Visualization — Las Vegas NAIP 2019 → 2022",
            use_container_width=True,
        )
    with col2:
        st.image(
            "https://github.com/user-attachments/assets/629caf85-0713-4e04-8023-f4273edbbb4c",
            caption="Comprehensive Analysis Report",
            use_container_width=True,
        )
    st.image(
        "https://github.com/user-attachments/assets/ea1f8a51-ea14-415a-9733-78b243061dd3",
        caption="Instance Analysis — individual change regions with confidence scores",
        use_container_width=True,
    )
    st.page_link("pages/1_Run_Detection.py", label="→ Go to Run Detection")
    st.stop()

# ── Summary Metrics ───────────────────────────────────────────────────────────
summary = results.get("summary", {})
c1, c2, c3 = st.columns(3)
c1.metric("Total Instances", summary.get("total_masks", "–"))
c2.metric("Image Shape",     str(summary.get("original_shape", "–")))
c3.metric("Output Folder",   out_folder)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Maps", "📈 Instance Stats", "📄 Report", "⬇️ Downloads"])

# ── Tab 1: Maps ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Change Detection Maps")

    if img_exists("probability_mask.tif"):
        if detector and before_path and after_path:
            with st.spinner("Rendering probability visualization…"):
                try:
                    detector.visualize_results(
                        before_path, after_path,
                        f"{out_folder}/binary_mask.tif",
                        f"{out_folder}/probability_mask.tif",
                    )
                except Exception as e:
                    st.warning(f"Could not regenerate visualization: {e}")

    prob_png = f"{out_folder}/probability_visualization.png"
    split_png = f"{out_folder}/split_comparison.png"

    if os.path.isfile(prob_png):
        st.image(prob_png, caption="Probability Map Overlay", use_container_width=True)
    else:
        st.info("Probability visualization image not found. It is generated automatically when detection runs with both binary and probability outputs enabled.")

    if os.path.isfile(split_png):
        st.image(split_png, caption="Split Comparison (Before | After | Changes)", use_container_width=True)
    else:
        if detector and before_path and after_path and img_exists("binary_mask.tif") and img_exists("probability_mask.tif"):
            if st.button("Generate Split Comparison"):
                with st.spinner("Creating split comparison…"):
                    detector.create_split_comparison(
                        before_path, after_path,
                        f"{out_folder}/binary_mask.tif",
                        f"{out_folder}/probability_mask.tif",
                        split_png,
                    )
                    st.image(split_png, use_container_width=True)

# ── Tab 2: Instance Stats ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### Instance-Level Statistics")

    masks = results.get("masks", [])
    stats = results.get("statistics", {})

    if stats:
        st.markdown("#### Quality Metrics")
        for metric, s in stats.items():
            col_a, col_b, col_c = st.columns(3)
            col_a.metric(f"{metric} — Mean",   f"{s['mean']:.3f}")
            col_b.metric(f"{metric} — Std Dev", f"{s['std']:.3f}")

    if masks:
        st.markdown("#### Top Detected Instances")
        import pandas as pd
        rows = []
        for m in masks[:50]:
            rows.append({
                "Instance ID":      m.get("mask_id", "–"),
                "IoU Prediction":   round(m.get("iou_pred", 0), 4),
                "Stability Score":  round(m.get("stability_score", 0), 4),
                "Area (px)":        m.get("area", "–"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        instance_png = f"{out_folder}/instance_analysis.png"
        if os.path.isfile(instance_png):
            st.image(instance_png, caption="Instance Analysis Chart", use_container_width=True)
        elif detector and img_exists("instance_masks.tif") and img_exists("instance_masks_scores.tif"):
            if st.button("Generate Instance Analysis Chart"):
                with st.spinner("Analyzing instances…"):
                    detector.analyze_instances(
                        f"{out_folder}/instance_masks.tif",
                        f"{out_folder}/instance_masks_scores.tif",
                        instance_png,
                    )
                    st.image(instance_png, use_container_width=True)
    else:
        st.info("No instance-level mask data in current results.")

# ── Tab 3: Report ─────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### Comprehensive Analysis Report")
    report_png = f"{out_folder}/comprehensive_report.png"

    if os.path.isfile(report_png):
        st.image(report_png, caption="Comprehensive Report", use_container_width=True)
    elif detector:
        if st.button("Generate Comprehensive Report"):
            with st.spinner("Building report…"):
                detector.create_comprehensive_report(results, report_png)
                st.image(report_png, use_container_width=True)
    else:
        st.info("Run detection first to generate the report.")

# ── Tab 4: Downloads ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("### Download Output Files")
    files_to_download = {
        "binary_mask.tif":              "Binary Change Mask (GeoTIFF)",
        "probability_mask.tif":         "Probability Mask (GeoTIFF)",
        "instance_masks.tif":           "Instance Segmentation Masks (GeoTIFF)",
        "instance_masks_scores.tif":    "Instance Confidence Scores (GeoTIFF)",
        "split_comparison.png":         "Split Comparison Image",
        "instance_analysis.png":        "Instance Analysis Chart",
        "comprehensive_report.png":     "Comprehensive Report",
    }

    found = False
    for fname, label in files_to_download.items():
        fpath = os.path.join(out_folder, fname)
        if os.path.isfile(fpath):
            found = True
            with open(fpath, "rb") as f:
                st.download_button(
                    label=f"⬇️  {label}",
                    data=f,
                    file_name=fname,
                    use_container_width=True,
                )

    if not found:
        st.info("No output files found. Run detection to generate outputs.")
