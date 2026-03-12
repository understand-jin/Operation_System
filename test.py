# -*- coding: utf-8 -*-
"""
FEFO 시뮬레이션 검증 스크립트
스크린샷 데이터를 입력으로, 매월/매 배치별 소진 과정을 상세 출력합니다.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np

# ======================================================
# 샘플 데이터 (실제 데이터 기반)
# 자재 9310458 — 이지듀멜라비토닝앰플쿠션21호내추럴13G
# 자사 배치 3개 (KHA, LHA, WGA) + 제조사 1개
# ======================================================
# data = {
#     "자재":           ["9310458",  "9310458",  "9310458",  "9310458"],
#     "배치":           ["KHA",      "LHA",      "WGA",      None    ],   # None = 제조사
#     "자재 내역":      [
#         "이지듀멜라비토닝앰플쿠션21호내추럴13G",
#         "이지듀멜라비토닝앰플쿠션21호내추럴13G",
#         "이지듀멜라비토닝앰플쿠션21호내추럴13G",
#         "멜라B_토닝앰플쿠션_21내추럴_본품_13g",
#     ],
#     "특별 재고":      ["T",        "",         "",         ""],
#     "저장 위치":      [5000,       5000,       5000,       None],
#     "기말 재고 수량": [2180,       12372,      1750,       137501],
#     "기말 재고 금액": [11668865.4, 66223487.2, 9367208.43, 711980178.0],
#     "단가":           [5352.691,   5352.691,   5352.691,   5178.0],
#     "유효기간":       ["2027-08-14", "2027-08-17", "2027-07-20", "2028-12-31"],
#     "남은일":         [521,        524,        496,        None],
#     "유효기한구간":   ["1년 이상", "1년 이상", "1년 이상", None],
#     "3평판":          [1736.667,   1736.667,   1736.667,   None],
#     "_mat_key":       ["9310458",  "9310458",  "9310458",  None],
#     "원가율":         [0.228398,   0.228398,   0.228398,   0.228398],
#     "대분류":         ["멜라(앰플쿠션)", "멜라(앰플쿠션)", "멜라(앰플쿠션)", "멜라(앰플쿠션)"],
#     "소분류":         ["본품21호(13G)", "본품21호(13G)", "본품21호(13G)", "본품21호(13G)"],
#     "평판":           [9378.2,     9378.2,     9378.2,     9378.2],
#     "출하원가":       [50198602,   50198602,   50198602,   48560320],
#     "출하판가":       [2.2e+08,    2.2e+08,    2.2e+08,    2.13e+08],
#     "판가":           [51089956,   2.9e+08,    41012580,   3.12e+09],
#     "who":            ["자사",     "자사",     "자사",     "제조사"],
# }

# 신규 제공 데이터
data = {
    "자재":           ["9310593"],
    "기말 재고 수량": [54895],
    "기말 재고 금액": [320577148],
    "자재 내역":      ["[EA]이지듀멜라비토닝원데이앰플로즈30ml"],
    "특별 재고":      [""],
    "저장 위치":      [5000],
    "배치":           ["BDA"],
    "단가":           [5839.824],
    "유효기간":       ["2028-04-30"],
    "남은일":         [781],
    "유효기한구간":   ["1년 이상"],
    "3평판":          [257],
    "_mat_key":       ["9310593"],
    "원가율":         [0.278841],
    "대분류":         ["로즈"],
    "소분류":         ["앰플 30ml"],
    "평판":           [999.7],
    "출하원가":       [5838072],
    "출하판가":       [20936945],
    "판가":           [1149678476.37717],
    "who":            ["자사"],
}

df_raw = pd.DataFrame(data)

print("=" * 70)
print("【입력 데이터】")
print("=" * 70)
pd.set_option("display.float_format", lambda x: f"{x:,.0f}")
print(df_raw[["자재", "배치", "기말 재고 수량", "기말 재고 금액", "유효기간", "단가", "출하원가", "who"]].to_string(index=False))
print()

# ======================================================
# FEFO 시뮬레이션 (verbose 버전)
# ======================================================
def simulate_fefo_verbose(
    df,
    start_ym=(2026, 1),
    end_ym=(2027, 12),
    mat_col="자재",
    expiry_candidates=("유효기간", "유효 기한", "유효기한"),
    amount_col="기말 재고 금액",
    burn_col="출하원가",
    qty_col="기말 재고 수량",
    season_mat_codes=None,
    season_months=(5, 6, 7, 8),
    col_fmt=lambda y, m: f"{str(y)[-2:]}_{m}",
    verbose=True,
):
    out = df.copy().reset_index(drop=True)
    exp_col = next((c for c in expiry_candidates if c in out.columns), None)
    if exp_col is None:
        raise KeyError(f"유효기간 컬럼 없음. 후보={expiry_candidates}")

    out[amount_col] = pd.to_numeric(out[amount_col], errors="coerce").fillna(0.0)
    out[burn_col]   = pd.to_numeric(out[burn_col],   errors="coerce").fillna(0.0)
    out["_exp_dt"]  = pd.to_datetime(out[exp_col].astype(str).str.strip(), errors="coerce")
    out["_has_exp"] = out["_exp_dt"].notna()
    out["_cutoff_dt"] = out["_exp_dt"] - pd.DateOffset(months=6)
    out["_cut_y"] = out["_cutoff_dt"].dt.year
    out["_cut_m"] = out["_cutoff_dt"].dt.month

    season_set = set(str(x).strip() for x in (season_mat_codes or []))
    out["_is_season"] = out[mat_col].astype(str).str.strip().isin(season_set)

    # ── 배치별 월 소진량: 이미 계산된 출하원가 컬럼 직접 사용 ──
    # (가중평균이 아닌, 각 자재코드-배치에 해당하는 단가 × 평판)
    if burn_col in out.columns:
        # 배치 행 인덱스 → 출하원가 맵
        batch_burn_map = out[burn_col].to_dict()          # {row_idx: 출하원가}
        # 자재별 시즌 여부는 첫 번째 배치 기준
        mat_season_map = (
            out.groupby(mat_col, sort=False)["_is_season"]
            .first()
            .to_dict()
        )
        mat_burn_map = None   # 배치별 사용으로 전환
    else:
        batch_burn_map = None
        mat_burn_map   = None
        mat_season_map = None

    # ── 월 목록 생성 ──
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

    # ── FEFO 정렬: 유효기한 오름차순 (이른 것 먼저) ──
    grouped = (
        out.reset_index()
           .sort_values(by=[mat_col, "_has_exp", "_exp_dt"], ascending=[True, False, True])
           .groupby(mat_col)["index"]
           .apply(list)
           .to_dict()
    )

    if verbose:
        print("=" * 70)
        print("【FEFO 정렬 결과 (각 자재별 배치 소진 순서)】")
        print("=" * 70)
        for mat, idx_list in grouped.items():
            print(f"\n  자재: {mat}")
            for rank, i in enumerate(idx_list, 1):
                batch   = out.at[i, "배치"] if "배치" in out.columns else "-"
                who     = out.at[i, "who"]  if "who"  in out.columns else "-"
                exp     = out.at[i, exp_col]
                cutoff  = out.at[i, "_cutoff_dt"]
                amt     = remaining[i]
                print(f"    [{rank}순위] 배치={batch}({who})  유효기한={exp}  "
                      f"판매마감(cutoff)={cutoff.strftime('%Y-%m-%d') if pd.notna(cutoff) else 'N/A'}  "
                      f"재고금액={amt:>15,.0f} 원")
        print()

    # ── 월별 소진 루프 ──
    prev_batch_per_mat = {}   # 배치 전환 감지용

    for (yy, mm) in months:
        col = col_fmt(yy, mm)
        season_allowed = (mm in season_months)

        if verbose:
            print("=" * 70)
            print(f"  【{yy}년 {mm}월 소진 시작】")
            print("=" * 70)

        for mat, idx_list in grouped.items():
            is_season = bool(mat_season_map.get(mat, False)) if mat_season_map else False

            if is_season and not season_allowed:
                if verbose:
                    print(f"  [SKIP] 자재 {mat} — 시즌 자재, {mm}월 판매 제외")
                continue

            # ── 자재별 월 소진 예산: 첫 유효 배치의 출하원가를 공유 예산으로 사용 ──
            first_i = next(
                (i for i in idx_list if bool(out.at[i, "_has_exp"]) and
                 (batch_burn_map is not None and float(batch_burn_map.get(i, 0)) > 0 or
                  batch_burn_map is None and float(out.at[i, burn_col]) > 0)),
                None
            )
            if first_i is None:
                continue

            mat_burn = float(batch_burn_map[first_i] if batch_burn_map is not None else out.at[first_i, burn_col])
            if mat_burn <= 0:
                continue

            burn_left = mat_burn   # 배치 간 공유·이월되는 예산
            if verbose:
                print(f"\n  자재 {mat}  월소진예산={mat_burn:,.0f} 원")

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

                batch   = out.at[i, "배치"] if "배치" in out.columns else "-"
                who     = out.at[i, "who"]  if "who"  in out.columns else "-"
                exp_str = str(out.at[i, exp_col])
                before  = remaining[i]

                # cutoff 지난 배치는 스킵 (부진재고 판정)
                if (yy > cy) or (yy == cy and mm > cm):
                    if verbose and before > 0:
                        print(f"    [SKIP] 배치={batch}({who})  유효기한={exp_str}  "
                              f"cutoff={cy}/{cm} 이미 지남 → 부진재고 처리")
                    continue

                use = min(before, burn_left)
                if use <= 0:
                    continue

                remaining[i] -= use
                burn_left    -= use
                after = remaining[i]

                if verbose:
                    # 배치 전환 감지
                    prev = prev_batch_per_mat.get(mat)
                    switch_msg = ""
                    if prev is not None and prev != (batch, who):
                        switch_msg = f"  ★ 배치 전환! [{prev[0]}({prev[1]})] → [{batch}({who})]"
                    prev_batch_per_mat[mat] = (batch, who)

                    print(f"    [소진] 배치={batch}({who})  유효기한={exp_str}  "
                          f"소진={use:>13,.0f}  잔량={after:>13,.0f}  "
                          f"남은예산={burn_left:>13,.0f}{switch_msg}")

            if verbose and burn_left > 0:
                print(f"    ※ 소진 예산 잔여: {burn_left:,.0f} 원 (소진 가능 배치 없음)")

        out.loc[out["_has_exp"], col] = remaining[out["_has_exp"].to_numpy()]

    out = out.drop(
        columns=["_exp_dt", "_has_exp", "_cutoff_dt", "_cut_y", "_cut_m", "_is_season"],
        errors="ignore",
    )

    # ── 결과 요약 ──
    month_cols = [col_fmt(y, m) for (y, m) in months]
    summary_cols = (
        ["자재", "배치", "who", "기말 재고 금액", exp_col]
        + [c for c in ["출하원가"] if c in out.columns]
        + [c for c in month_cols if c in out.columns]
    )
    summary_cols = [c for c in summary_cols if c in out.columns]

    if verbose:
        print()
        print("=" * 70)
        print("【시뮬레이션 결과 요약】")
        print("=" * 70)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        print(out[summary_cols].to_string(index=False))

    return out


# ======================================================
# 실행
# ======================================================
if __name__ == "__main__":
    result = simulate_fefo_verbose(
        df_raw,
        start_ym=(2026, 1),
        end_ym=(2028, 12),
        verbose=True,
    )
