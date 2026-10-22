import sys,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db import SessionLocal
from app.etl import import_csv,import_pdf
p=argparse.ArgumentParser();p.add_argument('--directory',default='data/synthetic');p.add_argument('--synthetic',action='store_true');p.add_argument('--pdf',action='store_true');args=p.parse_args();folder=Path(args.directory)
manifest={}
if (folder/'manifest.json').exists():manifest={r['name']:r.get('url') for r in json.loads((folder/'manifest.json').read_text())}
with SessionLocal() as db:
 for name in ['df_Uid_data_hack.csv','df_Fid_Uid_link_hack.csv','df_Uid_payment_hack.csv']:
  path=folder/name
  if path.exists():print(name,json.dumps(import_csv(db,path,args.synthetic),ensure_ascii=False),flush=True)
 if args.pdf:
  for path in sorted(folder.glob('*.pdf')):
   try:print(path.name,json.dumps(import_pdf(db,path,manifest.get(path.name),args.synthetic),ensure_ascii=False),flush=True)
   except Exception as e:print(path.name,'FAILED',str(e),flush=True)
