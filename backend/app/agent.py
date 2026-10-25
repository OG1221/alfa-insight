import asyncio,time,uuid,re
from sqlalchemy import select
from .db import Company,Article,AgentRun,AgentStep
from .profiles import profile,relations
from .ranking import rank,is_rate_event
from .search import search_bank
from .news import article_dict
from .llm import get_provider,readiness
from .config import settings
from .investigation import related_events,assess_evidence,build_evidence,merge_items,reference_stats

TOOL_LABELS={'get_company_profile':'Загружен профиль компании','get_bank_products':'Проверены банковские продукты','get_news_event':'Получено новостное событие','analyze_relationships':'Проверены платежные и групповые связи','search_related_news':'Найдены связанные события','search_bank_analytics':'Выполнен поиск по документам банка','broaden_search':'Поиск расширен из-за нехватки данных','calculate_relevance':'Рассчитана релевантность','get_evidence':'Собраны исходные доказательства','generation_failure':'Зафиксирована ошибка генерации или проверки LLM','review_interpretation':'Проведена повторная проверка ответа по источникам','generate_interpretation':'Запрошена разрешённая LLM','check_claims':'Проверены ссылки и полнота результата','save_result':'Результат сохранён'}
TOOL_LABELS.update(assess_evidence='Оценены полнота, противоречия и применимость источников', targeted_search='Повторный поиск по выявленным пробелам', reassess_evidence='Проверены доказательства после повторного поиска')

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
    return {'bank_view':[],'summary':claim(relevance['explanation']), 'risks':risks,'opportunities':opportunities,'actions':actions,'uncertainties':['Это условные направления проверки по правилам, а не генерация AI.','Денежное влияние, задолженность, остатки и рыночная доля не рассчитываются без исходных данных.']}

