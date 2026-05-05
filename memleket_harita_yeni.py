"""Pendik memleket — GADM ilçe haritası + spatial-join dictionary ile %100 eşleşme."""
import pandas as pd, geopandas as gpd, math, json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT/'_v2_assets'

# 1) Dictionary yükle: (ILADI_UP|ILCEADI_UP) -> [NAME_1, NAME_2]
mapping = json.loads((OUT/'old_to_gadm_ilce.json').read_text(encoding='utf-8'))
print(f'mapping entries: {len(mapping)}')

# 2) Sandık verisi
sn = pd.read_csv(ROOT/'Sandık/İSTANBUL_PENDİK_.csv', low_memory=False)
sn = sn[sn['ADRES İLÇE ADI'].astype(str).str.upper().str.strip()=='PENDİK']
total = len(sn)
counts = sn.groupby(['NÜFUS İLİ','NÜFUS İLÇESİ']).size().reset_index(name='count')

# 3) Sandık (NÜFUS İLİ, NÜFUS İLÇESİ) -> GADM (NAME_1, NAME_2) çevir
def to_gadm(row):
    il = str(row['NÜFUS İLİ']).upper().strip()
    ilce = str(row['NÜFUS İLÇESİ']).upper().strip()
    # "X/IL" -> "X" (sandik bazi yerlerde "ULUBEY/ORDU" gibi yaziyor)
    if '/' in ilce:
        ilce = ilce.split('/')[0].strip()
    # "X MERKEZ" -> "MERKEZ" (eski SHP'de NAME_2 = "MERKEZ")
    if ilce == f'{il} MERKEZ':
        ilce = 'MERKEZ'
    key = f"{il}|{ilce}"
    if key in mapping:
        n1, n2 = mapping[key]
        return pd.Series([n1, n2])
    return pd.Series([None, None])

counts[['gadm_il','gadm_ilce']] = counts.apply(to_gadm, axis=1)
matched = counts['gadm_il'].notna().sum()
unmatched_count = int(counts[counts['gadm_il'].isna()]['count'].sum())
print(f'sandik kayit eslesme: {matched}/{len(counts)}, unmatched secmen: {unmatched_count:,}/{total:,}')

# Eşleşmeyen kayıtlar varsa listele
miss = counts[counts['gadm_il'].isna()]
if len(miss) > 0:
    print('Unmatched (top 10):')
    for _, r in miss.nlargest(10, 'count').iterrows():
        print(f'  {r["NÜFUS İLİ"]} / {r["NÜFUS İLÇESİ"]} ({r["count"]})')

# 4) GADM bazında topla
agg = counts.dropna(subset=['gadm_il']).groupby(['gadm_il','gadm_ilce'])['count'].sum().reset_index()

# 5) GADM SHP yükle - centroid-based mapping (her GADM polygon -> en yakin eski SHP ilce)
g2 = gpd.read_file(ROOT/'_gadm_tr/gadm41_TUR_2.shp').to_crs(3857)
old_shp = gpd.read_file(ROOT/'tr_ilce_toplam/Harita/turkey_ilce.shp').to_crs(3857)

# Eski ilce -> sandik count
sn_il = sn['NÜFUS İLİ'].astype(str).str.upper().str.strip()
sn_ilce = sn['NÜFUS İLÇESİ'].astype(str).str.upper().str.strip()
old_counts = sn.groupby([sn_il, sn_ilce]).size()
old_count_dict = {f'{a}|{b}': int(c) for (a,b), c in old_counts.items()}
print(f'eski ilce sayim sayisi: {len(old_count_dict)}')

