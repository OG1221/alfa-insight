"""Download only public files explicitly linked by the official case; never commit them."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request, json, hashlib
FILES = {
'df_Fid_Uid_link_hack.csv':'1ZJCiqgY1ma4iQ1_ltabtUuaFIBkrqnOe',
'df_Uid_data_hack.csv':'12H7sbLwBcpur0fKaGHPqwPwfXfgQq10b',
'df_Uid_payment_hack.csv':'1zkvWkAS0kZqijD-og_0Cv3o01SoUMY_Z',
'Bond_Brief_14092026.pdf':'1bPzix_332N2CyMY0tqCHuYtGsfJWnFGv',
'ALFA_Russian_Steels_2021.pdf':'1yLCBrIoyIsubLTEBvBHh6io48ysnW-wn',
'ALFA-7M26.pdf':'1HZDq3WGRFdzgm1TZ5hWL23Q3I9c2Eq64',
'ALFA-consumption.pdf':'1riR1lhsb6EY1MwGMxdBlS_tI5ed9mIiz',
'ALFA-Macro_Insights-Policy_Rate_11Sep.pdf':'1shHG89LtMgHT1_uEebHmQSFZe_zbeq7-',
'ALFA-macro_stat1H26.pdf':'1khcHwoS0FkG9p_0J4XoHGaGq3B4V0ime',
'FI_Strategy_3Q26_22072026.pdf':'1hq3Fhyz9ce_sRyGUQB1MdoHeQdfAJfhK',
'Gold_digest_August26.pdf':'1a7TXOCHARfKzUR0hn9Cm9gQSrIldxTDE',
'Inflation_tracker_02.pdf':'19iW3Ph8_wO0HHQY7Ik4lTfC3jRc9gjWV'}
def download(item):
 name,fid=item; dest=Path('data/private')/name; url=f'https://drive.google.com/uc?export=download&id={fid}'
 try:
  if not dest.exists():
   with urllib.request.urlopen(url,timeout=90) as r: data=r.read(90_000_000)
   if data.lstrip().lower().startswith((b'<!doctype html',b'<html')): raise ValueError('HTML received; access/confirmation required')
   if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise ValueError('not a PDF')
   dest.write_bytes(data)
  return {'name':name,'url':f'https://drive.google.com/file/d/{fid}/view','bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'status':'downloaded'}
 except Exception as e: return {'name':name,'status':'failed','error':str(e)}
if __name__=='__main__':
 Path('data/private').mkdir(parents=True,exist_ok=True)
 with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(download,FILES.items()))
 Path('data/private/manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 for r in results: print(r['name'],r['status'],r.get('bytes',r.get('error')))
