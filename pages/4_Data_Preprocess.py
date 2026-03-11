import streamlit as st
import pandas as pd
import io
from utils import read_excel_with_smart_header, load_csv_any_encoding
from data_utils import aging_inventory_preprocess
from style import apply_style

st.set_page_config(page_title="재고 데이터 전처리", layout="wide")
apply_style()
st.title("재고 데이터 전처리")
st.caption("아래 5가지 파일을 업로드하면 전처리된 결과 파일을 다운로드할 수 있습니다.")

st.divider()

# ── 업로드 카드 ───────────────────────────────────────────────
UPLOAD_ITEMS = [
    ("1", "재고개요",        "standard_df", "overview"),
    ("2", "자재수불부",      "cost_df",     "ledger"),
    ("3", "배치별 유효기한", "expiration_df","expiration"),
    ("4", "3개월 매출",      "sales_df",    "sales"),
    ("5", "대분류 / 소분류", "cls_df",      "cls"),
]

cols = st.columns(5)
uploaded = {}

for col, (num, label, key, uploader_key) in zip(cols, UPLOAD_ITEMS):
    with col:
        with st.container(border=True):
            st.markdown(
                f'<p style="font-size:0.72rem; font-weight:700; color:#5A7AAA; '
                f'letter-spacing:0.08em; text-transform:uppercase; margin-bottom:0.3rem;">'
                f'파일 {num}</p>'
                f'<p style="font-size:0.95rem; font-weight:600; color:#1A2A4A; margin:0 0 0.8rem;">'
                f'{label}</p>',
                unsafe_allow_html=True,
            )
            f = st.file_uploader(
                label,
                type=["xlsx", "xls", "csv"],
                key=uploader_key,
                label_visibility="collapsed",
            )
            uploaded[key] = f
            if f:
                st.markdown(
                    f'<p style="font-size:0.8rem; color:#2E7D32; margin-top:0.4rem;">'
                    f'&#10003; {f.name}</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<p style="font-size:0.8rem; color:#B0BDD4; margin-top:0.4rem;">'
                    '파일을 선택해주세요</p>',
                    unsafe_allow_html=True,
                )

st.divider()

# ── 실행 버튼 ─────────────────────────────────────────────────
all_uploaded = all(uploaded.values())

if not all_uploaded:
    missing = [label for (_, label, key, _) in UPLOAD_ITEMS if not uploaded[key]]
    st.info(f"미업로드 파일: {', '.join(missing)}")

run = st.button("데이터 전처리 실행", disabled=not all_uploaded, use_container_width=False)


def load_file(uploaded_file):
    try:
        file_bytes = uploaded_file.read()
        if uploaded_file.name.lower().endswith(".csv"):
            return load_csv_any_encoding(file_bytes)
        else:
            return read_excel_with_smart_header(file_bytes)
    except Exception as e:
        st.error(f"{uploaded_file.name} 읽기 오류: {e}")
        return None


if run:
    with st.spinner("파일을 읽고 전처리하는 중입니다..."):
        dfs = {key: load_file(f) for key, f in uploaded.items()}

        if all(df is not None for df in dfs.values()):
            try:
                result_df = aging_inventory_preprocess(
                    cost_df=dfs["cost_df"],
                    standard_df=dfs["standard_df"],
                    expiration_df=dfs["expiration_df"],
                    sales_df=dfs["sales_df"],
                    cls_df=dfs["cls_df"],
                )

                st.success("전처리가 완료되었습니다.")

                with st.expander("결과 미리보기 (상위 5행)"):
                    st.dataframe(result_df.head(), use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    result_df.to_excel(writer, index=False, sheet_name="전처리결과")

                st.download_button(
                    label="엑셀 파일 다운로드",
                    data=output.getvalue(),
                    file_name="전처리_결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(f"전처리 중 오류가 발생했습니다: {str(e)}")
