"""GADM 4.1 + 2023 MV winner: il ve ilce duzeyinde birinci parti haritasi.
Stil: sunum_v2 TR il/ilce winner gibi (beyaz BG, parti rengi, beyaz ic sinir)."""
from __future__ import annotations
import re, sys, unicodedata
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd, geopandas as gpd

ROOT = Path(r'D:\Yepisyeni Seçim\Seçim')
SRC = ROOT / '_gadm_tr'
OUT = ROOT / '_v2_assets'
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

PARTIES = {
    'AK PARTİ', 'CHP', 'MHP', 'İYİ PARTİ', 'YEŞİL SOL PARTİ',
    'YENİDEN REFAH', 'ZAFER PARTİSİ', 'BBP', 'ANAP', 'GENÇPARTİ',
    'AP', 'HAK-PAR', 'GBP', 'MİLLİ YOL', 'YP', 'MİLLET',
    'TİP', 'MEMLEKET', 'VATAN PARTİSİ', 'SOL PARTİ', 'TKP', 'TKH', 'HKP', 'AB',
}
COLOR = {  # ank-ar.com paleti
    'AK PARTİ': '#FFC436', 'CHP': '#FE0000', 'MHP': '#11009E',
    'İYİ PARTİ': '#52D3D8', 'YEŞİL SOL PARTİ': '#8B1874',
    'YENİDEN REFAH': '#65B741', 'ZAFER PARTİSİ': '#765827', 'BBP': '#4F6F52',
}
DEFAULT_COLOR = '#888888'

def ascii_up(s: str) -> str:
    if not isinstance(s, str): return ''
    s = s.upper()
    s = (s.replace('İ','I').replace('I','I').replace('Ş','S').replace('Ğ','G')
           .replace('Ü','U').replace('Ö','O').replace('Ç','C'))
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).strip()

def winner(row, party_cols):
    vals = row[party_cols]
    return vals.idxmax() if vals.max() > 0 else None

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

def render(gdf, fill_col, label_col, out_path, width=1600, il_overlay_gdf=None):
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
        fill = row[fill_col] or DEFAULT_COLOR
        title = escape(str(row[label_col]))
        paths.append(f'    <path d="{d}" fill="{fill}"><title>{title}</title></path>')
    il_paths = []
    if il_overlay_gdf is not None:
        ilg = il_overlay_gdf.to_crs(3857)
        for _, row in ilg.iterrows():
            d = geom_path(row.geometry, tr)
            if d: il_paths.append(f'    <path d="{d}"/>')
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" '
        'shape-rendering="geometricPrecision">\n'
        '  <style>.polygons path { stroke: #fff; stroke-width: 0.3; }\n'
        '         .polygons path:hover { stroke: #000; stroke-width: 1.5; }\n'
        '         .il-borders path { fill: none; stroke: #000; stroke-width: 1.0; pointer-events: none; }</style>\n'
        '  <g class="polygons">\n' + '\n'.join(paths) + '\n  </g>\n'
        + ('  <g class="il-borders">\n' + '\n'.join(il_paths) + '\n  </g>\n' if il_paths else '')
        + '</svg>\n'
    )
    out_path.write_text(svg, encoding='utf-8')
    print(f'  {out_path.name}: {len(gdf)} feature, {len(svg)//1024}KB')

# ===== ADM-1 (il) =====
print('[il] 2023 MV winner...')
df1 = pd.read_csv(ROOT/'tr_il_toplam/oran_2023_MİLLETVEKİLİ_GENEL.csv')
party_cols = [c for c in df1.columns if c in PARTIES]
df1['winner'] = df1.apply(lambda r: winner(r, party_cols), axis=1)
df1['fill'] = df1['winner'].map(COLOR).fillna(DEFAULT_COLOR)
df1['_k'] = df1['il'].apply(ascii_up)
print('  parti dagilim:', df1['winner'].value_counts().to_dict())

g1 = gpd.read_file(SRC/'gadm41_TUR_1.shp')
g1['_k'] = g1['NAME_1'].apply(ascii_up)
# Eslesme manuel: GADM bazi isimleri farkli yazabilir
fix = {'K. MARAS':'KAHRAMANMARAS','ZINGULDAK':'ZONGULDAK','KINKKALE':'KIRIKKALE','AFYON':'AFYONKARAHISAR'}
g1['_k'] = g1['_k'].replace(fix)
g1 = g1.merge(df1[['_k','winner','fill']], on='_k', how='left')
no_match = g1[g1['fill'].isna()]['NAME_1'].tolist()
if no_match: print(f'  eslesmeyen iller: {no_match}')
g1['fill'] = g1['fill'].fillna(DEFAULT_COLOR)
g1['label'] = g1['NAME_1'] + ' — ' + g1['winner'].fillna('?')
render(g1, 'fill', 'label', OUT/'gadm_tr_il_2023mv.svg')

# ===== ADM-2 (ilce) =====
print('[ilce] 2023 MV winner...')
df2 = pd.read_csv(ROOT/'tr_ilce_toplam/oran_2023_MİLLETVEKİLİ_GENEL.csv')
party_cols2 = [c for c in df2.columns if c in PARTIES]
df2['winner'] = df2.apply(lambda r: winner(r, party_cols2), axis=1)
df2['fill'] = df2['winner'].map(COLOR).fillna(DEFAULT_COLOR)
df2['_kil'] = df2['il'].apply(ascii_up)
df2['_kilce'] = df2['ilce'].apply(ascii_up)
# "ELAZIG MERKEZ" -> "MERKEZ" stripping
df2['_kilce'] = df2.apply(lambda r: r['_kilce'][len(r['_kil'])+1:] if r['_kilce'].startswith(r['_kil']+' ') else r['_kilce'], axis=1)
df2['_key'] = df2['_kil'] + '|' + df2['_kilce']
print('  parti dagilim:', df2['winner'].value_counts().to_dict())

