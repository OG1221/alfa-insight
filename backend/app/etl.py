"""Idempotent, streaming CSV import. No inferred company names or monetary units."""
import csv, hashlib, io, math, json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from .pdf_extract import extract_pages
from .db import Company, PersonLink, Payment, BankDocument, Chunk, ImportBatch

PRODUCTS={'CL_PRODUCT_RKO_MARK':'РКО','CL_PRODUCT_GAR_MARK':'Гарантии','CL_PRODUCT_LOA_MARK':'Кредиты','CL_PRODUCT_LEA_MARK':'Лизинг','CL_PRODUCT_DEP_MARK':'Депозиты','CL_PRODUCT_ZPP_MARK':'Зарплатный проект','FACTORING_MARK':'Факторинг'}
def hash_id(value): return hashlib.sha256(value.encode()).hexdigest()
def number(value, default=None):
    try:
        n=float(str(value).replace(' ','').replace(',','.'))
        return n if math.isfinite(n) else default
    except (ValueError,TypeError): return default
def flag(value): return str(value).strip().lower() in {'1','1.0','true','да','y','yes'}
def cleaned(value):
    s=str(value or '').strip()
    return '' if s.lower() in {'nan','none','null','na'} else s

def read_csv(path):
    data=Path(path).read_bytes()
    try: text=data.decode('utf-8-sig'); encoding='utf-8-sig'
    except UnicodeDecodeError: text=data.decode('cp1251'); encoding='cp1251'
    delimiter=csv.Sniffer().sniff(text[:8192],delimiters=';,\t').delimiter
    return csv.DictReader(io.StringIO(text),delimiter=delimiter),encoding,delimiter,hashlib.sha256(data).hexdigest()

def upsert(db,model,rows):
    if not rows:return
    stmt=insert(model).values(rows)
    db.execute(stmt.on_conflict_do_update(index_elements=['id'],set_={k:getattr(stmt.excluded,k) for k in rows[0] if k!='id'}))

def import_csv(db,path,synthetic=False):
    reader,encoding,delimiter,digest=read_csv(path)
    old=db.get(ImportBatch,digest)
    if old:return {**old.report,'already_imported':True}
    fields=set(reader.fieldnames or [])
    if 'REVENUE_COMPANY' in fields: kind='companies';required={'SYNTHETIC_U','MAINOKVED_NAME','REVENUE_COMPANY'};model=Company
    elif 'PAY_AMT' in fields:kind='payments';required={'PAYER','BENEFICIARY','PAY_AMT','PAY_CNT'};model=Payment
    else:kind='person_links';required={'SYNTHETIC_F','SYNTHETIC_U'};model=PersonLink
    if not required <= fields:raise ValueError(f'Нет обязательных колонок: {required-fields}')
    report={'kind':kind,'rows':0,'accepted':0,'rejected':0,'duplicates':0,'missing_values':0,'unknown_company_links':0,'invalid_flags':0,'encoding':encoding,'delimiter':delimiter,'synthetic':synthetic,'sha256':digest}
    known=set(db.scalars(select(Company.id))) if kind!='companies' else set()
    seen=set();batch=[]
    for row in reader:
        report['rows']+=1
        r={k:cleaned(v) for k,v in row.items() if k};report['missing_values']+=sum(v=='' for v in r.values())
        if kind=='companies':
            ident=r.get('SYNTHETIC_U','')
            if not ident:report['rejected']+=1;continue
            if synthetic:ident='DEMO_'+ident if not ident.startswith('DEMO_') else ident
            products={label:flag(r.get(key)) for key,label in PRODUCTS.items()}
            report['invalid_flags']+=sum(r.get(k,'') not in ('','0','0.0','1','1.0') for k in PRODUCTS)
            value={'id':ident,'sector':r.get('MAINOKVED_NAME') or 'Не указан','okved':r.get('MAINOKVED_CODE',''),'city':r.get('CITY',''),'region':r.get('REGION',''),'revenue':number(r.get('REVENUE_COMPANY')),'group_id':r.get('GROUP_ID') or None,'products':products,'foreign_trade':flag(r.get('FTS_FLAG')),'countries':r.get('FTS_COUNTRY_NAME',''),'raw':r,'synthetic':synthetic}
        elif kind=='payments':
            payer=r.get('PAYER','');beneficiary=r.get('BENEFICIARY','');amount=number(r.get('PAY_AMT'));count=number(r.get('PAY_CNT'))
            if synthetic:payer='DEMO_'+payer if not payer.startswith('DEMO_') else payer;beneficiary='DEMO_'+beneficiary if not beneficiary.startswith('DEMO_') else beneficiary
            if not payer or not beneficiary or amount is None or count is None or amount<0 or count<0 or int(count)!=count:report['rejected']+=1;continue
            ident=hash_id(payer+'|'+beneficiary)
            value={'id':ident,'payer':payer,'beneficiary':beneficiary,'amount':amount,'count':int(count)}
            report['unknown_company_links']+=int(payer not in known or beneficiary not in known)
        else:
            co=r.get('SYNTHETIC_U','');person=r.get('SYNTHETIC_F','')
            if synthetic:co='DEMO_'+co if not co.startswith('DEMO_') else co;person='DEMO_'+person
            if not co or not person or co not in known:report['rejected']+=1;continue
            ident=hash_id(person+'|'+co)
            value={'id':ident,'company_id':co,'person_id':person,'city':r.get('CITY_NAME',''),'region':r.get('RC_NAME','')}
        if ident in seen:report['duplicates']+=1;continue
        seen.add(ident);batch.append(value);report['accepted']+=1
        if len(batch)>=700:upsert(db,model,batch);batch=[]
    upsert(db,model,batch)
    db.add(ImportBatch(sha256=digest,name=Path(path).name,report=report));db.commit()
    return report

def import_pdf(db,path,source_url=None,synthetic=False):
    path=Path(path);digest=hashlib.sha256(path.read_bytes()).hexdigest();ident=digest[:24]
    old=db.scalar(select(BankDocument).where(BankDocument.sha256==digest))
    if old:return {'id':old.id,'already_imported':True,'pages':old.pages}
    pages,extraction=extract_pages(path)
    title=path.stem.replace('_',' ')
    doc=BankDocument(id=ident,title=title,source_url=source_url,sha256=digest,pages=len(pages),extraction=extraction,synthetic=synthetic)
    db.add(doc);db.flush();count=0
    for page,text in enumerate(pages,1):
        text=' '.join(text.replace('\x00','').split())
        for start in range(0,len(text),1100):
            fragment=text[max(0,start-160):start+1100]
            if len(fragment)<35:continue
            count+=1;db.add(Chunk(id=f'{ident}:{page}:{start}',document_id=ident,page=page,text=fragment))
    db.commit();return {'id':ident,'pages':len(pages),'chunks':count,'title':title,'extraction':extraction}
