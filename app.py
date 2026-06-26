"""
app.py — Taiwan EIA OCR Pipeline: Streamlit web interface
"""

import os
import tempfile

import streamlit as st

from core import process_file

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="多語言 PDF 文字辨識工具",
    layout="centered",
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("多語言 PDF 文字辨識工具")
st.caption("Multilingual PDF OCR & Text Cleaning Tool")
st.markdown(
    """
    上傳任意 PDF，自動以最低成本辨識文字——電子版直接免費抽取，掃描件使用 AI OCR。
    文字清洗功能專為中文優化，亦支援英文、日文等多語言辨識。
    輸出結果可直接匯入 NVivo 等質性分析工具。

    Upload any PDF for automatic text extraction at the lowest possible cost —
    digital PDFs are extracted for free; scanned documents use AI OCR.
    Text cleaning is optimized for Chinese but OCR supports any language including English and Japanese.
    """
)

st.divider()

# ── Gemini API Key ─────────────────────────────────────────────────────────────
st.info(
    """
**如何免費獲取 Gemini API Key / How to get a free Gemini API Key**

① 前往 https://aistudio.google.com/apikey（只需 Google 帳號，無需信用卡）
② 點「Create API key」→ 選「Default Gemini Project」→ 複製金鑰貼在下方
③ 免費額度：每天約 1,500 次請求；超額後當天暫停，次日自動重置，不會自動扣費
④ 隱私注意：免費額度下 Google 可能將輸入用於模型訓練，處理機密文件請使用付費帳戶

① Go to https://aistudio.google.com/apikey — Google account only, no credit card needed
② Click "Create API key" → choose "Default Gemini Project" → copy and paste below
③ Free quota: ~1,500 requests/day; stops when exceeded, resets next day — no automatic charges
④ Privacy note: On the free tier, Google may use your inputs for model training. Use a paid account for confidential documents.
    """
)

api_key = st.text_input(
    "Gemini API Key",
    type="password",
    placeholder="貼上你的 Gemini API Key…",
)
st.caption(
    "此 Key 僅用於本次會話的 OCR 辨識，不會被儲存或上傳至任何伺服器。"
    " / This key is used only for the current session and is never stored or transmitted."
)

st.divider()

# ── File uploader ──────────────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "上傳 PDF 文件（可多選 / multiple files supported）",
    type="pdf",
    accept_multiple_files=True,
    help="支援一次上傳多個 PDF 檔案，系統將逐一處理。",
)

st.info(
    """
**輸出格式 / Output format**

處理完成後輸出 .txt 純文字檔 / Output is plain .txt files, suitable for:
NVivo・Atlas.ti・文本挖掘 / text mining・語料庫分析 / corpus analysis・任何需要純文字的工具 / any plain-text workflow
    """
)

# ── Cleaning options ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 文字清洗選項 / Text Cleaning Options")

# ── Gemini model selection ─────────────────────────────────────────────────────
_MODEL_OPTIONS = {
    "gemini-2.5-flash（免費推薦 / Free · Recommended）": "gemini-2.5-flash",
    "gemini-2.5-pro（付費帳戶，品質更高 / Paid account · Higher quality）": "gemini-2.5-pro",
}
selected_model_label = st.selectbox(
    "Gemini 模型 / Gemini Model",
    list(_MODEL_OPTIONS.keys()),
)
gemini_model = _MODEL_OPTIONS[selected_model_label]

st.markdown("**常用選項 / Common Options**")
remove_page_numbers = st.checkbox("去除頁碼與頁首頁尾 / Remove page numbers & headers", value=True)
merge_lines = st.checkbox("合併強制換行 / Merge line breaks", value=True)
to_simplified = st.checkbox("繁體轉簡體 / Traditional → Simplified Chinese", value=False)

with st.expander("進階清洗設定 / Advanced options"):
    use_doc_paragraph_rules = st.checkbox(
        "啟用中文公文段落識別 / Chinese document paragraph detection", value=True
    )
    custom_noise_raw = st.text_area(
        "自訂降噪文本 / Custom noise patterns",
        placeholder="每行輸入一段需去除的重複文字（如文件特定頁首）",
        help="每行輸入一段需去除的重複文字（如文件特定頁首），僅對短於 50 字的行有效",
        height=100,
    )
    show_confidence = st.checkbox(
        "顯示各頁辨識信心分數 / Show per-page confidence scores", value=False
    )

with st.expander("⚡ 進階省錢模式 / Cost-Saving Mode（需 Google Cloud Vision API）"):
    st.markdown(
        """
啟用後，掃描件將優先使用 Google Cloud Vision 處理（費用約為 Gemini 的 1/10），
識別品質不足時自動升級至 Gemini。適合批量純印刷掃描件。

需要 Google Cloud 帳號並開通 Vision API：https://cloud.google.com/vision/docs/setup

When enabled, scanned pages are first processed by Cloud Vision (≈1/10 the cost of Gemini),
and automatically upgraded to Gemini when quality is insufficient.
Best suited for bulk, printed-only scanned documents.

Requires a Google Cloud account with Vision API enabled: https://cloud.google.com/vision/docs/setup
        """
    )
    use_cloud_vision = st.checkbox(
        "啟用 Cloud Vision 省錢模式 / Enable Cloud Vision cost-saving mode",
        value=False,
    )
    if use_cloud_vision:
        cloud_vision_api_key = st.text_input(
            "Cloud Vision API Key",
            type="password",
            placeholder="貼上你的 Cloud Vision API Key…",
        )
    else:
        cloud_vision_api_key = None

