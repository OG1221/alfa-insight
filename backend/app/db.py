from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass

class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sector: Mapped[str] = mapped_column(Text, default='Не указан')
    okved: Mapped[str] = mapped_column(String(30), default='')
    region: Mapped[str] = mapped_column(Text, default='')
    city: Mapped[str] = mapped_column(Text, default='')
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    products: Mapped[dict] = mapped_column(JSON, default=dict)
    foreign_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    countries: Mapped[str] = mapped_column(Text, default='')
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index('ix_company_region', 'region'),)

class PersonLink(Base):
    __tablename__ = 'person_links'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(String(100), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    city: Mapped[str] = mapped_column(Text, default='')
    region: Mapped[str] = mapped_column(Text, default='')

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payer: Mapped[str] = mapped_column(String(100), index=True)
    beneficiary: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[float] = mapped_column(Float)
    count: Mapped[int] = mapped_column(Integer)

class Article(Base):
    __tablename__ = 'articles'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    category: Mapped[str] = mapped_column(String(50), index=True)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index('ix_article_date', 'published_at'),)

class BankDocument(Base):
    __tablename__ = 'bank_documents'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    pages: Mapped[int] = mapped_column(Integer)
    extraction: Mapped[str] = mapped_column(String(40), default='pdf-text')
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

class Chunk(Base):
    __tablename__ = 'document_chunks'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('bank_documents.id'), index=True)
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

class AgentRun(Base):
    __tablename__ = 'agent_runs'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey('articles.id'))
    role: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default='running')
    task: Mapped[str] = mapped_column(Text)
    plan: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(30), default='rules')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

class AgentStep(Base):
    __tablename__ = 'agent_steps'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('agent_runs.id'), index=True)
    tool: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Feedback(Base):
    __tablename__ = 'feedback'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('agent_runs.id'))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class LLMUsage(Base):
    __tablename__ = 'llm_usage'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_rub: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default='reserved')

class ImportBatch(Base):
    __tablename__ = 'import_batches'
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    report: Mapped[dict] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
def get_db():
    with SessionLocal() as db: yield db
