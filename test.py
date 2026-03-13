# -*- coding: utf-8 -*-
"""
FEFO 시뮬레이션 단계별 검증 스크립트
pages/5_Inventory_Simulation.py 의 실제 로직을 그대로 따라가며 각 단계를 출력합니다.
"""
import sys
import io
import types
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np

# ======================================================
# Streamlit mock
# ======================================================
class _FakeCtx:
    def __enter__(self): return self
    def __exit__(self, *a): pass

st_mock = types.ModuleType("streamlit")
for attr in [
    "set_page_config","title","caption","divider","subheader","info",
    "markdown","button","number_input","text_area","dataframe",
    "success","error","exception","stop","warning","download_button","write",
]:
    setattr(st_mock, attr, lambda *a, **kw: None)
st_mock.spinner   = lambda *a, **kw: _FakeCtx()
st_mock.expander  = lambda *a, **kw: _FakeCtx()
st_mock.container = lambda *a, **kw: _FakeCtx()
st_mock.columns   = lambda n, **kw: [_FakeCtx()] * (n if isinstance(n, int) else len(n))
st_mock.tabs      = lambda labels: [_FakeCtx()] * len(labels)
st_mock.file_uploader = lambda *a, **kw: None
sys.modules["streamlit"] = st_mock

style_mock = types.ModuleType("style")
style_mock.apply_style = lambda: None
sys.modules["style"] = style_mock

sys.path.insert(0, ".")
import importlib.util
spec = importlib.util.spec_from_file_location("inv_sim", "pages/5_Inventory_Simulation.py")
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

normalize_code = mod.normalize_code_to_int_string

# ======================================================
# 샘플 데이터
# ======================================================
data = {
    "자재":           ["9310458",  "9310458",  "9310458",  "9310458"],
    "배치":           ["KHA",      "LHA",      "WGA",      None    ],
    "자재 내역":      [
        "이지듀멜라비토닝앰플쿠션21호내추럴13G",
        "이지듀멜라비토닝앰플쿠션21호내추럴13G",
        "이지듀멜라비토닝앰플쿠션21호내추럴13G",
        "멜라B_토닝앰플쿠션_21내추럴_본품_13g",
    ],
    "기말 재고 수량": [2180,       12372,      1750,       137501],
    "기말 재고 금액": [11668865.4, 66223487.2, 9367208.43, 711980178.0],
    "단가":           [5352.691,   5352.691,   5352.691,   5178.0],
    "유효기간":       ["2027-08-14", "2027-08-17", "2027-07-20", "2028-12-31"],
    "원가율":         [0.228398,   0.228398,   0.228398,   0.228398],
    "대분류":         ["멜라(앰플쿠션)"] * 4,
    "소분류":         ["본품21호(13G)"] * 4,
    "평판":           [9378.2,     9378.2,     9378.2,     9378.2],
    "출하원가":       [50198602,   50198602,   50198602,   50198602],
    "출하판가":       [2.2e+08,    2.2e+08,    2.2e+08,    2.13e+08],
    "판가":           [51089956,   2.9e+08,    41012580,   3.12e+09],
    "who":            ["자사",     "자사",     "자사",     "제조사"],
}
df_raw = pd.DataFrame(data)

pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)

START_YM = (2026, 1)
END_YM   = (2028, 12)
col_fmt  = lambda y, m: f"{str(y)[-2:]}_{m}"

SEP  = "=" * 80
SEP2 = "-" * 80

# ======================================================
# ① 입력 데이터
# ======================================================
print(SEP)
print("【STEP 1】 입력 데이터")
print(SEP)
print(df_raw[["자재", "배치", "who", "기말 재고 수량", "기말 재고 금액", "유효기간", "단가", "출하원가"]].to_string(index=True))
print()

# ======================================================
# ② 전처리 (실제 시뮬레이션 로직 그대로)
# ======================================================
print(SEP)
print("【STEP 2】 전처리 — 유효기간 파싱 / cutoff 계산")
print(SEP)

