import pandas as pd

##################################################
# 해외 창고 대사 함수 
##################################################
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

def filter_special_stock(df: pd.DataFrame, mat_col: str, special_stock_col: str) -> pd.DataFrame:
    """
    자재코드가 '1'로 시작하지 않고(원료 아님) AND 특별재고가 None/NaN/빈값이 아닌 행 제거 (특별재고 처리 로직)
    """
    if mat_col not in df.columns or special_stock_col not in df.columns:
        return df
    
    is_not_raw      = ~df[mat_col].astype(str).str.startswith("1")
    is_special_stk  = ~df[special_stock_col].isna() & \
                      ~df[special_stock_col].astype(str).str.strip().str.lower().isin(["none", "nan", ""])
    
    return df[~(is_not_raw & is_special_stk)].reset_index(drop=True)

def sap_data_processing(overview_df: pd.DataFrame, ledger_df: pd.DataFrame) -> pd.DataFrame:
    price_map = ledger_df[["자재코드", "단가"]].copy()

    result = overview_df.merge(price_map, on="자재코드", how="left")
    result["단가"] = result["단가"].fillna(0)

    result["기말재고금액"] = result["기말재고수량"] * result["단가"]

    result = filter_special_stock(result, mat_col="자재코드", special_stock_col="특별재고")
    
    result["저장위치"] = (pd.to_numeric(result["저장위치"], errors="coerce").fillna(0).astype(int).astype(str))

    check = result.copy()

    agg = (result.groupby(["자재코드", "저장위치"], as_index=False, dropna=False)[["기말재고수량", "기말재고금액"]].sum())

    meta = (result.groupby("자재코드", as_index=False).agg({"자재내역": "first", "단가": "first"}))

    result = agg.merge(meta, on="자재코드", how="left")


    desired_cols = ["자재코드", "저장위치", "자재내역", "기말재고수량", "기말재고금액", "단가"]
    result = result[desired_cols]

    return result, check


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
    
    # 자재코드 숫자인 것만 필터링 (불필요한 행 제거)
    wms_filtered = wms_filtered[pd.to_numeric(wms_filtered["자재코드"], errors="coerce").notna()]
    wms_filtered["자재코드"] = wms_filtered["자재코드"].astype(str).str.strip()

    # 자재코드별 그룹화하여 수량 합산
    wms_agg = wms_filtered.groupby("자재코드", as_index=False).agg({
        "WMS수량": "sum",
        "자재내역": "first"  # 자재내역은 첫 번째 값 사용
    })

    sap_filtered["자재코드"] = sap_filtered["자재코드"].astype(str).str.strip()
    result_df = pd.merge(sap_filtered, wms_agg, on="자재코드", how="outer")

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


##################################################################
# 재고 데이터 전처리 함수 
##################################################################
def bucketize(days):
    if pd.isna(days):
        return "미상"
    if days < 0:
        return "기간만료"
    elif days <= 30:
        return "- 1달 미만"
    elif days <= 90:
        return "1~3달"
    elif days <= 180:
        return "3~6달"
    elif days <= 365:
        return "6~12달"
    else:
        return "1년 이상"

