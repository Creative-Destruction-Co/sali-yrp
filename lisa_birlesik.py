"""LISA HH bölgelerini tek harita üzerinde birleştir.
Her mahalleyi HH olduğu memleket bölgesinin rengiyle boya."""
from __future__ import annotations
import sys
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd, geopandas as gpd
from libpysal.weights import Queen
from esda.moran import Moran_Local

ROOT = Path(r'D:\Yepisyeni Seçim\Seçim')
sys.stdout.reconfigure(encoding='utf-8')

MARMARA = {'BALIKESİR','BİLECİK','BURSA','ÇANAKKALE','EDİRNE','KIRKLARELİ','KOCAELİ','SAKARYA','TEKİRDAĞ','YALOVA'}
KARADENIZ = {'AMASYA','ARTVİN','BARTIN','BAYBURT','BOLU','ÇORUM','DÜZCE','GİRESUN','GÜMÜŞHANE','KARABÜK','KASTAMONU','ORDU','RİZE','SAMSUN','SİNOP','TOKAT','TRABZON','ZONGULDAK'}
IC_ANADOLU = {'AKSARAY','ANKARA','ÇANKIRI','ESKİŞEHİR','KARAMAN','KAYSERİ','KIRIKKALE','KIRŞEHİR','KONYA','NEVŞEHİR','NİĞDE','SİVAS','YOZGAT'}
DOGU = {'AĞRI','ARDAHAN','BİNGÖL','BİTLİS','ELAZIĞ','ERZİNCAN','ERZURUM','HAKKARİ','IĞDIR','KARS','MALATYA','MUŞ','TUNCELİ','VAN'}
GUNEYDOGU = {'ADIYAMAN','BATMAN','DİYARBAKIR','GAZİANTEP','KİLİS','MARDİN','SİİRT','ŞANLIURFA','ŞIRNAK'}
AKDENIZ = {'ADANA','ANTALYA','BURDUR','HATAY','ISPARTA','KAHRAMANMARAŞ','MERSİN','OSMANİYE'}
EGE = {'AFYONKARAHİSAR','AYDIN','DENİZLİ','İZMİR','KÜTAHYA','MANİSA','MUĞLA','UŞAK'}

def bolge(il, ilce):
    il = str(il).upper().strip(); ilce = str(ilce).upper().strip()
    if il == 'İSTANBUL' and ilce == 'PENDİK': return 'PENDIK'
    if il == 'İSTANBUL': return 'ISTANBUL'
    if il in MARMARA: return 'MARMARA'
    if il in KARADENIZ: return 'KARADENIZ'
    if il in IC_ANADOLU: return 'IC_ANADOLU'
    if il in DOGU: return 'DOGU'
    if il in GUNEYDOGU: return 'GD_ANADOLU'
    if il in AKDENIZ: return 'AKDENIZ'
    if il in EGE: return 'EGE'
    return None

# Renk paleti
COLOR = {
    'PENDIK':     '#1a3a52',
    'ISTANBUL':   '#4a90b8',
    'MARMARA':    '#88b5cf',
    'KARADENIZ':  '#2a9d8f',
    'IC_ANADOLU': '#e9c46a',
    'DOGU':       '#e76f51',
    'GD_ANADOLU': '#9c6644',
    'AKDENIZ':    '#f4a261',
    'EGE':        '#588b8b',
}
LABEL = {
    'PENDIK':'Pendikli','ISTANBUL':'İstanbul (diğer ilçe)','MARMARA':'Marmara',
    'KARADENIZ':'Karadeniz','IC_ANADOLU':'İç Anadolu','DOGU':'Doğu Anadolu',
    'GD_ANADOLU':'Güneydoğu Anadolu','AKDENIZ':'Akdeniz','EGE':'Ege',
}

