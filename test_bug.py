import pandas as pd
import importlib.util
spec = importlib.util.spec_from_file_location("sim", "pages/5_Inventory_Simulation.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
simulate_monthly_remaining_amount_fefo = sim.simulate_monthly_remaining_amount_fefo
build_category_quarter_table = sim.build_category_quarter_table


# Create mock data for mapped_self_plain (1 material, 2 batches)
df_self = pd.DataFrame([
    {"자재": "A", "배치": "B1", "유효기간": "2027-01-01", "기말 재고 금액": 1000, "기말 재고 수량": 10, "출하원가": 500, "평판": 5, "원가율": 0.5, "출하판가": 1000, "단가": 100, "대분류": "M1", "소분류": "S1", "who": "자사"},
    {"자재": "A", "배치": "B2", "유효기간": "2027-04-01", "기말 재고 금액": 1000, "기말 재고 수량": 10, "출하원가": 500, "평판": 5, "원가율": 0.5, "출하판가": 1000, "단가": 100, "대분류": "M1", "소분류": "S1", "who": "자사"}
])

# Create empty manufacturer data
df_manu = pd.DataFrame(columns=df_self.columns)

# Combine
df_combined = pd.concat([df_self, df_manu], ignore_index=True)

# Simulate
sim_self = simulate_monthly_remaining_amount_fefo(df_self)
sim_comb = simulate_monthly_remaining_amount_fefo(df_combined)

add_obsolete_cols_at_cutoff_6m = sim.add_obsolete_cols_at_cutoff_6m

sim_self = add_obsolete_cols_at_cutoff_6m(sim_self)
sim_comb = add_obsolete_cols_at_cutoff_6m(sim_comb)

cols_to_check = [c for c in sim_self.columns if c.startswith("26_") or c.startswith("27_") or c.startswith("28_")]
print("Self Sums:")
print(sim_self[cols_to_check].sum())
print("Comb Sums:")
print(sim_comb[cols_to_check].sum())

# Quarterly tables
tbl_self = build_category_quarter_table(sim_self, quarter_col="부진재고진입분기")
tbl_comb = build_category_quarter_table(sim_comb, quarter_col="부진재고진입분기")

print("\nTable Self:")
print(tbl_self[["대분류", "소분류", "원가", "출하원가", "회전월", "합계"]])
print("\nTable Comb:")
print(tbl_comb[["대분류", "소분류", "원가", "출하원가", "회전월", "합계"]])
