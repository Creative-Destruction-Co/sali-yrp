"""Saadet 4 dönem (2011, 2015H, 2015K, 2018) — 2×2 panel.
Her panel kendi asimetrik diverging skalası + panel-içi lejant (gerçek puanlar)."""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'
BASE = ROOT / 'PENDİK/oranlar'
SHP = ROOT / 'PENDİK/Harita Teknik Dosya/PENDİK.shp'

sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

files = {
    '2011':         BASE/'oran_2011_MİLLETVEKİLİ_GENEL.csv',
    '2015 Haziran': BASE/'oran_2015_Haziran_MİLLETVEKİLİ_GENEL.csv',
    '2015 Kasım':   BASE/'oran_2015_Kasım_MİLLETVEKİLİ_GENEL.csv',
    '2018':         BASE/'oran_2018_MİLLETVEKİLİ_GENEL.csv',
}

def load(p):
    df = pd.read_csv(p)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    cands = [c for c in parties if 'SAADET' in c.upper()]
    if not cands: return None
    df['_avg'] = df[cands[0]] / df['n_sandik']
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']]

data = {k: load(p) for k,p in files.items()}
ilce_avg = {k: float((d['_avg']*d['gecerli_oy_toplam']).sum() / d['gecerli_oy_toplam'].sum() * 100) for k,d in data.items()}
print('İlçe ort:', {k: round(v,2) for k,v in ilce_avg.items()})

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_n'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
for k,d in data.items():
    gdf[f'v_{k}'] = gdf['_n'].map(d['_avg']) * 100

# Panel-bazli vmin/vmax
vstats = {}
for k in data:
    s = gdf[f'v_{k}']
    vstats[k] = (float(s.min()), float(s.max()))
    print(f'  {k}: min={vstats[k][0]:.2f}, max={vstats[k][1]:.2f}, ilce={ilce_avg[k]:.2f}')

def color(v, vmin, ilce, vmax):
    if pd.isna(v): return '#ececec'
    if v <= ilce:
        a = (ilce - v) / (ilce - vmin) if (ilce - vmin) > 0 else 0
        a = max(0, min(1, a))
        r=int(247+(178-247)*a); g=int(247+( 24-247)*a); b=int(247+( 43-247)*a)
    else:
        t = (v - ilce) / (vmax - ilce) if (vmax - ilce) > 0 else 0
        t = max(0, min(1, t))
        r=int(247+( 33-247)*t); g=int(247+(102-247)*t); b=int(247+(172-247)*t)
    return f'#{r:02x}{g:02x}{b:02x}'

minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx-minx, maxy-miny

# Layout: 2x2 grid
W, H = 1600, 1000
COLS, ROWS = 2, 2
cell_w = W / COLS
cell_h = H / ROWS
TITLE_H = 60
LEG_H = 70
inner_pad = 18
map_w = cell_w - 2*inner_pad
map_h = cell_h - TITLE_H - LEG_H - inner_pad
sp = min(map_w/bw, map_h/bh)
draw_w = bw*sp; draw_h = bh*sp

elems = []
elems.append('<defs><linearGradient id="sgrad" x1="0%" x2="100%"><stop offset="0%" stop-color="#b2182b"/><stop offset="50%" stop-color="#f7f7f7"/><stop offset="100%" stop-color="#2166ac"/></linearGradient></defs>')

panels = list(data.keys())
for i,k in enumerate(panels):
    cx = (i % COLS) * cell_w
    cy = (i // COLS) * cell_h
    vmin, vmax = vstats[k]; il = ilce_avg[k]
    # baslik
    elems.append(f'<text x="{cx + cell_w/2:.1f}" y="{cy + 32}" text-anchor="middle" font-size="22" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(k)}</text>')
    elems.append(f'<text x="{cx + cell_w/2:.1f}" y="{cy + 52}" text-anchor="middle" font-size="14" font-family="Inter Tight,sans-serif" font-style="italic" fill="#666">Pendik ortalaması: %{il:.2f}</text>')
    # harita transform
    ox = cx + (cell_w - draw_w)/2
    oy = cy + TITLE_H + (map_h - draw_h)/2
    def make_tr(ox=ox, oy=oy, sp=sp):
        def tr(x,y): return ox+(x-minx)*sp, (oy+draw_h)-(y-miny)*sp
        return tr
    tr = make_tr()
    # paths
    for _, row in gdf.iterrows():
        g = row.geometry
        if g is None or g.is_empty: continue
        polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
        rings = []
        for p in polys:
            for r in [p.exterior]+list(p.interiors):
                cs = list(r.coords)
                if not cs: continue
                d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs)+' Z'
                rings.append(d)
        if not rings: continue
        v = row[f'v_{k}']
        fill = color(v, vmin, il, vmax)
        lbl = f"{row['MAHALLEADI']} — %{v:.2f}" if not pd.isna(v) else f"{row['MAHALLEADI']} — veri yok"
        elems.append(f'<path d="{' '.join(rings)}" fill="{fill}" stroke="#fff" stroke-width="0.5"><title>{escape(lbl)}</title></path>')
    # panel-ici lejant (asimetrik gradient): vmin -> il -> vmax
    leg_y = cy + TITLE_H + map_h + 16
    leg_w = cell_w * 0.62
    leg_x0 = cx + (cell_w - leg_w)/2
    # ortalamanin bargradient'taki konumu
    midpct = (il - vmin)/(vmax - vmin)*100 if vmax>vmin else 50
    elems.append(f'<rect x="{leg_x0:.1f}" y="{leg_y}" width="{leg_w:.1f}" height="12" '
                 f'fill="url(#sgrad-{i})" stroke="#999" stroke-width="0.5"/>')
    elems.append(f'<linearGradient id="sgrad-{i}" x1="0%" x2="100%">'
                 f'<stop offset="0%" stop-color="#b2182b"/>'
                 f'<stop offset="{midpct:.1f}%" stop-color="#f7f7f7"/>'
                 f'<stop offset="100%" stop-color="#2166ac"/>'
                 f'</linearGradient>')
    elems.append(f'<text x="{leg_x0:.1f}" y="{leg_y + 28}" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">%{vmin:.2f}</text>')
    elems.append(f'<text x="{leg_x0 + leg_w*midpct/100:.1f}" y="{leg_y + 28}" text-anchor="middle" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">%{il:.2f}</text>')
    elems.append(f'<text x="{leg_x0 + leg_w:.1f}" y="{leg_y + 28}" text-anchor="end" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">%{vmax:.2f}</text>')

svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
       f'preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'
       + '\n'.join(elems) + '\n</svg>\n')
out = OUT/'pendik_saadet_4donem.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
