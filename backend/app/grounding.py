"""Structural source checks. Exact quotes are auditable anchors, not semantic proof."""
import re
from decimal import Decimal,InvalidOperation


def normalize(text):
    return ' '.join(text.lower().replace('ё','е').split())


def numeric_values(text):
    values=set()
    for match in re.finditer(r'(?<![\w\d])[-+−]?\d+(?:[.,]\d+)?(?!\d)',text):
        try:values.add(Decimal(match.group().replace(',','.').replace('−','-')))
        except InvalidOperation:pass
    return values


def validate_claims(generated,evidence,require_quotes=False):
    from .schemas import GeneratedInsight
    parsed=generated if isinstance(generated,GeneratedInsight) else GeneratedInsight.model_validate(generated)
    data=parsed.model_dump();available={e['id']:e['text'] for e in evidence};types={e['id']:e.get('type') for e in evidence};invalid=[];anchors=0
    claims=[data['summary']]+data['risks']+data['opportunities']+data['actions']+data['bank_view']
    for item in claims:
        ids=item['evidence_ids']
        if not ids or not set(ids)<=set(available):invalid.append('Неизвестный источник')
        corpus=' '.join(available.get(i,'') for i in ids)
        if not numeric_values(item['text'])<=numeric_values(corpus):invalid.append('Число отсутствует в указанных доказательствах')
        quotes=item.get('evidence_quotes',[])
        if require_quotes and not quotes:invalid.append('Для вывода отсутствует проверяемая цитата')
        for quote in quotes:
            eid=quote['evidence_id']
            if eid not in ids or eid not in available or normalize(quote['quote']) not in normalize(available.get(eid,'')):
                invalid.append('Цитата не найдена в указанном источнике')
            else:anchors+=1
    for item in data['bank_view']:
        if not any(types.get(i)=='bank' for i in item['evidence_ids']):invalid.append('Позиция банка не ссылается на банковский материал')
        if require_quotes and not any(types.get(q['evidence_id'])=='bank' for q in item.get('evidence_quotes',[])):
            invalid.append('Для позиции банка отсутствует цитата банка')
    if invalid:raise ValueError('; '.join(sorted(set(invalid))))
    return data,{'references_valid':True,'numeric_grounding':True,'verified_quote_count':anchors,'semantic_support':'Проверены источники, числовые значения и точные цитаты. Наличие цитаты не доказывает смысловую поддержку вывода; требуется экспертная оценка.'}


def model_context(*,company=None,event=None,evidence,role='cfo',task='',question=None,previous=None,candidate=None,review=False,errors=None):
    """Bound context without duplicating full profile/event/run payloads or exposing secrets."""
    ev=[]
    for item in evidence[:16]:
        cap=5200 if item.get('type')=='news' else 1800
        ev.append({k:v for k,v in item.items() if k in ('id','type','title','page','url','synthetic','extraction','published_at','document_date','date_status') } | {'text':item.get('text','')[:cap]})
    result={'task':task[:600],'role':role,'evidence':ev,'review':review}
    if company:result['company']={k:company.get(k) for k in ('id','sector','region','products','foreign_trade','countries','revenue','revenue_unit','group_id','business_features','limitations')}
    if event:result['event']={k:event.get(k) for k in ('id','title','category','published_at','source','synthetic')}
    if question:result['question']=question[:2000]
    if previous:result['previous_summary']=previous.get('summary',{})
    if candidate:result['candidate']=candidate.model_dump() if hasattr(candidate,'model_dump') else candidate
    if errors:result['validation_errors']=errors[:1000]
    import json
    # A reviewed structured response may be long; reduce source text, never truncate JSON.
    while len(json.dumps(result,ensure_ascii=False,default=str).encode())>35000:
        longest=max(ev,key=lambda e:len(e['text']),default=None)
        if not longest or len(longest['text'])<350:raise ValueError('Не удалось уложить контекст в лимит')
        longest['text']=longest['text'][:max(300,len(longest['text'])//2)]
    return result
