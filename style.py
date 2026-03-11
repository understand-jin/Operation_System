import streamlit as st


def apply_style():
    st.markdown("""
    <style>
    /* ── 전역 폰트 ── */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', 'Malgun Gothic', system-ui, -apple-system, sans-serif;
    }

    /* ── 사이드바 ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B4080 0%, #0F2A5A 100%) !important;
        border-right: none !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li {
        color: #D6E4FF !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] a {
        color: #A8C4FF !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] a:hover {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
        border-radius: 8px;
        margin: 2px 0;
        transition: background 0.15s ease;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
        background: rgba(255,255,255,0.12) !important;
    }
    [data-testid="stSidebar"] [aria-current="page"] {
        background: rgba(255,255,255,0.18) !important;
    }
    [data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"] span {
        color: #D6E4FF !important;
    }
    [data-testid="stSidebarNav"] [aria-current="page"] span {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* ── 제목 ── */
    h1 { color: #1B4080 !important; font-weight: 700 !important; }
    h2 { color: #1B4080 !important; font-weight: 600 !important; }
    h3 { color: #2A5AA0 !important; font-weight: 600 !important; }

    /* ── 기본 버튼 ── */
    .stButton > button {
        background-color: #1B4080 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 7px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 0.5rem 1.2rem !important;
        transition: background 0.18s ease, box-shadow 0.18s ease !important;
        box-shadow: 0 2px 6px rgba(27, 64, 128, 0.18) !important;
    }
    .stButton > button:hover {
        background-color: #0F2A5A !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(27, 64, 128, 0.28) !important;
    }
    .stButton > button:disabled {
        background-color: #B0BDD4 !important;
        box-shadow: none !important;
    }

    /* ── 다운로드 버튼 ── */
    .stDownloadButton > button {
        background-color: #1B4080 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 7px !important;
        font-weight: 600 !important;
        transition: background 0.18s ease !important;
    }
    .stDownloadButton > button:hover {
        background-color: #0F2A5A !important;
        color: #FFFFFF !important;
    }

    /* ── 테두리 컨테이너 ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #C5D6EF !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 10px rgba(27, 64, 128, 0.06) !important;
        background: #FFFFFF !important;
    }

    /* ── 메트릭 카드 ── */
    [data-testid="metric-container"] {
        background: #FFFFFF !important;
        border: 1px solid #C5D6EF !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 8px rgba(27, 64, 128, 0.07) !important;
    }
    [data-testid="stMetricValue"] {
        color: #1B4080 !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #5A7AAA !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }

    /* ── 탭 ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #C5D6EF !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 7px 7px 0 0 !important;
        font-weight: 600 !important;
        color: #5A7AAA !important;
        background: #EEF4FF !important;
        border: 1px solid #C5D6EF !important;
        border-bottom: none !important;
        padding: 0.5rem 1rem !important;
        transition: background 0.15s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: #1B4080 !important;
        color: #FFFFFF !important;
        border-color: #1B4080 !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: #C5D6EF !important;
        color: #1B4080 !important;
    }
    .stTabs [aria-selected="true"]:hover {
        background: #1B4080 !important;
        color: #FFFFFF !important;
    }

    /* ── 알림 메시지 ── */
    [data-testid="stSuccess"] {
        background-color: #EAF5EA !important;
        border-left: 4px solid #2E7D32 !important;
        border-radius: 6px !important;
    }
    [data-testid="stInfo"] {
        background-color: #EEF4FF !important;
        border-left: 4px solid #1B4080 !important;
        border-radius: 6px !important;
    }
    [data-testid="stWarning"] {
        background-color: #FFF8E8 !important;
        border-left: 4px solid #E08A00 !important;
        border-radius: 6px !important;
    }
    [data-testid="stError"] {
        background-color: #FFF0F0 !important;
        border-left: 4px solid #C0392B !important;
        border-radius: 6px !important;
    }

    /* ── 데이터프레임 헤더 ── */
    [data-testid="stDataFrame"] thead th {
        background-color: #1B4080 !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    /* ── 구분선 ── */
    hr {
        border-color: #C5D6EF !important;
    }

    /* ── 페이지 링크 버튼 ── */
    [data-testid="stPageLink"] a {
        background-color: #EEF4FF !important;
        color: #1B4080 !important;
        border: 1px solid #C5D6EF !important;
        border-radius: 7px !important;
        font-weight: 600 !important;
        transition: background 0.15s ease !important;
    }
    [data-testid="stPageLink"] a:hover {
        background-color: #1B4080 !important;
        color: #FFFFFF !important;
    }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        border: 1px solid #C5D6EF !important;
        border-radius: 8px !important;
        background: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)
