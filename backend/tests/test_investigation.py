import asyncio
from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from app.db import Company,Article,AgentStep
from app.agent import analyze
from app.news import add_article
from app.investigation import reference_stats,related_events,assess_evidence
from app.schemas import GeneratedInsight


def test_related_events_excludes_future_and_private(fixture_data):
    db=fixture_data;now=datetime.now(timezone.utc)
    event,_=add_article(db,'Импорт стали и логистика сегодня','Учебная новость об импорте стали и логистике поставок.',published_at=now)
    old,_=add_article(db,'Импорт стали вчера','Вчера обсуждали импорт стали и логистику поставок.',published_at=now-timedelta(days=1))
    future,_=add_article(db,'Импорт стали завтра','Завтра обсуждают импорт стали и логистику поставок.',published_at=now+timedelta(days=1))
    private,_=add_article(db,'Импорт стали закрытый','Закрытый материал про импорт стали и логистику поставок.',published_at=now-timedelta(hours=1),private=True)
    found={x['id'] for x in related_events(db,event,True)}
    assert old.id in found and future.id not in found and private.id not in found


def test_reference_coverage_is_measured():
    data={'summary':{'text':'a','evidence_ids':['news']},'risks':[{'text':'b','evidence_ids':['missing']}], 'actions':[], 'opportunities':[], 'bank_view':[]}
    stats=reference_stats(data,[{'id':'news'}])
    assert stats['reference_coverage']==.5 and stats['claims_with_checked_references']==1


def test_weak_bank_match_requests_search():
    from types import SimpleNamespace
    result=assess_evidence({'data_quality_conflicts':[{'sector':'conflict'}]},SimpleNamespace(title='Импорт стали',text='Изменение условий перевозки металла'),[{'text':'Ключевая ставка сохранена'}])
    assert result['needs_search'] and result['profile_conflicts']==1


class SearchingProvider:
    def __init__(self):self.contexts=[]
    async def generate(self,db,context):
        self.contexts.append(context)
        return GeneratedInsight(summary={'text':'Проверить условия импортных контрактов','evidence_ids':['profile','news']},risks=[],opportunities=[],actions=[],uncertainties=[],retrieval_queries=[] if context['review'] else ['импорт стали'],evidence_gaps=[] if context['review'] else ['Условия контрактов неизвестны'])


def test_agent_uses_context_and_executes_requested_search(fixture_data):
    db=fixture_data
    previous,_=add_article(db,'Импорт стали вчера для анализа','Импорт стали и сроки поставок: учебный предыдущий материал.',published_at=datetime.now(timezone.utc)-timedelta(days=1))
    event,_=add_article(db,'Импорт стали сегодня для анализа','Импорт стали и сроки поставок: новый учебный материал.')
    provider=SearchingProvider();run=asyncio.run(analyze(db,'DEMO_U_101',event.id,provider=provider))
    assert run.mode=='test' and len(provider.contexts)==2
    ids={x['id'] for x in provider.contexts[0]['evidence']}
    assert 'relationships' in ids and 'related:'+previous.id in ids
    assert 'targeted_search' in run.plan and 'reassess_evidence' in run.plan
    assert run.result['validation']['reference_coverage']==1
    names=[s.tool for s in db.scalars(select(AgentStep).where(AgentStep.run_id==run.id))]
    assert 'targeted_search' in names


def test_private_runs_not_counted_in_demo_metrics(fixture_data):
    from fastapi.testclient import TestClient
    from app.main import app,get_db,limits
    event,_=add_article(fixture_data,'Закрытая новость для метрик','Закрытая новость должна отсутствовать в метриках демо.',private=True)
    asyncio.run(analyze(fixture_data,'DEMO_U_101',event.id))
    app.dependency_overrides[get_db]=lambda:fixture_data;limits.clear()
    try:
        result=TestClient(app).get('/api/metrics').json()
        assert result['runs']==0 and result['reference_coverage'] is None
    finally:app.dependency_overrides.clear()


def test_followup_retrieves_and_remembers_dialogue(fixture_data,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    db=fixture_data
    event,_=add_article(db,'Новая логистика импортных поставок','Учебная новость о логистике импортных поставок и сроках контрактов.')
    run=asyncio.run(analyze(db,'DEMO_U_101',event.id))
    contexts=[]
    class FollowupProvider:
        async def generate(self,session,context):
            contexts.append(context)
            source=next(e for e in context['evidence'] if e['id']=='news')
            return GeneratedInsight(summary={'text':'Условия контрактов требуют проверки','evidence_ids':['news'],'evidence_quotes':[{'evidence_id':'news','quote':source['text'][:40]}]},risks=[],opportunities=[],actions=[],uncertainties=[])
    monkeypatch.setattr(main,'readiness',lambda:(True,'configured'))
    monkeypatch.setattr(main,'get_provider',lambda:FollowupProvider())
    main.app.dependency_overrides[main.get_db]=lambda:db;main.limits.clear()
    try:
        client=TestClient(main.app)
        one=client.post('/api/analyses/'+run.id+'/questions',json={'question':'Как проверить сроки поставок?'})
        assert one.status_code==200 and one.json()['evidence']
        two=client.post('/api/analyses/'+run.id+'/questions',json={'question':'Какие документы для этого нужны?'})
        assert two.status_code==200
        assert contexts[1]['conversation'][0]['question']=='Как проверить сроки поставок?'
        assert db.scalars(select(AgentStep).where(AgentStep.run_id==run.id,AgentStep.tool=='followup_question')).all()
    finally:main.app.dependency_overrides.clear()


def test_admin_upload_works_without_reopening_a_locked_tempfile(db):
    from fastapi.testclient import TestClient
    from app import main
    from app.config import settings
    main.app.dependency_overrides[main.get_db]=lambda:db;main.limits.clear()
    try:
        data=b'SYNTHETIC_U;MAINOKVED_NAME;REVENUE_COMPANY\nUPLOADED;Test sector;100\n'
        response=TestClient(main.app).post('/api/admin/import',headers={'Authorization':'Bearer '+settings.admin_token},files={'file':('company.csv',data,'text/csv')})
        assert response.status_code==200,response.text
        assert response.json()['accepted']==1 and db.get(Company,'UPLOADED') is not None
    finally:main.app.dependency_overrides.clear()
