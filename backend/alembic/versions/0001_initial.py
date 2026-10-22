"""Initial domain schema and Russian full-text indexes."""
from alembic import op
from app.db import Base
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    Base.metadata.create_all(op.get_bind())
    if op.get_bind().dialect.name=='postgresql':
        op.execute("CREATE INDEX ix_chunk_fts_ru ON document_chunks USING gin(to_tsvector('russian', text))")
        op.execute("CREATE INDEX ix_article_fts_ru ON articles USING gin(to_tsvector('russian', title || ' ' || text))")
def downgrade():
    Base.metadata.drop_all(op.get_bind())