out = df_raw.copy().reset_index(drop=True)
amount_col = "기말 재고 금액"
burn_col   = "출하원가"
mat_col    = "자재"
exp_col    = "유효기간"

out[amount_col] = pd.to_numeric(out[amount_col], errors="coerce").fillna(0.0)
out[burn_col]   = pd.to_numeric(out[burn_col],   errors="coerce").fillna(0.0)
out["_exp_dt"]    = pd.to_datetime(out[exp_col].astype(str).str.strip(), errors="coerce")
out["_has_exp"]   = out["_exp_dt"].notna()
out["_cutoff_dt"] = out["_exp_dt"] - pd.DateOffset(months=6)
out["_cut_y"]     = out["_cutoff_dt"].dt.year
out["_cut_m"]     = out["_cutoff_dt"].dt.month
out["_is_season"] = False

for i, row in out.iterrows():
    batch   = row.get("배치", "-") or "-"
    who     = row.get("who", "-")
    exp     = row["_exp_dt"].strftime("%Y-%m-%d") if pd.notna(row["_exp_dt"]) else "N/A"
    cutoff  = row["_cutoff_dt"].strftime("%Y-%m-%d") if pd.notna(row["_cutoff_dt"]) else "N/A"
    has_exp = row["_has_exp"]
    print(f"  [{i}] 배치={batch:>4}({who:>3})  유효기한={exp}  cutoff(판매마감-6M)={cutoff}  유효기간있음={has_exp}")
print()

# ======================================================
# ③ batch_burn_map 생성
# ======================================================
print(SEP)
print("【STEP 3】 배치별 소진 예산 맵 (batch_burn_map)")
print(SEP)

batch_burn_map = out[burn_col].to_dict()
mat_season_map = out.groupby(mat_col, sort=False)["_is_season"].first().to_dict()

for idx, burn in batch_burn_map.items():
    batch = out.at[idx, "배치"] or "None"
    who   = out.at[idx, "who"]
    print(f"  인덱스[{idx}] 배치={batch:>4}({who:>3})  출하원가={burn:>15,.0f} 원")
print()

# ======================================================
# ④ 월 목록 / FEFO 정렬
# ======================================================
print(SEP)
print("【STEP 4】 FEFO 정렬 — 자재별 배치 소진 순서")
print(SEP)

months = []
y, m = START_YM
ey, em = END_YM
while (y < ey) or (y == ey and m <= em):
    months.append((y, m))
    m += 1
    if m == 13: y, m = y + 1, 1

for (yy, mm) in months:
    out[col_fmt(yy, mm)] = 0.0

remaining = out[amount_col].to_numpy().copy()

grouped = (
    out.reset_index()
       .sort_values(by=[mat_col, "_has_exp", "_exp_dt"], ascending=[True, False, True])
       .groupby(mat_col)["index"]
       .apply(list)
       .to_dict()
)

for mat, idx_list in grouped.items():
    print(f"  자재: {mat}")
    for rank, i in enumerate(idx_list, 1):
        batch  = str(out.at[i, "배치"] or "None")
        who    = out.at[i, "who"]
        exp    = out.at[i, exp_col]
        cutoff = out.at[i, "_cutoff_dt"]
        cut_str = cutoff.strftime("%Y-%m") if pd.notna(cutoff) else "N/A"
        burn   = batch_burn_map.get(i, 0)
        amt    = remaining[i]
        print(f"    [{rank}순위] 배치={batch:>4}({who:>3})  유효기한={exp}  "
              f"판매마감={cut_str}  재고금액={amt:>15,.0f}  출하원가/월={burn:>12,.0f}")
print()

# ======================================================
# ⑤ 월별 소진 루프
# ======================================================
print(SEP)
print("【STEP 5】 월별 FEFO 소진 루프")
print(SEP)

season_months = (5, 6, 7, 8)

