"""Read-only source checks plus an explicitly historical event used for the live walkthrough."""
import sys,json,asyncio
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db import SessionLocal,Company,Article,BankDocument,Chunk
from app.news import add_article,refresh_news
from app.agent import analyze,run_dict
from sqlalchemy import select
with SessionLocal() as db:
 doc=db.scalar(select(BankDocument).where(BankDocument.title.ilike('%Policy Rate%')))
 chunk=db.scalar(select(Chunk).where(Chunk.document_id==doc.id,Chunk.page==1).order_by(Chunk.id))
 a,_=add_article(db,'Архив · 11 сентября 2026: ключевая ставка без изменения',chunk.text,doc.source_url,'Архив кейса — обзор Альфа-Банка (OCR)',datetime(2026,9,11,12,tzinfo=timezone.utc))
 outcomes=[]
 for cid in ['U_9250','U_57706']:
  run=asyncio.run(analyze(db,cid,a.id))
  outcomes.append({'company_id':cid,'products':db.get(Company,cid).products,'score':run.result['relevance']['score'],'explanation':run.result['relevance']['explanation'],'risks':run.result['interpretation']['risks'],'opportunities':run.result['interpretation']['opportunities'],'bank_excerpt_count':len(run.result['bank_excerpts']),'steps':len(run_dict(db,run)['steps']),'mode':run.mode,'run_id':run.id})
 assert outcomes[0]['score']!=outcomes[1]['score']
 assert outcomes[0]['risks']!=outcomes[1]['risks']
 assert all(r['bank_excerpt_count']>0 for r in outcomes)
 report={'historical_article_id':a.id,'comparison':outcomes,'rss':asyncio.run(refresh_news(db))}
 Path('runtime/official-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
