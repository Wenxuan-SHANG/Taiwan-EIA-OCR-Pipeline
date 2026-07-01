"""
app.py — Taiwan EIA OCR Pipeline: Streamlit web interface
"""

import os
import tempfile

import streamlit as st

from core import process_file

# ── Bilingual text registry ────────────────────────────────────────────────────
TEXTS = {
    "zh": {
        "title":    "✍️ Glyph OCR",
        "subtitle": "AI 驅動的手寫與印刷 PDF 文字辨識 · 由 Google Gemini 提供支援",
        "upload_label": "拖曳或點擊上傳，支援多個 PDF，單檔最大 500MB",
        "upload_help":  "系統將依序處理每個 PDF，電子版直接免費抽取，掃描件自動 OCR。",
        "api_key_placeholder": "貼上你的 Gemini API Key…",
        "api_key_caption": "此 Key 僅用於本次會話的 OCR 辨識，不會被儲存或上傳至任何伺服器。",
        "key_expander_label": "還沒有 key？",
        "key_guide": """\
**如何免費獲取 Gemini API Key**

① 前往 [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)（只需 Google 帳號，無需信用卡）

② 點「Create API key」→ 選「Default Gemini Project」→ 複製金鑰貼在上方

③ 免費額度：每天約 1,500 次請求；超額後當天暫停，次日自動重置，不會自動扣費

④ 隱私注意：免費額度下 Google 可能將輸入用於模型訓練，處理機密文件請使用付費帳戶

⑤ 模型說明：免費金鑰只能使用 Gemini Flash；若要使用 Gemini Pro 或提高額度，請開通付費帳戶（見下方說明）

---

**💳 如何開通 Gemini 付費帳戶**

開通付費帳戶後，同一個 API Key 自動升級，**無需重新生成 Key**。

① 前往 [Google Cloud Console](https://console.cloud.google.com/)，登入與 AI Studio 相同的 Google 帳號

② 左側選「結算 / Billing」→「建立結算帳戶」→ 填入信用卡資訊（**需要信用卡**）

③ 將結算帳戶與你的 AI Studio 專案連結

④ 完成後，原本的 Key 即自動升級為付費帳戶，可使用 Gemini Pro 並享有更高額度

Gemini Flash: ~\\$0.075 USD / 1M tokens · Gemini Pro: ~\\$1.25 USD / 1M tokens — [Google 官方定價](https://ai.google.dev/pricing)
""",
        "process_btn": "開始處理",
        "advanced_expander": "高級選項",
        "model_section_heading": "#### 🤖 模型選擇 — 適用於手寫與混合內容",
        "model_section_caption": "適用於手寫或混合內容。Flash 免費且適合大多數情況；Pro 可提升難以辨識的手寫準確度。",
        "model_options": {
            "gemini-2.5-flash（免費推薦）":      "gemini-2.5-flash",
            "gemini-2.5-pro（付費帳戶，品質更高）": "gemini-2.5-pro",
        },
        "model_selectbox_label": "Gemini 模型",
        "model_caption": "選擇 Pro 需付費帳戶金鑰，免費金鑰僅支援 Flash",
        "cost_section_heading": "#### ⚡ 進階省錢模式 — 適合批量印刷文件",
        "cost_section_caption": "僅建議批量純印刷／掃描 PDF 使用，手寫內容不需啟用。",
        "cost_desc": """\
啟用後，掃描件將優先使用 Google Cloud Vision 處理（費用約為 Gemini 的 1/10），
識別品質不足時自動升級至 Gemini。適合批量純印刷掃描件。

---

**如何獲取 Cloud Vision API Key：**

① 前往 [Google Cloud Console](https://console.cloud.google.com/)，需要 Google 帳號 + **信用卡**（這是與 Gemini 免費档最大的區別）

② 建立或選擇一個專案，啟用「Cloud Vision API」

③ 前往「API 和服務 > 憑證」，點「建立憑證 > API 金鑰」，複製後貼在下方

④ Cloud Vision 前 1,000 頁/月免費，之後約 $1.50 USD / 1,000 頁，比 Gemini 便宜約 10 倍

⑤ 詳細步驟：[https://cloud.google.com/vision/docs/setup](https://cloud.google.com/vision/docs/setup)
""",
        "cv_checkbox":        "啟用 Cloud Vision 省錢模式",
        "cv_key_placeholder": "貼上你的 Cloud Vision API Key…",
        "cleaning_section_heading": "#### 文字清洗選項",
        "cleaning_section_caption": "在 OCR 辨識完成後執行。這些選項對辨識結果進行後處理，與辨識過程本身無關。",
        "chk_remove_page_numbers": "去除頁碼與頁首頁尾",
        "chk_merge_lines":         "合併強制換行",
        "chk_to_simplified":       "繁體轉簡體",
        "chk_doc_paragraph":       "啟用中文公文段落識別",
        "chk_show_confidence":     "顯示各頁辨識信心分數",
        "noise_label":       "自訂降噪文本",
        "noise_caption":     "每行輸入一個模式，系統將精確比對，刪除獨立成行的相符內容。適合去除文件中重複出現的固定頁首或特定短語。",
        "noise_placeholder": "每行輸入一段需去除的重複文字（如文件特定頁首）",
        "noise_help":        "每行輸入一段需去除的重複文字（如文件特定頁首），僅對短於 50 字的行有效",
        # processing / results — no English equivalent in app.py; Chinese kept for both modes
        "warn_no_api_key":     "請先填入 Gemini API Key 才能開始處理。",
        "warn_no_files":       "請先上傳至少一個 PDF 檔案。",
        "progress_preparing":  "準備中…",
        "progress_file":       "正在處理第 {i} / {n} 個檔案：{name}",
        "progress_done":       "全部處理完成！",
        "success_msg":         "已完成 {n} 個檔案的處理。",
        "error_msg":           "處理失敗：{e}",
        "path_prefix":         "處理路徑：",
        "path_native":         "免費原生抽取（電子版 PDF，無需 OCR）",
        "path_gemini":         "Gemini OCR（含手寫辨識）",
        "path_cv":             "Cloud Vision OCR（印刷體）",
        "path_cv_upgrade":     "Cloud Vision 品質不足，已自動升級至 Gemini",
        "metric_pages":        "處理頁數",
        "metric_pages_suffix": "頁",
        "text_expander":       "查看文字內容",
        "conf_no_data":        "此文件為免費抽取，無置信度數據。",
        "conf_no_gemini":      "Gemini 模型不提供信心分數。",
        "conf_expander":       "各頁辨識信心分數（共 {n} 頁）",
        "conf_table_page":     "頁碼",
        "conf_table_score":    "信心分數",
        "download_btn": "下載 .txt",
        "about_expander": "關於本工具",
        "about_content": """\
**開發者**：Wenxuan Shang（北京大學畢業，現為早稻田大學在讀研究生）

**開發背景**：最初為處理台灣環境影響評估（環評）傳統中文文件而開發，現開源供研究者使用

**GitHub**：https://github.com/Wenxuan-SHANG/Taiwan-EIA-OCR-Pipeline

**引用建議**：如在學術研究中使用，請在方法論章節註明並附 GitHub 連結

**快速操作**：① 貼上 Gemini API Key → ② 上傳 PDF → ③ 點「開始處理」下載 .txt
""",
        "disclaimer": """\
**⚠️ 免責聲明**

🔒 **您的文件**：上傳的文件僅在記憶體中處理，處理完成後立即刪除，本工具不儲存任何文件內容。

🌐 **第三方處理**：文件內容將透過 Google Gemini API 傳送至 Google 進行辨識。使用本工具即表示您接受 Google 服務條款。請勿上傳您無權與 Google 共享的文件。

🔑 **API 金鑰**：金鑰僅在本次瀏覽器會話中使用，頁面關閉即失效，不會被記錄或傳送至 Google 以外的任何伺服器。

📄 **辨識準確性**：OCR 結果不保證完全正確，尤其手寫內容。學術引用前請人工核對。

⚙️ **服務可用性**：本工具依賴 Streamlit Community Cloud 及 Google Gemini API 等第三方服務，開發者不保證服務持續可用。

⚠️ **責任限制**：本工具按現狀提供，開發者不承擔因使用本工具產生的任何損失或法律責任。
""",
    },

    "en": {
        "title":    "✍️ Glyph OCR",
        "subtitle": "AI-powered OCR for handwritten & printed PDFs · Powered by Google Gemini",
        "upload_label": "Drag & drop or click, multiple PDFs supported, max 500MB each",
        "upload_help":  "系統將依序處理每個 PDF，電子版直接免費抽取，掃描件自動 OCR。",
        "api_key_placeholder": "Paste your Gemini API Key…",
        "api_key_caption": "This key is used only for the current session and is never stored or transmitted.",
        "key_expander_label": "Need a key?",
        "key_guide": """\
**How to get a free Gemini API Key**

① Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) — Google account only, no credit card needed

② Click "Create API key" → choose "Default Gemini Project" → copy and paste above

③ Free quota: ~1,500 requests/day; resets daily — no automatic charges

④ Privacy: On the free tier, Google may use your inputs for model training. Use a paid account for confidential documents.

⑤ Models: Free keys support Flash only. For Gemini Pro or higher quota, enable billing (see below).

---

**💳 How to upgrade to paid Gemini API**

After enabling billing, your existing API key upgrades automatically — **no need to create a new key**.

① Go to [Google Cloud Console](https://console.cloud.google.com/) using the same Google account as AI Studio

② Select "Billing" → "Create billing account" → enter credit card details (**credit card required**)

③ Link the billing account to your AI Studio project

④ Your existing key now supports Gemini Pro and higher quotas

Gemini Flash: ~\\$0.075 USD / 1M tokens · Gemini Pro: ~\\$1.25 USD / 1M tokens — [Google official pricing](https://ai.google.dev/pricing)
""",
        "process_btn": "Start Processing",
        "advanced_expander": "Advanced",
        "model_section_heading": "#### 🤖 Model Selection — For Handwritten & Mixed Content",
        "model_section_caption": "For handwritten or mixed content. Flash is free and sufficient for most cases; Pro improves accuracy on difficult handwriting.",
        "model_options": {
            "gemini-2.5-flash (Free · Recommended)":      "gemini-2.5-flash",
            "gemini-2.5-pro (Paid account · Higher quality)": "gemini-2.5-pro",
        },
        "model_selectbox_label": "Gemini Model",
        "model_caption": "Pro requires a paid-account key; free keys support Flash only",
        "cost_section_heading": "#### ⚡ Cost-Saving Mode — For Bulk Printed Documents",
        "cost_section_caption": "Only recommended if you have large volumes of printed/scanned PDFs. Not needed for handwritten content.",
        "cost_desc": """\
When enabled, scanned pages are first processed by Cloud Vision (≈1/10 the cost of Gemini),
and automatically upgraded to Gemini when quality is insufficient.
Best suited for bulk, printed-only scanned documents.

---

**How to get a Cloud Vision API Key:**

① Go to [Google Cloud Console](https://console.cloud.google.com/) — requires a Google account + **credit card** (this is the key difference from Gemini's free tier)

② Create or select a project, enable "Cloud Vision API"

③ Go to "APIs & Services > Credentials", click "Create Credentials > API Key", copy and paste below

④ First 1,000 pages/month free, then ~$1.50 USD per 1,000 pages — about 10x cheaper than Gemini

⑤ Full setup guide: [https://cloud.google.com/vision/docs/setup](https://cloud.google.com/vision/docs/setup)
""",
        "cv_checkbox":        "Enable Cloud Vision cost-saving mode",
        "cv_key_placeholder": "Paste your Cloud Vision API Key…",
        "cleaning_section_heading": "#### Text Cleaning Options",
        "cleaning_section_caption": "Applied after OCR is complete. These options post-process the recognized text and are independent of the OCR step itself.",
        "chk_remove_page_numbers": "Remove page numbers & headers",
        "chk_merge_lines":         "Merge line breaks",
        "chk_to_simplified":       "Traditional → Simplified Chinese",
        "chk_doc_paragraph":       "Chinese document paragraph detection",
        "chk_show_confidence":     "Show per-page confidence scores",
        "noise_label":       "Custom noise patterns",
        "noise_caption":     "Enter one pattern per line. Exact-match only — each line is removed if it appears verbatim as a standalone line in the output. Best for repeated headers or fixed phrases unique to your document.",
        "noise_placeholder": "Enter one pattern per line to remove (e.g. repeated document headers)",
        "noise_help":        "每行輸入一段需去除的重複文字（如文件特定頁首），僅對短於 50 字的行有效",
        # no English equivalent in app.py — kept as Chinese
        "warn_no_api_key":     "請先填入 Gemini API Key 才能開始處理。",
        "warn_no_files":       "請先上傳至少一個 PDF 檔案。",
        "progress_preparing":  "準備中…",
        "progress_file":       "正在處理第 {i} / {n} 個檔案：{name}",
        "progress_done":       "全部處理完成！",
        "success_msg":         "已完成 {n} 個檔案的處理。",
        "error_msg":           "處理失敗：{e}",
        "path_prefix":         "處理路徑：",
        "path_native":         "免費原生抽取（電子版 PDF，無需 OCR）",
        "path_gemini":         "Gemini OCR（含手寫辨識）",
        "path_cv":             "Cloud Vision OCR（印刷體）",
        "path_cv_upgrade":     "Cloud Vision 品質不足，已自動升級至 Gemini",
        "metric_pages":        "處理頁數",
        "metric_pages_suffix": "頁",
        "text_expander":       "查看文字內容",
        "conf_no_data":        "此文件為免費抽取，無置信度數據。",
        "conf_no_gemini":      "Gemini 模型不提供信心分數。",
        "conf_expander":       "各頁辨識信心分數（共 {n} 頁）",
        "conf_table_page":     "頁碼",
        "conf_table_score":    "信心分數",
        "download_btn": "Download .txt",
        "about_expander": "About",
        "about_content": """\
**Developer**: Wenxuan Shang (B.A. Peking University, currently a graduate student at Waseda University)

**Background**: Originally developed to process Traditional Chinese Environmental Impact Assessment documents; now open-sourced for researchers.

**GitHub**: https://github.com/Wenxuan-SHANG/Taiwan-EIA-OCR-Pipeline

**Citation**: If used in academic research, please acknowledge it in your methods section with the GitHub link.

**Quick start**: ① Paste key → ② Upload PDF → ③ Click Start, download .txt
""",
        "disclaimer": """\
**⚠️ Disclaimer & Privacy**

🔒 **Your files**: Uploaded files are processed in memory only and deleted immediately after processing. No file content is ever stored.

🌐 **Third-party processing**: File content is sent to Google via the Gemini API for OCR. By using this tool, you accept Google's terms of service. Do not upload documents you are not authorized to share with Google.

🔑 **API keys**: Used only within your current browser session. Never logged or transmitted to any server other than Google's.

📄 **OCR accuracy**: Results are not guaranteed to be error-free, especially for handwritten content. Verify before academic citation.

⚙️ **Service availability**: This tool depends on third-party services (Streamlit Community Cloud, Google Gemini API). Continuous availability is not guaranteed.

⚠️ **Liability**: This tool is provided as-is. The developer assumes no liability for any loss or inaccuracy arising from its use.
""",
    },
}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Glyph OCR",
    layout="centered",
)

