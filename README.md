# Glyph OCR

**A free, no-login web tool that turns handwritten and printed PDFs into clean, searchable text — powered by Google's Gemini and Cloud Vision AI, using your own API key.**

🔗 **Live app:** https://glyph-ocr.streamlit.app

> No account. No payment. No files stored. Open-source and auditable — you don't have to trust it, you can verify it.

<details>
<summary>🇯🇵 日本語での概要（クリックして展開）</summary>

## Glyph OCR について

早稲田大学大学院での修士論文（台湾の環境影響評価制度における少数意見と熟議民主主義の研究）で、繁体字中国語の行政文書10,000ページ以上（活字・スキャン・手書きが混在）をテキスト化する必要に迫られたことが開発のきっかけです。

### 直面した課題

既存の選択肢はいずれも要件を満たしませんでした。

- **従来型OCR**（Tesseractなど）はピクセルベースの認識のため、崩し字を含む手書き中国語には対応できない。
- **汎用AIチャットツール**は手書き認識自体は可能でも、数百ページを1枚ずつ処理する運用には向かない。
- **既存の小規模OCRサイト**の多くは会員登録や決済情報の入力を求め、ファイルを不明なサーバーへ送信する。実名・署名・個人の意見を含む行政文書を扱う上で、この見えないリスクは看過できない。

### 設計思想 — コストラダー方式

ページの内容を事前に「手書きか印刷か」判定するアプローチは、判定自体にコストがかかり精度も不安定になります。そこで採用したのは**最も安価な方式から順に試し、必要な場合のみ上位の方式へ引き上げる**設計です。

1. **PyMuPDFによるネイティブ抽出**（デジタルPDFの場合、無料・API不要）
2. **Google Cloud Vision API**（印刷文字向け、低コスト）
3. **Google Gemini API**（手書き・混在文書向け、Cloud Visionでは精度不足と判定された場合に自動的に引き継ぐ）

Cloud Visionが返す信頼度スコア（confidence score）を判断基準とし、スコアが低い場合はユーザーに警告を表示、さらに低い場合はGeminiキーが提供されていれば自動的に処理を引き継ぐ、という**オートエスカレーション**の仕組みを実装しています。

### プロダクト設計における配慮

- **検証可能な信頼性**：会員登録・決済不要。コードはオープンソースで、処理はメモリ上のみで行われファイルは保存されません。APIキーはセッション内でGoogleとの通信にのみ使用されます。
- **コストの透明性**：処理時間・トークン使用量・推定コストを結果画面に明示し、無料枠と有料枠の違いも明記しています。
- **エラー時の丁寧な提示**：APIキーの権限不足やクォータ超過など、内部エラーをそのまま表示せず、利用者が理解できる文言に変換して表示します。
- **テストによる検証を重視**：コードを読むだけでなく実際にテストを行うことで、環境依存の不具合や、清洗ロジックの想定外の挙動を複数発見・修正しました。

### 使用技術

Python / Streamlit / Google Gemini API / Google Cloud Vision API / PyMuPDF / opencc

開発には Claude Code をペアプログラミングのパートナーとして活用しましたが、アーキテクチャ設計・トレードオフの判断・テスト・検証はすべて自身で行っています（AIによるコード生成を鵜呑みにせず、内容を読み解き妥当性を検証する「agentic coding」的なアプローチです）。

🔗 アプリはこちら: https://glyph-ocr.streamlit.app

</details>

---

## Why this exists

This started as a research problem, not a product idea.

My master's thesis at Waseda University analyzes over 10,000 pages of Taiwan's Environmental Impact Assessment (EIA) records — a mix of printed government documents, scanned pages, and **handwritten** meeting notes and citizen comments, almost all in **Traditional Chinese**. Before any qualitative coding could begin, every page had to become accurate, searchable text.

Existing options each failed in a specific way:

