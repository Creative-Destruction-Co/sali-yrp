"""Pendik 2024 Belediye Meclisi — 4 panel (Pendik + 3 gelir grubu).
Hesap: kayitli secmen sayisi uzerinden."""
import pandas as pd
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT / '_v2_assets'

xls = pd.read_excel(ROOT/'PENDİK/Secim/2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.xlsx')

PALETTE = {
    'AK PARTİ':'#FFC436','CHP':'#FE0000','YENİDEN REFAH':'#65B741',
    'ZAFER PARTİSİ':'#765827','SAADET':'#6f4e7c','İYİ PARTİ':'#52D3D8',
    'BÜYÜK BİRLİK':'#4F6F52','TİP':'#C70039',
    'Diğer':'#9a9a9a','Geçersiz':'#5d5d5d','Sandığa Gitmeyen':'#bdb1a0',
}
PARTIES = ['AK PARTİ','CHP','YENİDEN REFAH','ZAFER PARTİSİ','SAADET','İYİ PARTİ','BÜYÜK BİRLİK','TİP']
ROWS = PARTIES + ['Diğer','Geçersiz','Sandığa Gitmeyen']

piv = xls.pivot_table(index='muhtarlik_ADI', columns='variable', values='value', aggfunc='sum').fillna(0)
need = ['secmen_SAYISI','oy_KULLANAN_SECMEN_SAYISI','gecerli_OY_TOPLAMI','gecersiz_OY_TOPLAMI'] + PARTIES
for c in need:
    if c not in piv.columns: piv[c] = 0; print(f'WARN: {c} yok!')

# Tum gercek parti kolonlarini bul (sayisal toplam, ittifak/teknik kolonlar haric)
EXCLUDE = {'secmen_SAYISI','oy_KULLANAN_SECMEN_SAYISI','gecerli_OY_TOPLAMI','gecersiz_OY_TOPLAMI',
           'itirazsiz_GECERLI_OY_SAYISI','itirazli_GECERLI_OY_SAYISI'}
ALL_PARTIES = [c for c in piv.columns if c not in EXCLUDE]

sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle
piv['_norm'] = [normalize_mahalle(m) for m in piv.index]
tip = pd.read_csv(ROOT/'PENDİK/tip/tip.csv').set_index('normalized')['durum']
piv['_durum'] = piv['_norm'].map(tip)

panels = [
    ('Pendik Geneli', piv,                          len(piv)),
    ('Düşük Gelir',   piv[piv['_durum']=='low'],    int((piv['_durum']=='low').sum())),
    ('Orta Gelir',    piv[piv['_durum']=='middle'], int((piv['_durum']=='middle').sum())),
    ('Taşra',         piv[piv['_durum']=='Tasra'],  int((piv['_durum']=='Tasra').sum())),
]

panel_data = []
for label, sub, n in panels:
    secmen = sub['secmen_SAYISI'].sum()
    oy_kul = sub['oy_KULLANAN_SECMEN_SAYISI'].sum()
    gecerli = sub['gecerli_OY_TOPLAMI'].sum()
    gecersiz = sub['gecersiz_OY_TOPLAMI'].sum()
    parti_top_all = sum(sub[p].sum() for p in ALL_PARTIES)  # tum partiler
    parti_top_named = sum(sub[p].sum() for p in PARTIES)    # adi gecen
    diger = parti_top_all - parti_top_named
    sandiga_gitmeyen = secmen - oy_kul
    vals = {p: sub[p].sum()/secmen*100 for p in PARTIES}
    vals['Diğer'] = diger/secmen*100
    vals['Geçersiz'] = gecersiz/secmen*100
    vals['Sandığa Gitmeyen'] = sandiga_gitmeyen/secmen*100
    panel_data.append((label, vals, n, int(secmen)))
    print(f'{label} (n={n}, secmen={int(secmen)}): ' + ', '.join(f"{k}={v:.1f}" for k,v in vals.items()) + f' | toplam={sum(vals.values()):.1f}')

global_max = max(max(v.values()) for _, v, _, _ in panel_data)
print(f'global_max = {global_max:.2f}')

# Layout (2023 ile ayni)
W, H = 1600, 920
PAD_L, PAD_R, PAD_T, PAD_B = 30, 30, 100, 65
panel_w = (W - PAD_L - PAD_R) / 4
inner_label_w = 175
inner_bar_w = panel_w - inner_label_w - 70
top_y = PAD_T
bot_y = H - PAD_B
plot_h = bot_y - top_y
n_row = len(ROWS)
row_h = plot_h / n_row
bar_h = row_h * 0.62

elems = []
for i, (label, vals, n, secmen) in enumerate(panel_data):
    px = PAD_L + i * panel_w
    elems.append(f'<text x="{px + panel_w/2:.1f}" y="44" text-anchor="middle" font-size="26" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(label)}</text>')
    elems.append(f'<text x="{px + panel_w/2:.1f}" y="72" text-anchor="middle" font-size="15" font-family="Inter Tight,sans-serif" font-style="italic" fill="#666">{n} mh · {secmen:,} seçmen</text>')
    if i > 0:
        elems.append(f'<line x1="{px:.1f}" y1="{top_y}" x2="{px:.1f}" y2="{bot_y}" stroke="#cfc8b8" stroke-width="1"/>')
    bar_x0 = px + inner_label_w
    for ri, name in enumerate(ROWS):
        v = vals[name]
        y = top_y + ri*row_h + (row_h - bar_h)/2
        bw = inner_bar_w * v / global_max if global_max > 0 else 0
        c = PALETTE.get(name, '#888')
        if i == 0:
            elems.append(f'<text x="{bar_x0 - 10:.1f}" y="{y + bar_h/2 + 6:.1f}" text-anchor="end" font-size="17" font-family="Inter Tight,sans-serif" font-weight="600" fill="{c}">{escape(name)}</text>')
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
out = OUT/'pendik_2024mec_4panel.svg'
out.write_text(svg, encoding='utf-8')
print(f'Wrote {out.name}: {len(svg)//1024}KB')
