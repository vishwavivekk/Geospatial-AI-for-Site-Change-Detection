"""
Page 3 – About
Project overview, architecture, and credits.
"""

import streamlit as st

st.set_page_config(page_title="About | Geospatial AI", page_icon="ℹ️", layout="wide")

st.markdown("# ℹ️ About This Project")
st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
## Geospatial AI for Site Change Detection

This project applies **instance segmentation** and **AI-powered confidence scoring** to detect
meaningful changes between two co-registered satellite or aerial images of the same geographic site.

### 🎯 Problem Statement

Traditional change detection methods produce binary masks — every pixel is either "changed" or "not changed."
This makes it impossible to:
- Count discrete change objects
- Rank changes by confidence
- Filter noise from genuine structural changes

### 💡 Solution

By combining **Facebook's Segment Anything Model (SAM)** with the **torchange** bitemporal matching
framework, this pipeline produces **instance-level** outputs:

| Output | Description |
|---|---|
| `binary_mask.tif` | Pixel-wise change/no-change GeoTIFF |
| `probability_mask.tif` | Weighted confidence per pixel |
| `instance_masks.tif` | Each change region has a unique integer ID |
| `instance_masks_scores.tif` | Per-instance confidence score raster |

---

### 🏗️ System Architecture

```
Input Imagery (T1, T2)
        │
        ▼
  [SAM vit_h / vit_l / vit_b]
  Segment Anything Model
  → generates candidate mask pool
        │
        ▼
  [torchange — bitemporal matching]
  → filters candidates by change confidence threshold
  → assigns unique IDs & scores
        │
        ▼
  GeoTIFF Export  +  PNG Visualizations
        │
        ▼
  Streamlit Dashboard
```

---

### 📦 Tech Stack

| Layer | Technology |
|---|---|
| AI Backbone | Segment Anything Model (SAM) by Meta AI |
| Change Framework | torchange by Dr. Zhuo Zheng |
| Geospatial Processing | GeoAI (opengeos) · rasterio · GDAL |
| Data | NAIP Aerial Imagery (USDA) via HuggingFace |
| Frontend | Streamlit |
| Language | Python 3.10+ |

---

### 📚 References

1. Kirillov, A. et al. (2023). [Segment Anything](https://arxiv.org/abs/2304.02643). ICCV.
2. Zheng, Z. et al. [pytorch-change-models / torchange](https://github.com/Z-Zheng/pytorch-change-models).
3. Wu, Q. (2023). [GeoAI — opengeos](https://github.com/opengeos/geoai).
""")

with col2:
    st.markdown("### 🛠️ Quick Start")
    st.code("""
# Clone the repository
git clone https://github.com/vishwavivekk/\\
  Geospatial-AI-for-Site-Change-Detection.git

cd Geospatial-AI-for-Site-Change-Detection

# Install dependencies
pip install -r requirements.txt

# Launch app
streamlit run app.py
""", language="bash")

    st.markdown("### 📊 Sample Results")
    st.image(
        "https://github.com/user-attachments/assets/e7c00b50-c456-4653-b8ce-0c9ec8f05b7f",
        caption="Las Vegas — 2019 → 2022",
        use_container_width=True,
    )

st.divider()
st.markdown(
    "Made with ❤️ · "
    "[![GitHub](https://img.shields.io/badge/GitHub-View%20Source-black?logo=github)]"
    "(https://github.com/vishwavivekk/Geospatial-AI-for-Site-Change-Detection)"
)
