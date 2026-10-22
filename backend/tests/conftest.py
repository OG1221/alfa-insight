import os,sys,uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import Base,engine

@pytest.fixture
def db():
    schema='test_'+uuid.uuid4().hex[:12]
    with engine.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
    isolated=create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated)
    factory=sessionmaker(bind=isolated,expire_on_commit=False)
    with factory() as session:yield session
    isolated.dispose()
    with engine.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))

@pytest.fixture
def fixture_data(db):
    from app.seed import seed
    seed(db)
    return db