for (yy, mm) in months:
    col = col_fmt(yy, mm)
    season_allowed = (mm in season_months)

    # 이번 달 소진이 발생하는지 체크
    any_action = False
    log_lines  = []

    for mat, idx_list in grouped.items():
        is_season = bool(mat_season_map.get(mat, False))
        if is_season and not season_allowed:
            log_lines.append(f"    [SKIP] 자재 {mat} — 시즌 자재, {mm}월 판매 제외")
            any_action = True
            continue

        first_i = next(
            (i for i in idx_list if bool(out.at[i, "_has_exp"]) and
             float(batch_burn_map.get(i, 0)) > 0),
            None
        )
        if first_i is None:
            continue

        mat_burn = float(batch_burn_map[first_i])
        if mat_burn <= 0:
            continue

        burn_left = mat_burn
        any_action = True
        log_lines.append(f"    자재={mat}  월소진예산={mat_burn:>14,.0f} 원")

        for i in idx_list:
            if burn_left <= 0:
                break
            if not bool(out.at[i, "_has_exp"]):
                continue
            cy = out.at[i, "_cut_y"]
            cm = out.at[i, "_cut_m"]
            if pd.isna(cy) or pd.isna(cm):
                continue
            cy, cm = int(cy), int(cm)

            batch  = str(out.at[i, "배치"] or "None")
            who    = out.at[i, "who"]
            exp_s  = str(out.at[i, exp_col])
            before = remaining[i]

            if (yy > cy) or (yy == cy and mm > cm):
                if before > 0:
                    log_lines.append(
                        f"      [CUTOFF초과] 배치={batch:>4}({who:>3})  유효기한={exp_s}  "
                        f"cutoff={cy}/{cm:02d} 지남 → 부진재고"
                    )
                continue

            use = min(before, burn_left)
            if use <= 0:
                continue
            remaining[i] -= use
            burn_left    -= use
            after = remaining[i]
            log_lines.append(
                f"      [소진] 배치={batch:>4}({who:>3})  유효기한={exp_s}  "
                f"소진={use:>13,.0f}  잔량={after:>13,.0f}  남은예산={burn_left:>13,.0f}"
            )

        if burn_left > 0:
            log_lines.append(f"      ※ 예산잔여 {burn_left:,.0f} 원 (소진 가능 배치 없음)")

    if any_action:
        print(f"\n  ── {yy}년 {mm:02d}월 ──")
        for line in log_lines:
            print(line)

    out.loc[out["_has_exp"], col] = remaining[out["_has_exp"].to_numpy()]

print()

# ======================================================
# ⑥ 최종 결과
# ======================================================
out_clean = out.drop(
    columns=["_exp_dt","_has_exp","_cutoff_dt","_cut_y","_cut_m","_is_season"],
    errors="ignore"
)

month_cols = [col_fmt(y, m) for y, m in months]

print(SEP)
print("【STEP 6】 월별 잔여 금액 (전체)")
print(SEP)
show = ["자재","배치","who","기말 재고 금액","유효기간","출하원가"] + month_cols
show = [c for c in show if c in out_clean.columns]
print(out_clean[show].to_string(index=True))
print()

# 부진재고 계산 (add_obsolete_cols_at_cutoff_6m 직접 재현)
print(SEP)
print("【STEP 7】 부진재고 — cutoff 시점 잔여량")
print(SEP)

exp_dt  = pd.to_datetime(out_clean[exp_col], errors="coerce")
cutoff_ = exp_dt - pd.DateOffset(months=6)

for i in out_clean.index:
    if pd.isna(exp_dt.iloc[i]):
        continue
    cy = cutoff_.iloc[i].year
    cm = cutoff_.iloc[i].month
    cc = col_fmt(cy, cm)
    batch = str(out_clean.at[i, "배치"] or "None")
    who   = out_clean.at[i, "who"]
    exp_s = out_clean.at[i, exp_col]
    val   = float(out_clean.at[i, cc]) if cc in out_clean.columns else float("nan")
    init  = float(df_raw.at[i, amount_col])
    print(f"  [{i}] 배치={batch:>4}({who:>3})  유효기한={exp_s}  "
          f"판매마감={cy}/{cm:02d}  초기금액={init:>15,.0f}  부진재고량={val:>15,.0f}")
print()

print(SEP)
print("시뮬레이션 완료")
print(SEP)
