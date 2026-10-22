import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db import SessionLocal,Company,Payment,PersonLink,BankDocument,Chunk,Article
from sqlalchemy import select,func
import httpx
with SessionLocal() as db:
 print(json.dumps({m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in [Company,Payment,PersonLink,BankDocument,Chunk,Article]},ensure_ascii=False))
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=100) as c:
 print('health',c.get('/api/health').json())
 print('refresh',c.post('/api/news/refresh').json())
