import re
from sqlalchemy import text, select
from .db import Chunk,BankDocument
from .ranking import tokens

def search_bank(db,query,limit=5,synthetic_only=False):
    terms=re.findall(r'[а-яёa-z0-9]{4,}',query.lower())[:35]
    if not terms:return []
    # OR full-text query lets the agent broaden an unsuccessful first search.
    tsquery=' | '.join(dict.fromkeys(terms))
    if db.bind.dialect.name=='postgresql':
        rows=db.execute(text("""SELECT c.id,c.document_id,c.page,c.text,d.title,d.source_url,d.synthetic,d.extraction,
            ts_rank_cd(to_tsvector('russian',c.text),to_tsquery('russian',:q)) AS rank
            FROM document_chunks c JOIN bank_documents d ON d.id=c.document_id
            WHERE (NOT :synthetic_only OR d.synthetic) AND to_tsvector('russian',c.text) @@ to_tsquery('russian',:q)
            ORDER BY rank DESC,c.id LIMIT :lim"""),{'q':tsquery,'lim':limit,'synthetic_only':synthetic_only}).mappings().all()
        return [dict(r) for r in rows]
    result=[]
    for chunk,doc in db.execute(select(Chunk,BankDocument).join(BankDocument,Chunk.document_id==BankDocument.id)):
        if synthetic_only and not doc.synthetic:continue
        overlap=len(tokens(query)&tokens(chunk.text))
        if overlap:result.append({'id':chunk.id,'document_id':doc.id,'page':chunk.page,'text':chunk.text,'title':doc.title,'source_url':doc.source_url,'synthetic':doc.synthetic,'rank':overlap})
    return sorted(result,key=lambda x:x['rank'],reverse=True)[:limit]
