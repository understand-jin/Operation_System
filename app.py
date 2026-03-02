import streamlit as st

st.set_page_config(page_title="Operation_System", layout="wide")

# 사이드바 레이아웃 최적화
st.sidebar.markdown("# 🚀 메뉴")
st.sidebar.info("상단 메뉴에서 원하는 기능을 선택하세요.")

# 메인 타이틀 및 소개
st.markdown("""
<div style="text-align: center; padding: 2rem 0rem;">
    <h1 style="font-size: 3.5rem; font-weight: 800; color: #1E1E1E;">⚙️ Operation Automation System</h1>
    <p style="font-size: 1.2rem; color: #555;">데이터 기반의 효율적인 관리 및 분석을 위한 자동화 시스템입니다.</p>
</div>
""", unsafe_allow_html=True)

st.divider()

# 주요 기능 카드 레이아웃
st.subheader("💡 주요 기능 안내")

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### 📥 Data Upload")
        st.write("분기별/월별/일별 데이터를 체계적으로 업로드하고 표준화된 CSV로 저장합니다. 모든 분석 데이터의 기초가 되는 과정입니다.")
        st.page_link("pages/1_Data_Upload.py", label="Data Upload로 이동", icon="📥", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("### ⚖️ Inventory Matching")
        st.write("SAP 전산 재고와 WMS 실재고를 비교하여 차이가 발생하는 품목을 자동 탐지하고 시각화합니다.")
        st.page_link("pages/2_Inventory_Alignment.py", label="Inventory Matching으로 이동", icon="⚖️", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("### 🌏 해외창고 재고대사")
        st.write("SAP 재고와 해외 WMS 실재고를 창고별로 대사하여 수량·금액 차이를 자동으로 산출하고 분석합니다.")
        st.page_link("pages/3_Overseas_Reconciliation.py", label="해외창고 재고대사로 이동", icon="🌏", use_container_width=True)

st.divider()

# 하단 푸터
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8rem; padding-top: 2rem;">
    © 2026 Operation_System Dashboard | Designed for Lee Hye Jin
</div>
""", unsafe_allow_html=True)