# (il,ilce) → (il,ilce) tam keys eslesme (il-spesifik, global degil)
PAIR_FIX = {
    # Genel isim varyasyonlari
    ('AFYONKARAHISAR','SINCANLI'): ('AFYONKARAHISAR','SINANPASA'),
    ('AGRI','DOGUBEYAZIT'): ('AGRI','DOGUBAYAZIT'),
    ('ANKARA','KAZAN'): ('ANKARA','KAHRAMANKAZAN'),
    ('ANKARA','SULTAN KOCHISAR'): ('ANKARA','SEREFLIKOCHISAR'),
    ('ANTALYA','KALE'): ('ANTALYA','DEMRE'),
    ('BURSA','MUSTAFA KEMALPASA'): ('BURSA','MUSTAFAKEMALPASA'),
    ('DENIZLI','AKKOY'): ('DENIZLI','PAMUKKALE'),
    ('EDIRNE','SULEOGLU'): ('EDIRNE','SULOGLU'),
    ('ERZURUM','ILICA'): ('ERZURUM','AZIZIYE'),
    ('GIRESUN','SULTAN KARAHISAR'): ('GIRESUN','SEBINKARAHISAR'),
    ('ISTANBUL','EYUP'): ('ISTANBUL','EYUPSULTAN'),
    ('MALATYA','ARAPKIR'): ('MALATYA','ARAPGIR'),
    ('MALATYA','POTURGE'): ('MALATYA','PUTURGE'),
    ('SAMSUN','ONDOKUZ MAYIS'): ('SAMSUN','19 MAYIS'),
    ('SIIRT','AYDINLAR'): ('SIIRT','TILLO'),
    # Buyuksehir Merkez → en buyuk merkez ilcesi
    ('ANTALYA','MERKEZ'): ('ANTALYA','MURATPASA'),
    ('AYDIN','MERKEZ'): ('AYDIN','EFELER'),
    ('BALIKESIR','MERKEZ'): ('BALIKESIR','KARESI'),
    ('DENIZLI','MERKEZ'): ('DENIZLI','MERKEZEFENDI'),
    ('DIYARBAKIR','MERKEZ'): ('DIYARBAKIR','SUR'),
    ('ERZURUM','MERKEZ'): ('ERZURUM','YAKUTIYE'),
    ('ESKISEHIR','MERKEZ'): ('ESKISEHIR','ODUNPAZARI'),
    ('HATAY','MERKEZ'): ('HATAY','ANTAKYA'),
    ('KAHRAMANMARAS','MERKEZ'): ('KAHRAMANMARAS','DULKADIROGLU'),
    ('KOCAELI','MERKEZ'): ('KOCAELI','IZMIT'),
    ('MALATYA','MERKEZ'): ('MALATYA','BATTALGAZI'),
    ('MANISA','MERKEZ'): ('MANISA','SEHZADELER'),
    ('MARDIN','MERKEZ'): ('MARDIN','ARTUKLU'),
    ('MERSIN','MERKEZ'): ('MERSIN','AKDENIZ'),
    ('MUGLA','MERKEZ'): ('MUGLA','MENTESE'),
    ('ORDU','MERKEZ'): ('ORDU','ALTINORDU'),
    ('SAKARYA','MERKEZ'): ('SAKARYA','ADAPAZARI'),
    ('SAMSUN','MERKEZ'): ('SAMSUN','ILKADIM'),
    ('SANLIURFA','MERKEZ'): ('SANLIURFA','HALILIYE'),
    ('TEKIRDAG','MERKEZ'): ('TEKIRDAG','SULEYMANPASA'),
    ('TRABZON','MERKEZ'): ('TRABZON','ORTAHISAR'),
    ('VAN','MERKEZ'): ('VAN','IPEKYOLU'),
}
g2 = gpd.read_file(SRC/'gadm41_TUR_2.shp')
g2['_kil'] = g2['NAME_1'].apply(ascii_up).replace(fix)
g2['_kilce'] = g2['NAME_2'].apply(ascii_up)
def remap(r):
    pair = (r['_kil'], r['_kilce'])
    return PAIR_FIX.get(pair, pair)
g2[['_kil','_kilce']] = g2.apply(lambda r: pd.Series(remap(r)), axis=1)
g2['_key'] = g2['_kil'] + '|' + g2['_kilce']
g2 = g2.merge(df2[['_key','winner','fill']], on='_key', how='left')
# Eslesmeyen Merkez ilceleri (buyuksehir yasasi ile kaldirilmis): il-toplami winner'i ile doldur
il_winner = df1.set_index('_k')['winner'].to_dict()
il_fill = df1.set_index('_k')['fill'].to_dict()
mask_na = g2['fill'].isna()
g2.loc[mask_na, 'winner'] = g2.loc[mask_na, '_kil'].map(il_winner)
g2.loc[mask_na, 'fill'] = g2.loc[mask_na, '_kil'].map(il_fill)
print(f'  eslesmeyen ilce (il-ortalama atandi): {int(mask_na.sum())}/{len(g2)}')
g2['fill'] = g2['fill'].fillna(DEFAULT_COLOR)
g2['label'] = g2['NAME_1'] + ' — ' + g2['NAME_2'] + ' — ' + g2['winner'].fillna('?')
# ADM-1 sinirlari overlay (siyah)
g1_overlay = gpd.read_file(SRC/'gadm41_TUR_1.shp')
render(g2, 'fill', 'label', OUT/'gadm_tr_ilce_2023mv.svg', il_overlay_gdf=g1_overlay)
