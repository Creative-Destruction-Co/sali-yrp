"""
Kurt cogunluklu ilcelerin DOGUM YERI bazli secmen sayisi.
Spesifik ilce listesi — tum il degil sadece kullanicinin verdigi ilceler.
"""
import pandas as pd
import geopandas as gpd
from pathlib import Path
from xml.sax.saxutils import escape
import sys, time

KURT = {
    'HAKKARİ': ['MERKEZ','HAKKARİ','ÇUKURCA','ŞEMDİNLİ','YÜKSEKOVA','DERECİK'],
    'ŞIRNAK': ['MERKEZ','ŞIRNAK','BEYTÜŞŞEBAP','CİZRE','GÜÇLÜKONAK','İDİL','SİLOPİ','ULUDERE'],
    'DİYARBAKIR': ['BAĞLAR','KAYAPINAR','SUR','YENİŞEHİR','BİSMİL','ÇERMİK','ÇINAR','ÇÜNGÜŞ','DİCLE','EĞİL','ERGANİ','HANİ','HAZRO','KOCAKÖY','KULP','LİCE','SİLVAN'],
    'BATMAN': ['MERKEZ','BATMAN','BEŞİRİ','GERCÜŞ','HASANKEYF','KOZLUK','SASON'],
    'MUŞ': ['MERKEZ','MUŞ','BULANIK','HASKÖY','KORKUT','MALAZGİRT','VARTO'],
    'BİNGÖL': ['MERKEZ','BİNGÖL','ADAKLI','GENÇ','KARLIOVA','KIĞI','SOLHAN','YAYLADERE','YEDİSU'],
    'TUNCELİ': ['MERKEZ','TUNCELİ','ÇEMİŞGEZEK','HOZAT','MAZGİRT','NAZIMİYE','OVACIK','PERTEK','PÜLÜMÜR'],
    'VAN': ['İPEKYOLU','TUŞBA','EDREMİT','BAHÇESARAY','BAŞKALE','ÇALDIRAN','ÇATAK','ERCİŞ','GEVAŞ','GÜRPINAR','MURADİYE','ÖZALP','SARAY'],
    'AĞRI': ['MERKEZ','AĞRI','DİYADİN','DOĞUBAYAZIT','ELEŞKİRT','HAMUR','PATNOS','TAŞLIÇAY','TUTAK'],
    'MARDİN': ['ARTUKLU','MERKEZ','MARDİN','DERİK','KIZILTEPE','MAZIDAĞI','NUSAYBİN','ÖMERLİ','SAVUR','YEŞİLLİ'],
    'SİİRT': ['MERKEZ','SİİRT','BAYKAN','ERUH','KURTALAN','PERVARİ','ŞİRVAN','TİLLO'],
    'BİTLİS': ['MERKEZ','BİTLİS','GÜROYMAK','HİZAN','MUTKİ'],
    'ŞANLIURFA': ['BOZOVA','HALFETİ','HİLVAN','SİVEREK','SURUÇ','VİRANŞEHİR'],
    'KARS': ['KAĞIZMAN','DİGOR'],
}
KURT_ILLER = set(KURT.keys())

