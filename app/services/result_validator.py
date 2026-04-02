"""
Validation des résultats des value bets après fin de match.
"""
import logging
from datetime import date, datetime, timezone

from app.extensions import db
from app.models import Match, ValueBet, DailySummary

logger = logging.getLogger(__name__)


def validate_pending_bets():
    """Résout tous les paris PENDING dont le match est FINISHED."""
    pending = (
        db.session.query(ValueBet)
        .join(Match)
        .filter(ValueBet.status == "PENDING", Match.status == "FINISHED")
        .all()
    )
    logger.info("Validation de %d paris en attente.", len(pending))
    for bet in pending:
        _resolve_bet(bet)
    db.session.commit()
    _rebuild_daily_summaries()


def _resolve_bet(bet: ValueBet):
    match = bet.match
    if not match or match.status != "FINISHED":
        return
    won = _check_outcome(bet, match)
    now = datetime.now(timezone.utc)
    if won is None:
        bet.status, bet.profit_units = "VOID", 0.0
    elif won:
        bet.status = "WON"
        bet.profit_units = round(bet.stake_units * (bet.best_odd - 1), 3)
    else:
        bet.status, bet.profit_units = "LOST", -bet.stake_units
    bet.resolved_at = now
    logger.info("Bet #%d: %s (%+.2fu)", bet.id, bet.status, bet.profit_units)


def _check_outcome(bet: ValueBet, match: Match):
    m, s = bet.market, bet.selection
    hg, ag = match.home_goals or 0, match.away_goals or 0
    total = hg + ag
    if m == "1X2":
        return match.result == {"HOME": "H", "DRAW": "D", "AWAY": "A"}.get(s)
    elif m == "OVER_25":
        return total > 2.5
    elif m == "UNDER_25":
        return total <= 2.5
    elif m == "BTTS":
        btts = hg > 0 and ag > 0
        return btts if s == "YES" else not btts
    return None


def update_match_results_from_api():
    """Met à jour les scores des matchs en cours / terminés via football-data.org."""
    from app.services.football_data_api import fetch_finished_matches, parse_match_status

    active = Match.query.filter(Match.status.in_(["SCHEDULED", "IN_PLAY"])).all()
    if not active:
        return

    league_ids = list({m.league_id for m in active})
    updated = 0
    for league_id in league_ids:
        finished = fetch_finished_matches(league_id, days_back=3)
        for raw in finished:
            api_id = raw.get("id")
            match = Match.query.filter_by(api_fixture_id=api_id).first()
            if not match:
                continue
            match.status = parse_match_status(raw.get("status", "SCHEDULED"))
            ft = raw.get("score", {}).get("fullTime", {})
            ht = raw.get("score", {}).get("halfTime", {})
            if match.status == "FINISHED" and ft.get("home") is not None:
                match.home_goals = ft.get("home")
                match.away_goals = ft.get("away")
                match.home_goals_ht = ht.get("home")
                match.away_goals_ht = ht.get("away")
                h, a = match.home_goals, match.away_goals
                match.result = "H" if h > a else ("A" if a > h else "D")
                updated += 1

    db.session.commit()
    logger.info("Résultats mis à jour pour %d matchs.", updated)


def _rebuild_daily_summaries():
    from sqlalchemy import func
    days = db.session.query(
        func.date(ValueBet.detected_at).label("day")
    ).filter(ValueBet.status != "PENDING").distinct().all()
    for (day,) in days:
        _upsert_daily_summary(day)
    db.session.commit()


def _upsert_daily_summary(day: date):
    bets = ValueBet.query.filter(db.func.date(ValueBet.detected_at) == day).all()
    if not bets:
        return
    won = sum(1 for b in bets if b.status == "WON")
    lost = sum(1 for b in bets if b.status == "LOST")
    void = sum(1 for b in bets if b.status == "VOID")
    settled = won + lost
    profit = sum(b.profit_units for b in bets)
    roi = profit / settled if settled else 0.0

    all_resolved = ValueBet.query.filter(
        ValueBet.status != "PENDING",
        db.func.date(ValueBet.detected_at) <= day
    ).all()
    cum_bets = len(all_resolved)
    cum_won = sum(1 for b in all_resolved if b.status == "WON")
    cum_profit = sum(b.profit_units for b in all_resolved)
    cum_settled = sum(1 for b in all_resolved if b.status in ("WON", "LOST"))
    cum_roi = cum_profit / cum_settled if cum_settled else 0.0

    summary = DailySummary.query.filter_by(date=day).first()
    if not summary:
        summary = DailySummary(date=day)
        db.session.add(summary)

    summary.total_bets = len(bets)
    summary.won = won
    summary.lost = lost
    summary.void = void
    summary.profit_units = round(profit, 3)
    summary.roi = round(roi, 4)
    summary.cumulative_bets = cum_bets
    summary.cumulative_won = cum_won
    summary.cumulative_profit_units = round(cum_profit, 3)
    summary.cumulative_roi = round(cum_roi, 4)