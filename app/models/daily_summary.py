from datetime import datetime
from app.extensions import db


class DailySummary(db.Model):
    __tablename__ = "daily_summaries"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False, index=True)

    total_bets = db.Column(db.Integer, default=0)
    won = db.Column(db.Integer, default=0)
    lost = db.Column(db.Integer, default=0)
    void = db.Column(db.Integer, default=0)
    profit_units = db.Column(db.Float, default=0.0)
    roi = db.Column(db.Float, default=0.0)

    # Cumulative stats updated each day
    cumulative_bets = db.Column(db.Integer, default=0)
    cumulative_won = db.Column(db.Integer, default=0)
    cumulative_profit_units = db.Column(db.Float, default=0.0)
    cumulative_roi = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)