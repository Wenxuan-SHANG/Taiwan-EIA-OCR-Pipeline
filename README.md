# Multilingual PDF OCR & Text Cleaning Tool

> **This repository contains two things:**
> 1. 🌐 A web app anyone can use instantly (no coding required) — see below
> 2. 📓 The original Colab-based OCR scripts with detailed technical documentation — see [Original Scripts](#original-scripts) section below

---

## 🌐 Web App

**Live tool:** https://multilingual-ocr-tool.streamlit.app

Upload any PDF and get clean, plain-text output automatically — no installation, no coding, just a free Google API key.

### How it works
The tool routes each file through a cost ladder:
1. **Free** — Digital PDFs: text layer extracted directly via PyMuPDF (zero API cost)
2. **Affordable** (optional advanced mode) — Printed scans: Google Cloud Vision API
3. **Universal fallback** — Handwritten or mixed content: Google Gemini Flash/Pro

### How to use
1. Open https://multilingual-ocr-tool.streamlit.app
2. Get a free Gemini API key at https://aistudio.google.com/apikey
   - Only a Google account is required. No credit card needed.
   - Free quota: ~1,500 requests/day, resets daily. Stops gracefully when exceeded — no automatic charges.
   - Note: On the free tier, Google may use your inputs for model improvement. Use a paid account for confidential documents.
3. Paste your key, upload PDF(s), click **Start Processing**, download `.txt` output

### Output
Plain `.txt` files ready for NVivo, Atlas.ti, corpus analysis, or any text-based workflow.

### Disclaimer & Privacy
- **Your files:** Uploaded files are processed in memory and deleted immediately after. They are never stored on any server controlled by this tool.
- **Third-party processing:** File content is sent to Google's Gemini API for OCR. By using this tool, you accept Google's terms of service. Do not upload documents you are not authorized to share with Google.
- **API keys:** Keys are used only within your current browser session and are never logged or transmitted to any server other than Google's.
- **OCR accuracy:** Results are not guaranteed to be error-free, especially for handwritten content. Always verify output before academic citation or publication.
- **Service availability:** This tool depends on Streamlit Community Cloud and Google Gemini API. The developer makes no guarantee of continuous availability.
- **No liability:** This tool is provided as-is. The developer assumes no responsibility for any loss, data breach, or inaccuracy arising from its use.

### Citation
If you use this tool in academic research, please acknowledge it in your methods section:

> Shang, W. (2026). *Multilingual PDF OCR & Text Cleaning Tool* [Software]. GitHub. https://github.com/Wenxuan-SHANG/Taiwan-EIA-OCR-Pipeline

### About the developer
**Wenxuan Shang** — B.A. Peking University; currently a graduate student at Waseda University. This tool was originally developed to process approximately 10,000 pages of Traditional Chinese Environmental Impact Assessment (EIA) documents (mixed printed and handwritten) for qualitative research. It is open-sourced for use by other researchers.

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## 📓 Original Scripts

# OCR Pipeline for Traditional Chinese EIA Documents

OCR pipeline for Traditional Chinese Environmental Impact Assessment (EIA) documents using `pdftotext`, Google Cloud Vision API, and the Gemini API.

> 📊 **For a detailed breakdown of the system architecture, tool-selection logic, and cost analysis, see the [Project Presentation (PDF)](./AI_Supported_OCR_Project_Presentation_PDF_PreView.pdf).**

## Overview

A preprocessing pipeline that turns Traditional Chinese EIA documents — a mix of printed text, handwritten notes, and scanned images — into clean, searchable text ready for qualitative coding in NVivo.

Developed as part of master's thesis research at Waseda University.

## Problem

- **Target:** 1,000+ pages of government administrative documents (PDF)
- **Challenge:** Mixed printed / handwritten content in Traditional Chinese
- **Constraint:** NVivo has no built-in OCR, so every page must already carry a recognized text layer before word-frequency analysis or cross-text search is possible
- **Gap:** Conventional OCR (e.g. Tesseract) is pixel-and-dictionary based and fails on scribbled handwriting

## Architecture: Why Three Different Tools?

Rather than forcing one tool to do everything, each file type is routed to the tool best suited to it. This keeps cost low while maximizing accuracy.

| Task | Tool | Why this tool |
|------|------|---------------|
| Extract an existing text layer | `pdftotext` | Already digital — 100% accurate, free |
| OCR printed text (no text layer) | Google Cloud Vision API (`DOCUMENT_TEXT_DETECTION`) | Cheap, fast, accurate on print; CNN-based |
| OCR handwritten / mixed text | Gemini API (multimodal) | Understands context — can reason through scribbled handwriting where pixel-based OCR fails |
| Remove text noise | Python (regex rules) | Deterministic, reproducible, free — no AI needed |
| Code & interpret | Researcher (human) | Theoretical sensitivity; not automatable |

**Principle:** match the tool to the nature of the task — never overuse AI, never underuse it.

## Tech Stack

- Python 3.x
- `pdftotext` (PyMuPDF / `fitz`) for digital-text extraction
- Google Cloud Vision API (`DOCUMENT_TEXT_DETECTION`) for printed-image OCR
- Gemini API (multimodal) for handwritten / mixed-content OCR
- `pandas`, `re` (regex) for post-processing

## Pipeline Overview

1. PDF → image conversion (per page)
2. Route each page to the appropriate engine (`pdftotext` / Cloud Vision / Gemini)
3. Text extraction → consolidate into a single `.txt` file
4. Rule-based noise removal and formatting (see below)
5. Output: clean, searchable text for NVivo analysis

## Data Denoising (Text Cleaning)

OCR and PDF extraction introduce noise that pollutes word-frequency analysis (repeated headers, page numbers, forced line breaks). This step is **pure Python regex — no AI, no API, no cost** — which keeps it deterministic and fully reproducible.

| Target | Pattern / logic | Example removed |
|--------|-----------------|-----------------|
| Blank lines | `if not line:` (after `strip()`) | empty / whitespace-only / tab-only lines |
| Standard page numbers | `^\d+[-—]\d+$` | `1-1`, `5-12`, `10—2` |
| Compound page numbers | `^\s*\d+\s*[頁页]\s*共?\s*\d*\s*[頁页]?$` | `1頁`, `第1頁 共5頁`, `2 共 10 页` |
| Symmetric page numbers | `^[-—]\s*\d+\s*[-—]$` | `- 1 -`, `—10—` |
| Repeated headers / footers | `pattern in line and len(line) < 50` | `環境影響評估報告書` (only when the line is short) |

**Design note:** The compound-page-number pattern supports both Simplified (`页`) and Traditional (`頁`) forms and tolerates surrounding whitespace, so it is fault-tolerant across inconsistent OCR output. The header/footer rule deletes a matching keyword **only when the line is under 50 characters** — a deliberate guard against over-deletion, so that a long body sentence containing the same keyword is preserved rather than wrongly stripped.

## Results

Pilot processing on a 212-page batch of Traditional Chinese EIA meeting records:

| Metric | Value |
|--------|-------|
| Pages processed | 212 |
| Raw character count | 179,243 |
| After cleaning | 162,104 |
| Noise reduction | 9.6% |
| Script preservation | Traditional Chinese retained (no Simplified conversion) |

Cost: About 1 million tokens; 440 JPY tax included.

## Limitations

For severely illegible handwritten text, manual review is required. Such instances are documented as a **methodological limitation** of the source material rather than being forcibly "corrected" by AI — preserving research integrity over the appearance of completeness.

## Research Context

Master's thesis: *"Minority Voices in Taiwan's Environmental Impact Assessment System"*
Waseda University, Graduate School of Social Sciences
