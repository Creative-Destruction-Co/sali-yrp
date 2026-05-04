"""
Ilce-bazli pipeline: AKP swing, Saadet, YRP 3-secim, sag-sol winner+LISA, bolge/gelir/cross bar.
Hardcoded ilceye dokunmaz; --ilce-dir + --il + --ilce parametre.
"""
import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import geopandas as gpd

sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

ap = argparse.ArgumentParser()
ap.add_argument('--ilce-dir', required=True)
ap.add_argument('--il', required=True)
ap.add_argument('--ilce', required=True)
ap.add_argument('--proje-dir', required=True)
args = ap.parse_args()

ILCE_DIR = Path(args.ilce_dir)
HARITALAR = ILCE_DIR / 'haritalar'; HARITALAR.mkdir(parents=True, exist_ok=True)
ORANLAR = ILCE_DIR / 'oranlar'
SHP = next((ILCE_DIR / 'Harita Teknik Dosya').glob('*.shp'))
IL = args.il.upper(); ILCE = args.ilce.upper()

SAG = {'AK PARTİ','MHP','İYİ PARTİ','YENİDEN REFAH','ZAFER PARTİSİ','BBP','ANAP','GENÇPARTİ','AP','HAK-PAR','GBP','MİLLİ YOL','YP','MİLLET'}
SOL = {'CHP','YEŞİL SOL PARTİ','TİP','MEMLEKET','VATAN PARTİSİ','SOL PARTİ','TKP','TKH','HKP','AB'}

def load(year_stem, party_query):
    p = ORANLAR / f'oran_{year_stem}.csv'
    if not p.exists(): return None
    df = pd.read_csv(p)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    cands = [c for c in parties if party_query in c.upper()]
    if not cands: return None
    df['_avg'] = df[cands[0]] / df['n_sandik']
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']]

gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
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

def page_dims():
    W = 1600; pad = 30; title_h = 36; legend_h = 80
    s_ = (W - 2 * pad) / bw
    map_h = int(round(bh * s_ + pad))
    H = title_h + map_h + legend_h + pad
    def tr(x, y): return pad + (x - minx) * s_, (title_h + map_h) - (y - miny) * s_
    return W, H, pad, title_h, map_h, legend_h, tr

def diverging(d, vmax):
    if pd.isna(d): return '#a5cce8'
    t = max(-1, min(1, d / vmax)) if vmax > 0 else 0
    if t >= 0:
        r = int(255 + (10 - 255) * t); g = int(255 + (90 - 255) * t); b = int(255 + (140 - 255) * t)
    else:
        r = int(255 + (200 - 255) * (-t)); g = int(255 + (20 - 255) * (-t)); b = int(255 + (40 - 255) * (-t))
    return f'#{r:02x}{g:02x}{b:02x}'

def write_svg(parts, fname):
    out = HARITALAR / fname
    out.write_text('\n'.join(parts), encoding='utf-8')
    print(f'  -> {out.name}')

# ======================================================================
# 1. AKP 2018->2023 swing (relative to ilce avg)
# ======================================================================
print('1. AKP 2018->2023 swing')
m18 = load('2018_MİLLETVEKİLİ_GENEL', 'AK PART')
m23 = load('2023_MİLLETVEKİLİ_GENEL', 'AK PART')
if m18 is not None and m23 is not None:
    ilce18 = (m18['_avg']*m18['gecerli_oy_toplam']).sum()/m18['gecerli_oy_toplam'].sum()*100
    ilce23 = (m23['_avg']*m23['gecerli_oy_toplam']).sum()/m23['gecerli_oy_toplam'].sum()*100
    ilce_swing = ilce23 - ilce18
    gdf['v18'] = gdf['_k'].map(m18['_avg']) * 100
    gdf['v23'] = gdf['_k'].map(m23['_avg']) * 100
    gdf['rel'] = (gdf['v23'] - gdf['v18']) - ilce_swing
    vmax = float(gdf['rel'].abs().max() or 0)
    W, H, pad, title_h, map_h, legend_h, tr = page_dims()
    paths = []
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr)
        if not d: continue
        rel = row['rel']; delta = row['v23'] - row['v18']
        fill = diverging(rel, vmax)
        lbl = f"{row['MAHALLEADI']} - degisim {delta:+.1f} pp, sapma {rel:+.1f}" if pd.notna(rel) else f"{row['MAHALLEADI']} - veri yok"
        paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    legend_y = title_h + map_h + 28; lw = 380; lx = (W - lw) / 2
    n = 24
    stops = [f'<rect x="{lx + (i/n)*lw:.1f}" y="{legend_y}" width="{lw/n + 1:.1f}" height="14" fill="{diverging((i/(n-1)*2-1)*vmax, vmax)}"/>' for i in range(n)]
    title = f"{ILCE.title()} - AK Parti 2018->2023, Ilce Ortalamasina Gore Sapma"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
        '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }</style>',
        f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>',
        '<g class="polygons">' + '\n'.join(paths) + '</g>',
        '<g>' + '\n'.join(stops) + f'<text x="{lx}" y="{legend_y - 6}" font-size="13" font-weight="600">Ilce sapmasi (puan), Ilce swing: {ilce_swing:+.2f}</text><text x="{lx}" y="{legend_y + 30}" font-size="12">{-vmax:+.1f}</text><text x="{lx + lw/2}" y="{legend_y + 30}" font-size="12" text-anchor="middle">0</text><text x="{lx + lw}" y="{legend_y + 30}" font-size="12" text-anchor="end">{vmax:+.1f}</text></g>',
        '</svg>'
    ]
    write_svg(parts, 'AKP_2018_2023_swing.svg')

