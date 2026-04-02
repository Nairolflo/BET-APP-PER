from datetime import datetime
from app.extensions import db


class Odds(db.Model):
    __tablename__ = "odds"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker = db.Column(db.String(64), nullable=False)
    market = db.Column(db.String(32), nullable=False)
    # Markets: 1X2, OVER_25, UNDER_25, BTTS_YES, BTTS_NO
    selection = db.Column(db.String(32), nullable=False)
    # Selections: HOME, DRAW, AWAY, OVER, UNDER, YES, NO
    odd_value = db.Column(db.Float, nullable=False)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)

    match = db.relationship("Match", back_populates="odds")

    __table_args__ = (
        db.UniqueConstraint("match_id", "bookmaker", "market", "selection", name="uq_odds"),
    )