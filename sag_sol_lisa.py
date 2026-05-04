import pandas as pd
import geopandas as gpd
from libpysal.weights import Queen
from esda.moran import Moran, Moran_Local
from pathlib import Path
from xml.sax.saxutils import escape
import sys
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

SAG = {'AK PARTİ','MHP','İYİ PARTİ','YENİDEN REFAH','ZAFER PARTİSİ','BBP','ANAP','GENÇPARTİ','AP','HAK-PAR','GBP','MİLLİ YOL','YP','MİLLET'}
SOL = {'CHP','YEŞİL SOL PARTİ','TİP','MEMLEKET','VATAN PARTİSİ','SOL PARTİ','TKP','TKH','HKP','AB'}

CSV = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/oranlar/oran_2023_MİLLETVEKİLİ_GENEL.csv')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/Harita Teknik Dosya/PENDİK.shp')
OUT = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/haritalar/PENDIK_SAG_SOL_LISA.svg')

df = pd.read_csv(CSV)
parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
sag_cols = [c for c in parties if c.upper() in SAG]
sol_cols = [c for c in parties if c.upper() in SOL]
df['_sag'] = df[sag_cols].sum(axis=1) / df['n_sandik'] * 100
df['_sol'] = df[sol_cols].sum(axis=1) / df['n_sandik'] * 100

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
gdf = gdf.merge(df[['normalized','_sag','_sol']], left_on='_k', right_on='normalized', how='left')
gdf = gdf.dropna(subset=['_sag','_sol']).reset_index(drop=True)

w = Queen.from_dataframe(gdf, use_index=False); w.transform = 'r'

def classify(lm, p_thresh=0.05):
    out = []
    for q, p in zip(lm.q, lm.p_sim):
        if p > p_thresh: out.append('NS')
        else: out.append({1:'HH', 2:'LH', 3:'LL', 4:'HL'}.get(q, 'NS'))
    return out

results = {}
for side, col in [('SAĞ','_sag'), ('SOL','_sol')]:
    y = gdf[col].fillna(0).values
    mi = Moran(y, w, permutations=999)
    lm = Moran_Local(y, w, permutations=999, seed=42)
    results[side] = (classify(lm), mi.I, mi.p_sim)
    print(f'{side}: Moran I = {mi.I:.3f}, p = {mi.p_sim:.3f}')

COLOR = {'HH':'#d62728','LL':'#1f77b4','HL':'#ff9896','LH':'#aec7e8','NS':'#dddddd'}
LABEL = {'HH':'High-High','LL':'Low-Low','HL':'High-Low','LH':'Low-High','NS':'Anlamsız'}

minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx - minx, maxy - miny

def geom_d(g, transform):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    rings = []
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            coords = list(ring.coords)
            if not coords: continue
            d = 'M ' + ' L '.join(f'{transform(x,y)[0]:.2f} {transform(x,y)[1]:.2f}' for x,y in coords) + ' Z'
            rings.append(d)
    return ' '.join(rings)

W, H = 1700, 760
parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }',
    '.polygons path { stroke: #fff; stroke-width: 0.5; }',
    '.title { font-size: 22px; font-weight: 700; }',
    '.panel-title { font-size: 17px; font-weight: 600; }',
    '.panel-sub { font-size: 13px; fill: #666; }</style>',
    '<text x="40" y="38" class="title">Pendik 2023 Milletvekili — Sağ ve Sol için LISA Mahalle Kümeleri</text>',
]
pw = W // 2
for i, (side, col) in enumerate([('SAĞ','_sag'),('SOL','_sol')]):
    cls, mi_i, mi_p = results[side]
    px = i * pw + 30
    py = 60
    pad_p = 18; title_p = 56
    map_w = pw - 2 * pad_p - 20
    map_h = H - py - pad_p - 70
    sp = min(map_w / bw, map_h / bh)
    ox = px + pad_p + (map_w - bw * sp) / 2
    oy = py + title_p + (map_h - bh * sp) / 2
    def make_t(ox=ox, oy=oy, sp=sp):
        def tr(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
        return tr
    tr_p = make_t()
    parts.append(f'<text x="{px}" y="{py + 22}" class="panel-title">{side} (Moran I = {mi_i:.2f}, p = {mi_p:.3f})</text>')
    counts = pd.Series(cls).value_counts()
    sub = ' · '.join(f'{LABEL[k]}: {int(counts.get(k,0))}' for k in ['HH','LL','HL','LH','NS'] if counts.get(k,0)>0)
    parts.append(f'<text x="{px}" y="{py + 42}" class="panel-sub">{escape(sub)}</text>')
    parts.append('<g class="polygons">')
    for idx, row in gdf.iterrows():
        d = geom_d(row.geometry, tr_p)
        if not d: continue
        c = cls[idx]
        fill = COLOR[c]
        v = row[col]
        lbl = f"{row['MAHALLEADI']} — {LABEL[c]} ({side} %{v:.1f})"
        parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    parts.append('</g>')

# Tek lejant alt
ly = H - 30
lx = 40
for k in ['HH','LL','HL','LH','NS']:
    parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="12" fill="{COLOR[k]}" stroke="#333" stroke-width="0.4"/>')
    parts.append(f'<text x="{lx + 18}" y="{ly + 10}" font-size="11">{LABEL[k]}</text>')
    lx += 140
parts.append('</svg>')

OUT.write_text('\n'.join(parts), encoding='utf-8')
print(f'Yazildi: {OUT}')
