import pandas as pd
import geopandas as gpd
from pathlib import Path
from xml.sax.saxutils import escape
import sys
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

BASE = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/oranlar')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/Harita Teknik Dosya/PENDİK.shp')
OUTDIR = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/haritalar')

def load_party(path, query):
    df = pd.read_csv(path)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    cands = [c for c in parties if query in c.upper()]
    if not cands: return None
    col = cands[0]
    df['_avg'] = df[col] / df['n_sandik']
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']]

files = {
    '2011': BASE / 'oran_2011_MİLLETVEKİLİ_GENEL.csv',
    '2015 Haziran': BASE / 'oran_2015_Haziran_MİLLETVEKİLİ_GENEL.csv',
    '2015 Kasım': BASE / 'oran_2015_Kasım_MİLLETVEKİLİ_GENEL.csv',
    '2018': BASE / 'oran_2018_MİLLETVEKİLİ_GENEL.csv',
}
data = {k: load_party(v, 'SAADET') for k,v in files.items()}
ilce_avg = {k: (d['_avg'] * d['gecerli_oy_toplam']).sum() / d['gecerli_oy_toplam'].sum() * 100
            for k,d in data.items() if d is not None}
print('Saadet ilce ort:', {k: round(v,2) for k,v in ilce_avg.items()})
ilce_swing = ilce_avg['2018'] - ilce_avg['2015 Kasım']
print(f'2015K -> 2018 swing: {ilce_swing:+.2f} pp')

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
for k, d in data.items():
    if d is None: continue
    gdf[f'v_{k}'] = gdf['_k'].map(d['_avg']) * 100
    gdf[f'rel_{k}'] = gdf[f'v_{k}'] - ilce_avg[k]

gdf['swing_rel'] = (gdf['v_2018'] - gdf['v_2015 Kasım']) - ilce_swing
all_rel = pd.concat([gdf[f'rel_{k}'] for k in data]).abs()
vmax_rel = float(all_rel.max())
vmax_swing = float(gdf['swing_rel'].abs().max())

def color(d, vmax):
    if pd.isna(d): return '#a5cce8'
    t = max(-1, min(1, d / vmax)) if vmax > 0 else 0
    if t >= 0:
        r = int(255 + (10 - 255) * t); g = int(255 + (90 - 255) * t); b = int(255 + (140 - 255) * t)
    else:
        r = int(255 + (200 - 255) * (-t)); g = int(255 + (20 - 255) * (-t)); b = int(255 + (40 - 255) * (-t))
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

# Harita 1: swing
W = 1600; pad = 30; title_h = 36; legend_h = 80
s_ = (W - 2 * pad) / bw
map_h = int(round(bh * s_ + pad))
H = title_h + map_h + legend_h + pad
def tr(x, y): return pad + (x - minx) * s_, (title_h + map_h) - (y - miny) * s_

paths = []
for _, row in gdf.iterrows():
    d = geom_d(row.geometry, tr)
    if not d: continue
    sr = row['swing_rel']
    fill = color(sr, vmax_swing)
    if pd.isna(sr):
        lbl = f"{row['MAHALLEADI']} - veri yok"
    else:
        delta = row['v_2018'] - row['v_2015 Kasım']
        lbl = f"{row['MAHALLEADI']} - degisim {delta:+.1f} pp, sapma {sr:+.1f}"
    paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

