"""Explicit real-API acceptance probe. Refuses to imply AI readiness without credentials."""
import argparse,sys,json,asyncio
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.llm import readiness
from app.db import SessionLocal,LLMUsage
from app.seed import seed
from app.news import add_article
from app.agent import analyze
from sqlalchemy import select
p=argparse.ArgumentParser();p.add_argument('--run',action='store_true',help='Perform paid organizer calls within configured daily budget');a=p.parse_args()
ready,reason=readiness()
if not ready:print('LLM не готова: '+reason);raise SystemExit(2)
if not a.run:print('Конфигурация заполнена. Реальный запрос не выполнялся. Для проверки: --run');raise SystemExit(0)
with SessionLocal() as db:
    seed(db)
    article,_=add_article(db,'Учебная проверка реального AI API','Учебный сценарий: ключевая ставка может влиять на новые кредитные договоры. Это синтетическая проверка API без банковского прогноза.',synthetic=True)
    run=asyncio.run(analyze(db,'DEMO_U_101',article.id))
    report={'mode':run.mode,'status':run.status,'error':run.result.get('generation_error'),'verified_quote_count':run.result.get('validation',{}).get('verified_quote_count',0),'run_id':run.id,'real_ai_verified':run.mode=='llm'}
    (ROOT/'runtime/llm-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if run.mode!='llm':raise SystemExit(1)
