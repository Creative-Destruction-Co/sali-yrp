"""v2 build (rev2): tüm text elementlerini sil (HTML başlık+lejant kullanıyor),
multi-panel SVG'lerde panel başlıklarını koru."""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(r'D:\Yepisyeni Seçim\Seçim')
OUT = ROOT / '_v2_assets'
OUT.mkdir(exist_ok=True)
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

TR_FIX = {
    'Gore': 'Göre', 'Sapmasi': 'Sapması', 'sapmasi': 'sapması',
    'Degisim': 'Değişim', 'Donem': 'Dönem', 'donem': 'dönem',
    'Ilce': 'İlçe', 'ilce': 'ilçe',
    'Ortalamasina': 'Ortalamasına', 'ortalamasina': 'ortalamasına',
    'Kume': 'Küme', 'Kasim': 'Kasım',
    'Kirmizi': 'Kırmızı', 'cok': 'çok',
}
def fix_text(s: str) -> str:
    for k, v in TR_FIX.items(): s = s.replace(k, v)
    return s

def color_fix(svg: str) -> str:
    return svg.replace('#a5cce8','#d8dde0').replace('#A5CCE8','#d8dde0')

def strip_all_text(svg: str) -> str:
    # Tum <text>...</text> sil (path icindeki <title> hover tooltip korunur)
    svg = re.sub(r'<text[^>]*>.*?</text>', '', svg, flags=re.DOTALL)
    # Tum <g class="legend">...</g> sil
    svg = re.sub(r'<g class="legend"[^>]*>.*?</g>', '', svg, flags=re.DOTALL)
    return svg

def strip_main_title_only(svg: str) -> str:
    """Sadece ilk text'i (ana baslik) ve lejant g'sini sil. Panel basliklari korunur."""
    # Ilk text element (DOTALL ile minimum match)
    svg = re.sub(r'<text[^>]*>.*?</text>', '', svg, count=1, flags=re.DOTALL)
    # Genel lejant g'sini sil
    svg = re.sub(r'<g class="legend"[^>]*>.*?</g>', '', svg, flags=re.DOTALL)
    # Lejant rect+text bloklarini sil (class'siz olanlar). Heuristic:
    # ardisik <rect ... fill="#"/> + <text font-size="11">label</text> ciftleri.
    # SAG_SOL_LISA tipinde: rect width=14 height=12, text font-size=11 etiket.
    # Bu pattern'i sil.
    pattern = re.compile(
        r'<rect\s+x="\d+"\s+y="\d+"\s+width="14"\s+height="12"[^/]*/>\s*'
        r'<text[^>]*font-size="11"[^>]*>[^<]+</text>\s*',
        re.DOTALL
    )
    svg = pattern.sub('', svg)
    return svg

def process(src, dst, mode='all'):
    raw = Path(src).read_text(encoding='utf-8')
    if mode == 'all':
        out = strip_all_text(raw)
    elif mode == 'panel':
        out = strip_main_title_only(raw)
    else:
        out = raw
    out = color_fix(out)
    out = fix_text(out)
    Path(dst).write_text(out, encoding='utf-8')
    print(f'  {Path(dst).name}: {len(raw)//1024}KB → {len(out)//1024}KB ({mode})')

# Tek-panel: tum text sil (HTML basliklari + lejant kullanacak)
print('[1] Tek-panel SVG\'ler...')
SINGLE = [
    ('PENDİK/haritalar/PENDIK_2023_MV_winner.svg', 'pendik_winner_2023mv.svg'),
    ('PENDİK/haritalar/PENDIK_AKP_2018_2023_swing.svg', 'pendik_akp_swing.svg'),
    ('PENDİK/haritalar/PENDIK_SAADET_2015K_2018_swing.svg', 'pendik_saadet_swing.svg'),
    ('PENDİK/haritalar/PENDIK_SAG_SOL_winner.svg', 'pendik_sag_sol_winner.svg'),
    ('PENDİK/tip/tip_harita.svg', 'pendik_tip.svg'),
]
for s, d in SINGLE:
    process(ROOT/s, OUT/d, mode='all')

# Multi-panel: ana basligi sil (class="title"), panel basliklari (class="panel-title") kalsin
print('[2] Multi-panel SVG\'ler...')

def strip_class_title(svg: str) -> str:
    """Sadece class='title' olan text + tum lejant elementlerini sil. Panel basliklari korunur."""
    svg = re.sub(r'<text[^>]*class="title"(?!-)[^>]*>.*?</text>', '', svg, flags=re.DOTALL)
    svg = re.sub(r'<text[^>]*class="title-text"[^>]*>.*?</text>', '', svg, flags=re.DOTALL)
    svg = re.sub(r'<g class="legend"[^>]*>.*?</g>', '', svg, flags=re.DOTALL)
    # Lejant rect+text ciftleri (class'siz). PENDIK_SAG_SOL_LISA tipinde:
    # <rect x="40" y="730" width="14" height="12" fill="..." stroke="#333" .../>
    # <text x="58" y="740" font-size="11">High-High</text>
    pat = re.compile(
        r'<rect\s+x="\d+"\s+y="\d+"\s+width="14"\s+height="12"[^>]*?/>\s*'
        r'<text[^>]*?font-size="11"[^>]*?>[^<]+</text>\s*',
        re.DOTALL
    )
    svg = pat.sub('', svg)
    return svg

