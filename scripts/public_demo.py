"""Create a separate synthetic-only demo, never tunnel the official-data workspace."""
import argparse,json,os,secrets,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.db import engine
from sqlalchemy import text,create_engine
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=18080);p.add_argument('--tunnel',action='store_true');a=p.parse_args()
if not 1024<=a.port<=65535:raise SystemExit('Port must be 1024..65535')
runtime=ROOT/'runtime/public-demo';runtime.mkdir(parents=True,exist_ok=True)
schema='insight_public_demo'
with engine.begin() as c:c.execute(text('CREATE SCHEMA IF NOT EXISTS '+schema))
url=engine.url.update_query_dict({'options':'-csearch_path='+schema})
secret_file=runtime/'admin-token'
if not secret_file.exists():secret_file.write_text(secrets.token_urlsafe(36));secret_file.chmod(0o600)
env={**os.environ,'PYTHONPATH':str(ROOT/'backend'),'DATABASE_URL':url.render_as_string(hide_password=False),'LLM_MODE':'disabled','LLM_API_KEY':'','ADMIN_TOKEN':secret_file.read_text().strip(),'DEMO_TOKEN':secrets.token_urlsafe(36),'DEMO_MODE':'true'}
subprocess.run([sys.executable,'-m','alembic','-c',str(ROOT/'backend/alembic.ini'),'upgrade','head'],cwd=ROOT,env=env,check=True)
# Fail closed if the isolated schema ever contains official/private material.
isolated=create_engine(url)
from app.db import Company,BankDocument,Article
from sqlalchemy import select,func
with isolated.connect() as c:
    for model,condition in [(Company,Company.synthetic.is_(False)),(BankDocument,BankDocument.synthetic.is_(False)),(Article,Article.private.is_(True))]:
        if c.scalar(select(func.count()).select_from(model).where(condition)):raise SystemExit('Private data detected: refusing public demo')
base=f'http://127.0.0.1:{a.port}'
try:
    with urllib.request.urlopen(base+'/api/health',timeout=2) as r:healthy=json.load(r).get('database')=='postgresql'
except OSError:healthy=False
if not healthy:
    with (runtime/'server.log').open('ab') as log:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(a.port)],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (runtime/'server.pid').write_text(str(proc.pid))
    for _ in range(30):
        try:
            with urllib.request.urlopen(base+'/api/health',timeout=2) as r:
                if json.load(r).get('database')=='postgresql':break
        except OSError:pass
        time.sleep(1)
    else:raise SystemExit('Demo failed to start; check runtime/public-demo/server.log')
with urllib.request.urlopen(base+'/api/companies',timeout=5) as r:companies=json.load(r)
if not companies['items'] or any(not c['synthetic'] for c in companies['items']):raise SystemExit('Synthetic data check failed')
print('Isolated synthetic demo:',base,flush=True)
if a.tunnel:
    binary=ROOT/'runtime/tools/bin/cloudflared'
    if not binary.exists():raise SystemExit('Install official cloudflared portable binary first')
    with (runtime/'tunnel.log').open('ab') as log:
        proc=subprocess.Popen([str(binary),'tunnel','--no-autoupdate','--url',base],cwd=runtime,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (runtime/'tunnel.pid').write_text(str(proc.pid))
    print('Temporary HTTPS URL will appear in runtime/public-demo/tunnel.log; no official data is shared.',flush=True)