- **Conventional OCR** (e.g. Tesseract) is pixel-and-dictionary based. It collapses on scribbled Traditional-Chinese handwriting.
- **General AI chat tools** can read handwriting, but processing hundreds of pages one screenshot at a time is not a workflow.
- **Many small online OCR sites** ask you to create an account, enter payment details, or upload sensitive files to an unknown server. For documents containing **real citizens' names, signatures, and opinions**, that trust cost is unacceptable — you often can't verify where the data goes or whether the payment page is safe.

Glyph is the tool I wanted to exist: something that reads difficult Traditional-Chinese handwriting well, works in a browser without any installation, and asks for **verifiable trust, not blind trust**.

---

## What it does

Upload one or more PDFs, paste a free API key, and download clean `.txt` output — with handwriting recognition as the primary strength, not an afterthought. Recognition is powered by **Google Gemini** (for handwriting and mixed content) and **Google Cloud Vision** (for printed text).

The interface is deliberately **tool-first** (inspired by DeepL): a large upload box comes first, advanced options stay collapsed, and the core action is always one click away.

Available in **English** and **繁體中文**, switchable in the top-right corner.

---

## How it works — a cost-ladder, not a classifier

The central design decision: **don't try to guess what a file is — try the cheapest method first, and only escalate when needed.** Pre-classifying whether a page is "handwritten" is itself expensive and unreliable; a fallback ladder avoids that problem entirely.

| Step | Method | When it's used | Cost |
|------|--------|----------------|------|
| 1 | **Native text extraction** (PyMuPDF) | Digital PDFs that already contain a text layer | **Free** — no API call |
| 2 | **Google Cloud Vision** *(optional cost-saving mode)* | Bulk **printed** scans | ~1/10 the cost of Gemini |
| 3 | **Google Gemini** (Flash / Pro) | **Handwritten** or mixed content, or when Cloud Vision quality is insufficient | Priced per token |

Each engine is matched to the task it's genuinely best at — never overused, never underused.

### The auto-navigation: a confidence-driven escalation

When Cloud Vision is used, it returns a **confidence score** per page, and the app treats that score as a steering signal:

- **High confidence** → the Cloud Vision result is used as-is (cheap and fast).
- **Below the threshold** → the app flags it: *"this engine is optimized for printed text; handwriting accuracy may be lower — consider Gemini."*
- **Lower still, and a Gemini key is provided** → the file is **automatically escalated to Gemini** for a better read.

The result is a system that quietly routes each file toward the right engine on its own — cheapest-first, but never at the expense of a result the user can trust. **Why two OCR engines at all?** Because they fail differently: in testing, Cloud Vision silently dropped whole lines of handwriting that Gemini read correctly. The app doesn't hide that trade-off — it navigates around it.

---

## Design principles

These are the decisions that shaped the product, and the reasoning behind each:

**Verifiable trust, not blind trust.** The danger with unknown small tools isn't that they're small — it's that they're *black boxes*: they take your identity (sign-up), your money (payment), or your files (unknown server), and you can't check what happens next. Glyph inverts this. The code is **open-source and in this repository** — anyone can audit it. Files are processed **in memory and never stored**. Your API key is used **only within your browser session** to talk directly to Google, and is never sent to or logged by any server of mine. You don't have to take my word for any of this; you can read the code. And as a further safeguard, you can create a **restricted, disposable API key** and delete it right after use — so even in the worst case, exposure is bounded.

**Bring your own key.** Instead of the developer paying for everyone's usage — unsustainable, and the reason many "free" tools eventually add paywalls or monetize data — each user supplies their own free Google API key. This is what keeps the tool genuinely free, private, and able to stay online indefinitely.

**Honest cost transparency.** Every result shows processing time, token usage, and an estimated cost — labeled clearly as an estimate at standard paid rates, because a free-tier key within quota is typically not charged. Most tools hide this; showing it lets the user make informed decisions.

**Fail gracefully, in plain language.** When something goes wrong — a free key that can't use Gemini Pro, a quota limit, a missing engine — the app shows a short human-readable message instead of a raw error dump.

