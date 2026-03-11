import streamlit as st
import pandas as pd
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path

from utils import (
    load_csv_any_encoding,
    read_excel_with_smart_header
)
from style import apply_style

st.set_page_config(page_title="Operation System - Inventory Matching", layout="wide")
apply_style()
st.title("Inventory Matching")

# 오늘 날짜 정보
now = datetime.now()

# -------------------------------------------------------
# 데이터 로드 함수 (저장하지 않음)
# -------------------------------------------------------
def load_uploaded_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if uploaded_file.name.lower().endswith(".csv"):
            df = load_csv_any_encoding(file_bytes)
        else:
            df = read_excel_with_smart_header(file_bytes)
        return df
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
        return None

# -------------------------------------------------------
# 1. 데이터 업로드 섹션
# -------------------------------------------------------
with st.container(border=True):
    st.subheader("일별 재고 데이터 업로드")

    col1, col2 = st.columns([1, 2])
    with col1:
        # 캘린더 위젯으로 날짜 선택
        selected_date = st.date_input("데이터 일자 선택", value=now, key="ia_date_input")
        ia_suffix = selected_date.strftime("%y%m%d")

    with col2:
        ia_file = st.file_uploader("재고 데이터 파일 업로드 (xlsx, xls, csv)", type=["xlsx", "xls", "csv"], key="ia_uploader")

    if st.button("데이터 분석 시작", key="btn_run_ia"):
        if not ia_file:
            st.warning("파일을 먼저 업로드해주세요.")
        else:
            raw_df = load_uploaded_file(ia_file)

            if raw_df is not None:
                st.success("데이터 로드 완료 (메모리에서 처리됨)")

                # -------------------------------------------------------
                # 2. 데이터 분석 (Grouping & Summing)
                # -------------------------------------------------------
                with st.spinner("데이터 분석 중..."):
                    # 컬럼명 유연하게 매칭
                    cols = raw_df.columns.tolist()

                    def find_col(target_names):
                        for name in target_names:
                            target_norm = name.replace(" ", "").lower()
                            for c in cols:
                                if c.replace(" ", "").lower() == target_norm:
                                    return c
                        return None

                    col_mat = find_col(["자재 코드", "자재코드", "자재"])
                    col_name = find_col(["자재명", "자재 명", "품명", "내역"])
                    col_sap = find_col(["SAP 재고", "SAP재고", "SAP"])
                    col_wms = find_col(["WMS 재고", "WMS재고", "WMS"])

                    if not col_mat or not col_sap or not col_wms:
                        st.error(f"필수 컬럼을 찾을 수 없습니다. (필요: 자재 코드, SAP 재고, WMS 재고)")
                        st.info(f"현재 컬럼 목록: {cols}")
                    else:
                        # (1) 데이터 정제: 자재 코드가 nan이거나 비어 있는 경우 제거
                        raw_df[col_mat] = raw_df[col_mat].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
                        raw_df = raw_df[raw_df[col_mat].notna() & (raw_df[col_mat] != "") & (raw_df[col_mat].str.lower() != "nan")]

                        if col_name:
                            raw_df[col_name] = raw_df[col_name].astype(str).str.strip()
                        else:
                            raw_df["자재명"] = "N/A"
                            col_name = "자재명"

                        raw_df[col_sap] = pd.to_numeric(raw_df[col_sap], errors="coerce").fillna(0)
                        raw_df[col_wms] = pd.to_numeric(raw_df[col_wms], errors="coerce").fillna(0)

                        # (2) 그룹화: 자재 코드 기준으로만 합산 (자재명은 첫 번째 값 사용)
                        analysis_df = raw_df.groupby(col_mat).agg({
                            col_name: 'first',
                            col_sap: 'sum',
                            col_wms: 'sum'
                        }).reset_index()

                        # 컬럼명 표준화
                        analysis_df.columns = ["자재 코드", "자재명", "SAP 총재고", "WMS 총재고"]

                        # 최종차이 계산
                        analysis_df["최종차이"] = analysis_df["SAP 총재고"] - analysis_df["WMS 총재고"]

                        # 컬럼 순서 조정: 자재 코드, 자재명, 최종차이, SAP 총재고, WMS 총재고
                        analysis_df = analysis_df[["자재 코드", "자재명", "최종차이", "SAP 총재고", "WMS 총재고"]]

                        # -------------------------------------------------------
                        # 3. 결과 분할 및 스코어카드
                        # -------------------------------------------------------
                        # SAP 우세 (최종차이 > 0)
                        sap_heavy = analysis_df[analysis_df["최종차이"] > 0].sort_values("최종차이", ascending=False).reset_index(drop=True)
                        # WMS 우세 (최종차이 < 0)
                        wms_heavy = analysis_df[analysis_df["최종차이"] < 0].sort_values("최종차이", ascending=True).reset_index(drop=True)
                        # 일치
                        matched = analysis_df[analysis_df["최종차이"] == 0].reset_index(drop=True)

                        st.divider()
                        # 요약 메트릭
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            with st.container(border=True):
                                st.metric("총 자재 수", f"{len(analysis_df):,}건")
                        with c2:
                            with st.container(border=True):
                                st.metric("SAP 전산 우세", f"{len(sap_heavy):,}건", delta_color="normal")
                        with c3:
                            with st.container(border=True):
                                st.metric("WMS 실재고 우세", f"{len(wms_heavy):,}건", delta_color="inverse")

                        # 스타일링 함수 (최종차이 색상 및 자재 코드/명 배경색 추가)
                        def get_styled_df(df, diff_color, diff_bg):
                            return df.style.set_properties(**{
                                'font-weight': 'bold',
                                'color': 'black',
                                'border': '1px solid black'
                            }).set_properties(subset=["자재 코드", "자재명"], **{
                                'background-color': '#f0f0f0'
                            }).map(lambda v: f"background-color: {diff_bg}; color: {diff_color}; font-weight: bold;", subset=["최종차이"]) \
                              .format("{:,}", subset=["최종차이", "SAP 총재고", "WMS 총재고"])

                        # 결과 섹션 (탭으로 구분)
                        tab_sap, tab_wms, tab_match = st.tabs(["SAP 전산재고 우세", "WMS 실재고 우세", "재고 일치"])

                        with tab_sap:
                            st.markdown(f"#### SAP 전산재고가 WMS보다 많은 항목 ({len(sap_heavy)}건)")
                            if sap_heavy.empty:
                                st.success("SAP 전산재고 우세 항목이 없습니다.")
                            else:
                                st.dataframe(get_styled_df(sap_heavy, "blue", "#e6f3ff"), use_container_width=True, height=400)

                        with tab_wms:
                            st.markdown(f"#### WMS 실재고가 SAP보다 많은 항목 ({len(wms_heavy)}건)")
                            if wms_heavy.empty:
                                st.success("WMS 실재고 우세 항목이 없습니다.")
                            else:
                                st.dataframe(get_styled_df(wms_heavy, "red", "#fff0f0"), use_container_width=True, height=400)

                        with tab_match:
                            st.markdown(f"#### SAP와 WMS 재고가 일치하는 항목 ({len(matched)}건)")
                            if matched.empty:
                                st.info("일치하는 항목이 없습니다.")
                            else:
                                st.dataframe(matched.style.set_properties(**{
                                    'font-weight': 'bold',
                                    'color': 'black',
                                    'border': '1px solid black'
                                }).set_properties(subset=["자재 코드", "자재명"], **{
                                    'background-color': '#f0f0f0'
                                }).format("{:,}", subset=["최종차이", "SAP 총재고", "WMS 총재고"]), use_container_width=True, height=400)

                        # -------------------------------------------------------
                        # 4. 시각화
                        # -------------------------------------------------------
                        diff_only_df = analysis_df[analysis_df["최종차이"] != 0].copy()
                        if diff_only_df.empty:
                            st.info("모든 재고가 일치합니다. 시각화할 데이터가 없습니다.")
                        else:
                            diff_only_df["abs_diff"] = diff_only_df["최종차이"].abs()
                            viz_df = diff_only_df.sort_values("abs_diff", ascending=False).head(20).copy()
                            viz_df = viz_df.reset_index(drop=True)
                            viz_df["진행번호"] = (viz_df.index + 1).astype(str)

                            fig = px.bar(
                                viz_df,
                                x="진행번호",
                                y="최종차이",
                                title="자재별 재고 차이 (SAP - WMS)",
                                color="최종차이",
                                color_continuous_scale="RdBu",
                                labels={"최종차이": "차이 수량"},
                                hover_data={
                                    "진행번호": False,
                                    "자재 코드": True,
                                    "자재명": True,
                                    "최종차이": True,
                                    "SAP 총재고": True,
                                    "WMS 총재고": True
                                },
                                text_auto=True
                            )
                            fig.update_layout(
                                xaxis_showticklabels=False,
                                xaxis_title="자재별 분석 결과 (막대에 마우스를 올리면 상세 정보가 표시됩니다)",
                                showlegend=False
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        # 다운로드 버튼
                        csv = analysis_df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            label="전체 분석 결과 CSV 다운로드",
                            data=csv,
                            file_name=f"Inventory_Matching_{ia_suffix}.csv",
                            mime="text/csv"
                        )