print('[1] Sandık verisi...')
sn = pd.read_csv(ROOT/'Sandık/İSTANBUL_PENDİK_.csv', low_memory=False)
sn = sn[sn['ADRES İLÇE ADI'].astype(str).str.upper().str.strip()=='PENDİK']
sn['MAHALLE'] = sn['ADRES MUHTARLIK ADI'].astype(str).str.upper().str.strip()
sn['BOLGE'] = sn.apply(lambda r: bolge(r['NÜFUS İLİ'], r['NÜFUS İLÇESİ']), axis=1)
sn = sn.dropna(subset=['BOLGE'])

# Mahalle × bölge yüzdesi
piv = sn.groupby(['MAHALLE','BOLGE']).size().unstack(fill_value=0)
piv = piv.div(piv.sum(axis=1), axis=0) * 100
print(f'  {len(piv)} mahalle, {len(piv.columns)} bölge')

print('[2] SHP yükle...')
import sys as _sys
_sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle
gdf = gpd.read_file(ROOT/'PENDİK/Harita Teknik Dosya/PENDİK.shp').to_crs(3857)
gdf['_k'] = gdf['MAHALLEADI'].apply(normalize_mahalle)
piv.index = [normalize_mahalle(m) for m in piv.index]
gdf = gdf.merge(piv, left_on='_k', right_index=True, how='left').reset_index(drop=True)
gdf = gdf.dropna(subset=['PENDIK']).reset_index(drop=True)
print(f'  {len(gdf)} mahalle eşleşti')

print('[3] Her bölge için LISA HH...')
w = Queen.from_dataframe(gdf, use_index=False); w.transform='r'
hh_per_bolge = {}
for b in COLOR.keys():
    if b not in gdf.columns: continue
    y = gdf[b].fillna(0).values
    if y.sum() == 0: continue
    lm = Moran_Local(y, w, permutations=999, seed=42)
    hh = [(lm.q[i]==1 and lm.p_sim[i]<=0.05) for i in range(len(gdf))]
    hh_per_bolge[b] = (hh, y)
    print(f'  {b}: {sum(hh)} HH mahalle')

# Her mahalle: hangi bölgenin HH'sıysa o bölge. Birden fazla varsa en yüksek y değerli.
gdf['_hh_bolge'] = None
for i in range(len(gdf)):
    candidates = []
    for b, (hh, y) in hh_per_bolge.items():
        if hh[i]:
            candidates.append((b, y[i]))
    if candidates:
        candidates.sort(key=lambda x: -x[1])
        gdf.loc[i, '_hh_bolge'] = candidates[0][0]

print('[4] SVG üret...')
minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx-minx, maxy-miny
W = 1600; pad = 30
s = (W-2*pad)/bw
H = int(round(bh*s + 2*pad))
def tr(x,y): return pad+(x-minx)*s, (H-pad)-(y-miny)*s

def gpath(g):
    if g is None or g.is_empty: return ''
    polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
    rings = []
    for p in polys:
        for ring in [p.exterior]+list(p.interiors):
            coords = list(ring.coords)
            if not coords: continue
            d = 'M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in coords)+' Z'
            rings.append(d)
    return ' '.join(rings)

paths = []
for _, row in gdf.iterrows():
    d = gpath(row.geometry)
    if not d: continue
    b = row['_hh_bolge']
    fill = COLOR[b] if b else '#e8e8e8'
    lbl = f"{row['MAHALLEADI']} — {LABEL.get(b,'HH değil')}"
    paths.append(f'    <path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')

svg = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
       f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision">\n'
       '  <style>.polygons path{stroke:#fff;stroke-width:0.5}</style>\n'
       '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n</svg>\n')
out = ROOT/'_v2_assets'/'pendik_memleket_hh_birlesik.svg'
out.write_text(svg, encoding='utf-8')
print(f'  Yazıldı: {out}')
print(f'\nHH dağılım: {gdf["_hh_bolge"].value_counts().to_dict()}')
print(f'HH değil: {gdf["_hh_bolge"].isna().sum()}')