def aging_inventory_preprocess(cost_df, standard_df, expiration_df, sales_df, cls_df):

    # 1. 데이터 불러오기 + 컬럼명 변경
    # 자재수불부 (cost_df) [자재코드, 기말수량_cosst, 기말금액]
    cost_df = cost_df[["자재","기말(수량)", "기말(금액)합계"]].copy()
    cost_df.rename(columns = {"자재" : "자재코드", "기말(수량)" : "기말수량_cost", "기말(금액)합계" : "기말금액"}, inplace = True)
    cost_df["자재코드"] = (cost_df["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))

    # 재고개요 (standard_df) [자재코드, 플랜트, 특별재고, 저장위치, 배치, 기말수량]
    standard_df = standard_df[["자재", "자재 내역", "플랜트", "특별 재고", "저장 위치", "배치", "기말 재고 수량"]].copy()
    standard_df.rename(columns = {"자재" : "자재코드", "자재 내역" : "자재내역", "특별 재고" : "특별재고", "저장 위치" : "저장위치", "기말 재고 수량" : "기말수량"}, inplace = True)
    standard_df["자재코드"] = (standard_df["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
    standard_df["배치"] = (standard_df["배치"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))

    # 배치별유효기한 (expiration_df) [자재코드, 배치, 유효기한]
    expiration_df = expiration_df[["자재", "배치", "배치만료일"]].copy()
    expiration_df.rename(columns = {"자재" : "자재코드", "배치만료일" : "유효기한"}, inplace = True)
    expiration_df["자재코드"] = (expiration_df["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
    expiration_df["배치"] = (expiration_df["배치"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
    

    # 3개월매출 (sales_df) [년월, 자재코드, 순매출금액, 순매출수량]
    sales_df = sales_df[["년월", "자재", "실매출액", "순매출수량"]].copy()
    sales_df.rename(columns = {"자재" : "자재코드", "실매출액" : "순매출금액"}, inplace = True)
    sales_df["자재코드"] = (sales_df["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
    

    # 대분류_소분류 (cls_df) [자재코드, 대분류, 소분류]
    cls_df = cls_df[["자재", "대분류", "소분류"]].copy()
    cls_df.rename(columns= {"자재" : "자재코드"}, inplace = True)
    cls_df["자재코드"] = (cls_df["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
    

    #2. 단가 계산 후 standard에 mapping
    cost_df["기말수량_cost"] = pd.to_numeric(cost_df["기말수량_cost"], errors="coerce")
    cost_df["기말금액"] = pd.to_numeric(cost_df["기말금액"], errors="coerce")
    cost_df["단가"] = cost_df["기말금액"] / cost_df["기말수량_cost"].replace(0, pd.NA)
    
    cost_map = cost_df.drop_duplicates(subset=["자재코드"]).set_index("자재코드")["단가"]
    standard_df["단가"] = standard_df["자재코드"].map(cost_map).fillna(0)
    standard_df = standard_df[["자재코드", "자재내역", "플랜트", "특별재고", "저장위치", "배치", "기말수량", "단가"]]

    #3. 소분류, 대분류 standard에 mapping
    big_map = cls_df.drop_duplicates(subset=["자재코드"]).set_index("자재코드")["대분류"]
    small_map = cls_df.drop_duplicates(subset=["자재코드"]).set_index("자재코드")["소분류"]
    standard_df["대분류"] = standard_df["자재코드"].map(big_map).fillna("미분류")
    standard_df["소분류"] = standard_df["자재코드"].map(small_map).fillna("미분류")

    # 4. 유효기한 standard에 mapping
    exp_map = (expiration_df.drop_duplicates(subset=["자재코드", "배치"]).set_index(["자재코드", "배치"])["유효기한"])
    standard_df = standard_df.join(exp_map, on=["자재코드", "배치"])
    standard_df["유효기한"] = standard_df["유효기한"].fillna("nan")
    
    # 5. 남은일 & 유효기한구간 계산
    standard_df["유효기한"] = pd.to_datetime(standard_df["유효기한"], errors="coerce").dt.normalize()
    today_ts = pd.Timestamp.today().normalize()
    standard_df["남은일"] = (standard_df["유효기한"] - today_ts).dt.days
    standard_df["유효기한구간"] = standard_df["남은일"].apply(bucketize)

    # 6.재고금액계산
    standard_df["기말금액"] = standard_df["기말수량"] * standard_df["단가"]

    # 7. 3평판 계산
    tmp = sales_df.copy()
    tmp["순매출수량"] = pd.to_numeric(tmp["순매출수량"], errors="coerce").fillna(0)
    tmp["년월"] = tmp["년월"].astype(str).str.strip()
    tmp["자재코드"] = tmp["자재코드"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    month_count = tmp.groupby("자재코드")["년월"].nunique()
    month_qty = tmp.groupby("자재코드")["순매출수량"].sum()
    sales_avg = (month_qty / month_count.replace(0, pd.NA)).fillna(0)

    standard_df["3평판"] = standard_df["자재코드"].map(sales_avg).fillna(0)
    
    # 8. 유효기한 포맷팅: YYYY-MM-DD 형태로 변환하고 NaN은 빈 문자열로 처리
    standard_df["유효기한"] = standard_df["유효기한"].dt.strftime("%Y-%m-%d").fillna("")
    
    standard_df = standard_df[["자재코드", "자재내역", "플랜트", "특별재고", "저장위치", "배치", "기말수량", "기말금액", "단가", "대분류", "소분류", "유효기한", "남은일", "유효기한구간", "3평판"]]
    standard_df = standard_df.reset_index(drop=True) 
    standard_df.insert(0, "인덱스", standard_df.index + 1)

    return standard_df