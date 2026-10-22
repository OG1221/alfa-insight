"""Protect organizer-derived news and admin manual input from demo access."""
from alembic import op
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('ALTER TABLE articles ADD COLUMN IF NOT EXISTS private BOOLEAN NOT NULL DEFAULT false')
    op.execute("UPDATE articles SET private=true WHERE source LIKE 'Архив кейса%'")
def downgrade():op.drop_column('articles','private')
