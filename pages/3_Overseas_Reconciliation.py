import streamlit as st
import pandas as pd
from data_utils import load_sap_data, sap_data_processing, wms_sap
from utils import read_excel_with_smart_header, load_csv_any_encoding
from style import apply_style

st.set_page_config(page_title="해외창고 재고대사", layout="wide")
apply_style()
st.title("해외 창고 재고대사")
st.divider()

# ── 파일 업로드 ────────────────────────────────────────────────
st.subheader("SAP 파일 업로드")

with st.container(border=True):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 재고개요")
        overview_file = st.file_uploader(
            "재고개요 파일 선택",
            type=["xlsx", "xls"],
            key="overview_uploader",
            label_visibility="collapsed",
        )
        if overview_file:
            st.success(f"{overview_file.name}")

    with col2:
        st.markdown("#### 자재수불부")
        ledger_file = st.file_uploader(
            "자재수불부 파일 선택",
            type=["xlsx", "xls"],
            key="ledger_uploader",
            label_visibility="collapsed",
        )
        if ledger_file:
            st.success(f"{ledger_file.name}")

# ── 공통 로더 ──────────────────────────────────────────────────
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
        st.error(f"파일 로드 오류 ({uploaded_file.name}): {e}")
        return None

# ── SAP 데이터 불러오기 ────────────────────────────────────────
if st.button("데이터 불러오기", disabled=not (overview_file and ledger_file)):
    try:
        df1 = load_uploaded_file(overview_file)
        df2 = load_uploaded_file(ledger_file)

        if df1 is None or df2 is None:
            st.stop()

        overview_df, ledger_df = load_sap_data(df1, df2)
        sap_df, check_df = sap_data_processing(overview_df, ledger_df)

        st.session_state["sap_df"]    = sap_df
        st.session_state["check_df"]  = check_df
        st.session_state["ledger_df"] = ledger_df
        st.success("데이터 로드 완료!")

    except Exception as e:
        st.error(f"오류 발생: {e}")

# ── SAP 결과 표시 ──────────────────────────────────────────────
if "sap_df" in st.session_state:
    sap_df = st.session_state["sap_df"]

    st.divider()
    st.subheader("SAP 재고 평가 결과")

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("총 품목 수", f"{len(sap_df):,}건")
    with m2:
        st.metric("총 기말재고수량", f"{sap_df['기말재고수량'].sum():,.0f}")
    with m3:
        st.metric("총 기말재고금액", f"{sap_df['기말재고금액'].sum():,.0f}원")

    st.dataframe(
        sap_df.style.format({
            "기말재고수량":  "{:,.0f}",
            "단가":         "{:,.2f}",
            "기말재고금액": "{:,.0f}",
        }),
        use_container_width=True,
        height=500,
    )

    csv_data = sap_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="SAP 재고 평가 결과 CSV 다운로드 (요약)",
        data=csv_data,
        file_name="SAP_Valuation_Summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if "check_df" in st.session_state:
        check_df = st.session_state["check_df"]
        csv_check = check_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="세부 내역 CSV 다운로드 (전체)",
            data=csv_check,
            file_name="SAP_Check_Details.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── WMS 대사 섹션 ──────────────────────────────────────────
    st.divider()
    st.subheader("WMS 재고 대사")

    with st.container(border=True):
        wms_col1, wms_col2 = st.columns([2, 1])

        with wms_col1:
            st.markdown("#### WMS 파일 업로드")
            wms_file = st.file_uploader(
                "WMS 파일 선택 (xlsx, xls, csv)",
                type=["xlsx", "xls", "csv"],
                key="wms_uploader",
                label_visibility="collapsed",
            )
            if wms_file:
                st.success(f"{wms_file.name}")

        with wms_col2:
            st.markdown("#### 창고 선택")
            WAREHOUSE_OPTIONS = [
                ("6020", "인니창고"),
                ("7020", "풀필먼트"),
                ("7070", "코스트코"),
                ("7080", "현대백화점"),
                ("6050", "홈쇼핑위탁창고(CJ)"),
                ("6060", "홈쇼핑위탁창고(GS)"),
                ("6070", "홈쇼핑위탁창고(롯데)"),
                (["6030", "7030", "7040"], "중국(통합)"),
                ("6030", "중국수출창고(6030)"),
                ("7030", "CN1_티며글로벌(7030)"),
                ("7040", "CN2_도우인글로벌(7040)"),
                ("7060", "이투마스"),
                ("7090", "아마존(JP)"),
                ("6080", "북미(직영)"),
                ("6090", "천지로지스"),
                ("7050", "북미(틱톡샵)"),
            ]
            selected = st.selectbox(
                "창고 선택",
                options=WAREHOUSE_OPTIONS,
                format_func=lambda x: f"{'+'.join(x[0]) if isinstance(x[0], list) else x[0]}  |  {x[1]}",
                key="warehouse_select",
                label_visibility="collapsed",
            )
            warehouse_code = selected[0] if selected else ""

    if st.button(
        "WMS 대사 실행",
        disabled=not (wms_file and (warehouse_code if not isinstance(warehouse_code, list) else len(warehouse_code) > 0)),
        use_container_width=True,
    ):
        try:
            wms_df = load_uploaded_file(wms_file)
            if wms_df is None:
                st.stop()

            result_df = wms_sap(sap_df, wms_df, warehouse_code)
            st.session_state["result_df"] = result_df
            st.session_state["warehouse_code"] = warehouse_code
            wh_label = "+".join(warehouse_code) if isinstance(warehouse_code, list) else warehouse_code
            st.success(f"저장위치 [{wh_label}] 대사 완료! ({len(result_df):,}건)")

        except Exception as e:
            st.error(f"오류 발생: {e}")

