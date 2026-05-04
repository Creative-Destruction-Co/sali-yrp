"""
Tum Turkiye ilceleri icin DOGUM YERI il bazli Trabzon+Rize+Giresun+Ordu yuzdesi.
Ilce adi -> il map. Origin illeri highlight edilmiyor (ayni renk skalasi).
"""
import pandas as pd
import geopandas as gpd
from pathlib import Path
from xml.sax.saxutils import escape
import sys, time

KARADENIZ4 = {'TRABZON','RİZE','GİRESUN','ORDU'}
SANDIK_DIR = Path(r'D:/Yepisyeni Seçim/Seçim/Sandık')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/Harita/turkey_ilce.shp')
IL_SHP = Path(r'D:/Yepisyeni Seçim/Seçim/tr_il_toplam/Harita/turkey_il.shp')
OUT_CSV = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/karadeniz4_dogum_oran.csv')
OUT_SVG = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/haritalar/TR_ILCE_KARADENIZ4_dogum_oran.svg')

# Ilce -> il map (TR ilce SHP'den)
print('Ilce->il map yukleniyor...', flush=True)
sgdf = gpd.read_file(SHP)
sgdf['_ilce_u'] = sgdf['ILCEADI'].astype(str).str.strip().str.upper()
sgdf['_il_u'] = sgdf['ILADI'].astype(str).str.strip().str.upper()
# Onemli: KARADENIZ4 illerinin ilceleri kesin TR/RZ/GR/OR'a yazilsin
ilce_il = {}
for il, ilce in sgdf[['_il_u','_ilce_u']].itertuples(index=False):
    # Cakismalarda KARADENIZ4 oncelikli
    if ilce in ilce_il and il in KARADENIZ4:
        ilce_il[ilce] = il
    elif ilce not in ilce_il:
        ilce_il[ilce] = il
# MERKEZ key'i guvensiz (her ilde var, son yazana gider) — sil
ilce_il.pop('MERKEZ', None)
# Il adlarini map'e ekle (il merkez DOGUM YERI = il adinin kendisi: BAYBURT, ERZURUM, RIZE...)
for il_u in sgdf['_il_u'].unique():
    ilce_il[il_u] = il_u
print(f'  {len(ilce_il)} mapping (MERKEZ haric)')

t0 = time.time()
files = sorted(SANDIK_DIR.glob('*.csv'))
print(f'{len(files)} sandik dosyasi taranıyor (DOGUM YERI)...', flush=True)
rows = []
for i, f in enumerate(files):
    if i % 50 == 0:
        print(f'  [{i}/{len(files)}] {f.name} | {time.time()-t0:.1f}s', flush=True)
    try:
        df = None
        for enc in ('utf-8', 'cp1254', 'latin-1'):
            try:
                df = pd.read_csv(f, usecols=['ADRES İL ADI','ADRES İLÇE ADI','DOĞUM YERİ'], encoding=enc, low_memory=False)
                break
            except UnicodeDecodeError:
                continue
        if df is None or len(df) == 0:
            continue
        il = str(df['ADRES İL ADI'].iloc[0]).strip().upper()
        ilce = str(df['ADRES İLÇE ADI'].iloc[0]).strip().upper()
        # Il prefix sok: "RIZE MERKEZ" -> "MERKEZ" (SHP'ye uyumlu)
        if ilce.startswith(il + ' '):
            ilce = ilce[len(il)+1:].strip()
        dogum = df['DOĞUM YERİ'].astype(str).str.strip().str.upper()
        # Ilce adini il'e cevir
        dogum_il = dogum.map(ilce_il)
        total = len(dogum)
        kok = dogum_il.isin(KARADENIZ4).sum()
        rows.append((il, ilce, total, int(kok), kok / total * 100 if total else 0))
    except Exception as e:
        print(f'  HATA {f.name}: {e}', file=sys.stderr)

