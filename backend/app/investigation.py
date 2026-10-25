"""Bounded local retrieval and evidence assessment; no model-controlled network access."""
import json
from sqlalchemy import select
from .db import Article
from .ranking import tokens


def related_events(db, article, synthetic_only, query=None):
    stmt = select(Article).where(Article.id != article.id, Article.published_at <= article.published_at)
    if synthetic_only:
        stmt = stmt.where(Article.private.is_(False))
    candidates = db.scalars(stmt.order_by(Article.published_at.desc()).limit(200)).all()
    terms = tokens(query or (article.title + ' ' + article.text[:1500]))
    scored = [(len(terms & tokens(a.title + ' ' + a.text[:1500])), a) for a in candidates]
    scored = sorted((x for x in scored if x[0]), key=lambda x: (x[0], x[1].published_at), reverse=True)
    return [{'id': a.id, 'title': a.title, 'text': a.text[:2200], 'url': a.url,
             'published_at': a.published_at.isoformat(), 'synthetic': a.synthetic}
            for _, a in scored[:3]]


def assess_evidence(company, article, bank):
    terms = tokens(article.title + ' ' + article.text[:1500])
    matches = [len(terms & tokens(b['text'])) for b in bank]
    gaps = []
    if not bank:
        gaps.append('Банковская аналитика не найдена')
    elif max(matches, default=0) < 2:
        gaps.append('Слабое тематическое совпадение банковских материалов')
    conflicts = company.get('data_quality_conflicts', [])
    if conflicts:
        gaps.append('Противоречащие варианты профиля: выводы требуют оговорок')
    return {'sufficient_for_draft': bool(bank) and not gaps, 'gaps': gaps,
            'bank_term_matches': matches, 'profile_conflicts': len(conflicts),
            'temporal_limit': 'Связанные события не позже анализируемого. Дата банковского материала требует сверки с оригиналом.',
            'needs_search': not bank or max(matches, default=0) < 2}


def build_evidence(p, article, bank, nearby):
    evidence = [
        {'id': 'profile', 'type': 'company', 'title': 'Профиль ' + p['id'],
         'text': json.dumps({k: p.get(k) for k in ['id', 'sector', 'region', 'products', 'foreign_trade', 'countries', 'revenue', 'revenue_unit', 'group_id', 'business_features']}, ensure_ascii=False), 'synthetic': p['synthetic']},
        {'id': 'news', 'type': 'news', 'title': article.title, 'text': article.text,
         'url': article.url, 'published_at': article.published_at.isoformat(), 'synthetic': article.synthetic},
    ]
    evidence += [{'id': 'bank:' + b['id'], 'type': 'bank', 'title': b['title'], 'text': b['text'],
                  'page': b['page'], 'url': b['source_url'], 'extraction': b.get('extraction', 'pdf-text'),
                  'document_date': None, 'date_status': 'Архив кейса; дату и применимость сверить с PDF', 'synthetic': b['synthetic']} for b in bank[:6]]
    if p['relationships']['items']:
        evidence.append({'id': 'relationships', 'type': 'relationships', 'title': 'Связи компании',
                         'text': json.dumps(p['relationships'], ensure_ascii=False), 'synthetic': p['synthetic']})
    if p.get('data_quality_conflicts'):
        evidence.append({'id': 'profile_conflicts', 'type': 'conflict', 'title': 'Противоречия профиля',
                         'text': json.dumps(p['data_quality_conflicts'][:3], ensure_ascii=False), 'synthetic': p['synthetic']})
    evidence += [{'id': 'related:' + a['id'], 'type': 'related_news', **{k: a[k] for k in ['title', 'text', 'url', 'published_at', 'synthetic']}} for a in nearby[:3]]
    return evidence


def merge_items(first, second, limit=6):
    return list({item['id']: item for item in first + second}.values())[:limit]


def reference_stats(interpretation, evidence):
    ids = {e['id'] for e in evidence}
    claims = [interpretation['summary']] + sum((interpretation.get(k, []) for k in ['risks', 'opportunities', 'actions', 'bank_view']), [])
    checked = sum(bool(c.get('evidence_ids')) and set(c['evidence_ids']) <= ids for c in claims)
    return {'claims_count': len(claims), 'claims_with_checked_references': checked,
            'reference_coverage': checked / len(claims) if claims else None}