# ── 대사 결과 표시 ─────────────────────────────────────────────
if "result_df" in st.session_state:
    result_df = st.session_state["result_df"]
    wh_code   = st.session_state.get("warehouse_code", "")
    wh_label  = "+".join(wh_code) if isinstance(wh_code, list) else wh_code

    st.divider()
    st.subheader(f"대사 결과 — 저장위치: {wh_label}")

    # 탭별 데이터 분리 (차이금액 기준 정렬)
    sort_col = "차이금액" if "차이금액" in result_df.columns else "차이"
    df_all = result_df.sort_values(sort_col, ascending=True)  # 전체: 오름차순
    if "차이" in result_df.columns:
        df_pos = result_df[result_df["차이"] > 0].sort_values(sort_col, ascending=False)
        df_neg = result_df[result_df["차이"] < 0].sort_values(sort_col, ascending=True)
    else:
        df_pos = result_df.iloc[0:0]
        df_neg = result_df.iloc[0:0]

    def show_scorecard_and_table(df):
        """스코어카드 + 데이터프레임 표시 헬퍼"""
        sum_cols = ["SAP금액", "WMS금액", "차이", "차이금액"]
        df_calc = df.copy()
        for col in sum_cols:
            if col in df_calc.columns:
                df_calc[col] = pd.to_numeric(df_calc[col], errors="coerce").fillna(0)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("총 수", f"{len(df):,}건")
        if "SAP금액" in df_calc.columns:
            c2.metric("SAP금액 합계", f"{df_calc['SAP금액'].sum():,.2f}원")
        if "WMS금액" in df_calc.columns:
            c3.metric("WMS금액 합계", f"{df_calc['WMS금액'].sum():,.2f}원")
        if "차이" in df_calc.columns:
            c4.metric("차이 합계", f"{df_calc['차이'].sum():,.0f}")
        if "차이금액" in df_calc.columns:
            c5.metric("차이금액 합계", f"{df_calc['차이금액'].sum():,.2f}원")

        st.dataframe(
            df.style.format({
                "WMS수량": "{:,.0f}",
                "SAP수량": "{:,.0f}",
                "WMS금액": "{:,.2f}",
                "SAP금액": "{:,.2f}",
                "차이": "{:,.0f}",
                "차이금액": "{:,.2f}",
                "단가": "{:,.2f}"
            }),
            use_container_width=True,
            height=500
        )

    tab_all, tab_pos, tab_neg = st.tabs([
        f"전체 ({len(result_df):,}건)",
        f"양수 ({len(df_pos):,}건)",
        f"음수 ({len(df_neg):,}건)",
    ])

    with tab_all:
        show_scorecard_and_table(df_all)
    with tab_pos:
        show_scorecard_and_table(df_pos)
    with tab_neg:
        show_scorecard_and_table(df_neg)

    # CSV 다운로드용 데이터프레임 (쉼표 포함)
    csv_df = result_df.copy()
    qty_cols = ["WMS수량", "SAP수량", "차이"]
    amt_cols = []

    for col in qty_cols:
        if col in csv_df.columns:
            csv_df[col] = csv_df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")

    for col in amt_cols:
        if col in csv_df.columns:
            csv_df[col] = csv_df[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")

    csv_result = csv_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"대사 결과 CSV 다운로드 (저장위치: {wh_code})",
        data=csv_result,
        file_name=f"WMS_SAP_Reconcile_{wh_code}.csv",
        mime="text/csv",
        use_container_width=True,
    )
