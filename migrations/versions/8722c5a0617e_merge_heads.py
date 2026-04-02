"""merge heads

Revision ID: 8722c5a0617e
Revises: 001, fix_cols_001
Create Date: 2026-04-02 23:54:49.737420

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8722c5a0617e'
down_revision = ('001', 'fix_cols_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
