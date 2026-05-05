"""3 flag mahalle bazli filtre haritasi:
  f_kayip  : 2024 Meclis kayip oy (gecersiz+sandiga gitmeyen+kucuk partiler) > ilce ort
  f_akp    : 2018->2023 AKP swing'i ilce ortalamasinin altinda kalan mahalleler (rel_swing < 0)
  f_yrp    : 2023 MV -> 2024 Meclis arasi YRP oy oraninda artis (yrp_2024 - yrp_2023 > 0)"""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'

# 1) AKP swing (2018->2023)
def load_akp(year, csv_name):
    df = pd.read_csv(ROOT/'PENDİK/oranlar'/csv_name)
    df['_avg'] = df['AK PARTİ'] / df['n_sandik']
    ilce = float((df['_avg']*df['gecerli_oy_toplam']).sum() / df['gecerli_oy_toplam'].sum() * 100)
    return df.set_index('normalized')[['_avg','gecerli_oy_toplam']], ilce

akp18, ilce18 = load_akp(2018, 'oran_2018_MİLLETVEKİLİ_GENEL.csv')
akp23, ilce23 = load_akp(2023, 'oran_2023_MİLLETVEKİLİ_GENEL.csv')
ilce_swing_akp = ilce23 - ilce18
print(f'AKP ilce: 2018={ilce18:.2f}, 2023={ilce23:.2f}, swing={ilce_swing_akp:+.2f}')

# 2) Kayip oy (2024 Meclis)
xls = pd.read_excel(ROOT/'PENDİK/Secim/2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.xlsx')
piv = xls.pivot_table(index='muhtarlik_ADI', columns='variable', values='value', aggfunc='sum').fillna(0)
EXCLUDE = {'secmen_SAYISI','oy_KULLANAN_SECMEN_SAYISI','gecerli_OY_TOPLAMI','gecersiz_OY_TOPLAMI','itirazsiz_GECERLI_OY_SAYISI','itirazli_GECERLI_OY_SAYISI'}
ALL = [c for c in piv.columns if c not in EXCLUDE]
NAMED = ['AK PARTİ','CHP','YENİDEN REFAH','ZAFER PARTİSİ','SAADET','İYİ PARTİ','BÜYÜK BİRLİK','TİP']
piv['kayip']     = (piv['gecersiz_OY_TOPLAMI'] + (piv['secmen_SAYISI']-piv['oy_KULLANAN_SECMEN_SAYISI']) + (sum(piv[p] for p in ALL)-sum(piv[p] for p in NAMED)))
piv['kayip_pct'] = piv['kayip']/piv['secmen_SAYISI']*100
ilce_kayip = piv['kayip'].sum()/piv['secmen_SAYISI'].sum()*100
print(f'Kayip ilce: %{ilce_kayip:.2f}')
piv['_n'] = [normalize_mahalle(m) for m in piv.index]
kayip_map = piv.set_index('_n')['kayip_pct']

# 3) YRP 2023 MV -> 2024 Meclis
yrp23 = pd.read_csv(ROOT/'PENDİK/oranlar/oran_2023_MİLLETVEKİLİ_GENEL.csv')
yrp23['_p'] = yrp23['YENİDEN REFAH']/yrp23['n_sandik']*100
yrp24 = pd.read_csv(ROOT/'PENDİK/oranlar/oran_2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.csv')
yrp24['_p'] = yrp24['YENİDEN REFAH']/yrp24['n_sandik']*100
yrp23m = yrp23.set_index('normalized')['_p']
yrp24m = yrp24.set_index('normalized')['_p']

# SHP
shp = gpd.read_file(ROOT/'PENDİK/Harita Teknik Dosya/PENDİK.shp').to_crs(3857)
shp['_n'] = shp['MAHALLEADI'].apply(normalize_mahalle)
shp['akp18'] = shp['_n'].map(akp18['_avg'])*100
shp['akp23'] = shp['_n'].map(akp23['_avg'])*100
shp['akp_swing'] = shp['akp23'] - shp['akp18']
shp['rel_swing'] = shp['akp_swing'] - ilce_swing_akp  # mahalle swing - ilce swing
shp['kayip_pct'] = shp['_n'].map(kayip_map)
shp['yrp23'] = shp['_n'].map(yrp23m)
shp['yrp24'] = shp['_n'].map(yrp24m)
shp['yrp_delta'] = shp['yrp24'] - shp['yrp23']

# Flag'lar
shp['f_kayip'] = (shp['kayip_pct'] > ilce_kayip).astype(int)
shp['f_akp']   = (shp['rel_swing'] < 0).astype(int)
shp['f_yrp']   = (shp['yrp_delta'] > 0).astype(int)
print(f'Flag sayilari: kayip={shp["f_kayip"].sum()}, akp={shp["f_akp"].sum()}, yrp={shp["f_yrp"].sum()}, hepsi={((shp["f_kayip"]==1)&(shp["f_akp"]==1)&(shp["f_yrp"]==1)).sum()}')

# SVG
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

paths = []
for _, row in shp.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    fk = int(row['f_kayip']) if not pd.isna(row['f_kayip']) else 0
    fa = int(row['f_akp']) if not pd.isna(row['f_akp']) else 0
    fy = int(row['f_yrp']) if not pd.isna(row['f_yrp']) else 0
    nm = escape(str(row['MAHALLEADI']))
    kp = '?' if pd.isna(row['kayip_pct']) else f'%{row["kayip_pct"]:.1f}'
    rs = '?' if pd.isna(row['rel_swing']) else f'{row["rel_swing"]:+.1f}'
    yd = '?' if pd.isna(row['yrp_delta']) else f'{row["yrp_delta"]:+.1f}'
    title = f'{nm} | kayıp={kp} (ilçe %{ilce_kayip:.1f}) | AKP rel-swing={rs} | YRP Δ={yd}'
    paths.append(f'    <path class="mh" data-fk="{fk}" data-fa="{fa}" data-fy="{fy}" d="{d}"><title>{title}</title></path>')

svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
       f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision">\n'
       '  <style>.mh{stroke:#fff;stroke-width:0.5;fill:#dcd6c8;transition:fill .25s}'
       '.mh.match{fill:#2166ac}'
       '.mh.dim{fill:#ece6d6}</style>\n'
       '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n</svg>\n')
out = OUT/'pendik_filter.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
