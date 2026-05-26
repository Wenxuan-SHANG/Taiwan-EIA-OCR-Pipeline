"""
Google Cloud Vision API OCR for Printed Documents
==================================================
Converts each page of a PDF into an image, then uses the Cloud Vision
API's DOCUMENT_TEXT_DETECTION to extract text. Best suited for printed
scanned documents (low cost, high accuracy on printed text).

Environment: Google Colab (no local Python installation required)
Dependencies: google-cloud-vision, pymupdf, pillow

Usage:
  1. Enable the Cloud Vision API in Google Cloud Console.
  2. Run this in a Colab notebook.
  3. Replace YOUR_API_KEY_HERE with your own API key.
  4. Update PDF_PATH to point to your file in Google Drive.

Note: language_hints is set to "zh-Hant" (Traditional Chinese).
WARNING: Never commit your real API key to a public repository.
"""

# --- Install dependencies (run once in Colab) ---
# !pip install -q google-cloud-vision pymupdf pillow

# --- Mount Google Drive (run in Colab) ---
# from google.colab import drive
# drive.mount('/content/drive')

from google.cloud import vision
import fitz          # PyMuPDF: handles PDF files
import os
import time

# ===== Configuration: edit these two lines =====
API_KEY = "YOUR_API_KEY_HERE"
PDF_PATH = "/content/drive/MyDrive/your_document.pdf"
# ================================================

OUTPUT_PATH = "/content/drive/MyDrive/ocr_result_vision.txt"


def main():
    # Initialize the Cloud Vision client with the API key
    client = vision.ImageAnnotatorClient(
        client_options={"api_key": API_KEY}
    )

    # Verify the input file exists
    print("File exists:", os.path.exists(PDF_PATH))

    # Open the PDF and count pages
    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    print(f"Total {total_pages} pages. Starting recognition...")

    results = []

    # Process each page one by one
    for i, page in enumerate(doc):
        print(f"Processing page {i + 1}/{total_pages}...", end=" ")

        # Render the PDF page to PNG bytes
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")

        try:
            # Build the Vision image object and set language hint
            image = vision.Image(content=img_bytes)
            image_context = vision.ImageContext(language_hints=["zh-Hant"])

            # DOCUMENT_TEXT_DETECTION is optimized for dense text
            response = client.document_text_detection(
                image=image,
                image_context=image_context
            )
            text = response.full_text_annotation.text
            print(f"OK {len(text)} chars")
        except Exception as e:
            text = f"[Recognition failed: {e}]"
            print("FAILED")

        # Append this page's result with a header separator
        results.append(
            f"\n{'=' * 50}\nPage {i + 1}\n{'=' * 50}\n{text}\n"
        )

        # Cloud Vision has generous rate limits; a short pause is enough
        time.sleep(0.5)

    # Write all results to a UTF-8 text file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(results)

    print(f"\nDone! Result saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
