"""fix missing columns — round, xg, created_at"""
from alembic import op
import sqlalchemy as sa
revision = 'fix_cols_001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        ALTER TABLE daily_summaries
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE matches
            ADD COLUMN IF NOT EXISTS round VARCHAR(64),
            ADD COLUMN IF NOT EXISTS home_xg FLOAT,
            ADD COLUMN IF NOT EXISTS away_xg FLOAT,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
    """)

def downgrade():
    pass
