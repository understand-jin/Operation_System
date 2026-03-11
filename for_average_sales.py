import pandas as pd

# 1. 엑셀 파일 읽기
df = pd.read_excel("for_average_sales.xlsx")

# 2. 자재코드 기준 그룹화
grouped_df = df.groupby("자재코드", as_index=False).agg({
    "자재내역": "first",
    "3평판": "first"
})

# 3. 엑셀 파일로 저장
grouped_df.to_excel("grouped_material.xlsx", index=False)

print("완료: grouped_material.xlsx 파일 생성")