"""Explainable ranking points, never a probability or estimated financial loss."""
import re
from sqlalchemy import select
from .db import Company

CATEGORIES={
 'Ставки и финансы':('ставк','кредит','инфляц','депозит','облигац','денежно-кредит'),
 'ВЭД и валюта':('валют','экспорт','импорт','санкц','тамож','доллар','юан'),
 'Отрасли и рынки':('металл','сталь','золот','нефт','сырь','промышлен','производств','потреблен'),
 'Регулирование':('налог','закон','регулирован','ндс','отчетност'),
 'Логистика':('логист','перевоз','транспорт','порт','поставк')}
STOP={'компани','деятельност','производств','проч','оптов','торговл','издел','товар','различ','основн','прочие','услуг','друг'}
def tokens(text):return {s[:7] for s in re.findall(r'[а-яёa-z]{4,}',text.lower()) if s[:7] not in STOP}
def classify(text):
    text=text.lower();scores={k:sum(text.count(t) for t in terms) for k,terms in CATEGORIES.items()}
    return max(scores,key=scores.get) if max(scores.values(),default=0)>0 else 'Другое'

def rank(company,article,role='cfo',related=None,bank_available=False):
    text=(article.title+' '+article.text).lower();reasons=[]
    def add(key,points,label):reasons.append({'feature':key,'points':points,'label':label})
    add('base',8,'Базовая оценка события')
    shared=tokens(company.sector)&tokens(text)
    if shared:add('sector',min(28,14+7*len(shared)),'Совпадение отраслевых признаков: '+', '.join(sorted(shared)))
    if company.region and any(t in text for t in tokens(company.region)):add('region',14,'Событие упоминает регион регистрации')
    rate=any(t in text for t in ['ставк','кредит','денежно-кредит'])
    if rate and company.products.get('Кредиты'):add('loans',25,'Есть кредитный продукт: проверить чувствительность условий финансирования')
    if rate and company.products.get('Депозиты'):add('deposits',18,'Есть депозитный продукт: проверить условия новых размещений')
    if rate and company.products.get('Лизинг'):add('leasing',10,'Есть лизинг: проверить стоимость новых договоров')
    if company.products.get('Факторинг') and any(t in text for t in ['ставк','платеж','оборотн','поставк']):add('factoring',9,'Есть факторинг: релевантны условия оборотного финансирования')
    if company.foreign_trade and any(t in text for t in ['валют','импорт','экспорт','санкц','тамож']):add('foreign_trade',26,'Есть данные ФТС: событие может быть связано с внешней торговлей')
    countries=tokens(company.countries)
    if countries and countries&tokens(text):add('countries',10,'Упомянута страна из профиля ФТС')
    if company.group_id and any(t in text for t in ['консолид','групп','холдинг']):add('group',5,'Компания входит в группу: проверить общий контекст')
    for rel in (related or {}).get('items',[]):
        if tokens(rel.get('sector',''))&tokens(text):add('counterparty',8,'Есть связь с компанией из затронутой отрасли; причинность не установлена');break
    if company.revenue is not None:add('scale_known',2,'Выручка присутствует в профиле; единица источника не уточнена')
    if role in ('cfo','treasury') and article.category in ('Ставки и финансы','ВЭД и валюта'):add('role',8,'Приоритет для финансовой роли')
    if role=='accountant' and article.category=='Регулирование':add('role',12,'Приоритет для главного бухгалтера')
    if role=='ceo' and article.category=='Отрасли и рынки':add('role',8,'Приоритет для генерального директора')
    if bank_available:add('bank',5,'В индексе есть тематический материал банка; требуется проверка фрагмента')
    return {'score':min(100,sum(r['points'] for r in reasons)),'reasons':reasons,'label':'Эвристический балл релевантности, не вероятность','explanation':'; '.join(r['label'] for r in reasons if r['feature'] not in ('base','scale_known')) or 'Прямых совпадений с известными признаками компании не найдено.'}