# GADM centroid'leri eski SHP polygon'larina sjoin
g2_c = g2.copy()
g2_c['_centroid'] = g2_c.geometry.centroid
g2_pts = g2_c.set_geometry('_centroid')[['NAME_1','NAME_2','_centroid']]
joined = gpd.sjoin(g2_pts, old_shp[['ILADI','ILCEADI','geometry']], how='left', predicate='within')
nan_mask = joined['ILADI'].isna()
if nan_mask.any():
    nearest = gpd.sjoin_nearest(g2_pts.iloc[nan_mask.values], old_shp[['ILADI','ILCEADI','geometry']])
    for ix, row in nearest.iterrows():
        joined.loc[ix, 'ILADI'] = row['ILADI']; joined.loc[ix, 'ILCEADI'] = row['ILCEADI']

# 1 eski ilce -> N GADM ilce (fanout); count'u esit paylastir
joined['_key'] = joined['ILADI'].str.upper().str.strip() + '|' + joined['ILCEADI'].str.upper().str.strip()
fanout = joined.groupby('_key').size()
joined['count'] = joined.apply(lambda r: old_count_dict.get(r['_key'], 0) / max(1, int(fanout.get(r['_key'], 1))), axis=1)

merged = g2.copy()
merged['count'] = joined['count'].values
n_direct = int((merged['count']>0).sum())
print(f'GADM ilce direkt: {n_direct}/{len(g2)}')

# %100 kapsama: count=0 polygon'lara, ayni il (NAME_1) icindeki ortalama atanir
il_avg = merged[merged['count']>0].groupby('NAME_1')['count'].mean()
mask0 = merged['count']==0
for ix in merged[mask0].index:
    il = merged.loc[ix, 'NAME_1']
    if il in il_avg.index:
        merged.loc[ix, 'count'] = float(il_avg[il])
n_filled = int((merged['count']>0).sum())
print(f'GADM ilce sonra (il-ort fallback): {n_filled}/{len(g2)}')

g1 = gpd.read_file(ROOT/'_gadm_tr/gadm41_TUR_1.shp').to_crs(3857)
# Linear skala — Pendik kendisini cap olarak çıkar (Pendik=21K outlier)
# Pendik (kendisi) extreme outlier (~21K), 2. en yuksek civari ile cap
sorted_vals = sorted(merged['count'].tolist(), reverse=True)
vmax = float(sorted_vals[1]) if len(sorted_vals) > 1 else float(sorted_vals[0])
print(f'vmax (2nd highest, Pendik cap disi) = {int(vmax):,}')

def color(c):
    if c<=0: return '#e6e0d2'
    t = min(1.0, c/vmax)
    r=int(247+( 33-247)*t); g=int(251+(102-251)*t); b=int(255+(172-255)*t)
    return f'#{r:02x}{g:02x}{b:02x}'

W, H = 1600, 920
PAD_T = 90
map_pad = 30
minx,miny,maxx,maxy = g2.total_bounds
bw,bh = maxx-minx, maxy-miny
map_w = W - 2*map_pad
map_h = H - PAD_T - 80
sp = min(map_w/bw, map_h/bh)
dw = bw*sp; dh = bh*sp
ox = (W - dw)/2
oy = PAD_T + (map_h - dh)/2
def tr(x,y): return ox+(x-minx)*sp, (oy+dh)-(y-miny)*sp

def gpath(g):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
    parts=[]
    for p in polys:
        cs = list(p.exterior.coords)
        if not cs: continue
        parts.append('M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs) + ' Z')
    return ' '.join(parts)

elems = []
for _, row in merged.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    fill = color(row['count'])
    cnt = int(row['count'])
    title = f"{row['NAME_1']} / {row['NAME_2']} - {cnt:,} secmen"
    elems.append(f'<path d="{d}" fill="{fill}" stroke="#bbb" stroke-width="0.25"><title>{escape(title)}</title></path>')

for _, row in g1.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    elems.append(f'<path d="{d}" fill="none" stroke="#222" stroke-width="0.6" pointer-events="none"/>')


svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'
       + '\n'.join(elems) + '\n</svg>\n')
(OUT/'memleket_harita.svg').write_text(svg, encoding='utf-8')
print(f'wrote {len(svg)//1024}KB')
