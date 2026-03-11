import streamlit as st
import pandas as pd
import io
from datetime import datetime
from pathlib import Path

from utils import (
    load_csv_any_encoding,
    read_excel_with_smart_header
)
from style import apply_style

st.set_page_config(page_title="Operation System - Data Upload", layout="wide")
apply_style()
st.title("Data Upload")

# 오늘 날짜 정보 (suffix용: YYMMDD)
now = datetime.now()
today_suffix = now.strftime("%y%m%d")

# 탭 구성: 분기별, 월별, 일별
tab1, tab2, tab3 = st.tabs(["분기별 데이터", "월별 데이터", "일별 데이터"])

# -------------------------------------------------------
# 공통 저장 함수
# -------------------------------------------------------
def save_uploaded_file(uploaded_file, save_path):
    try:
        file_bytes = uploaded_file.read()
        if uploaded_file.name.lower().endswith(".csv"):
            df = load_csv_any_encoding(file_bytes)
        else:
            df = read_excel_with_smart_header(file_bytes)

        # 저장 폴더 생성
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # CSV 저장
        df.to_csv(save_path, index=False, encoding="utf-8-sig")

        st.success("저장이 완료되었습니다.")
        st.info(f"저장 위치: `{save_path}`")

        with st.expander("데이터 미리보기 (상위 5행)"):
            st.dataframe(df.head(), use_container_width=True)
    except Exception as e:
        st.error(f"오류 발생: {e}")

# -------------------------------------------------------
# 탭 1: 분기별 데이터
# -------------------------------------------------------
with tab1:
    st.markdown("#### 분기별 데이터 업로드")
    st.info("저장 경로: `Datas/QuarterData/{연도}/{분기}/Data_{YYMMDD}.csv`")

    c1, c2 = st.columns(2)
    with c1:
        q_year = st.selectbox("연도", [str(y) for y in range(2023, 2041)], index=now.year - 2023, key="q_year")
    with c2:
        current_q_idx = (now.month - 1) // 3
        q_quarter = st.selectbox("분기", ["1분기", "2분기", "3분기", "4분기"], index=current_q_idx, key="q_quarter")

    q_file = st.file_uploader("분기 데이터 파일 선택", type=["xlsx", "xls", "csv"], key="q_uploader")

    if st.button("분기 데이터 저장", key="btn_save_q"):
        if q_file:
            save_path = Path("Datas") / "QuarterData" / q_year / q_quarter / f"Data_{today_suffix}.csv"
            save_uploaded_file(q_file, save_path)
        else:
            st.warning("파일을 선택해주세요.")

# -------------------------------------------------------
# 탭 2: 월별 데이터
# -------------------------------------------------------
with tab2:
    st.markdown("#### 월별 데이터 업로드")
    st.info("저장 경로: `Datas/MonthData/{연도}/{월}/Data_{YYMMDD}.csv`")

    c1, c2 = st.columns(2)
    with c1:
        m_year = st.selectbox("연도", [str(y) for y in range(2023, 2041)], index=now.year - 2023, key="m_year")
    with c2:
        m_month = st.selectbox("월", [f"{m}월" for m in range(1, 13)], index=now.month - 1, key="m_month")

    m_file = st.file_uploader("월별 데이터 파일 선택", type=["xlsx", "xls", "csv"], key="m_uploader")

    if st.button("월 데이터 저장", key="btn_save_m"):
        if m_file:
            save_path = Path("Datas") / "MonthData" / m_year / m_month / f"Data_{today_suffix}.csv"
            save_uploaded_file(m_file, save_path)
        else:
            st.warning("파일을 선택해주세요.")

# -------------------------------------------------------
# 탭 3: 일별 데이터
# -------------------------------------------------------
with tab3:
    st.markdown("#### 일별 데이터 업로드")
    st.info("저장 경로: `Datas/DailyData/{연도}/{월}/Data_{YYMMDD}.csv`")

    # 캘린더 위젯으로 날짜 선택
    selected_date = st.date_input("데이터 일자 선택", value=now, key="d_date_input")

    # 경로 구성을 위한 변수
    d_year = str(selected_date.year)
    d_month = f"{selected_date.month}월"
    d_suffix = selected_date.strftime("%y%m%d")

    d_file = st.file_uploader("일별 데이터 파일 선택", type=["xlsx", "xls", "csv"], key="d_uploader")

    if st.button("일 데이터 저장", key="btn_save_d"):
        if d_file:
            save_path = Path("Datas") / "DailyData" / d_year / d_month / f"Data_{d_suffix}.csv"
            save_uploaded_file(d_file, save_path)
        else:
            st.warning("파일을 선택해주세요.")
