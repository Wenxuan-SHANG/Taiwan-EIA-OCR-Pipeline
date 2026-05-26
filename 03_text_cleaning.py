"""
Text Cleaning and Noise Removal (Pure Python, No API)
======================================================
Cleans raw OCR output for qualitative analysis in NVivo:
  - Splits text by page
  - Removes page numbers, headers, and OCR stamp noise
  - Intelligently merges hard line breaks (recognizes numbered
    items and official-document markers as new-paragraph signals)
  - Optionally converts Traditional Chinese to Simplified
  - Reports how much noise was removed

Runs entirely offline and free of charge. No AI, no API key.

Environment: Google Colab or any local Python environment
Dependencies: opencc (only if Traditional->Simplified conversion is needed)

Usage:
  1. Mount Google Drive (in Colab) or set local paths.
  2. Update INPUT_FILENAME to your raw OCR text file.
  3. Set DO_SIMPLIFY to True/False depending on your needs.
"""

# --- Install dependency (only needed if DO_SIMPLIFY = True) ---
# !pip install -q opencc

# --- Mount Google Drive (run in Colab) ---
# from google.colab import drive
# drive.mount('/content/drive')

import re
import opencc

# ===== Configuration =====
INPUT_FILENAME = "ocr_result.txt"
OUTPUT_FILENAME = "ocr_result_cleaned.txt"

INPUT_PATH = f"/content/drive/MyDrive/{INPUT_FILENAME}"
OUTPUT_PATH = f"/content/drive/MyDrive/{OUTPUT_FILENAME}"

# True  = convert Traditional Chinese to Simplified
# False = keep original Traditional Chinese (recommended for academic use)
DO_SIMPLIFY = False
# =========================

# Initialize the converter ('t2s' = Traditional to Simplified)
if DO_SIMPLIFY:
    converter = opencc.OpenCC('t2s.json')


def is_noise_line(line):
    """Return True if a line is noise that should be removed."""
    line = line.strip()
    if not line:
        return True

    # Standalone page numbers, e.g. "1-1" (half- or full-width dash)
    if re.match(r'^\d+[-\uff0d]\d+$', line):
        return True

    # Footer page markers, e.g. Chinese "Page 5 of 5"
    if re.match(r'^\u7b2c\s*\d+\s*[\u9801\u9875]\s*\u5171?\s*\d*\s*[\u9801\u9875]?$', line):
        return True

    # Dash-wrapped page numbers, e.g. "- 1 -"
    if re.match(r'^[-\uff0d]\s*\d+\s*[-\uff0d]$', line):
        return True

    # Known repeated header noise (edit for your own documents)
    noise_patterns = [
        "\u6df1\u6c34\u6cb3\u5317\u5074\u6cbf\u6cb3\u5e73\u9762\u9053\u8def\u5de5\u7a0b",
        "\u74b0\u5883\u5f71\u97ff\u8a55\u4f30\u5831\u544a\u66f8",
    ]
    for pattern in noise_patterns:
        # Treat as header only if the line is short and contains the pattern
        if pattern in line and len(line) < 50:
            return True

    return False


def clean_page(page_text):
    """Clean a single page: remove noise and merge hard line breaks."""
    lines = page_text.split('\n')
    clean_lines = [l for l in lines if not is_noise_line(l)]

    merged = []
    buffer = ""
    for line in clean_lines:
        line = line.strip()
        if not line:
            continue

        # Signals that a NEW paragraph is starting
        starts_new_para = (
            re.match(r'^[\u4e00-\u4e5d\u5341]+[\u3001.]', line) or       # Chinese numerals: 一. 二.
            re.match(r'^\d+[\u3001.]', line) or                          # Arabic numerals: 1. 2.
            re.match(r'^\uff08[\u4e00-\u4e5d\u5341\d]+\uff09', line) or  # bracketed: (one)(1)
            re.match(r'^[\u2460-\u2469]', line) or                       # circled: (1)(2)(3)
            line.startswith(('\u4e3b\u65e8\uff1a', '\u4f9d\u64da\uff1a', '\u516c\u544a\u4e8b\u9805\uff1a'))
        )

        if starts_new_para and buffer:
            merged.append(buffer)
            buffer = line
        elif buffer.endswith(('\u3002', '\uff01', '\uff1f', '\uff1b')):  # sentence-final punctuation
            merged.append(buffer)
            buffer = line
        else:
            buffer += line

    if buffer:
        merged.append(buffer)

    return '\n\n'.join(merged)


def main():
    # Step 1: read the raw file
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    original_length = len(raw_text)
    print(f"Original length: {original_length:,} chars")

    # Step 2: split into pages (keep page info for later reference)
    pages = re.split(r'={30,}\s*\n\s*Page\s+\d+\s*\n={30,}', raw_text)
    pages = [p.strip() for p in pages if p.strip()]
    print(f"Detected {len(pages)} pages")

    # Step 3: clean each page
    cleaned_pages = []
    for i, page in enumerate(pages):
        cleaned = clean_page(page)
        if DO_SIMPLIFY:
            cleaned = converter.convert(cleaned)
        cleaned_pages.append(f"[Page {i + 1}]\n\n{cleaned}")

    # Step 4: join and save
    final_text = '\n\n' + ('=' * 50 + '\n') \
        + ('\n\n' + '=' * 50 + '\n').join(cleaned_pages)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(final_text)

    cleaned_length = len(final_text)
    reduction = (1 - cleaned_length / original_length) * 100

    print(f"\nDone!")
    print(f"  Original:  {original_length:,} chars")
    print(f"  Cleaned:   {cleaned_length:,} chars")
    print(f"  Reduction: {reduction:.1f}%")
    print(f"  Saved to:  {OUTPUT_PATH}")
    print(f"  Conversion: {'Simplified' if DO_SIMPLIFY else 'Traditional (kept)'}")


if __name__ == "__main__":
    main()
