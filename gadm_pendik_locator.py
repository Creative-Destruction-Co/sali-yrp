"""GADM 4.1 ile Pendik locator haritalari: il (Istanbul vurgulu) + ilce (Pendik vurgulu).
Stil sunum_v2'deki TR il/ilce winner gibi: beyaz BG, gri arkaplan, vurgu rengi, beyaz ic sinir."""
from __future__ import annotations
import sys
from pathlib import Path
from xml.sax.saxutils import escape
import geopandas as gpd

ROOT = Path(r'D:\Yepisyeni Seçim\Seçim')
SRC = ROOT / '_gadm_tr'
OUT = ROOT / '_v2_assets'
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

GRAY = '#d8dde0'
HIGHLIGHT = '#e63946'  # CHP kirmizi (canli)
STROKE_INNER = '#ffffff'
STROKE_OUTER = '#1a1a1a'

def geom_path(g, transform):
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

def render(gdf, hi_mask, label_col, hi_label, out_path, width=1600):
    gdf = gdf.to_crs(3857)
    minx, miny, maxx, maxy = gdf.total_bounds
    bw, bh = maxx - minx, maxy - miny
    pad = 30
    s = (width - 2 * pad) / bw
    height = int(round(bh * s + 2 * pad))
    def tr(x, y):
        return pad + (x - minx) * s, (height - pad) - (y - miny) * s

    paths = []
    for _, row in gdf.iterrows():
        d = geom_path(row.geometry, tr)
        if not d: continue
        is_hi = bool(hi_mask.loc[row.name]) if row.name in hi_mask.index else False
        fill = HIGHLIGHT if is_hi else GRAY
        title = escape(str(row[label_col]))
        paths.append(f'    <path d="{d}" fill="{fill}"><title>{title}</title></path>')

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" '
        'shape-rendering="geometricPrecision">\n'
        '  <style>\n'
        f'    .polygons path {{ stroke: {STROKE_INNER}; stroke-width: 0.4; }}\n'
        f'    .polygons path:hover {{ stroke: #000; stroke-width: 1.5; }}\n'
        '  </style>\n'
        '  <g class="polygons">\n'
        + '\n'.join(paths) + '\n'
        '  </g>\n'
        '</svg>\n'
    )
    out_path.write_text(svg, encoding='utf-8')
    print(f'  {out_path.name}: {len(gdf)} feature, {len(svg)//1024}KB, vurgu="{hi_label}"')

# ADM-1: Istanbul vurgulu
g1 = gpd.read_file(SRC / 'gadm41_TUR_1.shp')
mask1 = g1['NAME_1'].str.upper().str.contains('STANBUL', na=False)
print(f'ADM-1: Istanbul match = {int(mask1.sum())}')
render(g1, mask1, 'NAME_1', 'İstanbul', OUT / 'pendik_locator_il.svg')

# ADM-2: Pendik vurgulu
g2 = gpd.read_file(SRC / 'gadm41_TUR_2.shp')
mask2 = (g2['NAME_2'].str.upper() == 'PENDIK') | (g2['NAME_2'].str.upper() == 'PENDİK'.upper())
print(f'ADM-2: Pendik match = {int(mask2.sum())}')
render(g2, mask2, 'NAME_2', 'Pendik', OUT / 'pendik_locator_ilce.svg')
