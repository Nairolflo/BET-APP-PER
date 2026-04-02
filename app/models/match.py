from datetime import datetime
from app.extensions import db


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    api_fixture_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    league_id = db.Column(db.Integer, nullable=False, index=True)
    league_name = db.Column(db.String(128))
    season = db.Column(db.Integer)
    round = db.Column(db.String(64))

    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    match_date = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(32), default="NS")  # NS, FT, CANC, PST…

    # Results
    home_goals = db.Column(db.Integer)
    away_goals = db.Column(db.Integer)
    result = db.Column(db.String(4))  # H, D, A

    # xG if available
    home_xg = db.Column(db.Float)
    away_xg = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stats = db.relationship("MatchStats", back_populates="match", uselist=False)
    odds = db.relationship("Odds", back_populates="match", lazy="dynamic")
    value_bets = db.relationship("ValueBet", back_populates="match", lazy="dynamic")

    def __repr__(self):
        return f"<Match {self.home_team_id} vs {self.away_team_id} — {self.match_date.date()}>"


class MatchStats(db.Model):
    __tablename__ = "match_stats"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), unique=True)

    home_shots = db.Column(db.Integer)
    away_shots = db.Column(db.Integer)
    home_shots_on_target = db.Column(db.Integer)
    away_shots_on_target = db.Column(db.Integer)
    home_possession = db.Column(db.Float)
    away_possession = db.Column(db.Float)
    home_corners = db.Column(db.Integer)
    away_corners = db.Column(db.Integer)
    home_fouls = db.Column(db.Integer)
    away_fouls = db.Column(db.Integer)
    home_yellow_cards = db.Column(db.Integer)
    away_yellow_cards = db.Column(db.Integer)
    home_red_cards = db.Column(db.Integer)
    away_red_cards = db.Column(db.Integer)

    match = db.relationship("Match", back_populates="stats")