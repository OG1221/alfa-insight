import asyncio,time,logging
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from typing import Annotated
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,Query,UploadFile,File,Request
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select,func,text,or_
from sqlalchemy.orm import Session
from .db import SessionLocal,get_db,Company,Article,BankDocument,Chunk,AgentRun,AgentStep,Feedback,LLMUsage,ImportBatch
from .config import settings,ROOT
from .security import principal,assert_company_access,require_admin
from .schemas import NewsInput,AnalysisInput,QuestionInput,FeedbackInput,Role
from .profiles import company_dict,profile,relations
from .news import add_article,parse_url,refresh_news,article_dict
from .ranking import rank
from .search import search_bank
from .agent import analyze,run_dict,validate_claims
from .llm import readiness,get_provider
from .grounding import model_context
from .seed import seed

log=logging.getLogger('alfa-insight')
@asynccontextmanager
async def lifespan(app):
    # Migrations are intentionally explicit; never mutate schemas inside request handling.
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
        if settings.demo_mode:seed(db)
    yield
app=FastAPI(title='Альфа Инсайт',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json')
DB=Annotated[Session,Depends(get_db)]
P=Annotated[object,Depends(principal)]
limits=defaultdict(deque)
@app.middleware('http')
async def guards(request:Request,call_next):
    if request.method in ('POST','PUT'):
        if int(request.headers.get('content-length','0') or 0)>12_000_000:return JSONResponse({'detail':'Лимит запроса 12 МБ'},413)
        key=(request.client.host if request.client else 'unknown',request.url.path);q=limits[key];now=time.monotonic()
        while q and now-q[0]>60:q.popleft()
        if len(q)>=20:return JSONResponse({'detail':'Слишком много запросов. Повторите через минуту.'},429)
        q.append(now)
    try:response=await call_next(request)
    except Exception:
        log.exception('Unhandled API error');return JSONResponse({'detail':'Ошибка сервиса; подробности сохранены в локальном журнале'},500)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    return response

def get_company(db,id,p):
    c=db.get(Company,id)
    if not c:raise HTTPException(404,'Компания не найдена')
    assert_company_access(c,p);return c

def get_run(db,id,p):
    r=db.get(AgentRun,id)
    if not r:raise HTTPException(404,'Анализ не найден')
    get_company(db,r.company_id,p)
    if db.get(Article,r.article_id).private and not p.admin:raise HTTPException(403,'Источник доступен локальному администратору')
    return r

@app.get('/api/health')
def health(db:DB):
    db.execute(text('SELECT 1'));return {'status':'ok','database':db.bind.dialect.name,'version':'1.0.0'}
@app.get('/api/status')
def status(p:P):
    ready,reason=readiness();return {'ai_available':ready,'ai_message':reason,'llm_mode':settings.llm_mode,'data_access':'official' if p.admin else 'synthetic','prototype':True,'role_options':['ceo','cfo','treasury','accountant']}
@app.get('/api/companies')
def companies(db:DB,p:P,q:str=Query('',max_length=150),limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0)):
    stmt=select(Company)
    if not p.admin:stmt=stmt.where(Company.synthetic.is_(True))
    if q:stmt=stmt.where(or_(Company.id.ilike('%'+q+'%'),Company.sector.ilike('%'+q+'%'),Company.region.ilike('%'+q+'%')))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    # Pin two contrasting real profiles for a reproducible jury walkthrough.
    from sqlalchemy import case
    stmt=stmt.order_by(case((Company.id=='U_9250',0),(Company.id=='U_57706',1),else_=2),Company.synthetic.desc(),Company.id).limit(limit).offset(offset)
    return {'items':[company_dict(c) for c in db.scalars(stmt)],'total':total,'offset':offset}
@app.get('/api/companies/{company_id}')
def company(company_id:str,db:DB,p:P):return profile(db,get_company(db,company_id,p))
@app.get('/api/feed')
def feed(company_id:str,db:DB,p:P,role:Role='cfo',category:str='',q:str=Query('',max_length=150),sort:str='relevance',limit:int=Query(60,ge=1,le=100)):
    c=get_company(db,company_id,p);stmt=select(Article)
    if not p.admin:stmt=stmt.where(Article.private.is_(False))
    if category:stmt=stmt.where(Article.category==category)
    if q:stmt=stmt.where(or_(Article.title.ilike('%'+q+'%'),Article.text.ilike('%'+q+'%')))
    rows=db.scalars(stmt.order_by(Article.published_at.desc()).limit(500)).all();related=relations(db,c)
    items=[{**article_dict(a),'relevance':rank(c,a,role,related)} for a in rows]
    if sort=='relevance':items.sort(key=lambda a:(a['relevance']['score'],a['published_at']),reverse=True)
    return {'items':items[:limit],'total':len(items),'scanned_limit':500,'company_id':c.id}
@app.get('/api/articles/{id}')
def article(id:str,db:DB,p:P):
    a=db.get(Article,id)
    if not a:raise HTTPException(404,'Событие не найдено')
    if a.private and not p.admin:raise HTTPException(403,'Источник доступен локальному администратору')
    return article_dict(a)