from .grounding import validate_claims,model_context

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
        plan+=['search_related_news','search_bank_analytics','assess_evidence','calculate_relevance','get_evidence']
        if readiness()[0] or provider:plan+=['generate_interpretation','review_interpretation']
        plan+=['check_claims','save_result'];run.plan=plan;db.commit()
        tool('get_bank_products',lambda:company.products)
        related=tool('analyze_relationships',lambda:p['relationships']) if p['relationships']['items'] else {'items':[]}
        nearby=tool('search_related_news',lambda:related_events(db,article,company.synthetic))
        bank=tool('search_bank_analytics',lambda:search_bank(db,article.title,4,company.synthetic,article.url))
        assessment=tool('assess_evidence',lambda:assess_evidence(p,article,bank))
        if assessment['needs_search']:
            expanded=list(run.plan);expanded.insert(expanded.index('assess_evidence')+1,'broaden_search');run.plan=expanded;db.commit()
            bank=merge_items(bank,tool('broaden_search',lambda:search_bank(db,article.category+' '+company.sector+' '+company.countries,4,company.synthetic)))
            expanded=list(run.plan);expanded.insert(expanded.index('calculate_relevance'),'reassess_evidence');run.plan=expanded;db.commit()
            assessment=tool('reassess_evidence',lambda:assess_evidence(p,article,bank))
        relevance=tool('calculate_relevance',lambda:rank(company,article,role,related,bool(bank)))
        evidence=build_evidence(p,article,bank,nearby)
        tool('get_evidence',lambda:{'items':evidence})
        interpretation=rule_interpretation(company,article,relevance);mode='rules';generation_error=None
        validation={'references_valid':True,'numeric_grounding':True,'semantic_support':'Условные формулировки правил; банковские фрагменты приведены отдельно.'}
        if readiness()[0] or provider:
            try:
                t=time.monotonic()
                # Draft and bounded review follow the actual retrieval tools.
                selected_provider=provider or get_provider()
                context=model_context(task=run.task,company=p,event=event,evidence=evidence,role=role)
                context['assessment']=assessment
                generated=await asyncio.wait_for(selected_provider.generate(db,context),timeout=max(.1,settings.agent_timeout-(time.monotonic()-started)))
                tool('generate_interpretation',lambda:{'provider':'test' if provider else settings.llm_model,'request_duration_ms':int((time.monotonic()-t)*1000)})
                draft_error=None
                try:
                    validate_claims(generated,context['evidence'],require_quotes=not bool(provider))
                except (ValueError,TypeError) as exc:
                    draft_error=str(exc)[:1000]
                queries=getattr(generated,'retrieval_queries',[])[:2]
                gaps=getattr(generated,'evidence_gaps',[])[:6]
                if draft_error or queries or gaps:
                    if not queries:queries=[article.category+' '+company.sector]
                    # Model output can request text searches only. Source scope and limits
                    # are enforced here; it cannot choose a URL, SQL or arbitrary tool.
                    def retrieve():
                        nonlocal bank,nearby
                        used=[]
                        for query in queries:
                            query=' '.join(str(query).split())[:240]
                            if not query:continue
                            bank=merge_items(search_bank(db,query,4,company.synthetic),bank)
                            nearby=merge_items(related_events(db,article,company.synthetic,query),nearby,3)
                            used.append(query)
                        return {'queries':used,'gaps':gaps,'validation_errors':draft_error,'bank_ids':[b['id'] for b in bank]}
                    expanded=list(run.plan);idx=expanded.index('review_interpretation');expanded[idx:idx]=['targeted_search','reassess_evidence'];run.plan=expanded;db.commit()
                    tool('targeted_search',retrieve)
                    evidence=build_evidence(p,article,bank,nearby)
                    assessment=tool('reassess_evidence',lambda:assess_evidence(p,article,bank))
                # Review independently against evidence, or correct a rejected draft. Budget
                # reservation applies to both actual calls; no unbounded repair loop.
                t=time.monotonic()
                context=model_context(task=run.task,company=p,event=event,evidence=evidence,role=role,candidate=generated,review=True,errors=draft_error)
                context['assessment']=assessment
                reviewed=await asyncio.wait_for(selected_provider.generate(db,context),timeout=max(.1,settings.agent_timeout-(time.monotonic()-started)))
                interpretation,validation=validate_claims(reviewed,context['evidence'],require_quotes=not bool(provider));mode='test' if provider else 'llm'
                interpretation['uncertainties']+=getattr(reviewed,'evidence_gaps',[])[:6]
                tool('review_interpretation',lambda:{'validated':True,'draft_required_correction':bool(draft_error),'request_duration_ms':int((time.monotonic()-t)*1000)})
            except Exception as exc:
                generation_error=str(exc)[:250];tool('generation_failure',lambda:{'validated':False,'error':generation_error})
        uncertainties=interpretation['uncertainties']+p['limitations']+assessment['gaps']
        if not bank:uncertainties.append('Релевантная позиция банка не найдена.')
        else:uncertainties.append('Банковские материалы — архив кейса. Совпадение поиска не подтверждает причинность и актуальность; цитаты нужно проверить на странице оригинала. OCR может содержать ошибки.')
        if generation_error:uncertainties.append('Генерация недоступна: '+generation_error)
        validation['missing_bank']=not bool(bank);validation['evidence_count']=len(evidence);validation.update(reference_stats(interpretation,evidence))
        tool('check_claims',lambda:validation)
        result={'company':{k:p[k] for k in ['id','label','sector','products','synthetic']},'event':event,'relevance':relevance,'interpretation':interpretation,'bank_excerpts':bank,'evidence':evidence,'assessment':assessment,'uncertainties':list(dict.fromkeys(uncertainties)),'validation':validation,'mode':mode,'ai_available':readiness()[0],'generation_error':generation_error}
        run.result=result;run.mode=mode;run.status='complete';run.duration_ms=int((time.monotonic()-started)*1000);db.commit()
        tool('save_result',lambda:{'run_id':run.id,'status':'complete'});return run
    except (Exception,asyncio.CancelledError) as exc:
        db.rollback();run=db.get(AgentRun,run.id);run.status='failed';run.error=str(exc)[:300];run.duration_ms=int((time.monotonic()-started)*1000);db.commit();raise

def run_dict(db,run):
    steps=db.scalars(select(AgentStep).where(AgentStep.run_id==run.id).order_by(AgentStep.id)).all()
    return {'id':run.id,'company_id':run.company_id,'article_id':run.article_id,'status':run.status,'role':run.role,'mode':run.mode,'task':run.task,'plan':run.plan,'result':run.result,'duration_ms':run.duration_ms,'started_at':run.started_at.isoformat(),'error':run.error,'steps':[{'tool':s.tool,'summary':s.summary,'output':s.output,'duration_ms':s.duration_ms,'created_at':s.created_at.isoformat()} for s in steps]}
