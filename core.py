"""
core.py — Taiwan EIA OCR Pipeline: reusable processing functions

Cost ladder (lowest → highest):
  1. Native text layer  — PyMuPDF, free
  2. Cloud Vision API   — cheap, printed text only
  3. Gemini API         — handles handwriting and mixed layouts
"""

from __future__ import annotations

import io
import re
import time
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

# ── Module-level thresholds (tune here, not scattered in functions) ────────────
MIN_NATIVE_CHARS_PER_PAGE     = 50    # avg chars/page below this → treat as scanned
MIN_OCR_CHARS_PER_PAGE        = 20    # avg chars/page from Cloud Vision below this → upgrade
CONFIDENCE_THRESHOLD          = 0.70  # Cloud Vision page confidence below this → upgrade
CV_HANDWRITING_HINT_THRESHOLD = 0.85  # cloud_vision-only avg confidence below this → suggest Gemini

_SEP = "=" * 50


class CloudVisionUnavailableError(RuntimeError):
    """Raised when the google-cloud-vision package is not installed."""


class GeminiQuotaError(RuntimeError):
    """Raised when Gemini returns a quota/permission error (e.g. free key + Pro model)."""


class GeminiKeyRequiredError(RuntimeError):
    """Raised when a file's routing requires Gemini OCR but no Gemini API key was provided."""


class OpenCCUnavailableError(RuntimeError):
    """Raised when the opencc-python-reimplemented package is not installed."""

# ── API pricing constants (update here when rates change) ──────────────────────
GEMINI_FLASH_INPUT    = 0.30  / 1_000_000   # $ per input token
GEMINI_FLASH_OUTPUT   = 2.50  / 1_000_000   # $ per output token
GEMINI_PRO_INPUT      = 1.25  / 1_000_000   # $ per input token
GEMINI_PRO_OUTPUT     = 10.00 / 1_000_000   # $ per output token
CLOUD_VISION_PER_PAGE = 1.50  / 1_000       # $ per page

_GEMINI_PROMPT = (
    "Recognize all text in the image, including both printed and "
    "handwritten content. For handwriting, do your best to interpret it; "
    "mark uncertain characters with [?]. Preserve the original paragraph "
    "structure. Do not add any explanation."
)


def _page_header(n: int) -> str:
    return f"\n{_SEP}\nPage {n}\n{_SEP}\n"


def _count_pages(text: str) -> int:
    return len(re.findall(r"={30,}\s*\nPage\s+\d+\s*\n={30,}", text))


# ── 1. Native text extraction ──────────────────────────────────────────────────

def extract_native_text(pdf_path: str) -> tuple[str, bool]:
    """
    Extract the embedded text layer from a digital PDF (zero API cost).

    Returns:
        text:         combined text with ==Page N== separators
        is_sufficient: True when avg chars/page >= MIN_NATIVE_CHARS_PER_PAGE
    """
    doc = fitz.open(pdf_path)
    parts: list[str] = []
    total_chars = 0

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        total_chars += len(text)
        parts.append(f"{_page_header(i)}{text}\n")

    combined = "".join(parts)
    avg_chars = total_chars / len(doc) if len(doc) > 0 else 0
    return combined, avg_chars >= MIN_NATIVE_CHARS_PER_PAGE


# ── 2. Gemini OCR ─────────────────────────────────────────────────────────────

def ocr_with_gemini(
    pdf_path: str, api_key: str, model: str = "gemini-2.5-flash"
) -> tuple[str, int, dict]:
    """
    OCR every page with the Gemini multimodal API.
    Handles handwritten and mixed-layout documents.

    No sleep on success; exponential back-off only on failure:
      rate-limit errors → 5 s / 10 s / 20 s
      other errors      → capped at 5 s

    Returns:
        text:        combined text with ==Page N== separators
        page_count:  total pages processed
        token_usage: {"input_tokens": int, "output_tokens": int} accumulated across all pages
    """
    from google import genai  # deferred: not needed on the native path

    client = genai.Client(api_key=api_key)
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    parts: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0

    for i, page in enumerate(doc, start=1):
        print(f"Gemini OCR: page {i}/{total_pages}...", end=" ", flush=True)

        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        text = f"[Recognition failed]"
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[img, _GEMINI_PROMPT],
                )
                text = response.text
                um = getattr(response, "usage_metadata", None)
                if um:
                    total_input_tokens  += getattr(um, "prompt_token_count",     0) or 0
                    total_output_tokens += getattr(um, "candidates_token_count", 0) or 0
                print(f"OK ({len(text)} chars)")
                break
            except Exception as e:
                err = str(e)
                is_rate_limit = any(k in err for k in ("429", "RESOURCE_EXHAUSTED", "quota"))
                is_quota_or_permission = any(k in err for k in ("RESOURCE_EXHAUSTED", "PERMISSION_DENIED"))
                wait = (2 ** attempt) * 5  # 5 s, 10 s, 20 s
                if not is_rate_limit:
                    wait = min(wait, 5)
                if attempt < 2:
                    print(f"retrying in {wait}s...", end=" ", flush=True)
                    time.sleep(wait)
                else:
                    print(f"Gemini OCR page {i} FAILED: {e}")
                    if is_quota_or_permission:
                        raise GeminiQuotaError(f"Gemini quota/permission error: {e}") from e
                    text = f"[Recognition failed: {e}]"

        parts.append(f"{_page_header(i)}{text}\n")

    token_usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
    return "".join(parts), total_pages, token_usage


