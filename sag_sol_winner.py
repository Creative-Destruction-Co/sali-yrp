import pandas as pd
import geopandas as gpd
from pathlib import Path
from xml.sax.saxutils import escape
import sys
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

SAG = {'AK PARTİ','MHP','İYİ PARTİ','YENİDEN REFAH','ZAFER PARTİSİ','BBP','ANAP','GENÇPARTİ','AP','HAK-PAR','GBP','MİLLİ YOL','YP','MİLLET'}
SOL = {'CHP','YEŞİL SOL PARTİ','TİP','MEMLEKET','VATAN PARTİSİ','SOL PARTİ','TKP','TKH','HKP','AB'}

CSV = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/oranlar/oran_2023_MİLLETVEKİLİ_GENEL.csv')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/Harita Teknik Dosya/PENDİK.shp')
OUT = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/haritalar/PENDIK_SAG_SOL_winner.svg')

df = pd.read_csv(CSV)
parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
sag_cols = [c for c in parties if c.upper() in SAG]
sol_cols = [c for c in parties if c.upper() in SOL]
df['_sag'] = df[sag_cols].sum(axis=1) / df['n_sandik'] * 100
df['_sol'] = df[sol_cols].sum(axis=1) / df['n_sandik'] * 100
df['_winner'] = df.apply(lambda r: 'SAĞ' if r['_sag'] >= r['_sol'] else 'SOL', axis=1)
counts = df['_winner'].value_counts()
print('Kazanan:', counts.to_dict())

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
sag_map = dict(zip(df['normalized'], df['_sag']))
sol_map = dict(zip(df['normalized'], df['_sol']))
gdf['_sag'] = gdf['_k'].map(sag_map)
gdf['_sol'] = gdf['_k'].map(sol_map)
gdf['_winner'] = gdf.apply(lambda r: 'SAĞ' if pd.notna(r['_sag']) and pd.notna(r['_sol']) and r['_sag'] >= r['_sol'] else ('SOL' if pd.notna(r['_sol']) else None), axis=1)

COLOR = {'SAĞ': '#fdb924', 'SOL': '#d62728'}
WATER = '#a5cce8'

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

W = 1600; pad = 30; title_h = 36; legend_h = 70
s_ = (W - 2 * pad) / bw
map_h_int = int(round(bh * s_ + pad))
H = title_h + map_h_int + legend_h + pad
def tr(x, y): return pad + (x - minx) * s_, (title_h + map_h_int) - (y - miny) * s_

paths = []
for _, row in gdf.iterrows():
    d = geom_d(row.geometry, tr)
    if not d: continue
    w = row['_winner']
    if w is None:
        fill = WATER; lbl = f"{row['MAHALLEADI']} - veri yok (su)"
    else:
        fill = COLOR[w]
        lbl = f"{row['MAHALLEADI']} - {w} (Sağ %{row['_sag']:.1f} / Sol %{row['_sol']:.1f})"
    paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

# Lejant
ly = title_h + map_h_int + 28
lx = pad
items = []
counts_full = gdf['_winner'].value_counts(dropna=True)
for k in ['SAĞ','SOL']:
    c = int(counts_full.get(k, 0))
    items.append(f'<rect x="{lx}" y="{ly}" width="22" height="14" rx="2" fill="{COLOR[k]}" stroke="#222" stroke-width="0.6"/>')
    items.append(f'<text x="{lx + 30}" y="{ly + 12}" font-size="13" font-weight="500">{k} ({c})</text>')
    lx += 130

title = "Pendik 2023 Milletvekili — Mahallede Sağ vs Sol Birinci"
svg = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">\n'
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }\n'
    '.polygons path { stroke: #fff; stroke-width: 0.5; }</style>\n'
    f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>\n'
    '<g class="polygons">' + '\n'.join(paths) + '</g>\n'
    '<g>' + '\n'.join(items) + '</g>\n</svg>\n'
)
OUT.write_text(svg, encoding='utf-8')
print(f'Yazildi: {OUT}')
