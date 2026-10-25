"""Import authorized local datasets; fail the CLI when any import fails."""
import sys,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db import SessionLocal
from app.etl import import_csv,import_pdf


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',default='data/synthetic')
    parser.add_argument('--synthetic',action='store_true')
    parser.add_argument('--pdf',action='store_true')
    parser.add_argument('--only-pdf',action='store_true')
    args=parser.parse_args();folder=Path(args.directory)
    if not folder.is_dir():parser.error('Import directory does not exist')
    manifest={}
    if (folder/'manifest.json').exists():
        manifest={r['name']:r.get('url') for r in json.loads((folder/'manifest.json').read_text(encoding='utf-8'))}
    failures=[]
    with SessionLocal() as db:
        if not args.only_pdf:
            for name in ['df_Uid_data_hack.csv','df_Fid_Uid_link_hack.csv','df_Uid_payment_hack.csv']:
                path=folder/name
                if not path.exists():continue
                try:print(name,json.dumps(import_csv(db,path,args.synthetic),ensure_ascii=False),flush=True)
                except Exception as exc:
                    db.rollback();failures.append(name)
                    print(name,'FAILED',type(exc).__name__,file=sys.stderr,flush=True)
                    break
        if args.pdf or args.only_pdf:
            for path in sorted(folder.glob('*.pdf')):
                try:print(path.name,json.dumps(import_pdf(db,path,manifest.get(path.name),args.synthetic),ensure_ascii=False),flush=True)
                except Exception as exc:
                    db.rollback();failures.append(path.name)
                    print(path.name,'FAILED',str(getattr(exc,'orig',exc))[:300],file=sys.stderr,flush=True)
    return 1 if failures else 0


if __name__=='__main__':raise SystemExit(main())