# ======================================================================
# 2. Saadet swing 2015K->2018 + 4 (or 3) donem
# ======================================================================
print('2. Saadet')
periods = [('2011','2011_MİLLETVEKİLİ_GENEL'),('2015 Haziran','2015_Haziran_MİLLETVEKİLİ_GENEL'),
           ('2015 Kasım','2015_Kasım_MİLLETVEKİLİ_GENEL'),('2018','2018_MİLLETVEKİLİ_GENEL')]
data = {k: load(s, 'SAADET') for k,s in periods}
data = {k:v for k,v in data.items() if v is not None}
if '2015 Kasım' in data and '2018' in data:
    ilce_avg = {k: (d['_avg']*d['gecerli_oy_toplam']).sum()/d['gecerli_oy_toplam'].sum()*100 for k,d in data.items()}
    ilce_swing = ilce_avg['2018'] - ilce_avg['2015 Kasım']
    for k,d in data.items():
        gdf[f'sa_v_{k}'] = gdf['_k'].map(d['_avg']) * 100
        gdf[f'sa_rel_{k}'] = gdf[f'sa_v_{k}'] - ilce_avg[k]
    gdf['sa_swing_rel'] = (gdf['sa_v_2018'] - gdf['sa_v_2015 Kasım']) - ilce_swing
    # Swing harita
    vmax = float(gdf['sa_swing_rel'].abs().max() or 0)
    W, H, pad, title_h, map_h, legend_h, tr = page_dims()
    paths = []
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr)
        if not d: continue
        rel = row['sa_swing_rel']
        fill = diverging(rel, vmax)
        delta = row['sa_v_2018'] - row['sa_v_2015 Kasım'] if pd.notna(row['sa_v_2018']) and pd.notna(row['sa_v_2015 Kasım']) else None
        lbl = f"{row['MAHALLEADI']} - degisim {delta:+.1f} pp, sapma {rel:+.1f}" if delta is not None else f"{row['MAHALLEADI']} - veri yok"
        paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    legend_y = title_h + map_h + 28; lw = 380; lx = (W - lw) / 2
    n = 24
    stops = [f'<rect x="{lx + (i/n)*lw:.1f}" y="{legend_y}" width="{lw/n + 1:.1f}" height="14" fill="{diverging((i/(n-1)*2-1)*vmax, vmax)}"/>' for i in range(n)]
    title = f"{ILCE.title()} - Saadet 2015 Kasim->2018 Mahalle Sapmasi"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
        '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }</style>',
        f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>',
        '<g class="polygons">' + '\n'.join(paths) + '</g>',
        '<g>' + '\n'.join(stops) + f'<text x="{lx}" y="{legend_y - 6}" font-size="13" font-weight="600">Ilce sapmasi (puan), Ilce swing: {ilce_swing:+.2f}</text><text x="{lx}" y="{legend_y + 30}" font-size="12">{-vmax:+.1f}</text><text x="{lx + lw/2}" y="{legend_y + 30}" font-size="12" text-anchor="middle">0</text><text x="{lx + lw}" y="{legend_y + 30}" font-size="12" text-anchor="end">{vmax:+.1f}</text></g>',
        '</svg>'
    ]
    write_svg(parts, 'SAADET_2015K_2018_swing.svg')

    # 4 (or 3) donem panel
    n_panels = len(data)
    PX = 2; PY = (n_panels + 1) // 2
    W2, H2 = 1700, 550 * PY + 100
    pw = W2 // PX; ph = (H2 - 100) // PY
    all_rel = pd.concat([gdf[f'sa_rel_{k}'] for k in data]).abs()
    vmax2 = float(all_rel.max() or 0)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W2} {H2}" preserveAspectRatio="xMidYMid meet">',
        '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }\n.title { font-size: 22px; font-weight: 700; }\n.panel-title { font-size: 17px; font-weight: 600; }</style>',
        f'<text x="40" y="38" class="title">{escape(ILCE.title())} - Saadet, Ilce Ortalamasina Gore Mahalle Sapmasi</text>'
    ]
    for i, k in enumerate(data.keys()):
        px = (i % PX) * pw + 20; py = (i // PX) * ph + 50
        pad_p = 18; title_p = 40
        map_w = pw - 2 * pad_p; map_h_p = ph - title_p - 2 * pad_p
        sp = min(map_w / bw, map_h_p / bh)
        ox = px + pad_p + (map_w - bw * sp) / 2; oy = py + title_p + pad_p + (map_h_p - bh * sp) / 2
        def make_t(ox=ox, oy=oy, sp=sp):
            def tr2(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
            return tr2
        tr_p = make_t()
        parts.append(f'<text x="{px + pad_p}" y="{py + title_p - 6}" class="panel-title">{escape(k)} — {ILCE.title()}: %{ilce_avg[k]:.2f}</text>')
        parts.append('<g class="polygons">')
        for _, row in gdf.iterrows():
            d = geom_d(row.geometry, tr_p)
            if not d: continue
            rel = row[f'sa_rel_{k}']; v = row[f'sa_v_{k}']
            fill = diverging(rel, vmax2)
            lbl = f"{row['MAHALLEADI']} - %{v:.1f} (sapma {rel:+.1f})" if pd.notna(rel) else f"{row['MAHALLEADI']} - veri yok"
            parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
        parts.append('</g>')
    ly = H2 - 50; lx2 = (W2 - 380) / 2
    parts.extend(f'<rect x="{lx2 + (i/n)*380:.1f}" y="{ly}" width="{380/n + 1:.1f}" height="14" fill="{diverging((i/(n-1)*2-1)*vmax2, vmax2)}"/>' for i in range(n))
    parts.append(f'<text x="{lx2}" y="{ly - 6}" font-size="13" font-weight="600">Ilce ort sapma (puan)</text>')
    parts.append(f'<text x="{lx2}" y="{ly + 30}" font-size="12">{-vmax2:+.1f}</text>')
    parts.append(f'<text x="{lx2 + 190}" y="{ly + 30}" font-size="12" text-anchor="middle">0</text>')
    parts.append(f'<text x="{lx2 + 380}" y="{ly + 30}" font-size="12" text-anchor="end">{vmax2:+.1f}</text>')
    parts.append('</svg>')
    write_svg(parts, 'SAADET_donem_sapma.svg')

# ======================================================================
# 3. YRP 2024 3 secim divergent (ilce ort sapma)
# ======================================================================
print('3. YRP 2024 3-secim')
yrp_files = {
    'BB Baskanligi': '2024_BÜYÜKŞEHİR_BELEDİYE_BAŞKANLIĞI',
    'Belediye Baskanligi': '2024_BELEDİYE_BAŞKANLIĞI',
    'Belediye Meclisi': '2024_BELEDİYE_MECLİSİ_ÜYELİĞİ',
}
ydata = {k: load(v, 'YENİDEN REFAH') for k,v in yrp_files.items()}
ydata = {k:v for k,v in ydata.items() if v is not None}
if ydata:
    yilce = {k: (d['_avg']*d['gecerli_oy_toplam']).sum()/d['gecerli_oy_toplam'].sum()*100 for k,d in ydata.items()}
    for k,d in ydata.items():
        gdf[f'yrp_v_{k}'] = gdf['_k'].map(d['_avg']) * 100
        gdf[f'yrp_rel_{k}'] = gdf[f'yrp_v_{k}'] - yilce[k]
    all_rel = pd.concat([gdf[f'yrp_rel_{k}'] for k in ydata]).abs()
    vmax = float(all_rel.max() or 0)
    W, H = 1700, 760; PX = len(ydata); pw = W // PX
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
        '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }\n.title { font-size: 22px; font-weight: 700; }\n.panel-title { font-size: 17px; font-weight: 600; }\n.panel-sub { font-size: 13px; fill: #666; }</style>',
        f'<text x="40" y="38" class="title">{escape(ILCE.title())} 2024 - YRP, Ilce Ortalamasina Gore Sapma</text>'
    ]
    for i, k in enumerate(ydata.keys()):
        px = i * pw + 30; py = 60
        pad_p = 18; title_p = 56
        map_w = pw - 2 * pad_p - 20; map_h_p = H - py - pad_p - 70
        sp = min(map_w / bw, map_h_p / bh)
        ox = px + pad_p + (map_w - bw * sp) / 2; oy = py + title_p + (map_h_p - bh * sp) / 2
        def make_t(ox=ox, oy=oy, sp=sp):
            def tr3(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
            return tr3
        tr_p = make_t()
        parts.append(f'<text x="{px}" y="{py + 22}" class="panel-title">{escape(k)}</text>')
        parts.append(f'<text x="{px}" y="{py + 42}" class="panel-sub">{ILCE.title()} ort: %{yilce[k]:.2f}</text>')
        parts.append('<g class="polygons">')
        for _, row in gdf.iterrows():
            d = geom_d(row.geometry, tr_p)
            if not d: continue
            rel = row[f'yrp_rel_{k}']; v = row[f'yrp_v_{k}']
            fill = diverging(rel, vmax)
            lbl = f"{row['MAHALLEADI']} - %{v:.2f} (sapma {rel:+.2f})" if pd.notna(v) else f"{row['MAHALLEADI']} - veri yok"
            parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
        parts.append('</g>')
    ly = H - 36; lw = 380; lx = (W - lw) / 2
    parts.extend(f'<rect x="{lx + (i/n)*lw:.1f}" y="{ly}" width="{lw/n + 1:.1f}" height="14" fill="{diverging((i/(n-1)*2-1)*vmax, vmax)}"/>' for i in range(n))
    parts.append(f'<text x="{lx}" y="{ly - 6}" font-size="13" font-weight="600">Ilce ort sapma (puan)</text>')
    parts.append(f'<text x="{lx}" y="{ly + 28}" font-size="12">{-vmax:+.2f}</text>')
    parts.append(f'<text x="{lx + lw/2}" y="{ly + 28}" font-size="12" text-anchor="middle">0</text>')
    parts.append(f'<text x="{lx + lw}" y="{ly + 28}" font-size="12" text-anchor="end">{vmax:+.2f}</text>')
    parts.append('</svg>')
    write_svg(parts, 'YRP_2024_3secim.svg')

# ======================================================================
# 4. Sag-Sol winner + LISA
# ======================================================================
print('4. Sag-Sol winner + LISA')
mv23 = ORANLAR / 'oran_2023_MİLLETVEKİLİ_GENEL.csv'
if mv23.exists():
    df = pd.read_csv(mv23)
    parties = [c for c in df.columns if c not in ('il_ADI','ilce_ADI','orig_name','normalized','n_sandik','gecerli_oy_toplam')]
    sag_cols = [c for c in parties if c.upper() in SAG]
    sol_cols = [c for c in parties if c.upper() in SOL]
    df['_sag'] = df[sag_cols].sum(axis=1) / df['n_sandik'] * 100
    df['_sol'] = df[sol_cols].sum(axis=1) / df['n_sandik'] * 100
    sag_map = dict(zip(df['normalized'], df['_sag']))
    sol_map = dict(zip(df['normalized'], df['_sol']))
    gdf['_sag'] = gdf['_k'].map(sag_map)
    gdf['_sol'] = gdf['_k'].map(sol_map)

    # Winner harita
    W, H, pad, title_h, map_h, legend_h, tr = page_dims()
    COLOR = {'SAĞ': '#fdb924', 'SOL': '#d62728'}
    paths = []; counts = {'SAĞ': 0, 'SOL': 0}
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry, tr)
        if not d: continue
        if pd.notna(row['_sag']) and pd.notna(row['_sol']):
            w_ = 'SAĞ' if row['_sag'] >= row['_sol'] else 'SOL'
            counts[w_] += 1
            fill = COLOR[w_]
            lbl = f"{row['MAHALLEADI']} - {w_} (Sag %{row['_sag']:.1f} / Sol %{row['_sol']:.1f})"
        else:
            fill = '#a5cce8'; lbl = f"{row['MAHALLEADI']} - veri yok"
        paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    title = f"{ILCE.title()} 2023 MV - Mahallede Sag vs Sol Birinci"
    leg = []
    lx0 = pad; ly0 = title_h + map_h + 28
    for k in ['SAĞ','SOL']:
        leg.append(f'<rect x="{lx0}" y="{ly0}" width="22" height="14" rx="2" fill="{COLOR[k]}" stroke="#222" stroke-width="0.6"/>')
        leg.append(f'<text x="{lx0 + 30}" y="{ly0 + 12}" font-size="13" font-weight="500">{k} ({counts[k]})</text>')
        lx0 += 130
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
        '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }</style>',
        f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(title)}</text>',
        '<g class="polygons">' + '\n'.join(paths) + '</g>',
        '<g>' + '\n'.join(leg) + '</g>',
        '</svg>'
    ]
    write_svg(parts, 'SAG_SOL_winner.svg')
    print(f'   SAG: {counts["SAĞ"]} mahalle, SOL: {counts["SOL"]} mahalle')

    # LISA
    try:
        from libpysal.weights import Queen
        from esda.moran import Moran, Moran_Local
        gdf2 = gdf.dropna(subset=['_sag','_sol']).reset_index(drop=True)
        w = Queen.from_dataframe(gdf2, use_index=False); w.transform = 'r'
        def classify(lm, p_thresh=0.05):
            return [{1:'HH',2:'LH',3:'LL',4:'HL'}.get(q,'NS') if p<=p_thresh else 'NS' for q,p in zip(lm.q, lm.p_sim)]
        results = {}
        for side, col in [('SAĞ','_sag'),('SOL','_sol')]:
            y = gdf2[col].fillna(0).values
            mi = Moran(y, w, permutations=999)
            lm = Moran_Local(y, w, permutations=999, seed=42)
            results[side] = (classify(lm), mi.I, mi.p_sim)
            print(f'   {side}: Moran I = {mi.I:.3f}, p = {mi.p_sim:.3f}')
        COLOR = {'HH':'#d62728','LL':'#1f77b4','HL':'#ff9896','LH':'#aec7e8','NS':'#dddddd'}
        LABEL = {'HH':'High-High','LL':'Low-Low','HL':'High-Low','LH':'Low-High','NS':'Anlamsız'}
        W, H = 1700, 760; pw = W // 2
        bw2_, bh2_ = bw, bh
        parts = ['<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
            '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.polygons path { stroke: #fff; stroke-width: 0.5; }\n.title { font-size: 22px; font-weight: 700; }\n.panel-title { font-size: 17px; font-weight: 600; }\n.panel-sub { font-size: 13px; fill: #666; }</style>',
            f'<text x="40" y="38" class="title">{escape(ILCE.title())} 2023 MV - Sag ve Sol LISA Mahalle Kumeleri</text>'
        ]
        for i, (side, col) in enumerate([('SAĞ','_sag'),('SOL','_sol')]):
            cls, mi_i, mi_p = results[side]
            px = i * pw + 30; py = 60
            pad_p = 18; title_p = 56
            map_w = pw - 2*pad_p - 20; map_h_p = H - py - pad_p - 70
            sp = min(map_w/bw, map_h_p/bh)
            ox = px + pad_p + (map_w - bw * sp) / 2; oy = py + title_p + (map_h_p - bh * sp) / 2
            def make_t(ox=ox, oy=oy, sp=sp):
                def tr2(x, y): return ox + (x - minx) * sp, (oy + bh * sp) - (y - miny) * sp
                return tr2
            tr_p = make_t()
            parts.append(f'<text x="{px}" y="{py + 22}" class="panel-title">{side} (Moran I = {mi_i:.2f}, p = {mi_p:.3f})</text>')
            from collections import Counter
            cc = Counter(cls)
            sub = ' · '.join(f'{LABEL[k]}: {cc.get(k,0)}' for k in ['HH','LL','HL','LH','NS'] if cc.get(k,0)>0)
            parts.append(f'<text x="{px}" y="{py + 42}" class="panel-sub">{escape(sub)}</text>')
            parts.append('<g class="polygons">')
            for idx, row in gdf2.iterrows():
                d = geom_d(row.geometry, tr_p)
                if not d: continue
                c = cls[idx]; v = row[col]
                fill = COLOR[c]
                lbl = f"{row['MAHALLEADI']} — {LABEL[c]} ({side} %{v:.1f})"
                parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
            parts.append('</g>')
        ly = H - 30; lx = 40
        for k in ['HH','LL','HL','LH','NS']:
            parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="12" fill="{COLOR[k]}" stroke="#333" stroke-width="0.4"/>')
            parts.append(f'<text x="{lx + 18}" y="{ly + 10}" font-size="11">{LABEL[k]}</text>')
            lx += 140
        parts.append('</svg>')
        write_svg(parts, 'SAG_SOL_LISA.svg')
    except Exception as e:
        print(f'   LISA hata: {e}')

