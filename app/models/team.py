from datetime import datetime
from app.extensions import db


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    api_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    short_name = db.Column(db.String(32))
    country = db.Column(db.String(64))
    logo_url = db.Column(db.String(256))

    # Elo rating
    elo_rating = db.Column(db.Float, default=1500.0)
    elo_updated_at = db.Column(db.DateTime)

    # Cached aggregate stats (updated daily)
    avg_goals_scored_home = db.Column(db.Float, default=0.0)
    avg_goals_conceded_home = db.Column(db.Float, default=0.0)
    avg_goals_scored_away = db.Column(db.Float, default=0.0)
    avg_goals_conceded_away = db.Column(db.Float, default=0.0)
    btts_rate_home = db.Column(db.Float, default=0.0)
    btts_rate_away = db.Column(db.Float, default=0.0)
    clean_sheet_rate_home = db.Column(db.Float, default=0.0)
    clean_sheet_rate_away = db.Column(db.Float, default=0.0)
    over25_rate_home = db.Column(db.Float, default=0.0)
    over25_rate_away = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    matches_home = db.relationship(
        "Match", foreign_keys="Match.home_team_id", backref="home_team", lazy="dynamic"
    )
    matches_away = db.relationship(
        "Match", foreign_keys="Match.away_team_id", backref="away_team", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Team {self.name} (ELO={self.elo_rating:.0f})>"