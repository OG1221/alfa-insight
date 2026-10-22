"""Preserve official person links whose company profile is absent from supplied CSV."""
from alembic import op
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE person_links DROP CONSTRAINT IF EXISTS person_links_company_id_fkey')
def downgrade():
    # Retaining orphan rows is intentional; downgrade requires reconciling source profiles.
    raise RuntimeError('Reconcile missing company profiles before restoring this foreign key')