noise_patterns = [line.strip() for line in custom_noise_raw.splitlines() if line.strip()]

# ── Process button ─────────────────────────────────────────────────────────────
if st.button("開始處理 / Start Processing", type="primary", use_container_width=True):

    if not api_key.strip():
        st.warning("請先填入 Gemini API Key 才能開始處理。")
        st.stop()

    if not uploaded_files:
        st.warning("請先上傳至少一個 PDF 檔案。")
        st.stop()

    n = len(uploaded_files)
    progress = st.progress(0, text="準備中…")
    results = []

    for idx, uploaded_file in enumerate(uploaded_files):
        progress.progress(
            idx / n,
            text=f"正在處理第 {idx + 1} / {n} 個檔案：{uploaded_file.name}",
        )

        # Save the uploaded bytes to a temp file; process_file needs a path
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

    progress.progress(1.0, text="全部處理完成！")
    st.success(f"已完成 {n} 個檔案的處理。")
    st.divider()

    # ── Results ────────────────────────────────────────────────────────────────
    _PATH_LABELS = {
        "native":              "免費原生抽取（電子版 PDF，無需 OCR）",
        "gemini":              "Gemini OCR（含手寫辨識）",
        "cloud_vision":        "Cloud Vision OCR（印刷體）",
        "cloud_vision→gemini": "Cloud Vision 品質不足，已自動升級至 Gemini",
    }

    for i, item in enumerate(results):
        st.subheader(item["name"])

        if item["error"]:
            st.error(f"處理失敗：{item['error']}")
        else:
            r = item["result"]

            col1, col2 = st.columns([3, 1])
            col1.markdown(f"**處理路徑：** {_PATH_LABELS.get(r['path'], r['path'])}")
            col2.metric("處理頁數", f"{r['page_count']} 頁")

            with st.expander("查看文字內容", expanded=False):
                st.text_area(
                    label="cleaned",
                    value=r["text"],
                    height=400,
                    label_visibility="collapsed",
                )

            if show_confidence:
                confs = r.get("page_confidences")
                if confs is None:
                    st.info("此文件為免費抽取，無置信度數據。")
                elif not confs:
                    st.info("Gemini 模型不提供信心分數。")
                else:
                    with st.expander(f"各頁辨識信心分數（共 {len(confs)} 頁）", expanded=False):
                        rows = "\n".join(
                            f"| Page {j} | {c:.2%} |"
                            for j, c in enumerate(confs, start=1)
                        )
                        st.markdown(
                            f"| 頁碼 | 信心分數 |\n|------|----------|\n{rows}"
                        )

            stem = os.path.splitext(item["name"])[0]
            st.download_button(
                label="下載 .txt / Download .txt",
                data=r["text"].encode("utf-8"),
                file_name=f"{stem}_cleaned.txt",
                mime="text/plain",
                key=f"dl_{i}",
            )

        st.divider()

# ── About ──────────────────────────────────────────────────────────────────────
with st.expander("關於本工具 / About"):
    st.markdown(
        """
**開發者**：Wenxuan Shang｜北京大學畢業，現為早稻田大學在讀研究生

**開發背景**：最初為處理約一萬頁台灣環評傳統中文文件（含印刷體與手寫體）而開發，現開源供研究者使用

**GitHub**：https://github.com/Wenxuan-SHANG/Taiwan-EIA-OCR-Pipeline

**引用建議**：如在學術研究中使用本工具，請在方法論章節註明並附上 GitHub 連結

**快速操作（3 步）**：① 貼上 Gemini API Key → ② 上傳 PDF → ③ 點「開始處理 / Start Processing」→ 下載 .txt
    """
    )

# ── Disclaimer ─────────────────────────────────────────────────────────────────
st.warning(
    """
**免責聲明 / Disclaimer & Privacy**

🔒 **您的文件**：上傳的文件僅在記憶體中處理，處理完成後立即刪除，本工具不儲存任何文件內容。
🌐 **第三方處理**：文件內容將透過 Google Gemini API 傳送至 Google 進行辨識。使用本工具即表示您接受 Google 服務條款。請勿上傳您無權與 Google 共享的文件。
🔑 **API 金鑰**：金鑰僅在本次瀏覽器會話中使用，頁面關閉即失效，不會被記錄或傳送至 Google 以外的任何伺服器。
📄 **辨識準確性**：OCR 結果不保證完全正確，尤其手寫內容。學術引用前請人工核對。
⚙️ **服務可用性**：本工具依賴 Streamlit Community Cloud 及 Google Gemini API 等第三方服務，開發者不保證服務持續可用。
⚠️ **責任限制**：本工具按現狀提供，開發者不承擔因使用本工具產生的任何損失或法律責任。

🔒 **Your files**: Uploaded files are processed in memory only and deleted immediately after processing. No file content is ever stored.
🌐 **Third-party processing**: File content is sent to Google via the Gemini API for OCR. By using this tool, you accept Google's terms of service. Do not upload documents you are not authorized to share with Google.
🔑 **API keys**: Used only within your current browser session. Never logged or transmitted to any server other than Google's.
📄 **OCR accuracy**: Results are not guaranteed to be error-free, especially for handwritten content. Verify before academic citation.
⚙️ **Service availability**: This tool depends on third-party services (Streamlit Community Cloud, Google Gemini API). Continuous availability is not guaranteed.
⚠️ **Liability**: This tool is provided as-is. The developer assumes no liability for any loss or inaccuracy arising from its use.
    """
)
