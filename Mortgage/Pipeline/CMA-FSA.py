"""
build_fsa_cma.py
Spatial join of StatCan FSA and CMA boundary shapefiles.

Downloads needed (Cartographic Boundary Files, English):
  FSA: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcfsa000b21a_e.zip
  CMA: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcma000b21a_e.zip
  Province: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lpr_000b21a_e.zip

Unzip all three. Point the paths below at the .shp files.

Install dependency if needed:
  pip install geopandas
"""

import geopandas as gpd
import pandas as pd

# --- Configure these paths ---
FSA_SHP = "lfsa000b21a_e.shp"
CMA_SHP = "lcma000b21a_e.shp"
PR_SHP  = "lpr_000b21a_e.shp"
OUTPUT  = "fsa_to_cma.csv"
# -----------------------------

print("Loading shapefiles...")
fsa = gpd.read_file(FSA_SHP)
cma = gpd.read_file(CMA_SHP)
pr  = gpd.read_file(PR_SHP)

print(f"  FSA: {len(fsa)} features, columns: {list(fsa.columns)}")
print(f"  CMA: {len(cma)} features, columns: {list(cma.columns)}")
print(f"  PR:  {len(pr)} features, columns: {list(pr.columns)}")

# Reproject everything to the same CRS
cma = cma.to_crs(fsa.crs)
pr  = pr.to_crs(fsa.crs)

# Use FSA centroids for the join (faster and avoids edge ambiguity)
print("Computing FSA centroids...")
fsa_pts = fsa.copy()
fsa_pts["geometry"] = fsa.centroid

# Join FSA centroids -> CMA
print("Joining FSA to CMA...")
joined_cma = gpd.sjoin(
    fsa_pts[["CFSAUID", "PRUID", "geometry"]],
    cma[["CMAUID", "CMANAME", "CMATYPE", "geometry"]],
    how="left",
    predicate="within"
)

# Join FSA centroids -> Province (for province name)
print("Joining FSA to Province...")
joined_pr = gpd.sjoin(
    fsa_pts[["CFSAUID", "geometry"]],
    pr[["PRUID", "PRNAME", "geometry"]],
    how="left",
    predicate="within"
)

# Merge results
print("Building output...")
result = joined_cma[["CFSAUID", "PRUID", "CMANAME", "CMATYPE"]].copy()
result = result.merge(
    joined_pr[["CFSAUID", "PRNAME"]],
    on="CFSAUID",
    how="left"
)

# Clean up
result = result.rename(columns={
    "CFSAUID": "FSA",
    "CMANAME": "CMA",
    "CMATYPE": "CMA_TYPE",
    "PRNAME":  "Province"
})

# CMA_TYPE codes: B=CMA, K=Census Agglomeration, blank=not in any CMA
result["CMA_TYPE"] = result["CMA_TYPE"].fillna("")
result["CMA"]      = result["CMA"].fillna("")

# Drop PRUID (internal code, not needed in output)
result = result.drop(columns=["PRUID"])

# Sort by FSA
result = result.sort_values("FSA").reset_index(drop=True)

result.to_csv(OUTPUT, index=False, encoding="utf-8")

print(f"\nDone. {len(result)} FSAs written to {OUTPUT}")
print(f"  In a CMA:  {(result['CMA'] != '').sum()}")
print(f"  No CMA:    {(result['CMA'] == '').sum()}")
print(f"\nSample output:")
print(result[result["CMA"] != ""].head(5).to_string(index=False))
print(result[result["CMA"] == ""].head(3).to_string(index=False))