# ── 3. Cloud Vision OCR ───────────────────────────────────────────────────────

def ocr_with_cloud_vision(pdf_path: str, api_key: str) -> tuple[str, int, list[float]]:
    """
    OCR every page with Google Cloud Vision DOCUMENT_TEXT_DETECTION.
    Best suited for printed, scanned documents.

    Returns:
        text:               combined text with ==Page N== separators
        page_count:         total pages processed
        page_confidences:   per-page confidence scores (0.0–1.0); empty when
                            the API returns no confidence data
    """
    try:
        from google.cloud import vision  # deferred: not needed on other paths
    except ImportError as e:
        print(f"Cloud Vision import failed: {e}")
        raise CloudVisionUnavailableError("google-cloud-vision is not installed") from e

    client = vision.ImageAnnotatorClient(
        client_options={"api_key": api_key}
    )

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    parts: list[str] = []
    confidences: list[float] = []

    for i, page in enumerate(doc, start=1):
        print(f"Cloud Vision OCR: page {i}/{total_pages}...", end=" ", flush=True)

        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")

        try:
            image = vision.Image(content=img_bytes)
            image_context = vision.ImageContext(language_hints=["zh-Hant"])
            response = client.document_text_detection(
                image=image,
                image_context=image_context,
            )
            text = response.full_text_annotation.text

            pages = response.full_text_annotation.pages
            if pages:
                confidences.append(pages[0].confidence)

            print(f"OK ({len(text)} chars)")
        except Exception as e:
            text = f"[Recognition failed: {e}]"
            print("FAILED")

        parts.append(f"{_page_header(i)}{text}\n")
        time.sleep(0.5)

    return "".join(parts), total_pages, confidences


# ── 4. Text cleaning ──────────────────────────────────────────────────────────

def _is_noise_line(line: str, remove_page_numbers: bool = True) -> bool:
    """Return True if the line is built-in structural noise to be removed
    (page markers, etc). Caller-supplied noise_patterns are handled
    separately as substring removal, not whole-line removal — see
    _clean_page."""
    line = line.strip()
    if not line:
        return True
    if remove_page_numbers:
        # Page numbers like "1-1", "5-12" (half- or full-width dash)
        if re.match(r"^\d+[-－]\d+$", line):
            return True
        # Chinese page markers: 第N頁 / 第N頁共M頁
        if re.match(r"^第\s*\d+\s*[頁页]\s*共?\s*\d*\s*[頁页]?$", line):
            return True
        # Dash-wrapped page numbers: "- 1 -", "—10—"
        if re.match(r"^[-－]\s*\d+\s*[-－]$", line):
            return True
    return False


def _is_standalone_page_number(idx: int, raw_lines: list[str]) -> bool:
    """True if raw_lines[idx] is a bare 1-4 digit number sitting alone on its
    own raw OCR line (e.g. a page number like "1", "23").

    Real OCR output rarely surrounds a footer/header page number with a
    genuinely blank line — it usually sits directly next to body text on
    the adjacent line — so isolation is judged purely by the line's own
    content (nothing but 1-4 digits), not by blank neighbors.
    """
    line = raw_lines[idx].strip()
    return bool(re.match(r"^\d{1,4}$", line))


