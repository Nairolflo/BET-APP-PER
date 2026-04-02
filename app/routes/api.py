from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import ValueBet, Match

api_bp = Blueprint("api", __name__)


def _serialize(bet):
    m = bet.match
    return {
        "id": bet.id,
        "match": {
            "home": m.home_team.name if m.home_team else "",
            "away": m.away_team.name if m.away_team else "",
            "league": m.league_name,
            "date": m.match_date.isoformat(),
            "status": m.status,
        },
        "market": bet.market, "selection": bet.selection,
        "estimated_prob": bet.estimated_prob, "implied_prob": bet.implied_prob,
        "edge": bet.edge, "best_odd": bet.best_odd,
        "best_bookmaker": bet.best_bookmaker, "stake_units": bet.stake_units,
        "confidence": bet.confidence, "status": bet.status,
        "profit_units": bet.profit_units, "is_bete_noire": bet.is_bete_noire,
        "reason": bet.reason,
        "detected_at": bet.detected_at.isoformat() if bet.detected_at else None,
    }


@api_bp.route("/value-bets/today")
def today_bets():
    bets = (ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == date.today())
        .order_by(ValueBet.edge.desc()).all())
    return jsonify([_serialize(b) for b in bets])


@api_bp.route("/value-bets/history")
def history():
    page = request.args.get("page", 1, type=int)
    market = request.args.get("market")
    status = request.args.get("status")
    q = ValueBet.query.join(Match)
    if market: q = q.filter(ValueBet.market == market)
    if status: q = q.filter(ValueBet.status == status)
    p = q.order_by(ValueBet.detected_at.desc()).paginate(page=page, per_page=20)
    return jsonify({"total": p.total, "pages": p.pages, "items": [_serialize(b) for b in p.items]})


@api_bp.route("/stats/global")
def global_stats():
    bets = ValueBet.query.filter(ValueBet.status != "PENDING").all()
    total = len(bets)
    won = sum(1 for b in bets if b.status == "WON")
    settled = sum(1 for b in bets if b.status in ("WON", "LOST"))
    profit = sum(b.profit_units for b in bets)
    roi = profit / settled if settled else 0
    week_ago = date.today() - timedelta(days=7)
    w7 = [b for b in bets if b.resolved_at and b.resolved_at.date() >= week_ago]
    w7s = sum(1 for b in w7 if b.status in ("WON", "LOST"))
    streak = [{"status": b.status, "market": b.market} for b in
        ValueBet.query.filter(ValueBet.status.in_(["WON", "LOST"]))
        .order_by(ValueBet.resolved_at.desc()).limit(10).all()][::-1]
    return jsonify({
        "total_bets": total, "won": won,
        "win_rate": round(won / total, 4) if total else 0,
        "profit_units": round(profit, 3), "roi": round(roi, 4),
        "roi_7d": round(sum(b.profit_units for b in w7) / w7s if w7s else 0, 4),
        "pending": ValueBet.query.filter_by(status="PENDING").count(),
        "streak": streak,
    })


@api_bp.route("/stats/by-market")
def by_market():
    from sqlalchemy import func
    rows = db.session.query(
        ValueBet.market,
        func.count().label("total"),
        func.sum(db.case((ValueBet.status == "WON", 1), else_=0)).label("won"),
        func.sum(ValueBet.profit_units).label("profit"),
    ).filter(ValueBet.status != "PENDING").group_by(ValueBet.market).all()
    return jsonify([{
        "market": r.market, "total": r.total, "won": r.won or 0,
        "profit": round(float(r.profit or 0), 3),
        "roi": round(float(r.profit or 0) / r.total, 4) if r.total else 0,
    } for r in rows])


@api_bp.route("/trigger/morning", methods=["POST"])
def trigger_morning():
    from app.scheduler.tasks import (
        fetch_and_store_fixtures, fetch_and_store_odds,
        run_detection, send_detections_today,
    )
    fetch_and_store_fixtures(); fetch_and_store_odds()
    run_detection(); send_detections_today()
    return jsonify({"status": "ok", "message": "Pipeline matin exécuté."})


@api_bp.route("/trigger/evening", methods=["POST"])
def trigger_evening():
    from app.scheduler.tasks import (
        update_results, validate_bets, compute_summaries, send_summary_today,
    )
    update_results(); validate_bets(); compute_summaries(); send_summary_today()
    return jsonify({"status": "ok", "message": "Pipeline soir exécuté."})
@api_bp.route("/health")
def health():
    return {"status": "ok"}, 200
