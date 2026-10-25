import asyncio,json
import pytest
from sqlalchemy import select
from app.grounding import validate_claims,model_context
from app.schemas import GeneratedInsight
from app.db import Article,AgentStep
from app.agent import analyze
from app.news import add_article


def response(text='Компания имеет кредитный продукт',quote='Кредиты: доступны',eid='profile'):
    return GeneratedInsight(summary={'text':text,'evidence_ids':[eid],'evidence_quotes':[{'evidence_id':eid,'quote':quote}]},risks=[],opportunities=[],actions=[],bank_view=[],uncertainties=['Остаток задолженности неизвестен'])


def test_exact_quote_required_and_checked():
    ev=[{'id':'profile','type':'company','text':'Кредиты: доступны. Остаток неизвестен.'}]
    data,checks=validate_claims(response(),ev,require_quotes=True)
    assert checks['verified_quote_count']==1
    with pytest.raises(ValueError,match='Цитата'):validate_claims(response(quote='Свободная ликвидность подтверждена'),ev,require_quotes=True)
    missing=response().model_dump();missing['summary']['evidence_quotes']=[]
    with pytest.raises(ValueError,match='цитата'):validate_claims(missing,ev,require_quotes=True)


def test_number_must_be_a_value_not_substring():
    ev=[{'id':'profile','text':'Сумма 140 рублей. Кредиты: доступны.'}]
    with pytest.raises(ValueError,match='Число'):validate_claims(response(text='Сумма 14 рублей'),ev)
    with pytest.raises(ValueError,match='Число'):validate_claims(response(text='Сумма -140 рублей'),ev)


def test_bank_view_cannot_borrow_nonbank_sources():
    data=response().model_dump();data['bank_view']=[data['summary']]
    with pytest.raises(ValueError,match='банка'):validate_claims(data,[{'id':'profile','type':'company','text':'Кредиты: доступны.'}],require_quotes=True)


def test_large_context_is_bounded_without_secrets():
    c={'id':'C','sector':'Производство','raw':{'LLM_API_KEY':'do-not-send'},'products':{'Кредиты':True}}
    ev=[{'id':'news','type':'news','text':'Новость. '*10000}]+[{'id':f'bank:{i}','type':'bank','text':'Банковский материал. '*2000} for i in range(7)]
    context=model_context(company=c,evidence=ev,question='Вопрос '+('текст '*400))
    packed=json.dumps(context,ensure_ascii=False)
    assert len(packed.encode())<=39000 and 'do-not-send' not in packed
    assert len(context['evidence'])==8


class RepairProvider:
    def __init__(self):self.calls=[]
    async def generate(self,db,context):
        self.calls.append(context)
        if not context.get('review'):
            return GeneratedInsight(summary={'text':'Необоснованная сумма 999999','evidence_ids':['imaginary']},risks=[],opportunities=[],actions=[],uncertainties=[])
        return GeneratedInsight(summary={'text':'Проверить условия кредита; задолженность неизвестна','evidence_ids':['profile']},risks=[],opportunities=[],actions=[],uncertainties=['Неполные данные'])


def test_agent_repairs_invalid_draft_with_bounded_second_call(fixture_data):
    db=fixture_data;a,_=add_article(db,'Новая ставка для проверки','Ключевая ставка влияет на условия нового финансирования. Это учебная новость для проверки повторного анализа.')
    provider=RepairProvider();run=asyncio.run(analyze(db,'DEMO_U_101',a.id,provider=provider))
    assert run.mode=='test' and len(provider.calls)==2
    assert provider.calls[1]['review'] and provider.calls[1]['validation_errors']
    steps=db.scalars(select(AgentStep).where(AgentStep.run_id==run.id)).all()
    review=[s for s in steps if s.tool=='review_interpretation'][0]
    assert review.output['draft_required_correction'] and review.output['validated']
    assert all(s.tool!='generation_failure' for s in steps)
