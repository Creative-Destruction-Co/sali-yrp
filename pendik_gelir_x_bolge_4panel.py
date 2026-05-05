"""Pendik Gelir × Bölge — 4 panel (Pendik Geneli + Düşük + Orta + Taşra)."""
import pandas as pd
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'

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

ORDER = ['PENDIK','ISTANBUL','MARMARA','KARADENIZ','IC_ANADOLU','DOGU','GD_ANADOLU','AKDENIZ','EGE']
LABEL = {
    'PENDIK':'Pendikli','ISTANBUL':'İstanbul (diğer ilçe)','MARMARA':'Marmara',
    'KARADENIZ':'Karadeniz','IC_ANADOLU':'İç Anadolu','DOGU':'Doğu Anadolu',
    'GD_ANADOLU':'Güneydoğu','AKDENIZ':'Akdeniz','EGE':'Ege',
}
COLOR = {
    'PENDIK':'#1a3a52','ISTANBUL':'#4a90b8','MARMARA':'#88b5cf',
    'KARADENIZ':'#2a9d8f','IC_ANADOLU':'#e9c46a','DOGU':'#e76f51',
    'GD_ANADOLU':'#9c6644','AKDENIZ':'#f4a261','EGE':'#588b8b',
}

print('Sandık + tip yükle...')
sn = pd.read_csv(ROOT/'Sandık/İSTANBUL_PENDİK_.csv', low_memory=False)
sn = sn[sn['ADRES İLÇE ADI'].astype(str).str.upper().str.strip()=='PENDİK']
sn['MAHALLE'] = sn['ADRES MUHTARLIK ADI'].astype(str).str.upper().str.strip()
sn['BOLGE'] = sn.apply(lambda r: bolge(r['NÜFUS İLİ'], r['NÜFUS İLÇESİ']), axis=1)
sn = sn.dropna(subset=['BOLGE'])

sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle
sn['_n'] = sn['MAHALLE'].apply(normalize_mahalle)
tip = pd.read_csv(ROOT/'PENDİK/tip/tip.csv').set_index('normalized')['durum']
sn['_durum'] = sn['_n'].map(tip)
print(f'  total seçmen kaydı: {len(sn)}')

panels = [
    ('Pendik Geneli', sn,                         len(sn)),
    ('Düşük Gelir',   sn[sn['_durum']=='low'],    int((sn['_durum']=='low').sum())),
    ('Orta Gelir',    sn[sn['_durum']=='middle'], int((sn['_durum']=='middle').sum())),
    ('Taşra',         sn[sn['_durum']=='Tasra'],  int((sn['_durum']=='Tasra').sum())),
]

panel_data = []
for label, sub, n in panels:
    counts = sub.groupby('BOLGE').size()
    total = counts.sum()
    pct = {b: (counts.get(b,0)/total*100 if total>0 else 0) for b in ORDER}
    panel_data.append((label, pct, n))
    print(f'{label} (n={n}): ' + ', '.join(f"{b}={v:.1f}" for b,v in pct.items()))

global_max = max(max(p.values()) for _, p, _ in panel_data)
print(f'global_max = {global_max:.2f}')

# Layout
W, H = 1600, 920
PAD_L, PAD_R, PAD_T, PAD_B = 30, 30, 100, 65
panel_w = (W - PAD_L - PAD_R) / 4
inner_label_w = 175
inner_bar_w = panel_w - inner_label_w - 70
top_y = PAD_T
bot_y = H - PAD_B
plot_h = bot_y - top_y
n_row = len(ORDER)
row_h = plot_h / n_row
bar_h = row_h * 0.62

elems = []
for i, (label, pct, n) in enumerate(panel_data):
    px = PAD_L + i * panel_w
    elems.append(f'<text x="{px + panel_w/2:.1f}" y="44" text-anchor="middle" font-size="26" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(label)}</text>')
    elems.append(f'<text x="{px + panel_w/2:.1f}" y="72" text-anchor="middle" font-size="15" font-family="Inter Tight,sans-serif" font-style="italic" fill="#666">{n:,} seçmen</text>')
    if i > 0:
        elems.append(f'<line x1="{px:.1f}" y1="{top_y}" x2="{px:.1f}" y2="{bot_y}" stroke="#cfc8b8" stroke-width="1"/>')
    bar_x0 = px + inner_label_w
    for ri, b in enumerate(ORDER):
        v = pct[b]
        y = top_y + ri*row_h + (row_h - bar_h)/2
        bw = inner_bar_w * v / global_max if global_max > 0 else 0
        c = COLOR[b]
        if i == 0:
            elems.append(f'<text x="{bar_x0 - 10:.1f}" y="{y + bar_h/2 + 6:.1f}" text-anchor="end" font-size="17" font-family="Inter Tight,sans-serif" font-weight="600" fill="{c}">{escape(LABEL[b])}</text>')
        elems.append(f'<rect x="{bar_x0:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{c}" rx="2"/>')
        elems.append(f'<text x="{bar_x0 + bw + 8:.1f}" y="{y + bar_h/2 + 6:.1f}" font-size="16" font-family="Inter Tight,sans-serif" font-weight="700" fill="#1a1a1a">%{v:.1f}</text>')

for i in range(4):
    px = PAD_L + i * panel_w
    bar_x0 = px + inner_label_w
    elems.append(f'<line x1="{bar_x0:.1f}" y1="{bot_y + 8}" x2="{bar_x0 + inner_bar_w:.1f}" y2="{bot_y + 8}" stroke="#999" stroke-width="0.6"/>')
    elems.append(f'<text x="{bar_x0:.1f}" y="{bot_y + 28}" font-size="13" font-family="Inter Tight,sans-serif" fill="#666">0</text>')
    elems.append(f'<text x="{bar_x0 + inner_bar_w:.1f}" y="{bot_y + 28}" text-anchor="end" font-size="13" font-family="Inter Tight,sans-serif" fill="#666">%{global_max:.0f}</text>')

svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
       f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
       f'preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'
       + '\n'.join(elems) + '\n</svg>\n')
out = OUT/'pendik_gelir_x_bolge.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
