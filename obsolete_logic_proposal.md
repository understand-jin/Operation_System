# 시작 시점 이전 부진재고량(Cut-off) 처리 보완 방안

## 1. 현재 로직의 문제점 (As-Is)

현재 시뮬레이션 코드(`add_obsolete_cols_at_cutoff_6m` 함수)는 각 배치들의 **"유효기간 6개월 전(Cut-off Date)"**이 언제인지 계산한 뒤, **해당 마지노선 월(Month)의 기말 재고 수량열(Column)**을 찾아 그 값을 통째로 `부진재고량`으로 확정 짓고 있습니다.

*   **정상 동작 (시뮬레이션 기간 내 만료):** 유효기간 마지노선이 `2026-10`인 경우, 시뮬레이션 결과 표에 `26_10`이라는 열(Column)이 존재하므로, 그 칸에 적힌 수량을 "이건 못 팔고 남은 부진재고량이다!"라고 100% 정상적으로 가져옵니다.
*   **문제 상황 (시뮬레이션 시작 전 만료):** 어떤 배치의 유효기간 마지노선이 `2025-10`인 경우, 2026년부터 시뮬레이션을 돌렸기 때문에 결과 표에 `25_10`이라는 열 자체가 **존재하지 않습니다.**
*   **현재 코드의 한계:** `if cut_col not in out.columns: continue` (열을 못 찾으면 그냥 패스하라!) 라는 코드 때문에, 이 배치는 기초 수량을 고스란히 가지고 있음에도 불구하고 최종 집계표에서 `부진재고량 = 0`으로 누락되어 버립니다.

---

## 2. 해결 방안 모식도 (To-Be)

따라서, 마지노선 열(Column)을 찾지 못했을 때 무작정 건너뛰는 것이 아니라, **"마지노선이 시뮬레이션 시작 시점(예: 2026년 1월)보다 과거라면, 이건 깎아보지도 못하고 즉시 부진재고가 된 악성 재고이므로 1월 기말 수량(기초 수량) 전체를 그대로 부진재고량으로 꽂아주자!"** 라고 로직을 보완해야 합니다.

### 변경 전/후 파이썬 코드 비교

#### ❌ 현재 코드 (As-Is)
```python
    for idx in out.index:
        if not has_expiry.loc[idx]: continue
        y = int(cut_y.loc[idx]); m = int(cut_m.loc[idx])
        cut_col = col_fmt(y, m)
        
        # [문제점] 25_10 열이 없으면 여기서 묻지도 따지지도 않고 건너뜀 (부진재고량 0 처리)
        if cut_col not in out.columns: 
            continue 
            
        val = pd.to_numeric(out.at[idx, cut_col], errors="coerce")
        out.at[idx, "부진재고량"] = float(val)
        ...
```

