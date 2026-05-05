"""YRP 2024 — her seçim türü için ayrı SVG (3 ayrı slayt)."""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

BASE = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/oranlar')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/PENDİK/Harita Teknik Dosya/PENDİK.shp')
OUT = Path(r'D:/Yepisyeni Seçim/Seçim/_v2_assets')

files = {
    'ibb': (BASE/'oran_2024_BÜYÜKŞEHİR_BELEDİYE_BAŞKANLIĞI.csv', 'İBB Başkanlığı'),
    'ilce': (BASE/'oran_2024_BELEDİYE_BAŞKANLIĞI.csv', 'İlçe Belediye Başkanlığı'),
    'meclis': (BASE/'oran_2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.csv', 'Belediye Meclisi'),
}

def load_yrp(path):
    df = pd.read_csv(path)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    cands = [c for c in parties if 'YENİDEN REFAH' in c.upper()]
    if not cands: return None
    df['_avg'] = df[cands[0]] / df['n_sandik']
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']]

data = {k:(load_yrp(v[0]), v[1]) for k,v in files.items()}
ilce_avg = {k: (d[0]['_avg']*d[0]['gecerli_oy_toplam']).sum()/d[0]['gecerli_oy_toplam'].sum()*100 for k,d in data.items()}
print({k: round(v,2) for k,v in ilce_avg.items()})

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
for k,(d,_) in data.items():
    gdf[f'v_{k}'] = gdf['_k'].map(d['_avg']) * 100
    gdf[f'rel_{k}'] = gdf[f'v_{k}'] - ilce_avg[k]

# Diverging: rel = v - ilce_avg; alt = kirmizi, ust = mavi (ortak vmax)
vmax = float(pd.concat([gdf[f'rel_{k}'] for k in data]).abs().max())
print(f'vmax {vmax:.2f}')

def color(v):
    if pd.isna(v): return '#ececec'
    t = max(-1.0, min(1.0, v / vmax))
    if t >= 0:
        # beyaz (#f7f7f7) -> koyu mavi (#2166ac)
        r=int(247+( 33-247)*t); g=int(247+(102-247)*t); b=int(247+(172-247)*t)
    else:
        a=-t
        # beyaz (#f7f7f7) -> koyu kirmizi (#b2182b)
        r=int(247+(178-247)*a); g=int(247+( 24-247)*a); b=int(247+( 43-247)*a)
    return f'#{r:02x}{g:02x}{b:02x}'

minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx-minx, maxy-miny

def geom_d(g, tr):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
    rings=[]
    for p in polys:
        for r in [p.exterior]+list(p.interiors):
            cs = list(r.coords)
            if not cs: continue
            d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs) + ' Z'
            rings.append(d)
    return ' '.join(rings)

W, pad = 1600, 30
s_scale = (W-2*pad)/bw
H = int(round(bh*s_scale + 2*pad))
def tr(x,y): return pad+(x-minx)*s_scale, (H-pad)-(y-miny)*s_scale

for k,(_,label) in data.items():
    paths = []
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr)
        if not d: continue
        v = row[f'v_{k}']; rel = row[f'rel_{k}']
        fill = color(rel)
        lbl = f"{row['MAHALLEADI']} — %{v:.2f} (sapma {rel:+.2f})" if not pd.isna(v) else f"{row['MAHALLEADI']} — veri yok"
        paths.append(f'    <path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
           f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision">\n'
           '  <style>.polygons path { stroke: #fff; stroke-width: 0.5; }</style>\n'
           '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n</svg>\n')
    out = OUT/f'pendik_yrp_2024_{k}.svg'
    out.write_text(svg, encoding='utf-8')
    print(f'  {out.name}: {len(svg)//1024}KB, ortalama %{ilce_avg[k]:.2f}')
