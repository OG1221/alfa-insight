import hashlib, re
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit,urlunsplit
from bs4 import BeautifulSoup
import feedparser
from sqlalchemy import select,or_
from sqlalchemy.exc import IntegrityError
from .db import Article
from .ranking import classify
from .security import fetch_public

FEEDS=[{'name':'Банк России — пресс-релизы','url':'https://www.cbr.ru/rss/RssPress'}, {'name':'Интерфакс — бизнес','url':'https://www.interfax.ru/rss'}]
def canonical(url):
    p=urlsplit(url);return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),p.query,''))
def add_article(db,title,text,url=None,source='Ручной ввод — не проверено',published_at=None,synthetic=False):
    title=' '.join(title.split())[:500];text=' '.join(text.split())[:60000]
    if len(title)<5 or len(text)<30:raise ValueError('Недостаточно текста для обработки новости')
    fingerprint=hashlib.sha256(re.sub(r'\W+','',title.lower()).encode()).hexdigest()
    url=canonical(url) if url else None
    old=db.scalar(select(Article).where(or_(Article.fingerprint==fingerprint,Article.url==url) if url else Article.fingerprint==fingerprint))
    if old:return old,False
    facts=[s.strip() for s in re.split(r'(?<=[.!?])\s+',text) if len(s.strip())>20][:5]
    article=Article(id=fingerprint[:24],fingerprint=fingerprint,title=title,text=text,url=url,source=source,published_at=published_at or datetime.now(timezone.utc),category=classify(title+' '+text),facts=facts,synthetic=synthetic)
    db.add(article)
    try:db.commit()
    except IntegrityError:
        db.rollback();old=db.scalar(select(Article).where(Article.fingerprint==fingerprint));
        if old:return old,False
        raise
    return article,True

async def parse_url(url):
    raw=await fetch_public(url);soup=BeautifulSoup(raw,'html.parser')
    title=soup.find('meta',property='og:title');title=title.get('content') if title else (soup.title.get_text(' ',strip=True) if soup.title else '')
    for tag in soup(['script','style','nav','header','footer','form','aside']):tag.decompose()
    body=soup.find('article') or soup.find('main') or soup.body or soup
    text=' '.join(p.get_text(' ',strip=True) for p in body.find_all('p'))
    if len(text)<40:text=body.get_text(' ',strip=True)
    return title,text[:60000],urlsplit(url).hostname

async def refresh_news(db):
    result=[]
    for feed in FEEDS:
        try:
            raw=await fetch_public(feed['url']);parsed=feedparser.parse(raw)
            if parsed.bozo and not parsed.entries:raise ValueError('Некорректный RSS')
            added=0
            for entry in parsed.entries[:30]:
                title=entry.get('title','');body=BeautifulSoup(entry.get('summary',title),'html.parser').get_text(' ',strip=True)
                if len(body)<30:body=title+'. '+body
                date=None
                try:date=parsedate_to_datetime(entry.get('published',''))
                except (ValueError,TypeError):pass
                _,created=add_article(db,title,body,entry.get('link'),feed['name'],date)
                added+=int(created)
            result.append({'source':feed['name'],'status':'ok','added':added,'scanned':min(30,len(parsed.entries))})
        except Exception as exc:result.append({'source':feed['name'],'status':'error','error':str(exc)[:200]})
    return result

def article_dict(a):
    return {'id':a.id,'title':a.title,'text':a.text,'url':a.url,'source':a.source,'published_at':a.published_at.isoformat(),'fetched_at':a.fetched_at.isoformat(),'category':a.category,'facts':a.facts,'synthetic':a.synthetic}
