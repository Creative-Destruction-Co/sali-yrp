"""3 panel SVG: gelir, memleket (TR ilçe), seçim sonuçları."""
import pandas as pd, geopandas as gpd, sys, json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT/'_v2_assets'

data = json.loads((OUT/'_strategy_panel_data.json').read_text(encoding='utf-8'))
mem_b = pd.read_csv(OUT/'_strategy_mem_basari.csv')
mem_h = pd.read_csv(OUT/'_strategy_mem_hedef.csv')

PALETTE = {
    'AK PARTİ':'#FFC436','CHP':'#FE0000','YENİDEN REFAH':'#65B741','ZAFER PARTİSİ':'#765827',
    'SAADET':'#6f4e7c','İYİ PARTİ':'#52D3D8','BÜYÜK BİRLİK':'#4F6F52','TİP':'#C70039',
    'Diğer':'#9a9a9a','Geçersiz':'#5d5d5d','Sandığa Gitmeyen':'#bdb1a0',
}
ROWS = list(PALETTE.keys())

# === SVG 1: Gelir tipi (yan yana bar) — seçmen sayısı bazında ===
def render_gelir():
    sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
    from normalize import normalize_mahalle
    sets = json.loads((OUT/'_strategy_sets.json').read_text(encoding='utf-8'))
    basari_set = set(sets['basari']); hedef_set = set(sets['hedef'])
    xls = pd.read_excel(ROOT/'PENDİK/Secim/2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.xlsx')
    piv = xls.pivot_table(index='muhtarlik_ADI', columns='variable', values='value', aggfunc='sum').fillna(0)
    piv['_norm'] = [normalize_mahalle(m) for m in piv.index]
    tip = pd.read_csv(ROOT/'PENDİK/tip/tip.csv').set_index('normalized')['durum']
    piv['_durum'] = piv['_norm'].map(tip)
    def sec_by_durum(s):
        sub = piv[piv['_norm'].isin(s)]
        return {d: int(sub[sub['_durum']==d]['secmen_SAYISI'].sum()) for d in ['low','middle','Tasra']}
    sec_b = sec_by_durum(basari_set); sec_h = sec_by_durum(hedef_set)
    print(f'  gelir secmen: basari={sec_b}, hedef={sec_h}')

    W, H = 1600, 720
    PAD_T, PAD_B = 110, 50
    panel_w = W/2
    elems = []
    glabel = {'low':'Düşük Gelir','middle':'Orta Gelir','Tasra':'Taşra'}
    gcolor = {'low':'#3a86ff','middle':'#fb8500','Tasra':'#2a9d8f'}
    groups = ['low','middle','Tasra']
    by_g = {'basari': sec_b, 'hedef': sec_h}
    max_cnt = max(max(by_g[g][k] for k in groups) for g in ['basari','hedef'])
    nb = len(basari_set); nh = len(hedef_set)
    for i,(gkey,title) in enumerate([('basari',f'YRP Başarılı ({nb} mahalle)'),('hedef',f'YRP Hedeflemeli ({nh} mahalle)')]):
        cx = i*panel_w
        tot = sum(by_g[gkey].values())
        elems.append(f'<text x="{cx+panel_w/2:.1f}" y="48" text-anchor="middle" font-size="26" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(title)}</text>')
        elems.append(f'<text x="{cx+panel_w/2:.1f}" y="76" text-anchor="middle" font-size="15" font-family="Inter Tight,sans-serif" font-style="italic" fill="#666">{tot:,} seçmen — gelir tipine göre</text>')
        if i>0:
            elems.append(f'<line x1="{cx:.1f}" y1="{PAD_T-30}" x2="{cx:.1f}" y2="{H-PAD_B+10}" stroke="#cfc8b8" stroke-width="1"/>')
        n_row = len(groups)
        plot_h = H-PAD_T-PAD_B
        row_h = plot_h/n_row
        bar_h = row_h*0.6
        L = cx + 200; R = cx + panel_w - 140
        bar_w_max = R - L
        for ri,g in enumerate(groups):
            cnt = by_g[gkey][g]
            pct = cnt/tot*100 if tot>0 else 0
            y = PAD_T + ri*row_h + (row_h-bar_h)/2
            bw = bar_w_max * cnt/max_cnt if max_cnt>0 else 0
            elems.append(f'<text x="{L-12:.1f}" y="{y+bar_h/2+6:.1f}" text-anchor="end" font-size="20" font-family="Inter Tight,sans-serif" font-weight="600" fill="{gcolor[g]}">{glabel[g]}</text>')
            elems.append(f'<rect x="{L:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{gcolor[g]}" rx="2"/>')
            elems.append(f'<text x="{L+bw+10:.1f}" y="{y+bar_h/2+6:.1f}" font-size="20" font-family="Inter Tight,sans-serif" font-weight="700" fill="#1a1a1a">{cnt:,} <tspan font-size="15" font-weight="500" fill="#666">(%{pct:.1f})</tspan></text>')
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'+'\n'.join(elems)+'\n</svg>\n')
    (OUT/'pendik_strategy_gelir.svg').write_text(svg, encoding='utf-8')
    print(f'  gelir: {len(svg)//1024}KB')

