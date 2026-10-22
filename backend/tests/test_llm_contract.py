"""Contract and budget checks with an HTTP stub, never a real LLM quality test."""
import asyncio,json
import httpx,pytest
from sqlalchemy import select,func
from app import llm
from app.db import LLMUsage
from app.config import settings

@pytest.fixture
def production_config(monkeypatch):
    values={'llm_mode':'production','llm_api_key':'test-secret','llm_base_url':'https://organizer.invalid/v1','llm_model':'GLM-5.3-Flash','llm_approved_name':'GLM-5.3-Flash','llm_protocol':'openai-chat','llm_input_rub_per_million':100.0,'llm_output_rub_per_million':100.0,'llm_daily_budget_rub':500.0}
    for k,v in values.items():monkeypatch.setattr(settings,k,v)
    return values

def stub(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

def test_contract_and_real_usage_accounting(db,production_config,monkeypatch):
    def handler(request):
        data=json.loads(request.content);assert data['model']=='GLM-5.3-Flash'
        assert request.headers['authorization']=='Bearer test-secret'
        assert 'недоверенные' in data['messages'][0]['content']
        result={'summary':{'text':'Условный разбор','evidence_ids':['news']},'risks':[],'opportunities':[],'actions':[],'uncertainties':['Неполные данные']}
        return httpx.Response(200,json={'model':'GLM-5.3-Flash','usage':{'prompt_tokens':100,'completion_tokens':50},'choices':[{'message':{'content':json.dumps(result)}}]})
    stub(monkeypatch,handler)
    response=asyncio.run(llm.OrganizerProvider().generate(db,{'evidence':[{'id':'news','text':'Событие'}]}))
    assert response.summary.text=='Условный разбор'
    usage=db.scalar(select(LLMUsage));assert usage.status=='charged' and usage.input_tokens==100 and usage.cost_rub==pytest.approx(.015)

def test_budget_denies_request_before_network(db,production_config,monkeypatch):
    monkeypatch.setattr(settings,'llm_daily_budget_rub',.0001)
    stub(monkeypatch,lambda _:pytest.fail('Network must not be called after budget denial'))
    with pytest.raises(llm.LLMUnavailable,match='бюджет'):asyncio.run(llm.OrganizerProvider().generate(db,{}))
    assert db.scalar(select(func.count()).select_from(LLMUsage))==0

@pytest.mark.parametrize('kind',['bad_model','invalid_json','upstream_error'])
def test_failed_request_retains_budget_reservation(db,production_config,monkeypatch,kind):
    def handler(request):
        if kind=='upstream_error':return httpx.Response(503,json={})
        return httpx.Response(200,json={'model':'unauthorized' if kind=='bad_model' else 'GLM-5.3-Flash','choices':[{'message':{'content':'invalid'}}]})
    stub(monkeypatch,handler)
    with pytest.raises(llm.LLMUnavailable):asyncio.run(llm.OrganizerProvider().generate(db,{}))
    usage=db.scalar(select(LLMUsage));assert usage.status=='failed_reserved' and usage.cost_rub>0


def test_missing_prices_and_unknown_protocol_fail_closed(production_config,monkeypatch):
    monkeypatch.setattr(settings,'llm_input_rub_per_million',0)
    assert not llm.readiness()[0]
    monkeypatch.setattr(settings,'llm_input_rub_per_million',100)
    monkeypatch.setattr(settings,'llm_protocol','guessed')
    assert not llm.readiness()[0]