def _clean_page(
    page_text: str,
    noise_patterns: list[str],
    remove_page_numbers: bool = True,
    merge_lines: bool = True,
    use_doc_paragraph_rules: bool = True,
) -> str:
    """Remove noise lines and intelligently merge hard line-breaks."""
    # Caller-supplied document-specific noise is removed as a plain substring
    # wherever it appears, *before* splitting into lines — it may share a raw
    # OCR line with unrelated text (e.g. a cover-page title run together with
    # the following heading), so whole-line removal would delete too much.
    for pattern in noise_patterns:
        if pattern:
            page_text = page_text.replace(pattern, "")

    lines = page_text.split("\n")
    clean_lines = [
        l for i, l in enumerate(lines)
        if not _is_noise_line(l, remove_page_numbers)
        and not (remove_page_numbers and _is_standalone_page_number(i, lines))
    ]

    if not use_doc_paragraph_rules:
        return "\n\n".join(l.strip() for l in clean_lines if l.strip())

    merged: list[str] = []
    buffer = ""
    for line in clean_lines:
        line = line.strip()
        if not line:
            continue

        starts_new_para = bool(
            re.match(r"^[一-九十]+[、.]", line) or  # 一. 二. ...
            re.match(r"^\d+[、.]", line) or                      # 1. 2. ...
            re.match(r"^（[一-九十\d]+）", line) or  # （一）（1）
            re.match(r"^[①-⑩]", line) or                   # ①②③
            line.startswith(("主旨：", "依據：", "公告事項："))
        )

        if starts_new_para and buffer:
            merged.append(buffer)
            buffer = line
        elif buffer.endswith(("。", "！", "？", "；")):
            merged.append(buffer)
            buffer = line
        elif not merge_lines:
            if buffer:
                merged.append(buffer)
            buffer = line
        else:
            buffer += line

    if buffer:
        merged.append(buffer)

    return "\n\n".join(merged)


def clean_text(
    text: str,
    noise_patterns: Optional[list[str]] = None,
    remove_page_numbers: bool = True,
    merge_lines: bool = True,
    use_doc_paragraph_rules: bool = True,
    to_simplified: bool = False,
) -> str:
    """
    Remove OCR/PDF noise and merge hard line-breaks.

    Works on output from all three extraction functions (they share the same
    ==Page N== separator format).

    Args:
        text:                    raw combined text
        noise_patterns:          exact substrings to strip out wherever they occur
                                 (document-specific headers/titles/watermarks).
                                 Defaults to [].
        remove_page_numbers:     strip built-in page number / header patterns.
        merge_lines:             merge layout-forced line breaks into full sentences.
        use_doc_paragraph_rules: use Chinese doc numbering (一、②、（一）…) to detect
                                 paragraph starts; when False each line is independent.
        to_simplified:           convert output to Simplified Chinese via OpenCC t2s.

    Returns:
        Cleaned text with [Page N] markers and double-newline paragraph breaks.
    """
    if noise_patterns is None:
        noise_patterns = []

    pages = re.split(r"={30,}\s*\nPage\s+\d+\s*\n={30,}", text)
    pages = [p.strip() for p in pages if p.strip()]

    cleaned_pages: list[str] = []
    for i, page in enumerate(pages, start=1):
        cleaned = _clean_page(
            page, noise_patterns, remove_page_numbers, merge_lines, use_doc_paragraph_rules
        )
        cleaned_pages.append(f"[Page {i}]\n\n{cleaned}")

    sep = "\n\n" + "=" * 50 + "\n"
    result = "\n\n" + "=" * 50 + "\n" + sep.join(cleaned_pages)

    if to_simplified:
        try:
            from opencc import OpenCC
        except ImportError as e:
            raise OpenCCUnavailableError("opencc-python-reimplemented is not installed") from e
        result = OpenCC("t2s").convert(result)

    return result


# ── 5. Cost calculator ────────────────────────────────────────────────────────

def calculate_cost(usage: dict, gemini_model: str) -> float:
    """Return estimated USD cost from the usage dict produced by process_file."""
    kind = usage.get("type", "")
    if kind == "native":
        return 0.0
    if "flash" in gemini_model:
        inp_price, out_price = GEMINI_FLASH_INPUT, GEMINI_FLASH_OUTPUT
    else:
        inp_price, out_price = GEMINI_PRO_INPUT, GEMINI_PRO_OUTPUT
    if kind == "gemini":
        return usage["input_tokens"] * inp_price + usage["output_tokens"] * out_price
    if kind == "cloud_vision":
        return usage["pages"] * CLOUD_VISION_PER_PAGE
    if kind == "cloud_vision→gemini":
        cv_cost     = usage["cv_pages"] * CLOUD_VISION_PER_PAGE
        gemini_cost = usage["input_tokens"] * inp_price + usage["output_tokens"] * out_price
        return cv_cost + gemini_cost
    return 0.0


# ── 6. Main orchestrator ───────────────────────────────────────────────────────

