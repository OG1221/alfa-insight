import time,uuid,re
from sqlalchemy import select
from .db import Company,Article,AgentRun,AgentStep
from .profiles import profile,relations
from .ranking import rank,is_rate_event
from .search import search_bank
from .news import article_dict
from .llm import get_provider,readiness
from .config import settings

TOOL_LABELS={'get_company_profile':'Загружен профиль компании','get_bank_products':'Проверены банковские продукты','get_news_event':'Получено новостное событие','analyze_relationships':'Проверены платежные и групповые связи','search_related_news':'Найдены связанные события','search_bank_analytics':'Выполнен поиск по документам банка','broaden_search':'Поиск расширен из-за нехватки данных','calculate_relevance':'Рассчитана релевантность','get_evidence':'Собраны исходные доказательства','generate_interpretation':'Запрошена разрешённая LLM','check_claims':'Проверены ссылки и полнота результата','save_result':'Результат сохранён'}

def rule_interpretation(company,article,relevance):
    text=(article.title+' '+article.text).lower();risks=[];opportunities=[];actions=[]
    def claim(text,ids=None):return {'text':text,'evidence_ids':ids or ['profile','news']}
    if is_rate_event(text):
        if company.products.get('Кредиты'):
            risks.append(claim('Есть кредитный продукт. Чувствительность расходов к ставке возможна для плавающих договоров и нового финансирования; тип ставки и задолженность неизвестны.'))
            actions.append(claim('Проверить структуру ставок, даты пересмотра и погашения в кредитных договорах. Сумму эффекта оценивать после получения этих данных.'))
        if company.products.get('Депозиты'):
            opportunities.append(claim('Есть депозитный продукт. Изменение условий новых размещений может быть релевантно; направление и размер эффекта зависят от ставки, срока и фактической ликвидности.'))
            actions.append(claim('Сопоставить сроки депозитов, текущие предложения банка и платежный календарь. Наличие свободных средств не предполагается.'))
        if company.products.get('Лизинг'):
            risks.append(claim('При новом лизинге или пересмотре условий стоимость финансирования может зависеть от ставок; действующие условия неизвестны.'))
    if company.foreign_trade and any(t in text for t in ['валют','экспорт','импорт','санкц','тамож']):
        risks.append(claim('Данные ФТС указывают на внешнеторговый контекст. Валютные и регуляторные условия стоит проверить по реальным контрактам; открытая валютная позиция неизвестна.'))
        actions.append(claim('Проверить валюты, страны и сроки расчётов по действующим внешнеторговым контрактам.'))
    if any(r['feature']=='sector' for r in relevance['reasons']):
        risks.append(claim('Событие тематически связано с отраслью компании. Перед изменением планов проверить долю затронутой продукции или издержек; она отсутствует в профиле.'))
        actions.append(claim('Сверить событие с номенклатурой, договорами и бюджетом компании. Совпадение отрасли само по себе не доказывает влияние.'))
    if not actions:actions.append(claim('Уточнить связь события с договорами и операциями компании. Доступные признаки не позволяют обоснованно оценить финансовый эффект.'))
    return {'summary':claim(relevance['explanation']), 'risks':risks,'opportunities':opportunities,'actions':actions,'uncertainties':['Это условные направления проверки по правилам, а не генерация AI.','Денежное влияние, задолженность, остатки и рыночная доля не рассчитываются без исходных данных.']}

def validate_claims(generated,evidence):
    data=generated.model_dump() if hasattr(generated,'model_dump') else generated
    available={e['id']:e['text'] for e in evidence};invalid=[]
    for item in [data['summary']]+data['risks']+data['opportunities']+data['actions']:
        if not item['evidence_ids'] or not set(item['evidence_ids'])<=set(available):invalid.append('Неизвестный источник')
        corpus=' '.join(available.get(i,'') for i in item['evidence_ids'])
        for n in re.findall(r'\b\d+(?:[.,]\d+)?\b',item['text']):
            if n not in corpus:invalid.append('Число отсутствует в указанных доказательствах')
    if invalid:raise ValueError('; '.join(sorted(set(invalid))))
    return data,{'references_valid':True,'numeric_grounding':True,'semantic_support':'Автоматическая проверка ограничена ссылками и числами; смысловое соответствие требует экспертной оценки.'}