# ======================================================================
# 5. Bolge bar + Gelir bar + Gelir x Bolge (memleket+tip kullanir)
# ======================================================================
print('5. Bolge/Gelir bar + cross panel')
BOLGE = {
    'MARMARA': ['EDİRNE','KIRKLARELİ','TEKİRDAĞ','KOCAELİ','SAKARYA','BURSA','BALIKESİR','ÇANAKKALE','YALOVA','BİLECİK'],
    'EGE': ['İZMİR','MANİSA','AYDIN','MUĞLA','DENİZLİ','UŞAK','KÜTAHYA','AFYONKARAHİSAR'],
    'AKDENİZ': ['ANTALYA','MERSİN','ADANA','HATAY','OSMANİYE','KAHRAMANMARAŞ','ISPARTA','BURDUR'],
    'İÇ ANADOLU': ['ANKARA','KONYA','KAYSERİ','ESKİŞEHİR','SİVAS','YOZGAT','ÇANKIRI','KIRIKKALE','AKSARAY','NEVŞEHİR','NİĞDE','KARAMAN','KIRŞEHİR'],
    'KARADENİZ': ['SAMSUN','TRABZON','ORDU','GİRESUN','RİZE','ARTVİN','BAYBURT','GÜMÜŞHANE','TOKAT','AMASYA','ÇORUM','SİNOP','KASTAMONU','BARTIN','KARABÜK','BOLU','DÜZCE','ZONGULDAK'],
    'DOĞU ANADOLU': ['ERZURUM','ERZİNCAN','AĞRI','KARS','IĞDIR','ARDAHAN','VAN','MUŞ','BİNGÖL','BİTLİS','HAKKARİ','ELAZIĞ','TUNCELİ','MALATYA'],
    'GÜNEYDOĞU ANADOLU': ['GAZİANTEP','ŞANLIURFA','DİYARBAKIR','MARDİN','BATMAN','SİİRT','ŞIRNAK','ADIYAMAN','KİLİS'],
}
COLOR_B = {'YERLİ':'#1a3a52','İL':'#4a90b8','MARMARA':'#88b5cf','KARADENİZ':'#2a9d8f','DOĞU ANADOLU':'#e76f51','İÇ ANADOLU':'#e9c46a','GÜNEYDOĞU ANADOLU':'#9c6644','AKDENİZ':'#f4a261','EGE':'#588b8b'}
ORDER = ['YERLİ','İL','MARMARA','KARADENİZ','DOĞU ANADOLU','İÇ ANADOLU','GÜNEYDOĞU ANADOLU','AKDENİZ','EGE']
GELIR_LABEL = {'low':'Düşük gelir','middle':'Orta gelir','high':'Yüksek gelir','top':'Çok yüksek','Tasra':'Taşra','no data':'Veri yok'}

