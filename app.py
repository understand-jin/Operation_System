import streamlit as st
from style import apply_style

st.set_page_config(page_title="Operation System", layout="wide")

apply_style()

# 사이드바
st.sidebar.markdown("## Operation System")
st.sidebar.info("상단 메뉴에서 원하는 기능을 선택하세요.")

# ── 히어로 배너 ──────────────────────────────────────────────
st.markdown("""
<div style="
    background: linear-gradient(135deg, #1B4080 0%, #0F2A5A 100%);
    padding: 2.8rem 3rem;
    border-radius: 14px;
    margin-bottom: 2rem;
    box-shadow: 0 6px 24px rgba(27, 64, 128, 0.22);
">
    <div style="
        color: #A8C4FF;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    ">
        Operation Management Platform
    </div>
    <h1 style="
        color: #FFFFFF;
        font-size: 2.4rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.25;
        letter-spacing: -0.01em;
    ">
        Operation Automation System
    </h1>
    <p style="
        color: #C0D8FF;
        font-size: 1rem;
        margin-top: 0.9rem;
        margin-bottom: 0;
        line-height: 1.6;
    ">
        데이터 기반의 효율적인 운영 관리 및 자동화 분석 플랫폼입니다.
    </p>
</div>
""", unsafe_allow_html=True)

# ── 주요 기능 섹션 라벨 ──────────────────────────────────────
st.markdown("""
<p style="
    color: #5A7AAA;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
">주요 기능</p>
""", unsafe_allow_html=True)

# ── 기능 카드 ─────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    with st.container(border=True):
        st.markdown("""
        <div style="margin-bottom: 0.3rem;">
            <span style="background:#EEF4FF; color:#1B4080; font-size:0.72rem;
                font-weight:700; letter-spacing:0.06em; padding:0.22rem 0.7rem;
                border-radius:20px; text-transform:uppercase;">Data Upload</span>
        </div>
        <h3 style="margin-top:0.8rem; margin-bottom:0.5rem;">데이터 업로드</h3>
        <p style="color:#4A6080; font-size:0.92rem; line-height:1.6; margin-bottom:1rem;">
            분기별·월별·일별 데이터를 체계적으로 업로드하고 표준화된 CSV로 저장합니다.
            모든 분석 데이터의 기초가 되는 과정입니다.
        </p>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_Data_Upload.py", label="Data Upload 바로가기", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("""
        <div style="margin-bottom: 0.3rem;">
            <span style="background:#EEF4FF; color:#1B4080; font-size:0.72rem;
                font-weight:700; letter-spacing:0.06em; padding:0.22rem 0.7rem;
                border-radius:20px; text-transform:uppercase;">Inventory</span>
        </div>
        <h3 style="margin-top:0.8rem; margin-bottom:0.5rem;">재고 대사</h3>
        <p style="color:#4A6080; font-size:0.92rem; line-height:1.6; margin-bottom:1rem;">
            SAP 전산 재고와 WMS 실재고를 비교하여 차이가 발생하는 품목을
            자동 탐지하고 시각화합니다.
        </p>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Inventory_Alignment.py", label="Inventory Matching 바로가기", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("""
        <div style="margin-bottom: 0.3rem;">
            <span style="background:#EEF4FF; color:#1B4080; font-size:0.72rem;
                font-weight:700; letter-spacing:0.06em; padding:0.22rem 0.7rem;
                border-radius:20px; text-transform:uppercase;">Overseas</span>
        </div>
        <h3 style="margin-top:0.8rem; margin-bottom:0.5rem;">해외창고 재고대사</h3>
        <p style="color:#4A6080; font-size:0.92rem; line-height:1.6; margin-bottom:1rem;">
            SAP 재고와 해외 WMS 실재고를 창고별로 대사하여 수량·금액
            차이를 자동으로 산출하고 분석합니다.
        </p>
        """, unsafe_allow_html=True)
        st.page_link("pages/3_Overseas_Reconciliation.py", label="해외창고 재고대사 바로가기", use_container_width=True)

with col4:
    with st.container(border=True):
        st.markdown("""
        <div style="margin-bottom: 0.3rem;">
            <span style="background:#EEF4FF; color:#1B4080; font-size:0.72rem;
                font-weight:700; letter-spacing:0.06em; padding:0.22rem 0.7rem;
                border-radius:20px; text-transform:uppercase;">Simulation</span>
        </div>
        <h3 style="margin-top:0.8rem; margin-bottom:0.5rem;">재고 시뮬레이션</h3>
        <p style="color:#4A6080; font-size:0.92rem; line-height:1.6; margin-bottom:1rem;">
            자사 기말재고와 제조사 취소 PO를 기반으로 FEFO 방식의
            월별 소진·부진재고 시뮬레이션을 수행합니다.
        </p>
        """, unsafe_allow_html=True)
        st.page_link("pages/5_Inventory_Simulation.py", label="재고 시뮬레이션 바로가기", use_container_width=True)

st.divider()

# ── 푸터 ─────────────────────────────────────────────────────
st.markdown("""
<div style="text-align: center; color: #8A9BBB; font-size: 0.78rem; padding: 0.5rem 0 1rem;">
    © 2026 Operation Automation System &nbsp;·&nbsp; Designed for Lee Hye Jin
</div>
""", unsafe_allow_html=True)
