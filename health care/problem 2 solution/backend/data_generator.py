
import pandas as pd
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

facilities = [
    ("F001","City Hospital","Bengaluru",12.9716,77.5946),
    ("F002","District Hospital","Electronic City",12.8452,77.6602),
    ("F003","Community Health Center","Hosur",12.7409,77.8253),
    ("F004","Taluk Hospital","Anekal",12.7110,77.6960),
    ("F005","Primary Health Center","Sarjapur",12.8600,77.7860),
    ("F006","General Hospital","Mysuru",12.2958,76.6394),
    ("F007","District Hospital","Mandya",12.5218,76.8951),
    ("F008","Regional Hospital","Tumakuru",13.3392,77.1010),
]

medicines = [
    ("M001","Amoxicillin",1000),
    ("M002","Insulin",400),
    ("M003","Paracetamol",2500),
    ("M004","Ceftriaxone",800),
    ("M005","ORS",3000),
]

fac = pd.DataFrame(facilities, columns=["facility_id","facility_name","city","lat","lon"])
med = pd.DataFrame(medicines, columns=["medicine_id","medicine_name","normal_stock"])

# Facility inventory snapshots and daily consumption
rows = []
start = pd.Timestamp("2026-01-01")
days = 120

for _, f in fac.iterrows():
    for _, m in med.iterrows():
        stock = int(m.normal_stock * rng.uniform(0.55, 0.95))
        for d in range(days):
            date = start + pd.Timedelta(days=d)
            # Create a regional shortage shock for insulin and ceftriaxone.
            shock = 1.0
            if m.medicine_id in ("M002","M004") and 65 <= d <= 95:
                shock = 1.35  # demand rises
            if m.medicine_id == "M002" and f.facility_id in ("F005","F007") and 70 <= d <= 100:
                shock = 1.55

            consumption = max(1, int(rng.normal(m.normal_stock/70, m.normal_stock/140) * shock))
            receipt = 0
            if d % int(rng.integers(12, 24)) == 0 and rng.random() < 0.7:
                receipt = int(m.normal_stock * rng.uniform(0.35, 0.75))
            stock = max(0, stock + receipt - consumption)

            rows.append([
                date.date().isoformat(), f.facility_id, m.medicine_id,
                stock, consumption, receipt
            ])

inventory = pd.DataFrame(rows, columns=[
    "date","facility_id","medicine_id","stock_on_hand","daily_consumption","received"
])

fac.to_csv(OUT/"facilities.csv", index=False)
med.to_csv(OUT/"medicines.csv", index=False)
inventory.to_csv(OUT/"inventory.csv", index=False)
print("Generated synthetic data in", OUT)
