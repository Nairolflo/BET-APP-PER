from datetime import date, timedelta
from flask import Blueprint, render_template
from app.extensions import db
from app.models import ValueBet, Match

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    today = date.today()
    bets_today = (
        ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == today)
        .order_by(ValueBet.edge.desc()).all()
    )
    return render_template("dashboard.html",
        bets=bets_today, stats=_global_stats(),
        streak=_streak(10), today=today)


@dashboard_bp.route("/history")
def history():
    bets = (
        ValueBet.query.join(Match)
        .filter(ValueBet.status != "PENDING")
        .order_by(ValueBet.detected_at.desc()).limit(200).all()
    )
    return render_template("history.html", bets=bets, stats=_global_stats())


def _global_stats():
    bets = ValueBet.query.filter(ValueBet.status != "PENDING").all()
    total = len(bets)
    won = sum(1 for b in bets if b.status == "WON")
    profit = sum(b.profit_units for b in bets)
    settled = sum(1 for b in bets if b.status in ("WON", "LOST"))
    roi = profit / settled if settled else 0.0
    week_ago = date.today() - timedelta(days=7)
    w7 = [b for b in bets if b.resolved_at and b.resolved_at.date() >= week_ago]
    w7s = sum(1 for b in w7 if b.status in ("WON", "LOST"))
    roi7 = sum(b.profit_units for b in w7) / w7s if w7s else 0.0
    return dict(
        total=total, won=won, lost=total - won,
        win_rate=round(won / total * 100, 1) if total else 0,
        profit_units=round(profit, 2), roi=round(roi * 100, 2),
        roi_7d=round(roi7 * 100, 2),
        pending=ValueBet.query.filter_by(status="PENDING").count()
    )


def _streak(n):
    return (
        ValueBet.query
        .filter(ValueBet.status.in_(["WON", "LOST"]))
        .order_by(ValueBet.resolved_at.desc()).limit(n).all()
    )[::-1]