"""YRP 2024 Belediye Meclisi mahalle haritası — asimetrik diverging."""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'

df = pd.read_csv(ROOT/'PENDİK/oranlar/oran_2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.csv')
df['_avg'] = df['YENİDEN REFAH'] / df['n_sandik']
ilce_real = float((df['_avg']*df['gecerli_oy_toplam']).sum() / df['gecerli_oy_toplam'].sum() * 100)
ilce = 4.22  # ortak midpoint (15 ile aynı)

shp = gpd.read_file(ROOT/'PENDİK/Harita Teknik Dosya/PENDİK.shp').to_crs(3857)
shp['_n'] = shp['MAHALLEADI'].apply(normalize_mahalle)
shp = shp.merge(df.set_index('normalized')['_avg'], left_on='_n', right_index=True, how='left')
shp['v'] = shp['_avg']*100

vmin = 1.44; vmax = 6.73  # ortak skala
print(f'ilce_real={ilce_real:.2f}, ortak midpoint={ilce:.2f}, vmin={vmin:.2f}, vmax={vmax:.2f}')

def color(v):
    if pd.isna(v): return '#ececec'
    if v <= ilce:
        a = (ilce - v)/(ilce - vmin) if (ilce - vmin) > 0 else 0
        a = max(0, min(1, a))
        r=int(247+(178-247)*a); g=int(247+( 24-247)*a); b=int(247+( 43-247)*a)
    else:
        t = (v - ilce)/(vmax - ilce) if (vmax - ilce) > 0 else 0
        t = max(0, min(1, t))
        r=int(247+( 33-247)*t); g=int(247+(102-247)*t); b=int(247+(172-247)*t)
    return f'#{r:02x}{g:02x}{b:02x}'

W = 1600; PAD = 30
minx, miny, maxx, maxy = shp.total_bounds
bw, bh = maxx-minx, maxy-miny
s = (W-2*PAD)/bw
H = int(round(bh*s + 2*PAD))
def tr(x,y): return PAD+(x-minx)*s, (H-PAD)-(y-miny)*s

def gpath(g):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
    rings=[]
    for p in polys:
        for r in [p.exterior]+list(p.interiors):
            cs = list(r.coords)
            if not cs: continue
            d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs)+' Z'
            rings.append(d)
    return ' '.join(rings)

paths=[]
for _, row in shp.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    v = row['v']
    fill = color(v)
    lbl = f"{row['MAHALLEADI']} - %{v:.2f}" if not pd.isna(v) else f"{row['MAHALLEADI']} - veri yok"
    paths.append(f'    <path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
       f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision">\n'
       '  <style>.polygons path{stroke:#fff;stroke-width:0.5}</style>\n'
       '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n</svg>\n')
out = OUT/'pendik_yrp_2024_meclis.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
print(f'midpct={(ilce-vmin)/(vmax-vmin)*100:.1f}')
