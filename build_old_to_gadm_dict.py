"""Eski TR ilçe SHP centroid'lerini GADM 4.1 ilçelerine spatial join ile eşle.
Sonuç: (ILADI_UP, ILCEADI_UP) → (NAME_1, NAME_2) dictionary, JSON olarak kaydet."""
import geopandas as gpd, json, sys
from pathlib import Path

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT/'_v2_assets'

old = gpd.read_file(ROOT/'tr_ilce_toplam/Harita/turkey_ilce.shp').to_crs(3857)
gadm = gpd.read_file(ROOT/'_gadm_tr/gadm41_TUR_2.shp').to_crs(3857)
print(f'eski TR ilçe: {len(old)}, GADM ilçe: {len(gadm)}')

# Centroid kullanarak join
old['_centroid'] = old.geometry.centroid
old_pts = old.set_geometry('_centroid')[['ILADI','ILCEADI','_centroid']].copy()

# 1) within (centroid GADM polygonu içinde mi)
joined = gpd.sjoin(old_pts, gadm[['NAME_1','NAME_2','geometry']],
                   how='left', predicate='within')

# 2) eşleşmeyen centroid'ler için sjoin_nearest fallback
miss_mask = joined['NAME_1'].isna()
n_miss = int(miss_mask.sum())
if n_miss > 0:
    print(f'  {n_miss} ilce within ile eslesmedi -> sjoin_nearest fallback')
    miss_pts = old_pts.iloc[miss_mask.values].copy()
    nearest = gpd.sjoin_nearest(miss_pts, gadm[['NAME_1','NAME_2','geometry']],
                                how='left', distance_col='_dist')
    # joined'da ilgili satırları doldur
    for idx, row in nearest.iterrows():
        joined.loc[idx, 'NAME_1'] = row['NAME_1']
        joined.loc[idx, 'NAME_2'] = row['NAME_2']

ok = (joined['NAME_1'].notna()).sum()
print(f'eşleşme: {ok}/{len(joined)}')

# Dictionary üret
mapping = {}
for _, r in joined.iterrows():
    if r['NAME_1'] is None or (isinstance(r['NAME_1'], float) and r['NAME_1'] != r['NAME_1']):
        continue
    key = f"{str(r['ILADI']).upper().strip()}|{str(r['ILCEADI']).upper().strip()}"
    mapping[key] = [r['NAME_1'], r['NAME_2']]

print(f'sözlük entries: {len(mapping)}')
out_path = OUT/'old_to_gadm_ilce.json'
out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {out_path}')

# Sample 5 entry
import itertools
for k,v in itertools.islice(mapping.items(), 5):
    print(f'  {k} → {v}')
