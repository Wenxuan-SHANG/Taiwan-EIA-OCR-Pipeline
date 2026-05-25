# Taiwan-EIA-OCR-Pipeline
OCR pipeline for Traditional Chinese EIA documents using Google Cloud Vision and Gemini API

## Overview
Preprocessing pipeline for Traditional Chinese Environmental Impact 
Assessment (EIA) documents containing mixed printed text, handwritten 
notes, and scanned images.

Developed as part of master's thesis research at Waseda University.

## Problem
- Target: 1,000+ pages of government administrative documents (PDF)
- Challenge: Mixed printed/handwritten content in Traditional Chinese
- Existing OCR tools (e.g. Tesseract) insufficient for handwritten characters

## Solution
- Compared Google Cloud Vision API vs Gemini API for OCR accuracy
- Built preprocessing pipeline in Python
- Implemented text noise removal and post-processing
- Pilot processing: 212 pages completed

## Tech Stack
- Python 3.x
- Google Cloud Vision API (DOCUMENT_TEXT_DETECTION)
- Gemini API
- pandas, regex

## Pipeline Overview
1. PDF → image conversion
2. API call (Cloud Vision / Gemini)
3. Text extraction and comparison
4. Noise removal and formatting
5. Output: searchable text for NVivo analysis

## Limitations
For severely illegible handwritten text, manual review is required, and such instances should be documented as methodological limitations rather than being forcibly corrected by AI.

## Research Context
Master's thesis: "Minority Voices in Taiwan's Environmental 
Impact Assessment System"
Waseda University, Graduate School of Social Sciences