def process_file(
    pdf_path: str,
    gemini_api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
    cloud_vision_api_key: Optional[str] = None,
    use_cloud_vision: bool = False,
    noise_patterns: Optional[list[str]] = None,
    remove_page_numbers: bool = True,
    merge_lines: bool = True,
    use_doc_paragraph_rules: bool = True,
    to_simplified: bool = False,
) -> dict:
    """
    End-to-end pipeline: extract → OCR → clean.

    Cost ladder (lowest → highest):
      1. Native text layer (free)             — always tried first
      2. Cloud Vision API (cheap, printed)    — only when use_cloud_vision=True
         └─ auto-upgrades to Gemini when confidence < CONFIDENCE_THRESHOLD
            or avg chars/page < MIN_OCR_CHARS_PER_PAGE
      3. Gemini API (handles handwriting)     — default OCR path

    Args:
        pdf_path:                path to the input PDF
        gemini_api_key:          Gemini API key; required only for files that end up needing
                                 Gemini (default OCR path, or Cloud Vision quality upgrade)
        cloud_vision_api_key:    Cloud Vision API key (required when use_cloud_vision=True)
        use_cloud_vision:        set True to enable the Cloud Vision → Gemini tier
        noise_patterns:          forwarded to clean_text (document-specific headers)
        remove_page_numbers:     forwarded to clean_text
        merge_lines:             forwarded to clean_text
        use_doc_paragraph_rules: forwarded to clean_text
        to_simplified:           forwarded to clean_text

    Returns:
        {
            "text":             str,              # final cleaned output
            "path":             str,              # "native" | "cloud_vision" | "cloud_vision→gemini" | "gemini"
            "page_count":       int,
            "page_confidences": list[float]|None, # per-page scores; None for native, [] when unavailable
            "usage":            dict,             # token/page counts for cost calculation
        }
    """
    _clean = lambda raw: clean_text(
        raw, noise_patterns, remove_page_numbers, merge_lines, use_doc_paragraph_rules, to_simplified
    )

    # ── Step 1: native text layer (free) ──────────────────────────────────────
    native_text, is_sufficient = extract_native_text(pdf_path)
    if is_sufficient:
        print("Path: native text layer (no OCR needed)")
        return {
            "text": _clean(native_text),
            "path": "native",
            "page_count": _count_pages(native_text),
            "page_confidences": None,
            "usage": {"type": "native"},
        }

    # ── Step 2: Cloud Vision (optional, cheaper OCR) ──────────────────────────
    if use_cloud_vision and cloud_vision_api_key:
        cv_text, cv_page_count, page_confidences = ocr_with_cloud_vision(
            pdf_path, cloud_vision_api_key
        )
        avg_chars = len(cv_text) / cv_page_count if cv_page_count else 0
        avg_confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
        too_sparse     = avg_chars < MIN_OCR_CHARS_PER_PAGE
        low_confidence = avg_confidence > 0 and avg_confidence < CONFIDENCE_THRESHOLD

        if too_sparse or low_confidence:
            reason = "low confidence" if low_confidence else "sparse text"
            if not gemini_api_key:
                raise GeminiKeyRequiredError(
                    f"Cloud Vision quality insufficient ({reason}) and no Gemini API key was provided"
                )
            print(f"Cloud Vision quality insufficient ({reason}); upgrading to Gemini.")
            gemini_text, page_count, token_usage = ocr_with_gemini(pdf_path, gemini_api_key, gemini_model)
            return {
                "text": _clean(gemini_text),
                "path": "cloud_vision→gemini",
                "page_count": page_count,
                "page_confidences": [],
                "usage": {
                    "type": "cloud_vision→gemini",
                    "cv_pages": cv_page_count,
                    "input_tokens": token_usage["input_tokens"],
                    "output_tokens": token_usage["output_tokens"],
                },
            }

        return {
            "text": _clean(cv_text),
            "path": "cloud_vision",
            "page_count": cv_page_count,
            "page_confidences": page_confidences,
            "usage": {"type": "cloud_vision", "pages": cv_page_count},
        }

    # ── Step 3: Gemini (default OCR path) ─────────────────────────────────────
    if not gemini_api_key:
        raise GeminiKeyRequiredError("This file requires Gemini OCR, but no Gemini API key was provided")
    print("Path: Gemini OCR")
    gemini_text, page_count, token_usage = ocr_with_gemini(pdf_path, gemini_api_key, gemini_model)
    return {
        "text": _clean(gemini_text),
        "path": "gemini",
        "page_count": page_count,
        "page_confidences": [],
        "usage": {
            "type": "gemini",
            "input_tokens": token_usage["input_tokens"],
            "output_tokens": token_usage["output_tokens"],
        },
    }
