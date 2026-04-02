"""initial

Revision ID: 001
Revises: 
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('short_name', sa.String(50), nullable=True),
        sa.Column('tla', sa.String(10), nullable=True),
        sa.Column('logo_url', sa.String(255), nullable=True),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('elo_rating', sa.Float(), nullable=True),
        sa.Column('avg_goals_scored_home', sa.Float(), nullable=True),
        sa.Column('avg_goals_scored_away', sa.Float(), nullable=True),
        sa.Column('avg_goals_conceded_home', sa.Float(), nullable=True),
        sa.Column('avg_goals_conceded_away', sa.Float(), nullable=True),
        sa.Column('btts_rate_home', sa.Float(), nullable=True),
        sa.Column('btts_rate_away', sa.Float(), nullable=True),
        sa.Column('over25_rate_home', sa.Float(), nullable=True),
        sa.Column('over25_rate_away', sa.Float(), nullable=True),
        sa.Column('clean_sheet_rate_home', sa.Float(), nullable=True),
        sa.Column('clean_sheet_rate_away', sa.Float(), nullable=True),
        sa.Column('win_rate_home', sa.Float(), nullable=True),
        sa.Column('win_rate_away', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_fixture_id', sa.Integer(), nullable=True),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('league_name', sa.String(100), nullable=True),
        sa.Column('season', sa.String(10), nullable=True),
        sa.Column('matchday', sa.Integer(), nullable=True),
        sa.Column('stage', sa.String(50), nullable=True),
        sa.Column('home_team_id', sa.Integer(), nullable=True),
        sa.Column('away_team_id', sa.Integer(), nullable=True),
        sa.Column('match_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('home_goals', sa.Integer(), nullable=True),
        sa.Column('away_goals', sa.Integer(), nullable=True),
        sa.Column('home_goals_ht', sa.Integer(), nullable=True),
        sa.Column('away_goals_ht', sa.Integer(), nullable=True),
        sa.Column('result', sa.String(1), nullable=True),
        sa.ForeignKeyConstraint(['away_team_id'], ['teams.id']),
        sa.ForeignKeyConstraint(['home_team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('odds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=True),
        sa.Column('bookmaker', sa.String(50), nullable=True),
        sa.Column('market', sa.String(20), nullable=True),
        sa.Column('selection', sa.String(20), nullable=True),
        sa.Column('odd_value', sa.Float(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('value_bets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=True),
        sa.Column('market', sa.String(20), nullable=True),
        sa.Column('selection', sa.String(20), nullable=True),
        sa.Column('estimated_prob', sa.Float(), nullable=True),
        sa.Column('implied_prob', sa.Float(), nullable=True),
        sa.Column('edge', sa.Float(), nullable=True),
        sa.Column('best_odd', sa.Float(), nullable=True),
        sa.Column('best_bookmaker', sa.String(50), nullable=True),
        sa.Column('stake_units', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(10), nullable=True),
        sa.Column('profit_units', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_bete_noire', sa.Boolean(), nullable=True),
        sa.Column('bete_noire_rate', sa.Float(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('daily_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('total_bets', sa.Integer(), nullable=True),
        sa.Column('won', sa.Integer(), nullable=True),
        sa.Column('lost', sa.Integer(), nullable=True),
        sa.Column('void', sa.Integer(), nullable=True),
        sa.Column('profit_units', sa.Float(), nullable=True),
        sa.Column('roi', sa.Float(), nullable=True),
        sa.Column('cumulative_bets', sa.Integer(), nullable=True),
        sa.Column('cumulative_won', sa.Integer(), nullable=True),
        sa.Column('cumulative_profit_units', sa.Float(), nullable=True),
        sa.Column('cumulative_roi', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('daily_summaries')
    op.drop_table('value_bets')
    op.drop_table('odds')
    op.drop_table('matches')
    op.drop_table('teams')