il2bol = {il_:b for b,ills in BOLGE.items() for il_ in ills}

# Sandik dosyasini bul
def _ascii(s):
    return s.upper().replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
sandik_path = None
sd = Path(args.proje_dir) / 'Sandık'
for f in sd.glob('*.csv'):
    sa = _ascii(f.stem)
    if _ascii(IL) in sa and _ascii(ILCE) in sa:
        sandik_path = f; break

if sandik_path:
    sdf = pd.read_csv(sandik_path, low_memory=False, encoding='utf-8')
    sdf['_mah'] = sdf['ADRES MUHTARLIK ADI'].apply(normalize_mahalle)
    def cat(il_, ilce_):
        il_ = str(il_).strip().upper(); ilce_ = str(ilce_).strip().upper()
        if il_ == IL:
            return 'YERLİ' if ILCE in ilce_ else 'İL'
        return il2bol.get(il_, 'Diğer')
    sdf['_cat'] = sdf.apply(lambda r: cat(r['NÜFUS İLİ'], r['NÜFUS İLÇESİ']), axis=1)
    tip_csv = ILCE_DIR / 'tip' / 'tip.csv'
    if tip_csv.exists():
        tip = pd.read_csv(tip_csv)
        mah2dur = dict(zip(tip['normalized'], tip['durum']))
        sdf['_durum'] = sdf['_mah'].map(mah2dur).fillna('no data')
        gelir_order = [g for g in ['Tasra','low','middle','high','top'] if g in sdf['_durum'].unique()]
        sdf2 = sdf[sdf['_durum'].isin(gelir_order)]
        ct = sdf2.groupby(['_durum','_cat']).size().unstack(fill_value=0)
        ct = ct.reindex(index=gelir_order, columns=ORDER, fill_value=0)
        out_cross_csv = ILCE_DIR / 'memleket' / 'gelir_bolge.csv'
        out_cross_csv.parent.mkdir(parents=True, exist_ok=True)
        ct.to_csv(out_cross_csv, encoding='utf-8')
        ct_pct = ct.div(ct.sum(axis=1), axis=0) * 100

        # 3-panel paralel
        W = 1600; H = 800; n_panels = len(ct_pct)
        panel_gap = 24; pad_t = 100
        panel_w = (W - panel_gap * (n_panels + 1)) / n_panels
        chart_t = pad_t + 56; chart_b = H - 70
        chart_h = chart_b - chart_t
        n_bars = len(ORDER)
        bar_h = chart_h / n_bars * 0.78; gap = chart_h / n_bars * 0.22
        label_w = 175; bar_max = panel_w - label_w - 60
        parts = ['<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">',
            '<style>text { font-family: -apple-system, "Segoe UI", sans-serif; fill: #1a1a1a; }\n.title { font-size: 22px; font-weight: 700; }\n.subtitle { font-size: 14px; fill: #555; }\n.panel-title { font-size: 18px; font-weight: 600; }\n.panel-sub { font-size: 12px; fill: #666; }\n.cat { font-size: 12px; }\n.val { font-size: 11px; font-weight: 600; }</style>',
            f'<text x="40" y="40" class="title">{escape(ILCE.title())} - Gelir Grubu × Memleket Bölgesi</text>',
            '<text x="40" y="62" class="subtitle">%, sandık seçmen kütüğü</text>',
        ]
        for pi, durum in enumerate(ct_pct.index):
            px = panel_gap + pi * (panel_w + panel_gap)
            total = int(ct.loc[durum].sum())
            parts.append(f'<text x="{px:.1f}" y="{pad_t + 24}" class="panel-title">{escape(GELIR_LABEL.get(durum,durum))}</text>')
            parts.append(f'<text x="{px:.1f}" y="{pad_t + 42}" class="panel-sub">n = {total:,}</text>')
            for bi, bolge in enumerate(ORDER):
                y = chart_t + bi * (bar_h + gap)
                pct = float(ct_pct.loc[durum, bolge])
                bw_ = (pct / 100) * bar_max if pct > 0 else 0
                col = COLOR_B.get(bolge, '#888')
                lbl = bolge.replace('YERLİ', ILCE.title()).replace('İL', IL.title())
                parts.append(f'<text x="{px + label_w - 6:.1f}" y="{y + bar_h/2 + 4:.1f}" class="cat" text-anchor="end">{escape(lbl)}</text>')
                parts.append(f'<rect x="{px + label_w:.1f}" y="{y:.1f}" width="{bw_:.1f}" height="{bar_h:.1f}" rx="2" fill="{col}"/>')
                if pct > 0:
                    parts.append(f'<text x="{px + label_w + bw_ + 6:.1f}" y="{y + bar_h/2 + 4:.1f}" class="val">{pct:.1f}</text>')
        parts.append('</svg>')
        out_p = HARITALAR / 'gelir_x_bolge.svg'
        out_p.write_text('\n'.join(parts), encoding='utf-8')
        print(f'  -> {out_p.name}')

print('\nBitti.')