# class="title" olan multi-panel SVG'ler (4donem, yrp, sag_sol_lisa)
TITLED_MULTI = [
    ('PENDİK/haritalar/PENDIK_SAADET_4donem_sapma.svg', 'pendik_saadet_4donem.svg'),
    ('PENDİK/haritalar/PENDIK_YRP_2024_3secim.svg', 'pendik_yrp_3secim.svg'),
    ('PENDİK/haritalar/PENDIK_SAG_SOL_LISA.svg', 'pendik_sag_sol_lisa.svg'),
]
for s, d in TITLED_MULTI:
    raw = (ROOT/s).read_text(encoding='utf-8')
    out = strip_class_title(raw)
    out = color_fix(out)
    out = fix_text(out)
    (OUT/d).write_text(out, encoding='utf-8')
    print(f'  {d}: {len(raw)//1024}KB → {len(out)//1024}KB (titled-multi)')

# lisa_cluster.svg: sadece panel-title var, ana baslik yok. Lejant g'sini sil sadece.
src = ROOT/'PENDİK/memleket/lisa_cluster.svg'
raw = src.read_text(encoding='utf-8')
out = re.sub(r'<g class="legend"[^>]*>.*?</g>', '', raw, flags=re.DOTALL)
# Lejant rect+text pattern (ayni)
pat = re.compile(
    r'<rect\s+x="\d+"\s+y="\d+"\s+width="14"\s+height="12"[^>]*?/>\s*'
    r'<text[^>]*?font-size="11"[^>]*?>[^<]+</text>\s*',
    re.DOTALL
)
out = pat.sub('', out)
out = color_fix(out)
out = fix_text(out)
(OUT/'pendik_memleket_lisa.svg').write_text(out, encoding='utf-8')
print(f'  pendik_memleket_lisa.svg: {len(raw)//1024}KB → {len(out)//1024}KB (panel-only)')

# Bar charts: tum text icindeki ana basligi sil, kategorileri ve degerleri koru
print('[3] Bar chart SVG\'leri...')
def fix_bar(src, dst):
    raw = Path(src).read_text(encoding='utf-8')
    # Sadece class="title" olan text'i sil (ana baslik)
    raw = re.sub(r'<text[^>]*class="title"[^>]*>.*?</text>', '', raw, flags=re.DOTALL)
    raw = re.sub(r'<text[^>]*class="subtitle"[^>]*>.*?</text>', '', raw, flags=re.DOTALL)
    # viewBox 1600 -> 1700 (etiket tasmasi icin)
    raw = re.sub(r'viewBox="0 0 1600 (\d+)"', r'viewBox="0 0 1700 \1"', raw)
    raw = fix_text(raw)
    Path(dst).write_text(raw, encoding='utf-8')
    print(f'  {Path(dst).name}: viewBox=1600→1700')
fix_bar(ROOT/'PENDİK/tip/gelir_bar.svg', OUT/'pendik_gelir_bar.svg')
fix_bar(ROOT/'PENDİK/memleket/bolge_bar.svg', OUT/'pendik_bolge_bar.svg')

# Gelir × Bölge: sadece ana baslik sil, panel basliklarini koru
gxb = (ROOT/'PENDİK/memleket/gelir_x_bolge.svg').read_text(encoding='utf-8')
gxb = re.sub(r'<text[^>]*class="title"[^>]*>.*?</text>', '', gxb, flags=re.DOTALL)
gxb = re.sub(r'<text[^>]*class="subtitle"[^>]*>.*?</text>', '', gxb, flags=re.DOTALL)
gxb = fix_text(gxb)
(OUT/'pendik_gelir_x_bolge.svg').write_text(gxb, encoding='utf-8')
print('  pendik_gelir_x_bolge.svg: ana baslik silindi')

# Buyuk haritalar: title-text + legend strip
print('[4] Buyuk SVG\'ler...')
BIG = [
    ('tr_il_toplam/haritalar/TR_IL_2023_MV_winner.svg', 'tr_il_winner.svg'),
    ('tr_ilce_toplam/haritalar/TR_ILCE_2023_MV_winner.svg', 'tr_ilce_winner.svg'),
    ('PENDİK/memleket/memleket_harita.svg', 'memleket_harita.svg'),
]
for s, d in BIG:
    raw = (ROOT/s).read_text(encoding='utf-8')
    out = re.sub(r'<text[^>]*class="title-text"[^>]*>.*?</text>', '', raw, flags=re.DOTALL)
    out = re.sub(r'<g class="legend"[^>]*>.*?</g>', '', out, flags=re.DOTALL)
    out = re.sub(r'<text[^>]*class="legend-text"[^>]*>.*?</text>', '', out, flags=re.DOTALL)
    out = color_fix(out)
    out = fix_text(out)
    (OUT/d).write_text(out, encoding='utf-8')
    print(f'  {d}: {len(raw)//1024}KB → {len(out)//1024}KB')

print('Tamamlandı.')
