"""Pendik 2024 Meclis — Kayıp oy tek harita (Geçersiz + Sandığa Gitmeyen + Küçük Partiler).
Diverging: ilçe ortalamasından sapma (alt=kırmızı, üst=mavi)."""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'

xls = pd.read_excel(ROOT/'PENDİK/Secim/2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.xlsx')
piv = xls.pivot_table(index='muhtarlik_ADI', columns='variable', values='value', aggfunc='sum').fillna(0)

EXCLUDE = {'secmen_SAYISI','oy_KULLANAN_SECMEN_SAYISI','gecerli_OY_TOPLAMI','gecersiz_OY_TOPLAMI',
           'itirazsiz_GECERLI_OY_SAYISI','itirazli_GECERLI_OY_SAYISI'}
ALL_PARTIES = [c for c in piv.columns if c not in EXCLUDE]
NAMED = ['AK PARTİ','CHP','YENİDEN REFAH','ZAFER PARTİSİ','SAADET','İYİ PARTİ','BÜYÜK BİRLİK','TİP']

# Mahalle bazli toplam kayip = gecersiz + sandiga_gitmeyen + diger (kucuk partiler)
piv['kayip_oy']    = (piv['gecersiz_OY_TOPLAMI']
                      + (piv['secmen_SAYISI'] - piv['oy_KULLANAN_SECMEN_SAYISI'])
                      + (sum(piv[p] for p in ALL_PARTIES) - sum(piv[p] for p in NAMED)))
piv['kayip_pct']   = piv['kayip_oy'] / piv['secmen_SAYISI'] * 100

# Ilce ortalamasi (toplam kayip / toplam secmen)
ilce_avg = piv['kayip_oy'].sum() / piv['secmen_SAYISI'].sum() * 100
print(f'Pendik kayıp ortalaması: %{ilce_avg:.2f}')

sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle
piv['_n'] = [normalize_mahalle(m) for m in piv.index]

shp = gpd.read_file(ROOT/'PENDİK/Harita Teknik Dosya/PENDİK.shp').to_crs(3857)
shp['_n'] = shp['MAHALLEADI'].apply(normalize_mahalle)
gdf = shp.merge(piv[['_n','kayip_pct']], on='_n', how='left')
gdf['rel'] = gdf['kayip_pct'] - ilce_avg
print(f'rel min={gdf["rel"].min():.2f}, max={gdf["rel"].max():.2f}')
print(f'kayip_pct min={gdf["kayip_pct"].min():.2f}, max={gdf["kayip_pct"].max():.2f}')

# Asimetrik diverging: alt yarisi vmin->ilce, ust yarisi ilce->vmax
vmin = float(gdf['kayip_pct'].min())
vmax_v = float(gdf['kayip_pct'].max())
print(f'vmin={vmin:.2f}, ilce={ilce_avg:.2f}, vmax={vmax_v:.2f}')

def color(v):
    if pd.isna(v): return '#ececec'
    if v <= ilce_avg:
        a = (ilce_avg - v) / (ilce_avg - vmin) if (ilce_avg - vmin) > 0 else 0
        a = max(0, min(1, a))
        r=int(247+(178-247)*a); g=int(247+( 24-247)*a); b=int(247+( 43-247)*a)
    else:
        t = (v - ilce_avg) / (vmax_v - ilce_avg) if (vmax_v - ilce_avg) > 0 else 0
        t = max(0, min(1, t))
        r=int(247+( 33-247)*t); g=int(247+(102-247)*t); b=int(247+(172-247)*t)
    return f'#{r:02x}{g:02x}{b:02x}'

# Layout (yrp_2024_split ile ayni standart)
W = 1600
PAD = 30
minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx-minx, maxy-miny
s = (W - 2*PAD)/bw
H = int(round(bh*s + 2*PAD))
def tr(x,y): return PAD+(x-minx)*s, (H-PAD)-(y-miny)*s

def gpath(g):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
    rings = []
    for p in polys:
        for ring in [p.exterior]+list(p.interiors):
            cs = list(ring.coords)
            if not cs: continue
            d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs)+' Z'
            rings.append(d)
    return ' '.join(rings)

paths = []
for _, row in gdf.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    v = row['kayip_pct']; rel = row['rel']
    fill = color(v)
    lbl = f"{row['MAHALLEADI']} — kayıp %{v:.2f} (sapma {rel:+.2f})" if not pd.isna(v) else f"{row['MAHALLEADI']} — veri yok"
    paths.append(f'    <path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
       f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision">\n'
       '  <style>.polygons path{stroke:#fff;stroke-width:0.5}</style>\n'
       '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n</svg>\n')
out = OUT/'pendik_2024mec_kayip.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