render_gelir()

# === SVG 2: Memleket TR ilçe haritası (yan yana 2 panel) ===
def render_memleket():
    import json
    mapping = json.loads((OUT/'old_to_gadm_ilce.json').read_text(encoding='utf-8'))
    g2 = gpd.read_file(ROOT/'_gadm_tr/gadm41_TUR_2.shp').to_crs(3857)

    def total_count(mem_df):
        return int(mem_df['count'].sum())
    nb = total_count(mem_b); nh = total_count(mem_h)
    print(f'memleket toplam: başarılı={nb}, hedef={nh}')

    def merge_count(mem_df):
        m = mem_df.copy()
        def to_g(r):
            il = str(r['il']).upper().strip(); ilce = str(r['ilce']).upper().strip()
            if '/' in ilce: ilce = ilce.split('/')[0].strip()
            if ilce == f'{il} MERKEZ': ilce = 'MERKEZ'
            return mapping.get(f'{il}|{ilce}', [None,None])
        m[['n1','n2']] = m.apply(to_g, axis=1, result_type='expand')
        agg = m.dropna(subset=['n1']).groupby(['n1','n2'])['count'].sum().reset_index()
        merged = g2.merge(agg, left_on=['NAME_1','NAME_2'], right_on=['n1','n2'], how='left')
        merged['count'] = merged['count'].fillna(0)
        # Il ortalaması fallback (count=0 polygon'lar)
        il_avg = merged[merged['count']>0].groupby('NAME_1')['count'].mean()
        for ix in merged[merged['count']==0].index:
            il = merged.loc[ix, 'NAME_1']
            if il in il_avg.index:
                merged.loc[ix, 'count'] = float(il_avg[il])
        return merged

    g2b = merge_count(mem_b)
    g2h = merge_count(mem_h)
    g2b['pct'] = g2b['count']/nb*100
    g2h['pct'] = g2h['count']/nh*100
    vmax = max(g2b['pct'].max(), g2h['pct'].max())
    print(f'vmax (pct): {vmax:.2f}')

    W, H = 1600, 920
    PAD_T = 90
    panel_w = W/2
    map_pad = 20
    minx,miny,maxx,maxy = g2.total_bounds
    bw,bh = maxx-minx, maxy-miny
    map_w = panel_w - 2*map_pad
    map_h = H - PAD_T - 60
    sp = min(map_w/bw, map_h/bh)
    dw = bw*sp; dh = bh*sp

    def color(p):
        if p<=0: return '#ece6d6'
        t = min(1.0, p/vmax)
        r=int(247+( 33-247)*t); g=int(251+(102-251)*t); b=int(255+(172-255)*t)
        return f'#{r:02x}{g:02x}{b:02x}'

    elems = []
    for i,(gd,title) in enumerate([(g2b,'YRP Başarılı (25 mh)'),(g2h,'YRP Hedeflemeli (7 mh)')]):
        cx = i*panel_w
        elems.append(f'<text x="{cx+panel_w/2:.1f}" y="44" text-anchor="middle" font-size="24" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(title)}</text>')
        ox = cx + (panel_w - dw)/2
        oy = PAD_T + (map_h - dh)/2
        def tr(x,y, ox=ox, oy=oy): return ox+(x-minx)*sp, (oy+dh)-(y-miny)*sp
        if i>0:
            elems.append(f'<line x1="{cx:.1f}" y1="{PAD_T-30}" x2="{cx:.1f}" y2="{H-30}" stroke="#cfc8b8" stroke-width="1"/>')
        for _, row in gd.iterrows():
            g = row.geometry
            if g is None or g.is_empty: continue
            polys = [g] if g.geom_type=='Polygon' else list(g.geoms)
            d_parts = []
            for p in polys:
                cs = list(p.exterior.coords)
                if not cs: continue
                d_parts.append('M ' + ' L '.join(f'{tr(x,y)[0]:.2f} {tr(x,y)[1]:.2f}' for x,y in cs) + ' Z')
            if not d_parts: continue
            fill = color(row['pct'])
            elems.append(f'<path d="{" ".join(d_parts)}" fill="{fill}" stroke="#fff" stroke-width="0.2"/>')
    # Lejant (sequential)
    leg_y = H - 35
    leg_x0 = W*0.35; leg_w = W*0.30
    elems.append(f'<defs><linearGradient id="memg" x1="0%" x2="100%"><stop offset="0%" stop-color="#f7fbff"/><stop offset="100%" stop-color="#2166ac"/></linearGradient></defs>')
    elems.append(f'<rect x="{leg_x0}" y="{leg_y}" width="{leg_w}" height="10" fill="url(#memg)" stroke="#999" stroke-width="0.5"/>')
    elems.append(f'<text x="{leg_x0}" y="{leg_y+24}" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">%0</text>')
    elems.append(f'<text x="{leg_x0+leg_w}" y="{leg_y+24}" text-anchor="end" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">%{vmax:.1f}</text>')
    elems.append(f'<text x="{leg_x0+leg_w/2}" y="{leg_y-6}" text-anchor="middle" font-size="13" font-family="Inter Tight,sans-serif" fill="#444">grup içindeki seçmenlerin memleket dağılımı</text>')

    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'+'\n'.join(elems)+'\n</svg>\n')
    (OUT/'pendik_strategy_memleket.svg').write_text(svg, encoding='utf-8')
    print(f'  memleket: {len(svg)//1024}KB')

