"""
ValueBet FC — Service Telegram (alertes + bilans)
Utilise requests pur (pas de lib telegram) — compatible Gunicorn/APScheduler.
"""
import logging
import requests
from datetime import date

logger = logging.getLogger(__name__)


def _send(app, text: str):
    """Envoie un message HTML via l'API Telegram (requests sync)."""
    from app.config import Config
    token   = (app.config.get("TELEGRAM_BOT_TOKEN", "") if app else "") or Config.TELEGRAM_BOT_TOKEN
    chat_id = (app.config.get("TELEGRAM_CHAT_ID", "")   if app else "") or Config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        logger.warning("Telegram non configuré — message ignoré.")
        return
    for chunk in [text[i:i+4096] for i in range(0, len(text), 4096)]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=15,
            )
            if not r.ok:
                logger.error(f"Telegram erreur {r.status_code}: {r.text}")
        except Exception as e:
            logger.error(f"Telegram send erreur: {e}")


def send_detections(app, target_date: date):
    from app.models.value_bet import ValueBet
    from app.models.match import Match
    from app.extensions import db

    bets = (
        ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == target_date)
        .filter(ValueBet.status == "PENDING")
        .order_by(ValueBet.edge.desc())
        .all()
    )

    if not bets:
        _send(app,
            f"📭 <b>ValueBet FC — {target_date}</b>\n\n"
            "Aucun value bet détecté pour ce créneau."
        )
        return

    lines = [
        f"⚽ <b>ValueBet FC — Détections {target_date}</b>\n"
        f"<i>{len(bets)} opportunité(s)</i>\n"
    ]
    for bet in bets:
        m = bet.match
        home = m.home_team.name if m.home_team else "?"
        away = m.away_team.name if m.away_team else "?"
        bn   = "  🎯 <b>BÊTE NOIRE</b>" if bet.is_bete_noire else ""
        star = "🔥" if bet.edge >= 0.10 else "⭐"
        lines.append(
            f"{'─'*30}\n"
            f"{star} <b>{home} vs {away}</b>{bn}\n"
            f"🕐 {m.match_date.strftime('%d/%m %H:%M')} | {m.league_name}\n"
            f"📊 <b>{bet.market}</b> → <b>{bet.selection}</b>\n"
            f"💰 Cote: <b>{bet.best_odd:.2f}</b> ({bet.best_bookmaker.replace('_fr','').upper()})\n"
            f"📈 Edge: <b>+{bet.edge*100:.1f}%</b> | Confiance: {bet.confidence*100:.0f}%\n"
            f"🎯 Prob estimée: {bet.estimated_prob*100:.1f}% vs implicite: {bet.implied_prob*100:.1f}%\n"
            f"💵 Mise: <b>{bet.stake_units:.2f}u</b> "                f"({bet.stake_units * (app.config.get('UNIT_SIZE', 10) if app else 10):.0f}€) "                f"= <b>{bet.stake_units / (app.config.get('MAX_STAKE_UNITS', 2.0) if app else 2.0) * 2:.1f}% bankroll</b>\n"
        )
    _send(app, "\n".join(lines))
    logger.info(f"✅ {len(bets)} détection(s) Telegram envoyées.")


def send_daily_summary(app, target_date: date):
    from app.models.value_bet import ValueBet
    from app.models.match import Match
    from app.models.daily_summary import DailySummary
    from app.extensions import db

    bets = (
        ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == target_date)
        .filter(ValueBet.status != "PENDING")
        .order_by(ValueBet.resolved_at)
        .all()
    )
    summary = DailySummary.query.filter_by(date=target_date).first()
    icons   = {"WON": "✅", "LOST": "❌", "VOID": "⚪"}

    lines = [f"📋 <b>ValueBet FC — Bilan du {target_date}</b>\n"]
    for bet in bets:
        m    = bet.match
        home = m.home_team.name if m.home_team else "?"
        away = m.away_team.name if m.away_team else "?"
        lines.append(
            f"{icons.get(bet.status, '❓')} <b>{home} vs {away}</b> | "
            f"{bet.market}/{bet.selection} @ {bet.best_odd:.2f} → "
            f"<b>{bet.profit_units:+.2f}u</b>"
        )

    if summary:
        streak = _streak_str()
        wr = summary.cumulative_won / max(summary.cumulative_bets, 1) * 100
        lines += [
            f"\n{'═'*30}",
            f"📊 <b>Journée</b>",
            f"Paris: {summary.total_bets} | ✅ {summary.won} ❌ {summary.lost} ⚪ {summary.void}",
            f"Profit: <b>{summary.profit_units:+.2f}u</b> | ROI: <b>{summary.roi*100:+.1f}%</b>",
            f"\n📈 <b>Cumul global</b>",
            f"Total: {summary.cumulative_bets} paris | Win rate: {wr:.1f}%",
            f"Profit cumulé: <b>{summary.cumulative_profit_units:+.2f}u</b>",
            f"ROI global: <b>{summary.cumulative_roi*100:+.1f}%</b>",
            f"Série récente: {streak}",
        ]
    else:
        lines.append("\n<i>Aucun résumé journalier disponible.</i>")

    _send(app, "\n".join(lines))
    logger.info("✅ Bilan Telegram envoyé.")


def _streak_str(n: int = 10) -> str:
    from app.models.value_bet import ValueBet
    last = (
        ValueBet.query
        .filter(ValueBet.status.in_(["WON", "LOST"]))
        .order_by(ValueBet.resolved_at.desc())
        .limit(n).all()
    )
    return " ".join("✅" if b.status == "WON" else "❌" for b in reversed(last)) or "—"
