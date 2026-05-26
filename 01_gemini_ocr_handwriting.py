"""
Gemini API OCR for Handwritten / Mixed-Layout Documents
=========================================================
Converts each page of a PDF into an image, then uses the Gemini API
to recognize text (including handwriting). Designed for Traditional
Chinese EIA documents where handwriting and printed text are mixed.

Environment: Google Colab (no local Python installation required)
Dependencies: google-genai, pymupdf, pillow

Usage:
  1. Run this in a Colab notebook.
  2. Replace YOUR_API_KEY_HERE with your own Gemini API key.
  3. Update PDF_PATH to point to your file in Google Drive.

WARNING: Never commit your real API key to a public repository.
"""

# --- Install dependencies (run once in Colab) ---
# !pip install -q google-genai pymupdf pillow

# --- Mount Google Drive (run in Colab) ---
# from google.colab import drive
# drive.mount('/content/drive')

from google import genai
import fitz          # PyMuPDF: handles PDF files
from PIL import Image
import io
import time
import os

# ===== Configuration: edit these two lines =====
API_KEY = "YOUR_API_KEY_HERE"
PDF_PATH = "/content/drive/MyDrive/your_document.pdf"
# ================================================

OUTPUT_PATH = "/content/drive/MyDrive/ocr_result_gemini.txt"

# Prompt sent to the model along with each page image
PROMPT = (
    "Recognize all text in the image, including both printed and "
    "handwritten content. For handwriting, do your best to interpret it; "
    "mark uncertain characters with [?]. Preserve the original paragraph "
    "structure. Do not add any explanation."
)


def main():
    # Verify the input file exists before starting
    print("File exists:", os.path.exists(PDF_PATH))
    print("File size:", os.path.getsize(PDF_PATH), "bytes")

    # Initialize the Gemini client with the API key
    client = genai.Client(api_key=API_KEY)

    # Open the PDF and count pages
    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    print(f"Total {total_pages} pages. Starting recognition...")

    results = []

    # Process each page one by one
    for i, page in enumerate(doc):
        print(f"Processing page {i + 1}/{total_pages}...", end=" ")

        # Render the PDF page to a PNG image in memory
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Try up to 3 times in case of transient failures
        success = False
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=[img, PROMPT]
                )
                text = response.text
                print(f"OK {len(text)} chars")
                success = True
                break
            except Exception as e:
                if attempt < 2:
                    print("retrying...", end=" ")
                    time.sleep(15)
                else:
                    text = f"[Recognition failed: {e}]"
                    print("FAILED")

        # Append this page's result with a header separator
        results.append(
            f"\n{'=' * 50}\nPage {i + 1}\n{'=' * 50}\n{text}\n"
        )

        # Pause between pages to avoid hitting rate limits
        time.sleep(3)

    # Write all results to a UTF-8 text file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(results)

    print(f"\nDone! Result saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