render_memleket()

# === SVG 3: Seçim sonuçları + seçmen sayısı (yan yana bar) ===
def render_secim():
    W, H = 1600, 920
    PAD_T, PAD_B = 110, 50
    panel_w = W/2
    elems = []
    max_pct = max(max(data[g]['parti_pct'].values()) for g in ['basari','hedef'])
    for i,(gkey,title) in enumerate([('basari','YRP Başarılı'),('hedef','YRP Hedeflemeli')]):
        cx = i*panel_w
        d = data[gkey]
        elems.append(f'<text x="{cx+panel_w/2:.1f}" y="44" text-anchor="middle" font-size="26" font-family="Newsreader,serif" font-weight="600" fill="#1a1a1a">{escape(title)} <tspan font-weight="400" fill="#666">({d["mahalle"]} mahalle)</tspan></text>')
        elems.append(f'<text x="{cx+panel_w/2:.1f}" y="76" text-anchor="middle" font-size="20" font-family="Inter Tight,sans-serif" font-weight="600" fill="var(--accent)" style="fill:#b91c1c;">{d["secmen"]:,} seçmen</text>')
        if i>0:
            elems.append(f'<line x1="{cx:.1f}" y1="{PAD_T-30}" x2="{cx:.1f}" y2="{H-PAD_B+10}" stroke="#cfc8b8" stroke-width="1"/>')
        n_row = len(ROWS)
        plot_h = H-PAD_T-PAD_B
        row_h = plot_h/n_row
        bar_h = row_h*0.62
        L = cx + 200; R = cx + panel_w - 90
        bar_w_max = R - L
        for ri,p in enumerate(ROWS):
            v = d['parti_pct'].get(p,0)
            y = PAD_T + ri*row_h + (row_h-bar_h)/2
            bw = bar_w_max * v/max_pct if max_pct>0 else 0
            c = PALETTE[p]
            elems.append(f'<text x="{L-10:.1f}" y="{y+bar_h/2+5:.1f}" text-anchor="end" font-size="15" font-family="Inter Tight,sans-serif" font-weight="600" fill="{c}">{escape(p)}</text>')
            elems.append(f'<rect x="{L:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{c}" rx="2"/>')
            elems.append(f'<text x="{L+bw+8:.1f}" y="{y+bar_h/2+5:.1f}" font-size="14" font-family="Inter Tight,sans-serif" font-weight="700" fill="#1a1a1a">%{v:.1f}</text>')
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">\n'+'\n'.join(elems)+'\n</svg>\n')
    (OUT/'pendik_strategy_secim.svg').write_text(svg, encoding='utf-8')
    print(f'  secim: {len(svg)//1024}KB')

render_secim()