**Testing over assumptions.** Real testing (not code-reading) surfaced concrete bugs — a missing runtime dependency that disabled Cloud Vision, page-number and noise-removal rules that didn't fire on real OCR output. Each was reproduced with a minimal test before being fixed. Trusting "it should work" is how silent errors reach research data.

---

## Tech stack

- **Python** + **Streamlit** — application and UI
- **PyMuPDF** — native text-layer extraction
- **Google Cloud Vision API** — printed-text OCR
- **Google Gemini API** (Flash / Pro) — handwriting and mixed-content OCR
- **opencc** — optional Traditional → Simplified conversion
- **Streamlit Community Cloud** — hosting

Built and iterated with **Claude Code** as an AI pair-programmer, in an *agentic-coding + context-engineering* workflow — the AI writes code, but every architectural decision, trade-off, test, and verification is driven and reviewed by hand. This is not "vibe coding": the durable engineering work is reading and auditing AI-generated code, catching structural errors, and exercising judgment about what to build.

---

## How to use

1. Open **https://glyph-ocr.streamlit.app**
2. Get a free Gemini API key at https://aistudio.google.com/apikey — a Google account is enough, no credit card needed.
3. Upload your PDF(s), paste the key, click **Start Processing**, and download the `.txt` output.

*(An optional advanced mode supports Google Cloud Vision for cheaper bulk printed-document processing. For sensitive material, consider using a restricted, disposable API key.)*

---

## Honest limitations

- **Cloud Vision is weak on handwriting** — it is offered only as a cost-saver for printed documents; the app warns you when it may not be appropriate.
- **Estimated cost is an estimate.** It's computed at standard paid API rates; your actual cost depends on your key's tier and quota.
- **Severely illegible handwriting** may not be fully recoverable by any engine. Such cases are treated as a limitation of the source material — documented, not silently "corrected" by AI — to preserve research integrity.
- **Free-tier hosting sleeps** after inactivity and needs a moment to wake.

---

## Project history

- **v1** — `multilingual-ocr-tool.streamlit.app`, the first public milestone, preserved as-is.
- **v2 (Glyph OCR)** — a full redesign: tool-first interface, bilingual UI, dual-engine cost ladder, confidence-driven escalation, transparent cost reporting, and graceful error handling.


---

### Disclaimer & Privacy
- **Your files:** Uploaded files are processed in memory and deleted immediately after. They are never stored on any server controlled by this tool.
- **Third-party processing:** File content is sent to Google's Gemini API for OCR. By using this tool, you accept Google's terms of service. Do not upload documents you are not authorized to share with Google.
- **API keys:** Keys are used only within your current browser session and are never logged or transmitted to any server other than Google's.
- **OCR accuracy:** Results are not guaranteed to be error-free, especially for handwritten content. Always verify output before academic citation or publication.
- **Service availability:** This tool depends on Streamlit Community Cloud and Google Gemini API. The developer makes no guarantee of continuous availability.
- **No liability:** This tool is provided as-is. The developer assumes no responsibility for any loss, data breach, or inaccuracy arising from its use.

### Citation

If you use this tool in academic research, please acknowledge it in your methods section:

> Shang, W. (2026). *Glyph OCR: An AI-powered OCR tool for handwritten and printed Traditional Chinese documents* [Software]. GitHub. https://github.com/Wenxuan-SHANG/Taiwan-EIA-OCR-Pipeline (Live app: https://glyph-ocr.streamlit.app)

### About the developer
**Wenxuan Shang** — B.A. Peking University; currently a graduate student at Waseda University. This tool was originally developed to process approximately 10,000 pages of Traditional Chinese Environmental Impact Assessment (EIA) documents (mixed printed and handwritten) for qualitative research. It is open-sourced for use by other researchers.

Below this point is the original Colab-based OCR pipeline and the research background that this app grew out of.

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
