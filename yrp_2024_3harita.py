import pandas as pd
import geopandas as gpd
from pathlib import Path
from xml.sax.saxutils import escape
import sys
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

BASE = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/oranlar')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/Harita Teknik Dosya/PENDİK.shp')

files = {
    'İBB Başkanlığı': BASE / 'oran_2024_BÜYÜKŞEHİR_BELEDİYE_BAŞKANLIĞI.csv',
    'İlçe Belediye Başkanlığı': BASE / 'oran_2024_BELEDİYE_BAŞKANLIĞI.csv',
    'Belediye Meclisi': BASE / 'oran_2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.csv',
}
def load_yrp(path):
    df = pd.read_csv(path)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    cands = [c for c in parties if 'YENİDEN REFAH' in c.upper()]
    if not cands: return None
    df['_avg'] = df[cands[0]] / df['n_sandik']
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']]

data = {k: load_yrp(v) for k,v in files.items()}
ilce_avg = {k:(d['_avg']*d['gecerli_oy_toplam']).sum()/d['gecerli_oy_toplam'].sum()*100 for k,d in data.items() if d is not None}
print('YRP ilce ort:', {k: round(v,2) for k,v in ilce_avg.items()})

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
for k,d in data.items():
    gdf[f'v_{k}'] = gdf['_k'].map(d['_avg']) * 100
    gdf[f'rel_{k}'] = gdf[f'v_{k}'] - ilce_avg[k]

all_rel = pd.concat([gdf[f'rel_{k}'] for k in data]).abs()
vmax = float(all_rel.max() or 0)
print(f'rel abs max: {vmax:.2f}')

def color(v):
    if pd.isna(v): return '#a5cce8'
    t = max(-1, min(1, v / vmax)) if vmax > 0 else 0
    if t >= 0:
        # Mavi (uzeri ortalama)
        r = int(247 + (33 - 247) * t); g = int(252 + (102 - 252) * t); b = int(245 + (172 - 245) * t)
    else:
        # Kirmizi (alti ortalama)
        a = -t
        r = int(247 + (179 - 247) * a); g = int(252 + (24 - 252) * a); b = int(245 + (43 - 245) * a)
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
PX = 3
pw = W // PX
parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }',
    '.polygons path { stroke: #fff; stroke-width: 0.5; }',
    '.title { font-size: 22px; font-weight: 700; }',
    '.panel-title { font-size: 17px; font-weight: 600; }',
    '.panel-sub { font-size: 13px; fill: #666; }</style>',
    f'<text x="40" y="38" class="title">Pendik 2024 — Yeniden Refah Partisi: 3 Seçim Karşılaştırması</text>',
]
for i, k in enumerate(data.keys()):
    if data[k] is None: continue
    px = i * pw + 20
    py = 60
    pad_p = 18; title_p = 50
    map_w = pw - 2 * pad_p
    map_h = H - py - pad_p - 60
    sp = min(map_w / bw, map_h / bh)
    ox = px + pad_p + (map_w - bw * sp) / 2
    oy = py + title_p + (map_h - bh * sp) / 2
    def make_t(ox=ox, oy=oy, sp=sp):
        def tr(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
        return tr
    tr_p = make_t()
    parts.append(f'<text x="{px + pad_p}" y="{py + 22}" class="panel-title">{escape(k)}</text>')
    parts.append(f'<text x="{px + pad_p}" y="{py + 40}" class="panel-sub">Pendik ortalama: %{ilce_avg[k]:.2f}</text>')
    parts.append('<g class="polygons">')
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr_p)
        if not d: continue
        v = row[f'v_{k}']; rel = row[f'rel_{k}']
        fill = color(rel)
        if pd.isna(v):
            lbl = f"{row['MAHALLEADI']} - veri yok"
        else:
            lbl = f"{row['MAHALLEADI']} - %{v:.2f} (sapma {rel:+.2f})"
        parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    parts.append('</g>')

ly = H - 36
lw = 380
lx = (W - lw) / 2
n = 24
parts.extend(f'<rect x="{lx + (i/n)*lw:.1f}" y="{ly}" width="{lw/n + 1:.1f}" height="14" fill="{color((i/(n-1)*2-1)*vmax)}"/>' for i in range(n))
parts.append(f'<text x="{lx}" y="{ly - 6}" font-size="13" font-weight="600">Pendik ortalamasına göre sapma (puan)</text>')
parts.append(f'<text x="{lx}" y="{ly + 28}" font-size="12">{-vmax:+.2f}</text>')
parts.append(f'<text x="{lx + lw/2}" y="{ly + 28}" font-size="12" text-anchor="middle">0</text>')
parts.append(f'<text x="{lx + lw}" y="{ly + 28}" font-size="12" text-anchor="end">{vmax:+.2f}</text>')
parts.append('</svg>')

out = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/haritalar/PENDIK_YRP_2024_3secim.svg')
out.write_text('\n'.join(parts), encoding='utf-8')
print(f'Yazildi: {out}')
