"""Audit contradictory source rows rather than silently treating them as duplicates."""
from alembic import op
from app.db import DataIssue
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():DataIssue.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():DataIssue.__table__.drop(op.get_bind())
