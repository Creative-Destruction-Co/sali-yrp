"""Başarılı (25) vs Hedeflemeli (9) iki grup için panel grafikleri:
1) gelir tipi bar (yan yana)
2) memleket — Türkiye ilçe haritası (yan yana, sequential mavi)
3) 2024 Meclis seçim sonuçları + seçmen sayısı (yan yana)
"""
import pandas as pd, geopandas as gpd, sys
from pathlib import Path
from xml.sax.saxutils import escape
sys.path.insert(0, r'C:\Users\ismet\.claude\skills\secim-mahalle-match\scripts')
from normalize import normalize_mahalle

ROOT = Path(r'D:/Yepisyeni Seçim/Seçim')
OUT = ROOT/'_v2_assets'

# === Tek seferlik flag hesabı (önceki strategy script ile aynı) ===
xls = pd.read_excel(ROOT/'PENDİK/Secim/2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.xlsx')
piv = xls.pivot_table(index='muhtarlik_ADI', columns='variable', values='value', aggfunc='sum').fillna(0)
EXCL = {'secmen_SAYISI','oy_KULLANAN_SECMEN_SAYISI','gecerli_OY_TOPLAMI','gecersiz_OY_TOPLAMI','itirazsiz_GECERLI_OY_SAYISI','itirazli_GECERLI_OY_SAYISI'}
ALL = [c for c in piv.columns if c not in EXCL]
NAMED = ['AK PARTİ','CHP','YENİDEN REFAH','ZAFER PARTİSİ','SAADET','İYİ PARTİ','BÜYÜK BİRLİK','TİP']
piv['kayip'] = piv['gecersiz_OY_TOPLAMI']+(piv['secmen_SAYISI']-piv['oy_KULLANAN_SECMEN_SAYISI'])+(sum(piv[p] for p in ALL)-sum(piv[p] for p in NAMED))
piv['kayip_pct']=piv['kayip']/piv['secmen_SAYISI']*100
ilce_kayip=piv['kayip'].sum()/piv['secmen_SAYISI'].sum()*100
piv['_n']=[normalize_mahalle(m) for m in piv.index]
fk_map=(piv.set_index('_n')['kayip_pct']>ilce_kayip).astype(int)

def load_p(fn, party):
    df=pd.read_csv(ROOT/'PENDİK/oranlar'/fn); df['_p']=df[party]/df['n_sandik']*100
    ilce=float((df['_p']*df['gecerli_oy_toplam']).sum()/df['gecerli_oy_toplam'].sum())
    return df.set_index('normalized')['_p'], ilce
a18,i18 = load_p('oran_2018_MİLLETVEKİLİ_GENEL.csv','AK PARTİ')
a23,i23 = load_p('oran_2023_MİLLETVEKİLİ_GENEL.csv','AK PARTİ')
swing = i23-i18
files_s={'y11':'oran_2011_MİLLETVEKİLİ_GENEL.csv','y15h':'oran_2015_Haziran_MİLLETVEKİLİ_GENEL.csv','y15k':'oran_2015_Kasım_MİLLETVEKİLİ_GENEL.csv','y18':'oran_2018_MİLLETVEKİLİ_GENEL.csv'}
ilce_s={};v_s={}
for k,fn in files_s.items():
    df=pd.read_csv(ROOT/'PENDİK/oranlar'/fn); df['_p']=df['SAADET']/df['n_sandik']*100
    ilce_s[k]=float((df['_p']*df['gecerli_oy_toplam']).sum()/df['gecerli_oy_toplam'].sum())
    v_s[k]=df.set_index('normalized')['_p']
y23m,i23y = load_p('oran_2023_MİLLETVEKİLİ_GENEL.csv','YENİDEN REFAH')
y24m,i24y = load_p('oran_2024_BELEDİYE_MECLİSİ_ÜYELİĞİ.csv','YENİDEN REFAH')

shp = gpd.read_file(ROOT/'PENDİK/Harita Teknik Dosya/PENDİK.shp').to_crs(3857)
shp['_n']=shp['MAHALLEADI'].apply(normalize_mahalle)
shp['v23y']=shp['_n'].map(y23m); shp['v24y']=shp['_n'].map(y24m)
shp['fy']=(((shp['v23y']>i23y)&(shp['v24y']>i24y))|((shp['v24y']-shp['v23y'])>0)).astype(int)
shp['fk']=shp['_n'].map(fk_map).fillna(0).astype(int)
shp['v18']=shp['_n'].map(a18); shp['v23a']=shp['_n'].map(a23)
shp['fa']=(((shp['v23a']-shp['v18'])-swing)<0).astype(int)
for k in files_s:
    shp[f'sf_{k}']=(shp['_n'].map(v_s[k])>ilce_s[k]).astype('Int64')
shp['fsu']=((shp['sf_y11']==1)|(shp['sf_y15h']==1)|(shp['sf_y15k']==1)|(shp['sf_y18']==1)).astype(int)
shp['fixed_union']=((shp['fk']==1)|(shp['fa']==1)|(shp['fsu']==1)).astype(int)

basari_set = set(shp[(shp['fixed_union']==1)&(shp['fy']==1)]['_n'])
hedef_set  = set(shp[(shp['fixed_union']==1)&(shp['fy']==0)]['_n'])
print(f'başarılı: {len(basari_set)}, hedeflemeli: {len(hedef_set)}')

# Mahalle setini koru, devamı yapacağız
import json
(OUT/'_strategy_sets.json').write_text(json.dumps({'basari':sorted(basari_set), 'hedef':sorted(hedef_set)}, ensure_ascii=False, indent=2), encoding='utf-8')
print('sets saved')