# Cakisma kontrolu: SHP'de bir ilce adi birden fazla ilde varsa, hangi il oldugu belirsiz.
# Bu durumda o ilceyi sayim disinda birak (underestimate ama dogru).
import geopandas as _gpd
_sgdf_chk = _gpd.read_file(Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/Harita/turkey_ilce.shp'))
_sgdf_chk['_il'] = _sgdf_chk['ILADI'].astype(str).str.strip().str.upper()
_sgdf_chk['_ilce'] = _sgdf_chk['ILCEADI'].astype(str).str.strip().str.upper()
_dup_ilces = set(_sgdf_chk['_ilce'].value_counts().pipe(lambda s: s[s > 1]).index)
_dup_ilces.discard('MERKEZ')

KURT_TUPLES = set()
excluded = []
for il, ilces in KURT.items():
    for ilce in ilces:
        # Il adi versiyonu cakisma riski yok (il adlari unique)
        if ilce == il or ilce == 'MERKEZ':
            KURT_TUPLES.add((il, ilce))
            KURT_TUPLES.add((il, il))  # DOGUM YERI il adi olarak yazilmis olabilir
        elif ilce in _dup_ilces:
            excluded.append((il, ilce))
        else:
            KURT_TUPLES.add((il, ilce))
print(f'Cakisma nedeniyle dislanan ({len(excluded)}): {excluded}')

# Origin: sadece KURT_TUPLES'taki ilceler gri olur, diger ilceler (listede olmayan) renklendirilir

SANDIK_DIR = Path(r'D:/Yepisyeni Seçim/Seçim/Sandık')
SHP = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/Harita/turkey_ilce.shp')
IL_SHP = Path(r'D:/Yepisyeni Seçim/Seçim/tr_il_toplam/Harita/turkey_il.shp')
OUT_CSV = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/kurt_dogum_oran.csv')

# Ilce -> il map (Kurt ilceleri oncelikli cakismalarda)
print('Ilce->il map yukleniyor...', flush=True)
sgdf = gpd.read_file(SHP)
sgdf['_ilce_u'] = sgdf['ILCEADI'].astype(str).str.strip().str.upper()
sgdf['_il_u'] = sgdf['ILADI'].astype(str).str.strip().str.upper()
ilce_il = {}
for il, ilce in sgdf[['_il_u','_ilce_u']].itertuples(index=False):
    if ilce in ilce_il and il in KURT_ILLER:
        ilce_il[ilce] = il
    elif ilce not in ilce_il:
        ilce_il[ilce] = il
ilce_il.pop('MERKEZ', None)
for il_u in sgdf['_il_u'].unique():
    ilce_il[il_u] = il_u
print(f'  {len(ilce_il)} mapping')

t0 = time.time()
files = sorted(SANDIK_DIR.glob('*.csv'))
print(f'{len(files)} sandik dosyasi taranıyor (DOGUM YERI Kurt ilceleri)...', flush=True)
rows = []
for i, f in enumerate(files):
    if i % 100 == 0:
        print(f'  [{i}/{len(files)}] {f.name} | {time.time()-t0:.1f}s', flush=True)
    try:
        df = None
        for enc in ('utf-8', 'cp1254', 'latin-1'):
            try:
                df = pd.read_csv(f, usecols=['ADRES İL ADI','ADRES İLÇE ADI','DOĞUM YERİ'], encoding=enc, low_memory=False)
                break
            except UnicodeDecodeError:
                continue
        if df is None or len(df) == 0: continue
        il = str(df['ADRES İL ADI'].iloc[0]).strip().upper()
        ilce = str(df['ADRES İLÇE ADI'].iloc[0]).strip().upper()
        if ilce.startswith(il + ' '):
            ilce = ilce[len(il)+1:].strip()
        dogum = df['DOĞUM YERİ'].astype(str).str.strip().str.upper()
        dogum_il = dogum.map(ilce_il)
        # (il, dogum_yeri) tuple KURT_TUPLES'te mi?
        kurt_match = pd.Series([(i_, d) in KURT_TUPLES for i_, d in zip(dogum_il, dogum)])
        total = len(dogum)
        kok = int(kurt_match.sum())
        rows.append((il, ilce, total, kok, kok / total * 100 if total else 0))
    except Exception as e:
        print(f'  HATA {f.name}: {e}', file=sys.stderr)

out = pd.DataFrame(rows, columns=['il','ilce','toplam_secmen','kurt_secmen','yuzde'])
out.to_csv(OUT_CSV, index=False, encoding='utf-8')
print(f'\nCSV: {OUT_CSV} ({len(out)} ilce)')
_origin_keys = {f'{il}|{ic}' for (il, ic) in KURT_TUPLES} | {f'{il}|MERKEZ' for il in KURT_ILLER} | {f'{il}|{il}' for il in KURT_ILLER}
out['_k'] = out['il'] + '|' + out['ilce']
_non = out[~out['_k'].isin(_origin_keys)]
print('Top 10 yuzde (Kurt ilceleri haric):')
print(_non.sort_values('yuzde', ascending=False).head(10).drop(columns=['_k']).to_string(index=False))
print('\nTop 10 miktar (Kurt ilceleri haric):')
print(_non.sort_values('kurt_secmen', ascending=False).head(10).drop(columns=['_k']).to_string(index=False))

# 2 SVG: yuzde + miktar (origin gri)
gdf = gpd.read_file(SHP).to_crs(3857)
gdf['_key'] = gdf['ILADI'].str.strip().str.upper() + '|' + gdf['ILCEADI'].str.strip().str.upper()
out['_key'] = out['il'] + '|' + out['ilce']
gdf['_pct'] = gdf['_key'].map(dict(zip(out['_key'], out['yuzde']))).fillna(0.0)
gdf['_cnt'] = gdf['_key'].map(dict(zip(out['_key'], out['kurt_secmen']))).fillna(0).astype(int)
gdf['_il_u'] = gdf['ILADI'].str.strip().str.upper()
gdf['_ilce_u'] = gdf['ILCEADI'].str.strip().str.upper()
# Sadece KURT_TUPLES'ta listelenen (il, ilce) cifti gri
gdf['_origin'] = [(i, c) in KURT_TUPLES or (i, i) in KURT_TUPLES and c == 'MERKEZ' for i, c in zip(gdf['_il_u'], gdf['_ilce_u'])]

W = 1600; pad = 30; title_h = 36; legend_h = 80
minx, miny, maxx, maxy = gdf.total_bounds
bw, bh = maxx - minx, maxy - miny
s_ = (W - 2 * pad) / bw
map_h = int(round(bh * s_ + pad))
H = title_h + map_h + legend_h + pad
def tr(x, y): return pad + (x - minx) * s_, (title_h + map_h) - (y - miny) * s_
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

il_paths = []
il_gdf = gpd.read_file(IL_SHP).to_crs(3857)
for _, row in il_gdf.iterrows():
    d = geom_d(row.geometry)
    if d: il_paths.append(f'<path d="{d}"/>')

def render(value_col, max_val, fname, title_text, label_unit):
    def color(v, is_o):
        if is_o: return '#cccccc'
        if pd.isna(v) or v <= 0 or max_val <= 0: return '#f5f5f5'
        t = (v / max_val) ** 0.4
        t = min(1.0, t)
        # Kurt -> mor/koyu kirmizi gradyan
        r = int(255 + (139 - 255) * t); g = int(255 + (0 - 255) * t); b = int(255 + (139 - 255) * t)
        return f'#{r:02x}{g:02x}{b:02x}'
    paths = []
    for _, row in gdf.iterrows():
        d = geom_d(row.geometry)
        if not d: continue
        is_o = row['_origin']
        v = row[value_col]
        fill = color(v, is_o)
        if is_o:
            lbl = f"{row['ILADI']} - {row['ILCEADI']} (origin)"
        else:
            lbl = f"{row['ILADI']} - {row['ILCEADI']} | {int(row['_cnt']):,} kisi (%{row['_pct']:.2f})"
        paths.append(f'<path d="{d}" fill="{fill}"><title>{escape(lbl)}</title></path>')
    legend_y = title_h + map_h + 28
    lw = 380; lx = (W - lw) / 2
    n = 24
    stops = [f'<rect x="{lx + (i/n)*lw:.1f}" y="{legend_y}" width="{lw/n + 1:.1f}" height="14" fill="{color((i/(n-1))*max_val, False)}"/>' for i in range(n)]
    max_lbl = f'%{max_val:.1f}' if label_unit == 'pct' else f'{int(max_val):,}'
    labels = [
        f'<text x="{lx}" y="{legend_y - 6}" font-size="13" font-weight="600">{escape(title_text)}</text>',
        f'<text x="{lx}" y="{legend_y + 30}" font-size="12">0</text>',
        f'<text x="{lx + lw}" y="{legend_y + 30}" font-size="12" text-anchor="end">{max_lbl}</text>',
        f'<text x="{lx}" y="{legend_y + 50}" font-size="11" fill="#666">Gri: Kurt ilceleri (origin, dahil edilmedi); diger ilceler renklendirildi</text>',
    ]
    big_title = f"Turkiye - Dogum Yeri Kurt Ilcelerinde olan secmenler ({label_unit})"
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">\n'
        '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #1a1a1a; }\n'
        '.polygons path { stroke: #fff; stroke-width: 0.4; }\n'
        '.il-borders path { fill: none; stroke: #1a1a1a; stroke-width: 1.4; pointer-events: none; }</style>\n'
        f'<text x="{pad}" y="{pad - 2}" font-size="22" font-weight="600">{escape(big_title)}</text>\n'
        '<g class="polygons">' + '\n'.join(paths) + '</g>\n'
        '<g class="il-borders">' + '\n'.join(il_paths) + '</g>\n'
        '<g>' + '\n'.join(stops + labels) + '</g>\n</svg>\n'
    )
    out_svg = Path(r'D:/Yepisyeni Seçim/Seçim/tr_ilce_toplam/haritalar') / fname
    out_svg.write_text(svg, encoding='utf-8')
    print(f'Yazildi: {out_svg}')

max_pct = float(gdf.loc[~gdf['_origin'], '_pct'].max() or 0)
max_cnt = float(gdf.loc[~gdf['_origin'], '_cnt'].max() or 0)
print(f'max %: {max_pct:.2f}, max miktar: {int(max_cnt):,}')
render('_pct', max_pct, 'TR_ILCE_KURT_dogum_yuzde.svg', f'Kurt ilcelerinden gelen secmen yuzdesi (max %{max_pct:.1f})', 'pct')
render('_cnt', max_cnt, 'TR_ILCE_KURT_dogum_miktar.svg', f'Kurt ilcelerinden gelen secmen sayisi (max {int(max_cnt):,})', 'cnt')
print(f'Sure: {time.time()-t0:.1f}s')
