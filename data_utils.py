import pandas as pd


def load_sap_data(df1: pd.DataFrame, df2: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:

    # ── 1번 자료 (재고개요) ────────────────────────────────────
    overview_df = df1[["자재", "저장 위치", "특별 재고", "자재 내역", "기말 재고 수량"]].copy()
    overview_df.rename(columns={
        "자재":           "자재코드",
        "저장 위치":      "저장위치",
        "특별 재고":      "특별재고",
        "자재 내역":      "자재내역",
        "기말 재고 수량": "기말재고수량",
    }, inplace=True)

    # ── 2번 자료 (자재수불부) ──────────────────────────────────
    ledger_df = df2[["자재", "자재 내역", "기말(수량)", "기말(금액)합계"]].copy()
    ledger_df.rename(columns={"자재": "자재코드"}, inplace=True)

    # 수량/금액 숫자 변환
    ledger_df["기말(수량)"]    = pd.to_numeric(ledger_df["기말(수량)"],    errors="coerce").fillna(0)
    ledger_df["기말(금액)합계"] = pd.to_numeric(ledger_df["기말(금액)합계"], errors="coerce").fillna(0)

    # 단가 = 기말(금액)합계 / 기말(수량)  (수량 0이면 0)
    ledger_df["단가"] = ledger_df.apply(
        lambda r: r["기말(금액)합계"] / r["기말(수량)"] if r["기말(수량)"] != 0 else 0,
        axis=1,
    )

    return overview_df, ledger_df


def sap_data_processing(overview_df: pd.DataFrame, ledger_df: pd.DataFrame) -> pd.DataFrame:
    price_map = ledger_df[["자재코드", "단가"]].copy()

    result = overview_df.merge(price_map, on="자재코드", how="left")
    result["단가"] = result["단가"].fillna(0)

    result["기말재고금액"] = result["기말재고수량"] * result["단가"]

    # 자재코드가 '1'로 시작하지 않고(원료 아님) AND 특별재고가 None/NaN/빈값이 아닌 행 제거 (특별재고 처리 로직)
    is_not_raw      = ~result["자재코드"].astype(str).str.startswith("1")
    is_special_stk  = ~result["특별재고"].isna() & \
                      ~result["특별재고"].astype(str).str.strip().str.lower().isin(["none", "nan", ""])
    result = result[~(is_not_raw & is_special_stk)].reset_index(drop=True)
    
    result["저장위치"] = (pd.to_numeric(result["저장위치"], errors="coerce").fillna(0).astype(int).astype(str))

    agg = (result.groupby(["자재코드", "저장위치"], as_index=False, dropna=False)[["기말재고수량", "기말재고금액"]].sum())

    meta = (result.groupby("자재코드", as_index=False).agg({"자재내역": "first", "단가": "first"}))

    result = agg.merge(meta, on="자재코드", how="left")


    desired_cols = ["자재코드", "저장위치", "자재내역", "기말재고수량", "기말재고금액", "단가"]
    result = result[desired_cols]

    return result


def wms_sap(sap_df: pd.DataFrame, wms_df: pd.DataFrame, warehouse_code: str) -> pd.DataFrame:
    cost_df = sap_df[["자재코드", "단가"]].copy()
    cost_df["자재코드"] = cost_df["자재코드"].astype(str).str.strip()
    cost_df["단가"] = pd.to_numeric(cost_df["단가"], errors="coerce")
    cost_map = (cost_df.dropna(subset=["단가"]).drop_duplicates(subset=["자재코드"]).set_index("자재코드")["단가"])

    sap_filtered = sap_df[sap_df["저장위치"].astype(str) == str(warehouse_code)].copy()
    sap_filtered = sap_filtered[["자재코드", "저장위치", "자재내역", "기말재고수량", "기말재고금액", "단가"]]
    sap_filtered = sap_filtered.rename(columns = {"기말재고수량" : "SAP수량"})

    wms_filtered = wms_df.copy()
    wms_filtered = wms_filtered.rename(columns = {"가용재고" : "WMS수량"})
    wms_filtered = wms_filtered[pd.to_numeric(wms_filtered["자재코드"], errors="coerce").notna()]

    sap_filtered["자재코드"] = sap_filtered["자재코드"].astype(str).str.strip()
    wms_filtered["자재코드"] = wms_filtered["자재코드"].astype(str).str.strip()
    result_df = pd.merge(sap_filtered, wms_filtered, on="자재코드", how="outer")

    result_df["SAP수량"] = result_df["SAP수량"].fillna(0)
    result_df["WMS수량"] = result_df["WMS수량"].fillna(0)

    result_df["단가"] = pd.to_numeric(result_df["단가"], errors="coerce")
    result_df["단가"] = result_df["단가"].fillna(result_df["자재코드"].map(cost_map)).fillna(0)
    
    result_df["저장위치"] = result_df["저장위치"].fillna(str(warehouse_code))

    result_df["자재내역_x"] = result_df["자재내역_x"].fillna(result_df["자재내역_y"])
    result_df = result_df.rename(columns = {"자재내역_x" : "자재내역"})

    result_df = result_df[["자재코드", "저장위치", "자재내역", "SAP수량", "WMS수량", "단가"]]

    result_df["SAP금액"] = result_df["SAP수량"] * result_df["단가"]
    result_df["WMS금액"] = result_df["WMS수량"] * result_df["단가"]

    result_df["차이"] = result_df["WMS수량"] - result_df["SAP수량"]
    result_df["차이금액"] = result_df["WMS금액"] - result_df["SAP금액"]

    result_df = result_df[["자재코드", "자재내역", "저장위치", "WMS수량", "SAP수량", "WMS금액", "SAP금액", "차이", "차이금액", "단가"]]

    result_df = result_df.sort_values(by="차이", ascending=False)

    return result_df
