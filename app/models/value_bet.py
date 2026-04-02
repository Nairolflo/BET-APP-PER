from datetime import datetime
from app.extensions import db


class ValueBet(db.Model):
    __tablename__ = "value_bets"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, index=True)

    market = db.Column(db.String(32), nullable=False)
    selection = db.Column(db.String(32), nullable=False)

    # Probabilities
    estimated_prob = db.Column(db.Float, nullable=False)
    implied_prob = db.Column(db.Float, nullable=False)
    edge = db.Column(db.Float, nullable=False)

    # Best odd
    best_odd = db.Column(db.Float, nullable=False)
    best_bookmaker = db.Column(db.String(64), nullable=False)

    # Bankroll
    stake_units = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=False)  # 0–1

    # Explanation
    reason = db.Column(db.Text)

    # Result tracking
    status = db.Column(db.String(16), default="PENDING")  # PENDING, WON, LOST, VOID
    profit_units = db.Column(db.Float, default=0.0)
    resolved_at = db.Column(db.DateTime)

    # Bête noire signal
    is_bete_noire = db.Column(db.Boolean, default=False)

    detected_at = db.Column(db.DateTime, default=datetime.utcnow)

    match = db.relationship("Match", back_populates="value_bets")

    def __repr__(self):
        return f"<ValueBet {self.market}/{self.selection} edge={self.edge:.3f} [{self.status}]>"