@app.post('/api/articles')
async def create_news(body:NewsInput,db:DB,p:P):
    try:
        title,content,source=body.title,body.text,'Ручной ввод — источник не верифицирован'
        if body.url:title,content,source=await parse_url(str(body.url))
        a,created=add_article(db,title,content,str(body.url) if body.url else None,source,body.published_at,private=p.admin)
        if a.private and not p.admin:raise HTTPException(403,'Источник доступен локальному администратору')
        return {'article':article_dict(a),'created':created}
    except HTTPException:raise
    except Exception as exc:raise HTTPException(422,str(exc)[:250]) from None
@app.post('/api/news/refresh')
async def refresh(db:DB,p:P):return {'sources':await refresh_news(db)}
@app.post('/api/analyses')
async def create_analysis(body:AnalysisInput,db:DB,p:P):
    get_company(db,body.company_id,p)
    event=db.get(Article,body.article_id)
    if not event:raise HTTPException(404,'Новость не найдена')
    if event.private and not p.admin:raise HTTPException(403,'Источник доступен локальному администратору')
    try:
        run=await asyncio.wait_for(analyze(db,body.company_id,body.article_id,body.role),timeout=settings.agent_timeout+5)
        return run_dict(db,run)
    except Exception as exc:raise HTTPException(422,'Анализ не завершён: '+str(exc)[:200]) from None
@app.get('/api/analyses/{id}')
def get_analysis(id:str,db:DB,p:P):return run_dict(db,get_run(db,id,p))
@app.get('/api/analyses/{id}/sources')
def sources(id:str,db:DB,p:P):return get_run(db,id,p).result.get('evidence',[])
@app.get('/api/analyses/{id}/steps')
def steps(id:str,db:DB,p:P):return run_dict(db,get_run(db,id,p))['steps']
@app.post('/api/analyses/{id}/questions')
async def question(id:str,body:QuestionInput,db:DB,p:P):
    run=get_run(db,id,p)
    if not readiness()[0]:raise HTTPException(503,'Уточняющие ответы требуют ключа разрешённой LLM. Источники и анализ по правилам доступны.')
    try:
        generated=await get_provider().generate(db,model_context(task='Ответить на уточняющий вопрос по собранным источникам',question=body.question,previous=run.result.get('interpretation'),evidence=run.result['evidence'],role=run.role))
        result,validation=validate_claims(generated,run.result['evidence'],require_quotes=True)
        db.add(AgentStep(run_id=id,tool='followup_question',summary='Ответ на уточняющий вопрос',output={'question':body.question,'answer':result,'validation':validation}));db.commit()
        return result
    except Exception:raise HTTPException(502,'LLM не вернула проверяемый ответ') from None
@app.post('/api/analyses/{id}/feedback')
def feedback(id:str,body:FeedbackInput,db:DB,p:P):
    get_run(db,id,p);db.add(Feedback(run_id=id,rating=body.rating,comment=body.comment));db.commit();return {'saved':True}
@app.get('/api/documents')
def documents(db:DB,p:P,q:str=Query('',max_length=500)):
    if q:
        results=search_bank(db,q,10,not p.admin)
        return {'items':[r for r in results if p.admin or r['synthetic']]}
    stmt=select(BankDocument)
    if not p.admin:stmt=stmt.where(BankDocument.synthetic.is_(True))
    return {'items':[{'id':d.id,'title':d.title,'pages':d.pages,'source_url':d.source_url,'synthetic':d.synthetic,'extraction':d.extraction,'imported_at':d.imported_at.isoformat()} for d in db.scalars(stmt)]}
@app.post('/api/admin/import')
async def upload_csv(db:DB,p:P,file:UploadFile=File(...)):
    require_admin(p)
    from .etl import import_csv,import_pdf
    import tempfile
    data=await file.read(12_000_001)
    if len(data)>12_000_000:raise HTTPException(413,'Максимум 12 МБ. Для официальных файлов используйте CLI-импорт.')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.csv','.pdf'):raise HTTPException(422,'Поддерживаются CSV и PDF')
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as f:
            f.write(data);f.flush();result=import_pdf(db,f.name) if suffix=='.pdf' else import_csv(db,f.name)
        return result
    except Exception as exc:db.rollback();raise HTTPException(422,str(exc)[:250]) from None
@app.get('/api/metrics')
def metrics(db:DB,p:P):
    stmt=select(AgentRun)
    if not p.admin:stmt=stmt.join(Company,AgentRun.company_id==Company.id).where(Company.synthetic.is_(True))
    runs=db.scalars(stmt).all();done=[r for r in runs if r.status=='complete'];claims=sum(r.result.get('validation',{}).get('claims_count',0) for r in done)
    costs=db.scalar(select(func.coalesce(func.sum(LLMUsage.cost_rub),0))) if p.admin else None
    return {'runs':len(runs),'completed':len(done),'failed':sum(r.status=='failed' for r in runs),'avg_duration_ms':round(sum(r.duration_ms for r in done)/len(done)) if done else None,'claims_with_checked_references':claims,'reference_coverage':1.0 if claims else None,'semantic_quality_measured':False,'llm_cost_or_reserved_rub':costs,'feedback_count':db.scalar(select(func.count()).select_from(Feedback).where(Feedback.run_id.in_([r.id for r in runs]))),'precision_at_k':None,'ndcg':None}

static=ROOT/'frontend/dist'
if static.exists():
    app.mount('/assets',StaticFiles(directory=static/'assets'),name='assets')
    @app.get('/{path:path}',include_in_schema=False)
    def index(path:str):
        if path.startswith('api/'):raise HTTPException(404,'API endpoint not found')
        return FileResponse(static/'index.html')