async def analyze(db,company_id,article_id,role='cfo',provider=None):
    company=db.get(Company,company_id);article=db.get(Article,article_id)
    if not company or not article:raise ValueError('Компания или новость не найдена')
    started=time.monotonic();run=AgentRun(id=uuid.uuid4().hex,company_id=company_id,article_id=article_id,role=role,task='Подготовить персональный разбор события: '+article.title,status='running',plan=[])
    db.add(run);db.commit();steps=0
    def tool(name,fn):
        nonlocal steps
        if steps>=settings.agent_max_steps or time.monotonic()-started>settings.agent_timeout:raise ValueError('Достигнут лимит шагов или времени')
        t=time.monotonic();value=fn();steps+=1
        output=value if isinstance(value,dict) else {'items':value}
        db.add(AgentStep(run_id=run.id,tool=name,summary=TOOL_LABELS[name],output=output,duration_ms=int((time.monotonic()-t)*1000)));db.commit();return value
    try:
        p=tool('get_company_profile',lambda:profile(db,company))
        event=tool('get_news_event',lambda:article_dict(article))
        plan=['get_company_profile','get_news_event','get_bank_products']
        if p['relationships']['items']:plan+=['analyze_relationships']
        plan+=['search_related_news','search_bank_analytics','calculate_relevance','get_evidence']
        if readiness()[0] or provider:plan+=['generate_interpretation']
        plan+=['check_claims','save_result'];run.plan=plan;db.commit()
        tool('get_bank_products',lambda:company.products)
        related=tool('analyze_relationships',lambda:p['relationships']) if p['relationships']['items'] else {'items':[]}
        nearby=tool('search_related_news',lambda:[{'id':a.id,'title':a.title} for a in db.scalars(select(Article).where(Article.category==article.category,Article.id!=article.id,Article.private.is_(False) if company.synthetic else True).limit(4))])
        bank=tool('search_bank_analytics',lambda:search_bank(db,article.title,4,company.synthetic,article.url))
        if not bank:
            run.plan=run.plan[:-2]+['broaden_search']+run.plan[-2:];db.commit()
            bank=tool('broaden_search',lambda:search_bank(db,article.category+' '+company.sector,4,company.synthetic))
        relevance=tool('calculate_relevance',lambda:rank(company,article,role,related,bool(bank)))
        evidence=[{'id':'profile','type':'company','title':'Профиль '+company.id,'text':str({k:p[k] for k in ['id','sector','region','products','foreign_trade','countries','revenue']}),'synthetic':company.synthetic}, {'id':'news','type':'news','title':article.title,'text':article.text,'url':article.url,'synthetic':article.synthetic}]
        evidence += [{'id':'bank:'+b['id'],'type':'bank','title':b['title'],'text':b['text'],'page':b['page'],'url':b['source_url'],'extraction':b.get('extraction','pdf-text'),'synthetic':b['synthetic']} for b in bank]
        tool('get_evidence',lambda:{'items':evidence})
        interpretation=rule_interpretation(company,article,relevance);mode='rules';generation_error=None
        validation={'references_valid':True,'numeric_grounding':True,'semantic_support':'Условные формулировки правил; банковские фрагменты приведены отдельно.'}
        if readiness()[0] or provider:
            try:
                t=time.monotonic()
                # Single provider call follows actual retrieval tools; this is not the entire agent.
                generated=await (provider or get_provider()).generate(db,{'task':run.task,'company':p,'event':event,'evidence':evidence,'relevance':relevance,'related_news':nearby})
                interpretation,validation=validate_claims(generated,evidence);mode='test' if provider else 'llm'
                tool('generate_interpretation',lambda:{'provider':'test' if provider else settings.llm_model,'validated':True,'request_duration_ms':int((time.monotonic()-t)*1000)})
            except Exception as exc:
                generation_error=str(exc)[:250];tool('generate_interpretation',lambda:{'validated':False,'error':generation_error})
        uncertainties=interpretation['uncertainties']+p['limitations']
        if not bank:uncertainties.append('Релевантная позиция банка не найдена.')
        else:uncertainties.append('Банковские материалы — архив кейса. Совпадение поиска не подтверждает причинность и актуальность; цитаты нужно проверить на странице оригинала. OCR может содержать ошибки.')
        if generation_error:uncertainties.append('Генерация недоступна: '+generation_error)
        validation['missing_bank']=not bool(bank);validation['evidence_count']=len(evidence);validation['claims_count']=1+sum(len(interpretation[k]) for k in ['risks','opportunities','actions'])
        tool('check_claims',lambda:validation)
        result={'company':{k:p[k] for k in ['id','label','sector','products','synthetic']},'event':event,'relevance':relevance,'interpretation':interpretation,'bank_excerpts':bank,'evidence':evidence,'uncertainties':uncertainties,'validation':validation,'mode':mode,'ai_available':readiness()[0],'generation_error':generation_error}
        run.result=result;run.mode=mode;run.status='complete';run.duration_ms=int((time.monotonic()-started)*1000);db.commit()
        tool('save_result',lambda:{'run_id':run.id,'status':'complete'});return run
    except Exception as exc:
        db.rollback();run=db.get(AgentRun,run.id);run.status='failed';run.error=str(exc)[:300];run.duration_ms=int((time.monotonic()-started)*1000);db.commit();raise

def run_dict(db,run):
    steps=db.scalars(select(AgentStep).where(AgentStep.run_id==run.id).order_by(AgentStep.id)).all()
    return {'id':run.id,'company_id':run.company_id,'article_id':run.article_id,'status':run.status,'role':run.role,'mode':run.mode,'task':run.task,'plan':run.plan,'result':run.result,'duration_ms':run.duration_ms,'started_at':run.started_at.isoformat(),'error':run.error,'steps':[{'tool':s.tool,'summary':s.summary,'output':s.output,'duration_ms':s.duration_ms,'created_at':s.created_at.isoformat()} for s in steps]}
