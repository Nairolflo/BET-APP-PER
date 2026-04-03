"""Tâches métier orchestrées par le scheduler."""
import logging
from datetime import date, datetime, timedelta

from app.config import Config
from app.extensions import db
from app.models import Team, Match, Odds, ValueBet
from app.services import football_data_api as fda
from app.services import odds_api
from app.services import detection_engine as engine
from app.services.result_validator import (
    update_match_results_from_api, validate_pending_bets, _rebuild_daily_summaries,
)
from app.services.telegram_service import send_detections, send_daily_summary

logger = logging.getLogger(__name__)


# ── Fixtures ──────────────────────────────────────────────────────────

def fetch_and_store_fixtures():
    for league_id in Config.MONITORED_LEAGUES:
        raw_matches = fda.fetch_upcoming_matches(league_id, days_ahead=2)
        logger.info("Ligue %d: %d matchs récupérés.", league_id, len(raw_matches))
        for raw in raw_matches:
            _upsert_match(raw, league_id)
    db.session.commit()


def _upsert_match(raw: dict, league_id: int, league_name: str):
    api_id = raw.get("id")
    if not api_id:
        return

    home_raw = raw.get("homeTeam", {})
    away_raw  = raw.get("awayTeam", {})
    home = _get_or_create_team(home_raw, league_id)
    away = _get_or_create_team(away_raw, league_id)
    if not home or not away:
        return

    try:
        from datetime import datetime
        match_date = datetime.fromisoformat(
            raw.get("utcDate", "").replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        return

    from app.services.football_data_api import parse_match_status
    status = parse_match_status(raw.get("status", "SCHEDULED"))
    score  = raw.get("score", {})
    full   = score.get("fullTime", {})
    home_g = full.get("home")
    away_g = full.get("away")
    result = None
    if home_g is not None and away_g is not None:
        result = "H" if home_g > away_g else ("A" if away_g > home_g else "D")

    season_str = str(raw.get("season", {}).get("startDate", "2024"))[:4]
    try:
        season = int(season_str)
    except (ValueError, TypeError):
        season = 2024

    existing = Match.query.filter_by(api_fixture_id=api_id).first()
    if not existing:
        m = Match(
            api_fixture_id=api_id,
            league_id=league_id,
            league_name=league_name,
            season=season,
            home_team_id=home.id,
            away_team_id=away.id,
            match_date=match_date,
            status=status,
            home_goals=home_g,
            away_goals=away_g,
            result=result,
        )
        db.session.add(m)
    else:
        existing.status     = status
        existing.home_goals = home_g
        existing.away_goals = away_g
        existing.result     = result
    db.session.flush()
    return team


# ── Cotes ──────────────────────────────────────────────────────────────

def fetch_and_store_odds():
    today = date.today()
    for league_id in Config.MONITORED_LEAGUES:
        all_odds = odds_api.fetch_odds_for_league(league_id)
        upcoming = Match.query.filter(
            Match.league_id == league_id,
            Match.status == "SCHEDULED",
            db.func.date(Match.match_date) >= today,
            db.func.date(Match.match_date) <= today + timedelta(days=1),
        ).all()
        for match in upcoming:
            _store_match_odds(match, all_odds)
    db.session.commit()


def _store_match_odds(match: Match, all_odds: list):
    home_name = match.home_team.name if match.home_team else ""
    away_name = match.away_team.name if match.away_team else ""
    pairs = [
        ("1X2", "HOME"), ("1X2", "DRAW"), ("1X2", "AWAY"),
        ("OVER_25", "OVER"), ("UNDER_25", "UNDER"),
        ("BTTS", "YES"), ("BTTS", "NO"),
    ]
    for market, selection in pairs:
        best_odd, best_bm = odds_api.get_best_odd(
            all_odds, home_name, away_name, market, selection
        )
        if not best_odd:
            continue
        existing = Odds.query.filter_by(
            match_id=match.id, bookmaker=best_bm, market=market, selection=selection
        ).first()
        if existing:
            existing.odd_value = best_odd
            existing.fetched_at = datetime.utcnow()
        else:
            db.session.add(Odds(
                match_id=match.id, bookmaker=best_bm,
                market=market, selection=selection, odd_value=best_odd,
            ))


# ── Détection ─────────────────────────────────────────────────────────

def run_detection():
    today = date.today()
    matches = Match.query.filter(
        Match.status == "SCHEDULED",
        db.func.date(Match.match_date) >= today,
        db.func.date(Match.match_date) <= today + timedelta(days=1),
    ).all()
    detected = sum(_analyze_match(m) for m in matches if m.odds_entries.count())
    db.session.commit()
    logger.info("Détection: %d value bets trouvés sur %d matchs.", detected, len(matches))


def _analyze_match(match: Match) -> int:
    home, away = match.home_team, match.away_team
    if not home or not away:
        return 0

    home_recent = _recent(home.id)
    away_recent = _recent(away.id)
    h2h = _h2h(home.id, away.id)

    form_h = engine.compute_form_score(home_recent, home.id)
    form_a = engine.compute_form_score(away_recent, away.id)

    p1x2 = engine.compute_1x2_probs(home, away, home_recent, away_recent, h2h)
    pou = engine.compute_ou_probs(home, away)
    pbtts = engine.compute_btts_probs(home, away)
    is_bn, bn_rate, _ = engine.detect_bete_noire(h2h, away.id)

    to_check = [
        ("1X2", "HOME", p1x2["HOME"]),
        ("1X2", "DRAW", p1x2["DRAW"]),
        ("1X2", "AWAY", p1x2["AWAY"]),
        ("OVER_25", "OVER", pou["OVER"]),
        ("UNDER_25", "UNDER", pou["UNDER"]),
        ("BTTS", "YES", pbtts["YES"]),
        ("BTTS", "NO", pbtts["NO"]),
    ]

    created = 0
    for market, selection, est_prob in to_check:
        odd_val, bm = _best_odd_db(match.id, market, selection)
        if not odd_val:
            continue
        edge = engine.compute_edge(est_prob, odd_val)
        if not engine.is_value_bet(edge):
            continue
        if ValueBet.query.filter_by(match_id=match.id, market=market, selection=selection).first():
            continue

        implied = 1.0 / odd_val
        stake = engine.kelly_stake(est_prob, odd_val)
        conf = engine.compute_confidence(edge, stake, len(h2h), (form_h + form_a) / 2)
        bet_is_bn = is_bn and market == "1X2" and selection == "AWAY"
        if bet_is_bn:
            edge = min(edge * 1.10, 0.50)

        db.session.add(ValueBet(
            match_id=match.id, market=market, selection=selection,
            estimated_prob=round(est_prob, 4), implied_prob=round(implied, 4),
            edge=round(edge, 4), best_odd=odd_val, best_bookmaker=bm,
            stake_units=stake, confidence=conf,
            reason=engine.build_reason(market, selection, est_prob, implied, edge,
                                       form_h, form_a, bet_is_bn, bn_rate),
            is_bete_noire=bet_is_bn, bete_noire_rate=bn_rate,
        ))
        created += 1
    return created


def _recent(team_id: int, n: int = 10):
    return (Match.query
        .filter(db.or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == "FINISHED")
        .order_by(Match.match_date.desc()).limit(n).all())


def _h2h(home_id: int, away_id: int, n: int = 10):
    return (Match.query
        .filter(db.or_(
            db.and_(Match.home_team_id == home_id, Match.away_team_id == away_id),
            db.and_(Match.home_team_id == away_id, Match.away_team_id == home_id),
        ), Match.status == "FINISHED")
        .order_by(Match.match_date.desc()).limit(n).all())


def _best_odd_db(match_id: int, market: str, selection: str):
    entries = Odds.query.filter_by(match_id=match_id, market=market, selection=selection).all()
    if not entries:
        return 0.0, ""
    best = max(entries, key=lambda o: o.odd_value)
    return best.odd_value, best.bookmaker


# ── Pipelines ─────────────────────────────────────────────────────────

def update_results():      update_match_results_from_api()
def validate_bets():       validate_pending_bets()
def compute_summaries():   _rebuild_daily_summaries()
def send_detections_today(app=None): send_detections(app, date.today())
def send_summary_today(app=None): send_daily_summary(app, date.today())


def refresh_team_stats():
    from app.services.detection_engine import update_elo
    teams = Team.query.all()
    for team in teams:
        hm = Match.query.filter_by(home_team_id=team.id, status="FINISHED").all()
        am = Match.query.filter_by(away_team_id=team.id, status="FINISHED").all()
        if hm:
            team.avg_goals_scored_home = sum(m.home_goals or 0 for m in hm) / len(hm)
            team.avg_goals_conceded_home = sum(m.away_goals or 0 for m in hm) / len(hm)
            team.clean_sheet_rate_home = sum(1 for m in hm if (m.away_goals or 0) == 0) / len(hm)
            team.btts_rate_home = sum(1 for m in hm if (m.home_goals or 0) > 0 and (m.away_goals or 0) > 0) / len(hm)
            team.over25_rate_home = sum(1 for m in hm if (m.home_goals or 0) + (m.away_goals or 0) > 2) / len(hm)
            team.win_rate_home = sum(1 for m in hm if m.result == "H") / len(hm)
        if am:
            team.avg_goals_scored_away = sum(m.away_goals or 0 for m in am) / len(am)
            team.avg_goals_conceded_away = sum(m.home_goals or 0 for m in am) / len(am)
            team.clean_sheet_rate_away = sum(1 for m in am if (m.home_goals or 0) == 0) / len(am)
            team.btts_rate_away = sum(1 for m in am if (m.home_goals or 0) > 0 and (m.away_goals or 0) > 0) / len(am)
            team.over25_rate_away = sum(1 for m in am if (m.home_goals or 0) + (m.away_goals or 0) > 2) / len(am)
            team.win_rate_away = sum(1 for m in am if m.result == "A") / len(am)

        # Recalcul Elo incrémental
        all_played = sorted(_recent(team.id, n=50), key=lambda m: m.match_date)
        for m in all_played:
            if not m.result:
                continue
            other_id = m.away_team_id if m.home_team_id == team.id else m.home_team_id
            other = Team.query.get(other_id)
            if not other:
                continue
            nh, na = update_elo(team.elo_rating, other.elo_rating, m.result)
            team.elo_rating = nh if m.home_team_id == team.id else na

    db.session.commit()
    logger.info("Stats équipes rafraîchies pour %d équipes.", len(teams))