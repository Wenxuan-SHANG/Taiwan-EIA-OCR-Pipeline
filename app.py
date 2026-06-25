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

# ── Cloud Vision toggle — v1: hidden from UI, ready to wire up in v2 ──────────
USE_CLOUD_VISION = False
CLOUD_VISION_API_KEY = None

# ── Cleaning options ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 文字清洗選項")

st.markdown("**常用選項**")
remove_page_numbers = st.checkbox("去除頁碼與頁首頁尾", value=True)
merge_lines = st.checkbox("合併強制換行", value=True)
to_simplified = st.checkbox("繁體轉簡體", value=False)

with st.expander("進階清洗設定 / Advanced options"):
    use_doc_paragraph_rules = st.checkbox("啟用中文公文段落識別", value=True)
    custom_noise_raw = st.text_area(
        "自訂降噪文本",
        placeholder="每行輸入一段需去除的重複文字（如文件特定頁首）",
        help="每行輸入一段需去除的重複文字（如文件特定頁首），僅對短於 50 字的行有效",
        height=100,
    )
    show_confidence = st.checkbox("顯示各頁辨識信心分數", value=False)

noise_patterns = [l.strip() for l in custom_noise_raw.splitlines() if l.strip()]

# ── Process button ─────────────────────────────────────────────────────────────
if st.button("開始處理", type="primary", use_container_width=True):

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
                cloud_vision_api_key=CLOUD_VISION_API_KEY,
                use_cloud_vision=USE_CLOUD_VISION,
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
                label="下載 .txt",
                data=r["text"].encode("utf-8"),
                file_name=f"{stem}_cleaned.txt",
                mime="text/plain",
                key=f"dl_{i}",
            )

        st.divider()
