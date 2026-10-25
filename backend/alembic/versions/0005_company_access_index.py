"""Index the company access filter used on every initial page load."""
from alembic import op
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None


def upgrade():
    # The original initial migration creates current ORM metadata on fresh installs.
    op.create_index('ix_company_synthetic','companies',['synthetic'],if_not_exists=True)


def downgrade():
    op.drop_index('ix_company_synthetic',table_name='companies')