# ── Language selector ──────────────────────────────────────────────────────────
if "lang_radio" not in st.session_state:
    st.session_state["lang_radio"] = "English"

_col_title, _col_lang = st.columns([3, 1])
with _col_lang:
    st.radio(
        "Language",
        ["English", "繁體中文"],
        key="lang_radio",
        horizontal=True,
        label_visibility="collapsed",
    )

T = TEXTS["en" if st.session_state.lang_radio == "English" else "zh"]

with _col_title:
    st.title(T["title"])
    st.caption(T["subtitle"])

# ── File uploader ──────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 2px solid #4A90D9 !important;
    border-radius: 14px !important;
    background-color: #F0F6FF !important;
    box-shadow: 0 2px 10px rgba(74, 144, 217, 0.15);
}
[data-testid="stFileUploader"] {
    border: 2px dashed #4A90D9;
    border-radius: 10px;
    padding: 12px 16px;
    background-color: rgba(255, 255, 255, 0.6);
}
</style>
    """,
    unsafe_allow_html=True,
)
with st.container(border=True):
    uploaded_files = st.file_uploader(
        T["upload_label"],
        type="pdf",
        accept_multiple_files=True,
        help=T["upload_help"],
    )

# ── Gemini API Key ─────────────────────────────────────────────────────────────
api_key = st.text_input(
    "Gemini API Key",
    type="password",
    placeholder=T["api_key_placeholder"],
)
st.caption(T["api_key_caption"])

with st.expander(T["key_expander_label"]):
    st.markdown(T["key_guide"])

# ── Process button ─────────────────────────────────────────────────────────────
process = st.button(T["process_btn"], type="primary", use_container_width=True)

# ── Advanced options ───────────────────────────────────────────────────────────
with st.expander(T["advanced_expander"]):

    st.markdown(T["model_section_heading"])
    st.caption(T["model_section_caption"])

    _MODEL_OPTIONS = T["model_options"]
    selected_model_label = st.selectbox(
        T["model_selectbox_label"],
        list(_MODEL_OPTIONS.keys()),
    )
    gemini_model = _MODEL_OPTIONS[selected_model_label]
    st.caption(T["model_caption"])

    st.divider()

    st.markdown(T["cost_section_heading"])
    st.caption(T["cost_section_caption"])
    st.markdown(T["cost_desc"])
    use_cloud_vision = st.checkbox(T["cv_checkbox"], value=False)
    if use_cloud_vision:
        cloud_vision_api_key = st.text_input(
            "Cloud Vision API Key",
            type="password",
            placeholder=T["cv_key_placeholder"],
        )
    else:
        cloud_vision_api_key = None

    st.divider()

    st.markdown(T["cleaning_section_heading"])
    st.caption(T["cleaning_section_caption"])

    remove_page_numbers = st.checkbox(T["chk_remove_page_numbers"], value=True)
    merge_lines = st.checkbox(T["chk_merge_lines"], value=True)
    to_simplified = st.checkbox(T["chk_to_simplified"], value=False)
    use_doc_paragraph_rules = st.checkbox(T["chk_doc_paragraph"], value=True)
    show_confidence = st.checkbox(T["chk_show_confidence"], value=False)
    st.caption(T["noise_caption"])
    custom_noise_raw = st.text_area(
        T["noise_label"],
        placeholder=T["noise_placeholder"],
        help=T["noise_help"],
        height=100,
    )

noise_patterns = [line.strip() for line in custom_noise_raw.splitlines() if line.strip()]

# ── Processing ─────────────────────────────────────────────────────────────────
if process:

    if not api_key.strip():
        st.warning(T["warn_no_api_key"])
        st.stop()

    if not uploaded_files:
        st.warning(T["warn_no_files"])
        st.stop()

    n = len(uploaded_files)
    progress = st.progress(0, text=T["progress_preparing"])
    results = []

    for idx, uploaded_file in enumerate(uploaded_files):
        progress.progress(
            idx / n,
            text=T["progress_file"].format(i=idx + 1, n=n, name=uploaded_file.name),
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        try:
            result = process_file(
                pdf_path=tmp_path,
                gemini_api_key=api_key.strip(),
                gemini_model=gemini_model,
                cloud_vision_api_key=cloud_vision_api_key,
                use_cloud_vision=use_cloud_vision,
                noise_patterns=noise_patterns,
                remove_page_numbers=remove_page_numbers,
                merge_lines=merge_lines,
                use_doc_paragraph_rules=use_doc_paragraph_rules,
                to_simplified=to_simplified,
            )
            results.append({"name": uploaded_file.name, "result": result, "error": None})
        except Exception as e:
            results.append({"name": uploaded_file.name, "result": None, "error": str(e)})
        finally:
            os.unlink(tmp_path)

    progress.progress(1.0, text=T["progress_done"])
    st.success(T["success_msg"].format(n=n))
    st.divider()

    # ── Results ────────────────────────────────────────────────────────────────
    _PATH_LABELS = {
        "native":              T["path_native"],
        "gemini":              T["path_gemini"],
        "cloud_vision":        T["path_cv"],
        "cloud_vision→gemini": T["path_cv_upgrade"],
    }

    for i, item in enumerate(results):
        st.subheader(item["name"])

        if item["error"]:
            st.error(T["error_msg"].format(e=item["error"]))
        else:
            r = item["result"]

            col1, col2 = st.columns([3, 1])
            col1.markdown(f"**{T['path_prefix']}** {_PATH_LABELS.get(r['path'], r['path'])}")
            col2.metric(T["metric_pages"], f"{r['page_count']} {T['metric_pages_suffix']}")

            with st.expander(T["text_expander"], expanded=False):
                st.text_area(
                    label="cleaned",
                    value=r["text"],
                    height=400,
                    label_visibility="collapsed",
                )

            if show_confidence:
                confs = r.get("page_confidences")
                if confs is None:
                    st.info(T["conf_no_data"])
                elif not confs:
                    st.info(T["conf_no_gemini"])
                else:
                    with st.expander(T["conf_expander"].format(n=len(confs)), expanded=False):
                        rows = "\n".join(
                            f"| Page {j} | {c:.2%} |"
                            for j, c in enumerate(confs, start=1)
                        )
                        st.markdown(
                            f"| {T['conf_table_page']} | {T['conf_table_score']} |\n|------|----------|\n{rows}"
                        )

            stem = os.path.splitext(item["name"])[0]
            st.download_button(
                label=T["download_btn"],
                data=r["text"].encode("utf-8"),
                file_name=f"{stem}_cleaned.txt",
                mime="text/plain",
                key=f"dl_{i}",
            )

        st.divider()

# ── About ──────────────────────────────────────────────────────────────────────
with st.expander(T["about_expander"]):
    st.markdown(T["about_content"])

# ── Disclaimer ─────────────────────────────────────────────────────────────────
st.markdown(T["disclaimer"])