out = pd.DataFrame(rows, columns=['il','ilce','toplam_secmen','karadeniz4_secmen','yuzde'])
out.to_csv(OUT_CSV, index=False, encoding='utf-8')
print(f'\nCSV: {OUT_CSV} ({len(out)} ilce)')
print('Top 15:'); print(out.sort_values('yuzde', ascending=False).head(15).to_string(index=False))

# SVG choropleth — origin highlight YOK, tum ilceler ayni skalada
gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_key'] = gdf['ILADI'].str.strip().str.upper() + '|' + gdf['ILCEADI'].str.strip().str.upper()
out['_key'] = out['il'] + '|' + out['ilce']
pct_map = dict(zip(out['_key'], out['yuzde']))
cnt_map = dict(zip(out['_key'], out['karadeniz4_secmen']))
gdf['_pct'] = gdf['_key'].map(pct_map).fillna(0.0)
gdf['_cnt'] = gdf['_key'].map(cnt_map).fillna(0).astype(int)
max_pct = float(gdf['_pct'].max() or 0)
print(f'max: {max_pct:.2f}%')

def color(p):
    if pd.isna(p) or p <= 0 or max_pct <= 0: return '#f5f5f5'
    t = (p / max_pct) ** 0.4
    t = min(1.0, t)
    r = int(255 + (10 - 255) * t); g = int(255 + (90 - 255) * t); b = int(255 + (40 - 255) * t)
    return f'#{r:02x}{g:02x}{b:02x}'

W = 1600; pad = 30; title_h = 36; legend_h = 70
minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx - minx, maxy - miny
s = (W - 2 * pad) / bw
map_h = int(round(bh * s + pad))
H = title_h + map_h + legend_h + pad
def tr(x, y): return pad + (x - minx) * s, (title_h + map_h) - (y - miny) * s

def geom_d(g):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    rings = []
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            coords = list(ring.coords)
            if not coords: continue
            d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in coords) + ' Z'
            rings.append(d)
    return ' '.join(rings)

paths = []
for _, row in gdf.iterrows():
    d = geom_d(row.geometry)
    if not d: continue
    p = row['_pct']; c = row['_cnt']
    fill = color(p)
    lbl = f"{row['ILADI']} - {row['ILCEADI']} | {c:,} kisi (%{p:.2f})"
    paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

il_paths = []
il_gdf = gpd.read_file(IL_SHP).to_crs(3857)
for _, row in il_gdf.iterrows():
    d = geom_d(row.geometry)
    if d: il_paths.append(f'<path d="{d}"/>')

legend_y = title_h + map_h + 28
lw = 360; lx = (W - lw) / 2
n = 24
stops = [f'<rect x="{lx + (i/n)*lw:.1f}" y="{legend_y}" width="{lw/n + 1:.1f}" height="14" fill="{color((i/(n-1))*max_pct)}"/>' for i in range(n)]
labels = [
    f'<text x="{lx}" y="{legend_y - 6}" font-size="13" font-weight="600">DOGUM YERI Trabzon+Rize+Giresun+Ordu yuzdesi</text>',
    f'<text x="{lx}" y="{legend_y + 30}" font-size="12">0%</text>',
    f'<text x="{lx + lw}" y="{legend_y + 30}" font-size="12" text-anchor="end">{max_pct:.1f}%</text>',
]
title = "Turkiye - Dogum Yeri Trabzon/Rize/Giresun/Ordu olan secmenler (Ilce)"
svg = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">\n'
    '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }\n'
    '.polygons path { stroke: #fff; stroke-width: 0.4; }\n'
    '.il-borders path { fill: none; stroke: #1a1a1a; stroke-width: 1.4; pointer-events: none; }</style>\n'
    f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>\n'
    '<g class="polygons">' + '\n'.join(paths) + '</g>\n'
    '<g class="il-borders">' + '\n'.join(il_paths) + '</g>\n'
    '<g>' + '\n'.join(stops + labels) + '</g>\n</svg>\n'
)
OUT_SVG.write_text(svg, encoding='utf-8')
print(f'SVG: {OUT_SVG}')
print(f'Sure: {time.time()-t0:.1f}s')