legend_y = title_h + map_h + 28; lw = 380; lx = (W - lw) / 2
n = 24
stops = [f'<rect x="{lx + (i/n)*lw:.1f}" y="{legend_y}" width="{lw/n + 1:.1f}" height="14" fill="{color((i/(n-1)*2-1)*vmax_swing, vmax_swing)}"/>' for i in range(n)]
labels = [
    f'<text x="{lx}" y="{legend_y - 6}" font-size="13" font-weight="600">Saadet 2015K-2018 mahalle sapmasi (puan) — Pendik swing: {ilce_swing:+.2f}</text>',
    f'<text x="{lx}" y="{legend_y + 30}" font-size="12">{-vmax_swing:+.1f}</text>',
    f'<text x="{lx + lw/2}" y="{legend_y + 30}" font-size="12" text-anchor="middle">0</text>',
    f'<text x="{lx + lw}" y="{legend_y + 30}" font-size="12" text-anchor="end">{vmax_swing:+.1f}</text>',
]
title = "Pendik - Saadet 2015 Kasim -> 2018 Degisim, Ilce Ortalamasina Gore Mahalle Sapmasi"
svg1 = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">\n'
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }\n'
    '.polygons path { stroke: #fff; stroke-width: 0.5; }</style>\n'
    f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>\n'
    '<g class="polygons">' + '\n'.join(paths) + '</g>\n'
    '<g>' + '\n'.join(stops + labels) + '</g>\n</svg>\n'
)
out1 = OUTDIR / 'PENDIK_SAADET_2015K_2018_swing.svg'
out1.write_text(svg1, encoding='utf-8')
print('Yazildi:', out1)

# Harita 2: 4 panel
W2, H2 = 1700, 1100
PX, PY = 2, 2
pw, ph = W2 // PX, H2 // PY
parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W2} {H2}" preserveAspectRatio="xMidYMid meet">',
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }',
    '.polygons path { stroke: #fff; stroke-width: 0.5; }',
    '.title { font-size: 22px; font-weight: 700; }',
    '.panel-title { font-size: 17px; font-weight: 600; }</style>',
    '<text x="40" y="38" class="title">Pendik - Saadet, Ilce Ortalamasina Gore Mahalle Sapmasi (4 donem)</text>',
]
for i, k in enumerate(data.keys()):
    if data[k] is None: continue
    px = (i % PX) * pw + 20
    py = (i // PX) * ph + 50
    pad_p = 20; title_p = 40
    map_w = pw - 2 * pad_p
    map_h_p = ph - title_p - 2 * pad_p
    sp = min(map_w / bw, map_h_p / bh)
    ox = px + pad_p + (map_w - bw * sp) / 2
    oy = py + title_p + pad_p + (map_h_p - bh * sp) / 2
    def make_t(ox=ox, oy=oy, sp=sp):
        def tr2(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
        return tr2
    tr_p = make_t()
    parts.append(f'<text x="{px + pad_p}" y="{py + title_p - 6}" class="panel-title">{escape(k)} - Pendik: %{ilce_avg[k]:.2f}</text>')
    parts.append('<g class="polygons">')
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr_p)
        if not d: continue
        rel = row[f'rel_{k}']; v = row[f'v_{k}']
        fill = color(rel, vmax_rel)
        lbl = f"{row['MAHALLEADI']} - %{v:.1f} (sapma {rel:+.1f})" if pd.notna(rel) else f"{row['MAHALLEADI']} - veri yok"
        parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    parts.append('</g>')

ly = H2 - 50
lx2 = (W2 - 380) / 2
n = 24
parts.extend(f'<rect x="{lx2 + (i/n)*380:.1f}" y="{ly}" width="{380/n + 1:.1f}" height="14" fill="{color((i/(n-1)*2-1)*vmax_rel, vmax_rel)}"/>' for i in range(n))
parts.append(f'<text x="{lx2}" y="{ly - 6}" font-size="13" font-weight="600">Ilce ortalamasina gore sapma (puan)</text>')
parts.append(f'<text x="{lx2}" y="{ly + 30}" font-size="12">{-vmax_rel:+.1f}</text>')
parts.append(f'<text x="{lx2 + 190}" y="{ly + 30}" font-size="12" text-anchor="middle">0</text>')
parts.append(f'<text x="{lx2 + 380}" y="{ly + 30}" font-size="12" text-anchor="end">{vmax_rel:+.1f}</text>')
parts.append('</svg>')
out2 = OUTDIR / 'PENDIK_SAADET_4donem_sapma.svg'
out2.write_text('\n'.join(parts), encoding='utf-8')
print('Yazildi:', out2)
