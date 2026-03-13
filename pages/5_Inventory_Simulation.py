import streamlit as st
import pandas as pd
import numpy as np
import io

from utils import read_excel_with_smart_header, load_csv_any_encoding
from data_utils import filter_special_stock
from style import apply_style

st.set_page_config(page_title="재고 시뮬레이션", layout="wide")
apply_style()

st.title("재고 시뮬레이션")
st.caption("자사 기말재고 및 제조사 취소 PO를 기반으로 FEFO 방식의 월별 소진 시뮬레이션을 수행합니다.")

st.divider()

# ======================================================
# 파일 업로드 섹션
# ======================================================
st.subheader("입력 파일 업로드")
st.markdown(
    '<p style="font-size:0.88rem; color:#5A7AAA; margin-bottom:1rem;">'
    "아래 4개 파일을 모두 업로드한 후 시뮬레이션을 실행하세요."
    "</p>",
    unsafe_allow_html=True,
)

UPLOAD_ITEMS = [
    ("inv",    "기말재고 Data",       "자재, 배치, 유효기간, 기말재고 수량/금액"),
    ("cls",    "분류 및 원가율",       "자재코드, 대분류, 소분류, 원가율"),
    ("rating", "평판 기준",           "자재, 평판, 평판 * 1.38배"),
    ("cancel", "제조사 취소 현황",     "제품코드, 제품명, 잔여 PO, 금액"),
]

cols = st.columns(4)
raw_files = {}

for col, (key, label, hint) in zip(cols, UPLOAD_ITEMS):
    with col:
        with st.container(border=True):
            st.markdown(
                f'<p style="font-size:0.72rem; font-weight:700; color:#5A7AAA; '
                f'letter-spacing:0.08em; text-transform:uppercase; margin-bottom:0.3rem;">'
                f'{label}</p>'
                f'<p style="font-size:0.78rem; color:#8A9BBB; margin:0 0 0.7rem;">{hint}</p>',
                unsafe_allow_html=True,
            )
            f = st.file_uploader(
                label,
                type=["xlsx", "xls", "csv"],
                key=f"sim_{key}",
                label_visibility="collapsed",
            )
            raw_files[key] = f
            if f:
                st.markdown(
                    f'<p style="font-size:0.8rem; color:#2E7D32; margin-top:0.3rem;">&#10003; {f.name}</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<p style="font-size:0.8rem; color:#B0BDD4; margin-top:0.3rem;">파일을 선택해주세요</p>',
                    unsafe_allow_html=True,
                )

st.divider()

# ======================================================
# 시뮬레이션 설정
# ======================================================
with st.expander("시뮬레이션 설정 (선택)"):
    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        start_year = st.number_input("시작 연도", min_value=2024, max_value=2040, value=2026)
        start_month = st.number_input("시작 월", min_value=1, max_value=12, value=1)
    with scol2:
        end_year = st.number_input("종료 연도", min_value=2024, max_value=2040, value=2028)
        end_month = st.number_input("종료 월", min_value=1, max_value=12, value=12)
    with scol3:
        season_codes_input = st.text_area(
            "시즌 자재코드 (줄바꿈으로 구분)",
            value="\n".join([
                "9305997","9307728","9307905","9307906","9308000","9308231",
                "9308427","9310455","9310878","9311190","9311191","9311719"
            ]),
            height=150,
        )

all_uploaded = all(raw_files.values())
if not all_uploaded:
    missing = [label for key, label, _ in UPLOAD_ITEMS if not raw_files[key]]
    st.info(f"미업로드 파일: {', '.join(missing)}")

run = st.button("시뮬레이션 실행", disabled=not all_uploaded)

# ======================================================
# Utils
# ======================================================
def load_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if uploaded_file.name.lower().endswith(".csv"):
            return load_csv_any_encoding(file_bytes)
        else:
            return read_excel_with_smart_header(file_bytes)
    except Exception as e:
        st.error(f"{uploaded_file.name} 읽기 오류: {e}")
        return None