#### ✅ 수정 제안 코드 (To-Be)
```python
    # 시뮬레이션의 가장 첫 번째 달에 해당하는 컬럼명 (예: "26_1")
    first_month_col = out.columns[out.columns.str.match(r"^\d{2}_\d{1,2}$")].min()

    for idx in out.index:
        if not has_expiry.loc[idx]: continue
        y = int(cut_y.loc[idx]); m = int(cut_m.loc[idx])
        cut_col = col_fmt(y, m)
        
        if cut_col in out.columns:
            # 1. 정상 케이스: 해당 마지노선 열이 존재하면 그 달의 재고를 가져옴
            val = pd.to_numeric(out.at[idx, cut_col], errors="coerce")
        else:
            # 2. 보완 케이스: 컬럼이 없다면 "과거"인지 확인
            # (과거라서 없어진 것인지 미래라서 안 만들어진 것인지 판단)
            sim_start_y = 2000 + int(first_month_col.split('_')[0])
            sim_start_m = int(first_month_col.split('_')[1])
            
            if (y < sim_start_y) or (y == sim_start_y and m < sim_start_m):
                # ★ 과거 컷오프(시뮬레이션 전부터 이미 부진) -> 강제로 "첫 달(기초)" 수량 100%를 가져옴
                val = pd.to_numeric(out.at[idx, first_month_col], errors="coerce")
            else:
                # 시뮬레이션 기간을 한참 뛰어넘는 먼 미래의 유기한이면 0 처리
                val = 0.0

        if pd.isna(val): continue
        out.at[idx, "부진재고량"] = float(val)
        
        # 진입 시점 기록 부분
        if float(val) > 0:
            entry_dt = cutoff_dt.loc[idx]
            # 이미 시뮬레이션 시작 전부터 부진재고였으므로 "기초 부진재고(Before Simulation)" 태그 달기
            out.at[idx, "부진재고진입시점"] = entry_dt.strftime("%Y-%m-%d") if pd.notna(entry_dt) else ""
            
            sim_start_y = 2000 + int(first_month_col.split('_')[0])
            sim_start_m = int(first_month_col.split('_')[1])
            if (y < sim_start_y) or (y == sim_start_y and m < sim_start_m):
                out.at[idx, "부진재고진입분기"] = "기초부진(Start)" 
            else:
                q = (entry_dt.month - 1) // 3 + 1
                yy = str(entry_dt.year)[-2:]
                out.at[idx, "부진재고진입분기"] = f"{yy}년 {q}Q"
```

---

## 3. 쉬운 비유로 이해해보기 (사진 찍기)

시뮬레이션 프로그램은 매달 기차(1월 기차, 2월 기차...)가 지나갈 때마다 **"너는 이제 유효기간이 6개월밖에 안 남았으니 악성 재고야!"** 라며 그 달에 남은 수량을 사진(찰칵!) 찍어서 최종 보고서(부진재고 금액표)에 올립니다.

### ❌ 기존 방식의 문제점
*   **A자재 (2026년 5월에 악성 재고 판정):** 5월 기차가 지나갈 때 정상적으로 사진을 찰칵! 찍어서 "5월에 부진재고 500개 발생!" 하고 보고서에 올립니다.
*   **B자재 (2025년 10월에 이미 악성 재고 판정):** 얘는 작년에 이미 악성 재고 판정을 받고 기차에 타고 있었습니다. 그런데 시뮬레이션 사진사는 **오늘은 2026년 1월이니까 이때부터 출근**했습니다.
*   사진사는 B자재의 기록을 보고 *"어? 너는 25년 10월에 사진을 찍혔어야 하는데 내 달력(시뮬레이션 기간)엔 작년 날짜가 없네? 나 출근 안 했을 때네! 그럼 너는 사진 못 찍었으니까 그냥 부진재고 0개인 걸로 할게!"* 라고 무시해 버립니다.
*   **결과:** 그 B자재는 여전히 창고에 1,000개나 쌓여서 굴러다니고 있는데도, **최종 보고서의 부진재고 총액에서는 '0원'으로 계산되어 허공으로 증발**해 버립니다.

### ✅ 이렇게 고치겠습니다! (개선된 사진사)
*   사진사(새로운 코드)가 B자재를 봅니다. *"어? 너 25년 10월에 찍혔어야 하는데, 지금 보니 내가 첫 출근(26년 1월)하기도 전에 이미 악성 재고가 된 애구나?"*
*   *"그럼 묻지도 따지지도 않고, 너는 애초부터 썩은 재고로 넘어왔으니 내가 첫 출근한 날(26년 1월) 네가 들고 있는 그 수량 전체(1,000개)를 지금 여기서 100% 사진 찍어줄게!"* 
*   그리고 사진 밑에 **[기초부진(Start)]**이라는 특별한 도장을 찍어서, 이놈은 도중에 발생한 게 아니라 애초부터 팔 수 없는 상태로 넘어온 재고라는 것을 분기표(최종 보고서)에 한눈에 알 수 있게 따로 모아서 올립니다!
