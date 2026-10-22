from sqlalchemy import select, func, or_
from .db import Company, Payment, PersonLink

def company_dict(c):
    return {'id':c.id,'label':f'Компания {c.id}','sector':c.sector,'okved':c.okved,'region':c.region,'city':c.city,'revenue':c.revenue,'revenue_unit':'ед. источника — единица в кейсе не уточнена','group_id':c.group_id,'products':c.products,'foreign_trade':c.foreign_trade,'countries':c.countries,'synthetic':c.synthetic}

def relations(db,c,limit=12):
    payments=db.scalars(select(Payment).where(or_(Payment.payer==c.id,Payment.beneficiary==c.id),Payment.payer!=Payment.beneficiary).order_by(Payment.amount.desc()).limit(limit)).all()
    related={};total=db.scalar(select(func.count()).select_from(Payment).where(or_(Payment.payer==c.id,Payment.beneficiary==c.id),Payment.payer!=Payment.beneficiary)) or 0
    for p in payments:
        other=p.beneficiary if p.payer==c.id else p.payer
        related.setdefault(other,{'id':other,'kinds':[],'amount':0,'count':0})
        related[other]['kinds'].append('исходящие платежи' if p.payer==c.id else 'входящие платежи');related[other]['amount']+=p.amount;related[other]['count']+=p.count
    if c.group_id:
        for other in db.scalars(select(Company.id).where(Company.group_id==c.group_id,Company.id!=c.id).limit(limit)):
            related.setdefault(other,{'id':other,'kinds':[],'amount':0,'count':0})['kinds'].append('общая группа')
    persons=select(PersonLink.person_id).where(PersonLink.company_id==c.id)
    for other in db.scalars(select(PersonLink.company_id).where(PersonLink.person_id.in_(persons),PersonLink.company_id!=c.id).distinct().limit(limit)):
        related.setdefault(other,{'id':other,'kinds':[],'amount':0,'count':0})['kinds'].append('общее физическое лицо')
    for item in related.values():
        co=db.get(Company,item['id']);item['sector']=co.sector if co else 'Нет профиля в датасете';item['region']=co.region if co else ''
    return {'items':list(related.values())[:limit],'payment_edges':total,'truncated':total>limit,'note':'Платежи агрегированы. Период и денежная единица не указаны. Связь не доказывает зависимость или владение.'}

def profile(db,c):
    result=company_dict(c);result['raw']=c.raw;result['relationships']=relations(db,c)
    result['limitations']=['Обезличенные данные: название компании неизвестно.','Наличие продукта не определяет задолженность или остаток средств.','Рыночная доля, структура издержек и валютная позиция неизвестны.','Единица выручки и период платежей в спецификации не уточнены; денежные оценки влияния не рассчитываются.']
    return result