def normalize_code_to_int_string(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.strip().str.replace(",", "", regex=False)
    num = pd.to_numeric(x, errors="coerce")
    out = x.copy()
    mask = num.notna()
    out.loc[mask] = num.loc[mask].round(0).astype("Int64").astype(str)
    out = out.replace({"nan": "", "<NA>": ""})
    return out

def pick_col(df: pd.DataFrame, candidates):
    return next((c for c in candidates if c in df.columns), None)

def download_excel(df: pd.DataFrame, filename: str, sheet_name: str = "Report"):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    st.download_button(
        label="엑셀 다운로드",
        data=buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ======================================================
# 자사 기말재고 매핑
# ======================================================
def build_mapped_inventory_df(
    inv_df, cls_df, rating_df,
    inv_code_col="자재",
    cls_code_col="자재코드",
    rating_code_col="자재",
    remove_keywords_regex="용역비|배송비",
    inv_item_candidates=("자재 내역", "자재내역", "자재명", "자재 명"),
    drop_inv_cols=("평가 유형", "플랜트", "저장위치", "특별재고"),
    cls_take_cols=("대분류", "소분류", "원가율"),
    rating_mode="both",
    dedup_by_material=False,
    set_expiry_2099_when_rating_zero=True,
):
    inv = inv_df.copy()
    cls = cls_df.copy()
    rating = rating_df.copy()

    inv_item_col = next((c for c in inv_item_candidates if c in inv.columns), None)
    if inv_item_col is not None:
        inv = inv[~inv[inv_item_col].astype(str).str.contains(remove_keywords_regex, na=False)].copy()

    inv = inv.drop(columns=[c for c in drop_inv_cols if c in inv.columns], errors="ignore")

    for need_col, df_name, df_obj in [
        (inv_code_col, "기말재고", inv),
        (cls_code_col, "기준정보", cls),
        (rating_code_col, "평판기준", rating),
    ]:
        if need_col not in df_obj.columns:
            raise ValueError(f"필수 컬럼 누락: [{df_name}]에 '{need_col}' 컬럼이 없습니다.")

    inv["_mat_key"] = normalize_code_to_int_string(inv[inv_code_col])
    cls["_mat_key"] = normalize_code_to_int_string(cls[cls_code_col])
    rating["_mat_key"] = normalize_code_to_int_string(rating[rating_code_col])

    # Category columns priority logic
    major_col = "대분류_x" if "대분류_x" in cls.columns else "대분류"
    minor_col = "소분류_x" if "소분류_x" in cls.columns else "소분류"

    # Rename before extracting take_cols to uniformly handle rest of function
    if major_col == "대분류_x" or minor_col == "소분류_x":
        rename_map = {}
        if major_col == "대분류_x": rename_map["대분류_x"] = "대분류"
        if minor_col == "소분류_x": rename_map["소분류_x"] = "소분류"
        cls = cls.rename(columns=rename_map)

    for col in cls_take_cols:
        if col not in cls.columns:
            raise ValueError(f"기준정보 파일에 '{col}' 컬럼이 없습니다.")
    cls_small = (
        cls[["_mat_key"] + list(cls_take_cols)]
        .dropna(subset=["_mat_key"])
        .drop_duplicates(subset=["_mat_key"])
    )

    if rating_mode == "both":
        rating_take_cols = ("평판", "평판 * 1.38배")
    elif rating_mode == "plain":
        rating_take_cols = ("평판",)
    elif rating_mode == "x138":
        rating_take_cols = ("평판 * 1.38배",)
    else:
        raise ValueError("rating_mode는 'both'/'plain'/'x138' 중 하나여야 합니다.")

    for col in rating_take_cols:
        if col not in rating.columns:
            raise ValueError(f"평판 기준 파일에 '{col}' 컬럼이 없습니다.")
    rating_small = (
        rating[["_mat_key"] + list(rating_take_cols)]
        .dropna(subset=["_mat_key"])
        .drop_duplicates(subset=["_mat_key"])
    )

    out = inv.merge(cls_small, on="_mat_key", how="left")

    # Dynamically handle category columns after merge
    # If '대분류' or '소분류' existed in 'inv' and also in 'cls_small', they will be suffixed with '_x' and '_y'
    # We want to use the ones from 'cls_small' (which would be '_y' if conflict, or just the column name if no conflict)
    # And rename them to the standard '대분류', '소분류'
    if "대분류_y" in out.columns:
        out["대분류"] = out["대분류_y"]
        out = out.drop(columns=["대분류_x", "대분류_y", "대분류_x_x", "대분류_x_y"], errors="ignore")
    elif "대분류_x" in out.columns and "대분류" not in out.columns: # if inv had '대분류' but cls_small didn't
        if "대분류_x" in cls_take_cols: # if renaming matched it directly
            out["대분류"] = out["대분류_x"]
        out = out.drop(columns=["대분류_x"])
    out["대분류"] = out["대분류"].fillna("미분류") if "대분류" in out.columns else "미분류"

    if "소분류_y" in out.columns:
        out["소분류"] = out["소분류_y"]
        out = out.drop(columns=["소분류_x", "소분류_y", "소분류_x_x", "소분류_x_y"], errors="ignore")
    elif "소분류_x" in out.columns and "소분류" not in out.columns: # if inv had '소분류' but cls_small didn't
        if "소분류_x" in cls_take_cols:
            out["소분류"] = out["소분류_x"]
        out = out.drop(columns=["소분류_x"])
    out["소분류"] = out["소분류"].fillna("미분류") if "소분류" in out.columns else "미분류"

    out = out.merge(rating_small, on="_mat_key", how="left")

    qty_candidates = ["기말 재고 수량", "기말수량", "재고수량", "Stock Quantity on Period End"]
    amt_candidates = ["기말 재고 금액", "기말금액", "재고금액", "Stock Amount on Period End"]
    qty_col = pick_col(out, qty_candidates)
    amt_col = pick_col(out, amt_candidates)
    if qty_col is None or amt_col is None:
        raise ValueError(f"수량/금액 컬럼을 찾지 못했습니다. qty={qty_col}, amt={amt_col}")

    out[qty_col] = pd.to_numeric(out[qty_col], errors="coerce").fillna(0.0)
    out[amt_col] = pd.to_numeric(out[amt_col], errors="coerce").fillna(0.0)

    if dedup_by_material:
        mat_key = inv_code_col if inv_code_col in out.columns else "_mat_key"
        batch_key_candidates = ("배치", "Batch", "배치번호")
        batch_key = next((c for c in batch_key_candidates if c in out.columns), None)
        group_keys = [mat_key, batch_key] if batch_key else [mat_key]
        agg_map = {qty_col: "sum", amt_col: "sum"}
        for c in out.columns:
            if c not in agg_map and c not in group_keys:
                agg_map[c] = "first"
        out = out.groupby(group_keys, as_index=False, dropna=False).agg(agg_map)

    expiry_candidates = ["유효 기한", "유효기간", "유효기한"]
    expiry_col = next((c for c in expiry_candidates if c in out.columns), None)

    for col in ["평판", "평판 * 1.38배"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    if set_expiry_2099_when_rating_zero and expiry_col is not None:
        base_rating_col = "평판 * 1.38배" if rating_mode == "x138" else ("평판" if "평판" in out.columns else None)
        if base_rating_col:
            mask_zero = out[base_rating_col].fillna(0).eq(0)
            out.loc[mask_zero, expiry_col] = pd.Timestamp("2099-12-31")

    qty_num = out[qty_col]
    amt_num = out[amt_col]

    # 단가: 자재코드별 전체 금액합 / 전체 수량합 (배치별 단가가 아닌 자재 단위 가중평균)
    mat_key_for_price = inv_code_col if inv_code_col in out.columns else "_mat_key"
    mat_totals = out.groupby(mat_key_for_price, sort=False).agg(
        _sum_amt=(amt_col, "sum"),
        _sum_qty=(qty_col, "sum"),
    )
    mat_totals["_unit_cost"] = mat_totals["_sum_amt"] / mat_totals["_sum_qty"].replace({0: np.nan})
    out["단가"] = out[mat_key_for_price].map(mat_totals["_unit_cost"])

    sales_col = "평판 * 1.38배" if rating_mode == "x138" else ("평판" if "평판" in out.columns else None)
    out["출하원가"] = pd.to_numeric(out["단가"], errors="coerce") * pd.to_numeric(out.get(sales_col, 0), errors="coerce")
    out["원가율"] = pd.to_numeric(out.get("원가율"), errors="coerce")
    out["출하판가"] = out["출하원가"] / out["원가율"].replace({0: pd.NA})
    out["판가"] = amt_num / out["원가율"].replace({0: pd.NA})
    out["who"] = "자사"
    
    if expiry_col is not None and expiry_col in out.columns:
        out[expiry_col] = pd.to_datetime(out[expiry_col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        
    return out

# ======================================================
# 제조사 취소 PO 매핑
# ======================================================
def build_mapped_cancel_po_df(
    cancel_df, cls_df, rating_df,
    inv_mapped_df=None,
    prod_code_candidates=("제품코드", "제품 코드", "자재", "자재코드"),
    prod_name_candidates=("제품명", "품명", "자재 내역", "자재명"),
    qty_candidates=("잔여 PO", "잔여PO", "잔여_PO", "수량", "잔여수량"),
    amt_candidates=("금액", "재고금액", "취소금액", "잔여금액"),
    cls_code_col="자재코드",
    rating_code_col="자재",
    cls_take_cols=("대분류", "소분류", "원가율"),
    rating_mode="plain",
    remove_keywords_regex="용역비|배송비",
    dedup_by_material=True,
    expiry_default=pd.Timestamp("2028-12-31"),
):
    base = cancel_df.copy()
    cls = cls_df.copy()
    rating = rating_df.copy()

    code_col = pick_col(base, prod_code_candidates)
    name_col = pick_col(base, prod_name_candidates)
    qty_col  = pick_col(base, qty_candidates)
    amt_col  = pick_col(base, amt_candidates)

    missing = [label for label, col in [("제품코드", code_col), ("제품명", name_col), ("잔여PO", qty_col), ("금액", amt_col)] if col is None]
    if missing:
        raise ValueError(f"[취소현황] 필수 컬럼을 찾지 못했습니다: {missing}\n현재 컬럼: {list(base.columns)}")

    base = base[~base[name_col].astype(str).str.contains(remove_keywords_regex, na=False)].copy()

    out = pd.DataFrame({
        "자재": base[code_col],
        "자재 내역": base[name_col],
        "기말 재고 수량": pd.to_numeric(base[qty_col], errors="coerce").fillna(0.0),
        "기말 재고 금액": pd.to_numeric(base[amt_col], errors="coerce").fillna(0.0),
    })

    out["_mat_key"] = normalize_code_to_int_string(out["자재"])
    cls["_mat_key"] = normalize_code_to_int_string(cls[cls_code_col])
    rating["_mat_key"] = normalize_code_to_int_string(rating[rating_code_col])

    # Category columns priority logic
    major_col = "대분류_x" if "대분류_x" in cls.columns else "대분류"
    minor_col = "소분류_x" if "소분류_x" in cls.columns else "소분류"

    if major_col == "대분류_x" or minor_col == "소분류_x":
        rename_map = {}
        if major_col == "대분류_x": rename_map["대분류_x"] = "대분류"
        if minor_col == "소분류_x": rename_map["소분류_x"] = "소분류"
        cls = cls.rename(columns=rename_map)

    cls_small = (
        cls[["_mat_key"] + list(cls_take_cols)]
        .dropna(subset=["_mat_key"])
        .drop_duplicates("_mat_key")
    )

    if rating_mode == "both":
        rating_take_cols = ("평판", "평판 * 1.38배")
    elif rating_mode == "plain":
        rating_take_cols = ("평판",)
    elif rating_mode == "x138":
        rating_take_cols = ("평판 * 1.38배",)
    else:
        raise ValueError("rating_mode는 'both'/'plain'/'x138' 중 하나여야 합니다.")

    rating_small = (
        rating[["_mat_key"] + list(rating_take_cols)]
        .dropna(subset=["_mat_key"])
        .drop_duplicates("_mat_key")
    )

    out = out.merge(cls_small, on="_mat_key", how="left")
    out = out.merge(rating_small, on="_mat_key", how="left")

    # Dynamically handle category columns after merge
    if "대분류_y" in out.columns:
        out["대분류"] = out["대분류_y"]
        out = out.drop(columns=["대분류_x", "대분류_y", "대분류_x_x", "대분류_x_y"], errors="ignore")
    elif "대분류_x" in out.columns and "대분류" not in out.columns:
        if "대분류_x" in cls_take_cols:  # It came from cls_small because of rename logic
             out["대분류"] = out["대분류_x"]
        out = out.drop(columns=["대분류_x"])
    out["대분류"] = out["대분류"].fillna("미분류") if "대분류" in out.columns else "미분류"

    if "소분류_y" in out.columns:
        out["소분류"] = out["소분류_y"]
        out = out.drop(columns=["소분류_x", "소분류_y", "소분류_x_x", "소분류_x_y"], errors="ignore")
    elif "소분류_x" in out.columns and "소분류" not in out.columns:
        if "소분류_x" in cls_take_cols:
             out["소분류"] = out["소분류_x"]
        out = out.drop(columns=["소분류_x"])
    out["소분류"] = out["소분류"].fillna("미분류") if "소분류" in out.columns else "미분류"

    out["원가율"] = pd.to_numeric(out["원가율"], errors="coerce").fillna(0.0) if "원가율" in out.columns else 0.0

    for col in ["평판", "평판 * 1.38배"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    if dedup_by_material:
        agg_map = {"기말 재고 수량": "sum", "기말 재고 금액": "sum"}
        for c in out.columns:
            if c not in agg_map and c not in ["자재", "_mat_key"]:
                agg_map[c] = "first"
        out = out.groupby("자재", as_index=False).agg(agg_map)

    out["단가"] = out["기말 재고 금액"] / out["기말 재고 수량"].replace({0: pd.NA})

    # inv_mapped_df의 단가를 자재코드 기준으로 덮어쓰기
    unmatched_df = pd.DataFrame()
    if inv_mapped_df is not None and "단가" in inv_mapped_df.columns and "자재" in inv_mapped_df.columns:
        inv_key = normalize_code_to_int_string(inv_mapped_df["자재"].astype(str))
        inv_price_map = dict(zip(inv_key, pd.to_numeric(inv_mapped_df["단가"], errors="coerce")))
        cancel_key = normalize_code_to_int_string(out["자재"].astype(str))
        matched_prices = cancel_key.map(inv_price_map)
        mask = matched_prices.notna()
        out.loc[mask, "단가"] = matched_prices.loc[mask]
        out["_단가_매칭"] = mask.map({True: "매칭", False: "미매칭"})
        unmatched_df = out.loc[~mask, ["자재", "자재 내역", "기말 재고 수량", "기말 재고 금액", "단가"]].copy()
    else:
        out["_단가_매칭"] = "inv_mapped_df 없음"

    sales_col = "평판 * 1.38배" if rating_mode == "x138" else ("평판" if "평판" in out.columns else None)
    out["출하원가"] = pd.to_numeric(out["단가"], errors="coerce") * pd.to_numeric(out.get(sales_col, 0), errors="coerce")
    out["출하판가"] = out["출하원가"] / out["원가율"].replace({0: pd.NA})
    out["판가"] = out["기말 재고 금액"] / out["원가율"].replace({0: pd.NA})
    out["유효기간"] = expiry_default
    if "유효기간" in out.columns:
        out["유효기간"] = pd.to_datetime(out["유효기간"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    out["who"] = "제조사"
    return out, unmatched_df

# ======================================================
# 대분류 소계 리포트
# ======================================================
def build_major_only_report_table(df_self, df_manu, major_col="대분류", sub_col="소분류",
                                   cost_col="기말 재고 금액", price_col="판가",
                                   self_name="자사", manu_name="제조사"):
    s = df_self.copy(); m = df_manu.copy()
    for d in [s, m]:
        if major_col not in d.columns: d[major_col] = "미분류"
        if sub_col not in d.columns:   d[sub_col] = "미분류"
    s["_who"] = self_name; m["_who"] = manu_name
    s["_cost"] = pd.to_numeric(s.get(cost_col), errors="coerce").fillna(0.0)
    m["_cost"] = pd.to_numeric(m.get(cost_col), errors="coerce").fillna(0.0)
    s["_price"] = pd.to_numeric(s.get(price_col), errors="coerce").fillna(0.0)
    m["_price"] = pd.to_numeric(m.get(price_col), errors="coerce").fillna(0.0)

    base = pd.concat([s[[major_col, sub_col, "_who", "_cost", "_price"]],
                      m[[major_col, sub_col, "_who", "_cost", "_price"]]], ignore_index=True)
    piv = base.pivot_table(index=[major_col, sub_col], columns="_who",
                            values=["_cost", "_price"], aggfunc="sum", fill_value=0.0)
    def col_name(measure, who):
        return f"{who} 원가" if measure == "_cost" else f"{who} 판가"
    piv.columns = [col_name(measure, who) for (measure, who) in piv.columns]
    piv = piv.reset_index()

    for c in [f"{self_name} 원가", f"{self_name} 판가", f"{manu_name} 원가", f"{manu_name} 판가"]:
        if c not in piv.columns: piv[c] = 0.0
    piv["합계 원가"] = piv[f"{self_name} 원가"] + piv[f"{manu_name} 원가"]
    piv["합계 판가"] = piv[f"{self_name} 판가"] + piv[f"{manu_name} 판가"]

    rows = [pd.DataFrame([{
        major_col: "총계", sub_col: "",
        f"{self_name} 원가": piv[f"{self_name} 원가"].sum(),
        f"{self_name} 판가": piv[f"{self_name} 판가"].sum(),
        f"{manu_name} 원가": piv[f"{manu_name} 원가"].sum(),
        f"{manu_name} 판가": piv[f"{manu_name} 판가"].sum(),
        "합계 원가": piv["합계 원가"].sum(),
        "합계 판가": piv["합계 판가"].sum(),
    }])]
    for maj, maj_df in piv.groupby(major_col, sort=False):
        rows.append(pd.DataFrame([{
            major_col: maj, sub_col: "소계",
            f"{self_name} 원가": maj_df[f"{self_name} 원가"].sum(),
            f"{self_name} 판가": maj_df[f"{self_name} 판가"].sum(),
            f"{manu_name} 원가": maj_df[f"{manu_name} 원가"].sum(),
            f"{manu_name} 판가": maj_df[f"{manu_name} 판가"].sum(),
            "합계 원가": maj_df["합계 원가"].sum(),
            "합계 판가": maj_df["합계 판가"].sum(),
        }]))
        rows.append(maj_df)
    final = pd.concat(rows, ignore_index=True)
    mask_detail = (final[major_col] != "총계") & (final[sub_col] != "소계")
    final.loc[mask_detail, major_col] = ""
    return final[[major_col, sub_col,
                  f"{self_name} 원가", f"{self_name} 판가",
                  f"{manu_name} 원가", f"{manu_name} 판가",
                  "합계 원가", "합계 판가"]]

# ======================================================
# FEFO 시뮬레이션
# ======================================================
def simulate_monthly_remaining_amount_fefo(
    df, start_ym=(2026, 1), end_ym=(2028, 12),
    mat_col="자재", batch_col="배치",
    expiry_candidates=("유효기간", "유효 기한", "유효기한"),
    amount_col="기말 재고 금액", burn_col="출하원가",
    season_mat_codes=None, season_months=(5, 6, 7, 8),
    col_fmt=lambda y, m: f"{str(y)[-2:]}_{m}",
):
    out = df.copy()
    if mat_col not in out.columns:
        raise KeyError(f"'{mat_col}' 컬럼이 필요합니다.")
    # 배치 컬럼이 없어도 동작 (제조사 데이터 등)
    exp_col = next((c for c in expiry_candidates if c in out.columns), None)
    if exp_col is None:
        raise KeyError(f"유효기간 컬럼이 없습니다. 후보={expiry_candidates}")

    qty_candidates_sim = ["기말 재고 수량", "기말수량", "재고수량"]
    qty_col_sim = next((c for c in qty_candidates_sim if c in out.columns), None)

    out[amount_col] = pd.to_numeric(out.get(amount_col), errors="coerce").fillna(0.0)
    out[burn_col]   = pd.to_numeric(out.get(burn_col), errors="coerce").fillna(0.0)
    out["_exp_dt"]  = pd.to_datetime(out[exp_col].astype(str).str.strip(), errors="coerce")
    out["_has_exp"] = out["_exp_dt"].notna()
    out["_cutoff_dt"] = out["_exp_dt"] - pd.DateOffset(months=6)
    out["_cut_y"] = out["_cutoff_dt"].dt.year
    out["_cut_m"] = out["_cutoff_dt"].dt.month

    season_set = set(str(x).strip() for x in (season_mat_codes or []))
    out["_is_season"] = out[mat_col].astype(str).str.strip().isin(season_set)

    # ── 배치별 월 소진량: 이미 계산된 출하원가 컨럼 직접 사용 ──
    # (각 자재코드-배치에 해당하는 실제 단가 × 평판으로 계산된 값을 그대로 사용)
    if burn_col in out.columns:
        batch_burn_map = out[burn_col].to_dict()   # {row_idx: 출하원가}
        mat_season_map = (
            out.groupby(mat_col, sort=False)["_is_season"]
            .first()
            .to_dict()
        )
    else:
        batch_burn_map = None
        mat_season_map = None
    # 배치가 여러 개일 때 가중평균 단가(총금액/총수량) × 평판으로 계산하여 배치별 단가 편차 제거
    sales_col_candidates = ["출하원가"]  # burn_col 기본값
    if qty_col_sim is not None and "평판" in out.columns:
        mat_totals = (
            out.groupby(mat_col, sort=False)
            .agg(
                _total_amt=(amount_col, "sum"),
                _total_qty=(qty_col_sim, "sum"),
                _rating=("평판", "first"),
                _is_season=("_is_season", "first"),
            )
            .reset_index()
        )
        mat_totals["_unit_cost"] = mat_totals["_total_amt"] / mat_totals["_total_qty"].replace({0: np.nan})
        mat_totals["_mat_burn"] = mat_totals["_unit_cost"] * mat_totals["_rating"]
        mat_burn_map   = mat_totals.set_index(mat_col)["_mat_burn"].to_dict()
        mat_season_map = mat_totals.set_index(mat_col)["_is_season"].to_dict()
    else:
        # 평판 컬럼 없는 경우 기존 방식 fallback
        mat_burn_map   = None
        mat_season_map = None

    months = []
    y, m = start_ym
    ey, em = end_ym
    while (y < ey) or (y == ey and m <= em):
        months.append((y, m))
        m += 1
        if m == 13: y, m = y + 1, 1

    for (yy, mm) in months:
        out[col_fmt(yy, mm)] = 0.0

    remaining = out[amount_col].to_numpy().copy()
    # FEFO 정렬: 유효기한 빠른 배치 먼저 (exp_dt ascending)
    grouped = (
        out.reset_index()
           .sort_values(by=[mat_col, "_has_exp", "_exp_dt"], ascending=[True, False, True])
           .groupby(mat_col)["index"]
           .apply(list)
           .to_dict()
    )

    for (yy, mm) in months:
        col = col_fmt(yy, mm)
        season_allowed = (mm in season_months)
        for mat, idx_list in grouped.items():
            is_season_item = bool(mat_season_map.get(mat, False)) if mat_season_map else False
            if is_season_item and not season_allowed:
                continue

            # 자재별 월 소진 예산: 첫 유효 배치의 출하원가를 공유 예산으로 사용
            first_i = next(
                (i for i in idx_list if bool(out.at[i, "_has_exp"]) and
                 float((batch_burn_map or {}).get(i, 0) if batch_burn_map else out.at[i, burn_col]) > 0),
                None
            )
            if first_i is None:
                continue

            mat_burn = float(batch_burn_map[first_i] if batch_burn_map is not None else out.at[first_i, burn_col])
            if mat_burn <= 0:
                continue

            burn_left = mat_burn   # 배치 간 공유·이월되는 예산
            for i in idx_list:
                if burn_left <= 0:
                    break
                if not bool(out.at[i, "_has_exp"]): continue
                cy = out.at[i, "_cut_y"]; cm = out.at[i, "_cut_m"]
                if pd.isna(cy) or pd.isna(cm): continue
                cy = int(cy); cm = int(cm)
                if (yy > cy) or (yy == cy and mm > cm): continue
                use = min(remaining[i], burn_left)
                if use <= 0: continue
                remaining[i] -= use
                burn_left -= use
        out.loc[out["_has_exp"], col] = remaining[out["_has_exp"].to_numpy()]

    out = out.drop(columns=["_exp_dt","_has_exp","_cutoff_dt","_cut_y","_cut_m","_is_season"], errors="ignore")
    return out


# ======================================================
# 부진재고 컬럼 추가
# ======================================================
def add_obsolete_cols_at_cutoff_6m(
    df, expiry_candidates=("유효기간", "유효 기한", "유효기한"),
    col_fmt=lambda y, m: f"{str(y)[-2:]}_{m}",
    amount_col="기말 재고 금액", burn_col="출하원가",
):
    out = df.copy()
    out["부진재고량"] = 0.0
    out["부진재고진입시점"] = 0
    out["부진재고진입분기"] = 0
    out["회전월"] = 0.0

    amt = pd.to_numeric(out.get(amount_col), errors="coerce")
    burn = pd.to_numeric(out.get(burn_col), errors="coerce")
    mask_turn = burn.notna() & (burn != 0) & amt.notna()
    out.loc[mask_turn, "회전월"] = amt.loc[mask_turn] / burn.loc[mask_turn]

    expiry_col = next((c for c in expiry_candidates if c in out.columns), None)
    if expiry_col is None: return out

    exp_dt = pd.to_datetime(out[expiry_col], errors="coerce")
    has_expiry = exp_dt.notna()
    if not has_expiry.any(): return out

    cutoff_dt = exp_dt - pd.DateOffset(months=6)
    cut_y = cutoff_dt.dt.year
    cut_m = cutoff_dt.dt.month

    for idx in out.index:
        if not has_expiry.loc[idx]: continue
        y = int(cut_y.loc[idx]); m = int(cut_m.loc[idx])
        cut_col = col_fmt(y, m)
        if cut_col not in out.columns: continue
        val = pd.to_numeric(out.at[idx, cut_col], errors="coerce")
        if pd.isna(val): continue
        out.at[idx, "부진재고량"] = float(val)
        if float(val) > 0:
            entry_dt = cutoff_dt.loc[idx]
            out.at[idx, "부진재고진입시점"] = entry_dt.strftime("%Y-%m-%d") if pd.notna(entry_dt) else ""
            q = (entry_dt.month - 1) // 3 + 1
            yy = str(entry_dt.year)[-2:]
            out.at[idx, "부진재고진입분기"] = f"{yy}년 {q}Q"
    return out

# ======================================================
# 분기 집계표
# ======================================================
def make_quarter_cols(start_year, end_year):
    cols = []
    for y in range(start_year, end_year + 1):
        yy = str(y)[-2:]
        for q in [1,2,3,4]:
            cols.append(f"{yy}년 {q}Q")
    return cols

def build_category_quarter_table(
    df, cat_cols=("대분류", "소분류"), value_col="부진재고량",
    quarter_col="부진재고진입분기", start_year=2026, end_year=2028,
    cost_col="기말 재고 금액", qty_col="기말 재고 수량",
    sales_col="평판", sales_fallback_cols=("평판 * 1.38배", "평판"),
    cost_rate_col="원가율", ship_cost_col="출하원가",
    ship_price_col="출하판가", mat_col="자재",
):
    base = df.copy()
    quarter_cols = make_quarter_cols(start_year, end_year)

    if quarter_col not in base.columns:
        raise KeyError(f"'{quarter_col}' 컬럼 없음.")
    base["_분기"] = base[quarter_col].where(base[quarter_col].isin(quarter_cols), pd.NA)

    pivot_detail = (
        base.dropna(subset=["_분기"])
        .pivot_table(index=list(cat_cols), columns="_분기", values=value_col, aggfunc="sum", fill_value=0.0)
        .reindex(columns=quarter_cols, fill_value=0.0)
    )
    pivot_detail["합계"] = pivot_detail.sum(axis=1)
    pivot_detail = pivot_detail.reset_index()

    if sales_col not in base.columns:
        found = next((c for c in sales_fallback_cols if c in base.columns), None)
        if found is None:
            raise KeyError(f"sales_col='{sales_col}'을 찾을 수 없습니다.")
        sales_col = found

    tmp = base.copy()
    for c in [cost_col, qty_col, sales_col, cost_rate_col, ship_cost_col, ship_price_col]:
        if c in tmp.columns:
            tmp[c] = pd.to_numeric(tmp[c], errors="coerce").fillna(0.0)

    mat_agg = (
        tmp.groupby(mat_col, dropna=False)
        .agg(**{
            cat_cols[0]: (cat_cols[0], "first"),
            cat_cols[1]: (cat_cols[1], "first"),
            cost_col: (cost_col, "sum"),
            qty_col: (qty_col, "sum"),
            sales_col: (sales_col, "first"),
            cost_rate_col: (cost_rate_col, "first"),
            ship_cost_col: (ship_cost_col, "first"),
            ship_price_col: (ship_price_col, "first"),
        })
        .reset_index()
    )

    kpi = (
        mat_agg.groupby(list(cat_cols), dropna=False)
        .agg(원가=(cost_col, "sum"), 출하원가=(ship_cost_col, "sum"), 출하판가=(ship_price_col, "sum"))
        .reset_index()
    )
    kpi["회전월"] = 0.0
    m_ship = kpi["출하원가"] != 0
    kpi.loc[m_ship, "회전월"] = kpi.loc[m_ship, "원가"] / kpi.loc[m_ship, "출하원가"]
    detail = kpi.merge(pivot_detail, on=list(cat_cols), how="left").fillna(0.0)

    major_kpi = (
        mat_agg.groupby(cat_cols[0], dropna=False)
        .agg(원가=(cost_col, "sum"), 출하원가=(ship_cost_col, "sum"), 출하판가=(ship_price_col, "sum"))
        .reset_index()
    )
    major_kpi["회전월"] = 0.0
    m2 = major_kpi["출하원가"] != 0
    major_kpi.loc[m2, "회전월"] = major_kpi.loc[m2, "원가"] / major_kpi.loc[m2, "출하원가"]

    major_q = (
        base.dropna(subset=["_분기"])
        .groupby([cat_cols[0], "_분기"])[value_col].sum()
        .unstack("_분기").reindex(columns=quarter_cols, fill_value=0.0).reset_index()
    )
    major_q["합계"] = major_q[quarter_cols].sum(axis=1)
    major_tbl = major_kpi.merge(major_q, on=cat_cols[0], how="left").fillna(0.0)
    major_tbl[cat_cols[1]] = "소계"

    total_cost = mat_agg[cost_col].sum()
    total_ship_cost = mat_agg[ship_cost_col].sum()
    total = pd.DataFrame([{
        cat_cols[0]: "총계", cat_cols[1]: "",
        "원가": total_cost, "출하원가": total_ship_cost,
        "출하판가": mat_agg[ship_price_col].sum(),
        "회전월": (total_cost / total_ship_cost if total_ship_cost != 0 else 0),
        **{q: base.loc[base["_분기"] == q, value_col].sum() for q in quarter_cols},
        "합계": base[value_col].sum()
    }])

    rows = [total]
    for d in major_tbl[cat_cols[0]].unique():
        rows.append(major_tbl[major_tbl[cat_cols[0]] == d])
        rows.append(detail[detail[cat_cols[0]] == d])

    final = pd.concat(rows, ignore_index=True)
    final = final[[*cat_cols, "원가", "출하원가", "출하판가", "회전월", "합계", *quarter_cols]]
    mask_detail = (final[cat_cols[0]] != "총계") & (final[cat_cols[1]] != "소계")
    final.loc[mask_detail, cat_cols[0]] = ""
    return final

# ======================================================
# 최종 보고서 병합
# ======================================================
def add_merge_keys(df, major="대분류", sub="소분류"):
    out = df.copy()
    if "소분" in out.columns and sub not in out.columns:
        out = out.rename(columns={"소분": sub})
    out["merge_major"] = out[major].replace("", np.nan).ffill()
    out["merge_sub"] = out[sub].fillna("")
    return out

def attach_cat_table(base_df, cat_df, prefix, drop_mode="cost_price_only",
                     include_ship_cols=True, major="대분류", sub="소분류"):
    ct = cat_df.copy()
    if drop_mode == "cost_price_only":
        def is_drop_col(c):
            has_cost_price = ("원가" in c) or ("판가" in c)
            if not has_cost_price: return False
            return has_cost_price and (not ("출하" in c)) if include_ship_cols else True
        drop_cols = [c for c in ct.columns if is_drop_col(c)]
    else:
        drop_cols = [c for c in ct.columns if any(k in c for k in ["원가", "판가", "출하", "회전"])]
    ct = ct.drop(columns=drop_cols, errors="ignore")
    ct = add_merge_keys(ct, major=major, sub=sub)
    value_cols = [c for c in ct.columns if c not in [major, sub, "merge_major", "merge_sub"]]
    ct_small = ct[["merge_major", "merge_sub"] + value_cols].copy()
    rename_map = {c: f"{prefix}_{c}" for c in value_cols}
    ct_small = ct_small.rename(columns=rename_map)
    renamed_cols = list(rename_map.values())
    tmp = base_df[["merge_major", "merge_sub"]].merge(ct_small, on=["merge_major", "merge_sub"], how="left")
    tmp[renamed_cols] = tmp[renamed_cols].fillna(0)
    return pd.concat([base_df, tmp[renamed_cols]], axis=1)

# ======================================================
# 시뮬레이션 실행
# ======================================================
if run:
    with st.spinner("파일을 읽는 중..."):
        inv_df    = load_file(raw_files["inv"])
        cls_df    = load_file(raw_files["cls"])
        rating_df = load_file(raw_files["rating"])
        cancel_df = load_file(raw_files["cancel"])

    if any(df is None for df in [inv_df, cls_df, rating_df, cancel_df]):
        st.stop()

    original_inv_len = len(inv_df)
    inv_df = filter_special_stock(inv_df, mat_col="자재", special_stock_col="특별 재고")
    filtered_inv_len = len(inv_df)

    st.divider()
    st.subheader("기말재고 특별재고 필터링 결과")
    st.info(f"자재코드 '1'로 시작하지 않음 & 특별재고 값 있음 → 제거됨 (원본: {original_inv_len:,.0f}건 → 적용 후: {filtered_inv_len:,.0f}건)")
    st.dataframe(inv_df, use_container_width=True)

    st.divider()
    with st.expander("업로드된 원본 데이터 확인 (미리보기)", expanded=False):
        t1, t2, t3, t4 = st.tabs(["기말재고", "분류 및 원가율", "평판 기준", "제조사 취소 현황"])
        with t1:
            st.dataframe(inv_df.head(50), use_container_width=True)
        with t2:
            st.dataframe(cls_df.head(50), use_container_width=True)
        with t3:
            st.dataframe(rating_df.head(50), use_container_width=True)
        with t4:
            st.dataframe(cancel_df.head(50), use_container_width=True)

    season_codes = [s.strip() for s in season_codes_input.strip().splitlines() if s.strip()]
    start_ym = (int(start_year), int(start_month))
    end_ym   = (int(end_year), int(end_month))

    try:
        with st.spinner("데이터 매핑 중..."):
            mapped_self_plain = build_mapped_inventory_df(inv_df, cls_df, rating_df, rating_mode="plain", dedup_by_material=True)
            mapped_self_x138  = build_mapped_inventory_df(inv_df, cls_df, rating_df, rating_mode="x138",  dedup_by_material=True)
            mapped_manu_plain, unmatched_plain = build_mapped_cancel_po_df(cancel_df, cls_df, rating_df, mapped_self_plain, rating_mode="plain", dedup_by_material=True)
            mapped_manu_x138,  unmatched_x138  = build_mapped_cancel_po_df(cancel_df, cls_df, rating_df, mapped_self_x138,  rating_mode="x138",  dedup_by_material=True)

        st.divider()
        st.subheader("매핑 결과 확인")
        tab_self, tab_manu, tab_unmatched = st.tabs(["자사 기말재고 매핑", "제조사 취소 PO 매핑", "단가 미매칭 항목"])
        with tab_self:
            st.dataframe(mapped_self_plain, use_container_width=True)
        with tab_manu:
            st.dataframe(mapped_manu_plain, use_container_width=True)
        with tab_unmatched:
            st.caption("취소 PO 자재코드가 자사 기말재고에 없어 단가를 덮어쓰지 못한 항목입니다.")
            if unmatched_plain.empty:
                st.success("모든 항목이 매칭되었습니다.")
            else:
                st.warning(f"미매칭 항목: {len(unmatched_plain)}건")
                st.dataframe(unmatched_plain, use_container_width=True)

        with st.spinner("대분류 소계 리포트 생성 중..."):
            major_report_df = build_major_only_report_table(
                df_self=mapped_self_plain, df_manu=mapped_manu_plain,
            )

        st.divider()
        st.subheader("대분류 소계 통합 리포트")
        st.dataframe(major_report_df, use_container_width=True)

        with st.spinner("FEFO 시뮬레이션 실행 중... (시간이 걸릴 수 있습니다)"):
            combined_plain = pd.concat([mapped_self_plain, mapped_manu_plain], ignore_index=True, sort=False)
            combined_x138  = pd.concat([mapped_self_x138,  mapped_manu_x138],  ignore_index=True, sort=False)

        st.divider()
        with st.expander("시뮬레이션(FEFO) 입력 데이터 확인", expanded=False):
            t1, t2 = st.tabs(["평판 기준 입력 데이터", "평판 * 1.38배 입력 데이터"])
            with t1:
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.dataframe(combined_plain, use_container_width=True)
                with col2:
                    download_excel(combined_plain, filename="fefo_input_plain.xlsx", sheet_name="InputData")
            with t2:
                col1, col2 = st.columns([8, 2])
                with col1:
                    st.dataframe(combined_x138, use_container_width=True)
                with col2:
                    download_excel(combined_x138, filename="fefo_input_x138.xlsx", sheet_name="InputData")

        with st.spinner("FEFO 시뮬레이션 실행 중... (시간이 걸릴 수 있습니다)"):
            sim_plain      = simulate_monthly_remaining_amount_fefo(combined_plain,    start_ym=start_ym, end_ym=end_ym, season_mat_codes=season_codes)
            sim_x138       = simulate_monthly_remaining_amount_fefo(combined_x138,     start_ym=start_ym, end_ym=end_ym, season_mat_codes=season_codes)
            sim_self_plain = simulate_monthly_remaining_amount_fefo(mapped_self_plain, start_ym=start_ym, end_ym=end_ym, season_mat_codes=season_codes)
            sim_self_x138  = simulate_monthly_remaining_amount_fefo(mapped_self_x138,  start_ym=start_ym, end_ym=end_ym, season_mat_codes=season_codes)

            sim_plain      = add_obsolete_cols_at_cutoff_6m(sim_plain)
            sim_x138       = add_obsolete_cols_at_cutoff_6m(sim_x138)
            sim_self_plain = add_obsolete_cols_at_cutoff_6m(sim_self_plain)
            sim_self_x138  = add_obsolete_cols_at_cutoff_6m(sim_self_x138)

        st.divider()
        st.subheader("시뮬레이션 결과 요약")
        tab_p, tab_x, tab_sp, tab_sx = st.tabs([
            "평판 (자사+제조사)", "평판 * 1.38배 (자사+제조사)",
            "평판 (자사)", "평판 * 1.38배 (자사)",
        ])
        with tab_p:
            st.dataframe(sim_plain, use_container_width=True)
        with tab_x:
            st.dataframe(sim_x138, use_container_width=True)
        with tab_sp:
            st.dataframe(sim_self_plain, use_container_width=True)
        with tab_sx:
            st.dataframe(sim_self_x138, use_container_width=True)

        with st.spinner("분기 집계표 생성 중..."):
            _sy, _ey = int(start_year), int(end_year)
            cat_table_plain      = build_category_quarter_table(sim_plain,      sales_col="평판",         start_year=_sy, end_year=_ey)
            cat_table_x138       = build_category_quarter_table(sim_x138,       sales_col="평판 * 1.38배", start_year=_sy, end_year=_ey)
            cat_table_self_plain = build_category_quarter_table(sim_self_plain,  sales_col="평판",         start_year=_sy, end_year=_ey)
            cat_table_self_x138  = build_category_quarter_table(sim_self_x138,   sales_col="평판 * 1.38배", start_year=_sy, end_year=_ey)

        st.divider()
        st.subheader("분기 집계표")
        tab_q1, tab_q2 = st.tabs(["평판 기준", "평판 * 1.38배 기준"])
        with tab_q1:
            st.dataframe(cat_table_plain, use_container_width=True)
        with tab_q2:
            st.dataframe(cat_table_x138, use_container_width=True)

        with st.spinner("최종 보고서 생성 중..."):
            mr = add_merge_keys(major_report_df)
            merged = attach_cat_table(mr,     cat_table_plain,      prefix="자사+제조사")
            merged = attach_cat_table(merged, cat_table_x138,       prefix="자사+제조사1.38배")
            merged = attach_cat_table(merged, cat_table_self_plain,  prefix="자사")
            merged = attach_cat_table(merged, cat_table_self_x138,   prefix="자사1.38배")
            merged2 = merged.drop(columns=["merge_major", "merge_sub"], errors="ignore")

            EOK = 100_000_000
            num_cols = merged2.select_dtypes(include="number").columns.tolist()
            num_cols = [c for c in num_cols if "회전" not in c]
            merged2[num_cols] = merged2[num_cols] / EOK

        st.divider()
        st.subheader("보유재고 운영 시뮬레이션 보고 (단위: 억원)")
        st.dataframe(merged2, use_container_width=True, height=900)
        download_excel(merged2, filename="보유재고_운영_시뮬레이션_보고.xlsx", sheet_name="MergedReport")

        st.success("시뮬레이션이 완료되었습니다.")

    except Exception as e:
        st.error(f"시뮬레이션 오류: {e}")
        st.exception(e)
