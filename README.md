# 🛰️ Geospatial AI for Site Change Detection

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Instance-level change detection in satellite & aerial imagery** using Segment Anything Model (SAM) + torchange bitemporal matching — with a production-ready Streamlit dashboard.

---

## 🎯 What It Does

Traditional change detection gives you a binary "changed / not changed" pixel mask. This project goes further:

| Capability | Description |
|---|---|
| 🔍 **Instance Segmentation** | Each change region gets a unique integer ID |
| 📈 **Confidence Scoring** | Per-instance IoU prediction & stability score |
| 🗺️ **GeoTIFF Output** | All outputs preserve CRS & spatial reference |
| 🖼️ **Rich Visualizations** | Split comparisons, probability maps, instance overlays |
| ⚡ **One-Click Pipeline** | Detection → export → visualizations in a single call |

---

## 🚀 Demo

![Probability Visualization](https://github.com/user-attachments/assets/e7c00b50-c456-4653-b8ce-0c9ec8f05b7f)

*Las Vegas NAIP 2019 → 2022 | Probability-weighted change map*

---

## 🏗️ Project Structure

```
Geospatial-AI-for-Site-Change-Detection/
│
├── app.py                        # Streamlit home page
├── requirements.txt              # Python dependencies
├── .streamlit/
│   └── config.toml               # Theme & server settings
│
├── pages/
│   ├── 1_Run_Detection.py        # Upload images & run pipeline
│   ├── 2_Results_Viewer.py       # View maps, stats & download outputs
│   └── 3_About.py                # Architecture, references, quick-start
│
└── notebooks/
    └── change_detection.ipynb    # Original Colab exploration notebook
```

---

## 🛠️ Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/vishwavivekk/Geospatial-AI-for-Site-Change-Detection.git
cd Geospatial-AI-for-Site-Change-Detection

# 2. Install
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

---

## ☁️ Deploy to Streamlit Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set:
   - **Repository**: `vishwavivekk/Geospatial-AI-for-Site-Change-Detection`
   - **Main file path**: `app.py`
4. Click **Deploy**.

> ⚠️ SAM `vit_h` requires ~2.4 GB RAM. Use `vit_b` on the free Streamlit Cloud tier.

---

## 🔄 Pipeline Architecture

```
Input Imagery (T1, T2)
        │
        ▼
  [SAM vit_h / vit_l / vit_b]
  → candidate mask pool
        │
        ▼
  [torchange — bitemporal matching]
  → filters by confidence threshold
  → assigns unique IDs & scores
        │
        ▼
  GeoTIFF Export  +  PNG Visualizations
        │
        ▼
  Streamlit Dashboard
```

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| AI Backbone | [Segment Anything Model](https://github.com/facebookresearch/segment-anything) (Meta AI) |
| Change Framework | [torchange](https://github.com/Z-Zheng/pytorch-change-models) (Dr. Zhuo Zheng) |
| Geospatial | [GeoAI](https://github.com/opengeos/geoai) · rasterio · GDAL |
| Sample Data | NAIP Aerial Imagery (USDA) via HuggingFace |
| Frontend | Streamlit |
| Language | Python 3.10+ |

---

## 📊 Output Files

| File | Description |
|---|---|
| `binary_mask.tif` | Traditional binary change detection |
| `probability_mask.tif` | Probability-weighted change map |
| `instance_masks.tif` | Instance segmentation with unique IDs |
| `instance_masks_scores.tif` | Confidence scores per instance |
| `split_comparison.png` | Before / After / Change side-by-side |
| `instance_analysis.png` | Per-instance metrics chart |
| `comprehensive_report.png` | Full analysis summary figure |

---

## 📚 References

1. Kirillov, A. et al. (2023). [Segment Anything](https://arxiv.org/abs/2304.02643). ICCV 2023.
2. Zheng, Z. et al. [pytorch-change-models](https://github.com/Z-Zheng/pytorch-change-models).
3. Wu, Q. (2023). [GeoAI](https://github.com/opengeos/geoai).

---

## 📄 License

MIT © 2024
