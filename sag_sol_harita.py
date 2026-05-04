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
OUT = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/haritalar/PENDIK_SAG_SOL_2023MV.svg')

df = pd.read_csv(CSV)
parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
sag_cols = [c for c in parties if c.upper() in SAG]
sol_cols = [c for c in parties if c.upper() in SOL]
print(f'SAG ({len(sag_cols)}): {sag_cols}')
print(f'SOL ({len(sol_cols)}): {sol_cols}')

df['_sag'] = df[sag_cols].sum(axis=1) / df['n_sandik'] * 100
df['_sol'] = df[sol_cols].sum(axis=1) / df['n_sandik'] * 100
ilce_sag = (df['_sag'] * df['gecerli_oy_toplam']).sum() / df['gecerli_oy_toplam'].sum()
ilce_sol = (df['_sol'] * df['gecerli_oy_toplam']).sum() / df['gecerli_oy_toplam'].sum()
print(f'Pendik SAG ort: %{ilce_sag:.2f}, SOL ort: %{ilce_sol:.2f}')

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
sag_map = dict(zip(df['normalized'], df['_sag']))
sol_map = dict(zip(df['normalized'], df['_sol']))
gdf['_sag'] = gdf['_k'].map(sag_map)
gdf['_sol'] = gdf['_k'].map(sol_map)

# Ortak max iki panel icin
vmax = float(max(gdf['_sag'].max(), gdf['_sol'].max()) or 0)
print(f'max %: {vmax:.2f}')

def color_sag(v):
    if pd.isna(v): return '#a5cce8'
    t = (v / vmax) ** 0.6
    t = min(1.0, t)
    # acik bej -> koyu kahve
    r = int(255 + (140 - 255) * t); g = int(250 + (60 - 250) * t); b = int(220 + (10 - 220) * t)
    return f'#{r:02x}{g:02x}{b:02x}'

def color_sol(v):
    if pd.isna(v): return '#a5cce8'
    t = (v / vmax) ** 0.6
    t = min(1.0, t)
    # acik kirmizi -> koyu kirmizi
    r = int(255 + (165 - 255) * t); g = int(245 + (15 - 245) * t); b = int(245 + (35 - 245) * t)
    return f'#{r:02x}{g:02x}{b:02x}'

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
    '<text x="40" y="38" class="title">Pendik 2023 Milletvekili — Sağ ve Sol Parti Oranı (Mahalle)</text>',
]
panels = [
    ('SAĞ', '_sag', color_sag, ilce_sag, 'AKP, MHP, İYİ, YRP, ZP, BBP, ...'),
    ('SOL', '_sol', color_sol, ilce_sol, 'CHP, YSP, TİP, Memleket, Vatan, ...'),
]
pw = W // 2
for i, (label, col, cfn, ort, alt) in enumerate(panels):
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
    parts.append(f'<text x="{px}" y="{py + 22}" class="panel-title">{label} (%{ort:.2f} Pendik ortalama)</text>')
    parts.append(f'<text x="{px}" y="{py + 42}" class="panel-sub">{escape(alt)}</text>')
    parts.append('<g class="polygons">')
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr_p)
        if not d: continue
        v = row[col]
        fill = cfn(v)
        lbl = f"{row['MAHALLEADI']} - {label} %{v:.2f}" if pd.notna(v) else f"{row['MAHALLEADI']} - veri yok"
        parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    parts.append('</g>')

# Iki lejant
ly = H - 36
n = 24
for i, (label, col, cfn, ort, alt) in enumerate(panels):
    lw = 280
    lx = i * pw + (pw - lw) / 2 + 30
    parts.extend(f'<rect x="{lx + (j/n)*lw:.1f}" y="{ly}" width="{lw/n + 1:.1f}" height="14" fill="{cfn((j/(n-1))*vmax)}"/>' for j in range(n))
    parts.append(f'<text x="{lx}" y="{ly - 6}" font-size="12" font-weight="600">{label} %</text>')
    parts.append(f'<text x="{lx}" y="{ly + 28}" font-size="11">0</text>')
    parts.append(f'<text x="{lx + lw}" y="{ly + 28}" font-size="11" text-anchor="end">%{vmax:.1f}</text>')
parts.append('</svg>')

OUT.write_text('\n'.join(parts), encoding='utf-8')
print(f'Yazildi: {OUT}')
