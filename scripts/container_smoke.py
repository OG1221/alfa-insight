"""Verify a clean synthetic-only Docker/public demo over HTTP; never requires LLM."""
import argparse,json,urllib.request,urllib.error,time
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:18081');a=p.parse_args();base=a.url.rstrip('/')
def call(path,method='GET',body=None,token=None):
    h={'Content-Type':'application/json'}
    if token:h['Authorization']='Bearer '+token
    req=urllib.request.Request(base+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=h,method=method)
    with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
def denied(path,method='GET',body=None,token=None):
    try:call(path,method,body,token)
    except urllib.error.HTTPError as e:assert e.code in (401,403,404);return
    raise AssertionError('Protected route unexpectedly allowed')
assert call('/api/health')['status']=='ok'
companies=call('/api/companies')['items'];assert len(companies)==3 and all(c['synthetic'] for c in companies)
assert call('/api/documents')['items']==[]
denied('/api/companies/U_9250');denied('/api/status',token='alfa-local-admin')
title='Учебное новое событие '+str(time.time_ns())
article=call('/api/articles','POST',{'title':title,'text':'Учебный сценарий: ключевая ставка требует проверки новых кредитных договоров и депозитов. Это синтетическая проверка запуска.'})['article']
runs=[call('/api/analyses','POST',{'company_id':cid,'article_id':article['id'],'role':'cfo'}) for cid in ['DEMO_U_101','DEMO_U_202']]
assert all(r['status']=='complete' and r['mode']=='rules' and r['steps'] for r in runs)
assert runs[0]['result']['relevance']['score']!=runs[1]['result']['relevance']['score']
try:call('/api/analyses/'+runs[0]['id']+'/questions','POST',{'question':'Как это влияет на компанию?'})
except urllib.error.HTTPError as e:assert e.code==503
else:raise AssertionError('AI unexpectedly enabled')
print(json.dumps({'url':base,'health':'passed','synthetic_only':'passed','private_access':'denied','new_event':'passed','two_company_personalization':'passed','trace':'passed','llm':'disabled, honest mode'},ensure_ascii=False,indent=2))
