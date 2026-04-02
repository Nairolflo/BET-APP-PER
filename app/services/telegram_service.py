"""
Service Telegram — alertes de détection et bilans quotidiens.
"""
import asyncio
import logging
from datetime import date

import telegram

from app.config import Config

logger = logging.getLogger(__name__)


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


async def _send(text: str):
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram non configuré — message ignoré.")
        return
    bot = telegram.Bot(token=Config.TELEGRAM_BOT_TOKEN)
    for chunk in [text[i:i + 4096] for i in range(0, len(text), 4096)]:
        await bot.send_message(
            chat_id=Config.TELEGRAM_CHAT_ID,
            text=chunk,
            parse_mode="HTML",
        )


def send_detections(target_date: date):
    from app.models import ValueBet, Match
    from app.extensions import db

    bets = (
        ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == target_date)
        .filter(ValueBet.status == "PENDING")
        .order_by(ValueBet.edge.desc())
        .all()
    )

    if not bets:
        msg = f"📭 <b>ValueBet FC — {target_date}</b>\n\nAucun value bet détecté aujourd'hui."
    else:
        lines = [
            f"⚽ <b>ValueBet FC — Détections du {target_date}</b>\n"
            f"<i>{len(bets)} opportunité(s) identifiée(s)</i>\n"
        ]
        for bet in bets:
            m = bet.match
            home = m.home_team.name if m.home_team else "?"
            away = m.away_team.name if m.away_team else "?"
            bn = "  🎯 <b>BÊTE NOIRE</b>" if bet.is_bete_noire else ""
            lines.append(
                f"{'─'*32}\n"
                f"🏟 <b>{home} vs {away}</b>{bn}\n"
                f"🕐 {m.match_date.strftime('%H:%M')} | {m.league_name}\n"
                f"📊 <b>{bet.market}</b> → <b>{bet.selection}</b>\n"
                f"💰 Cote: <b>{bet.best_odd:.2f}</b> | {bet.best_bookmaker.replace('_fr','').upper()}\n"
                f"📈 Edge: <b>+{bet.edge*100:.1f}%</b> | Confiance: {bet.confidence*100:.0f}%\n"
                f"🎯 Estimée: {bet.estimated_prob*100:.1f}% vs Implicite: {bet.implied_prob*100:.1f}%\n"
                f"💵 Mise: <b>{bet.stake_units:.2f}u</b>\n"
            )
        msg = "\n".join(lines)

    try:
        _run(_send(msg))
        logger.info("Détections Telegram envoyées.")
    except Exception as e:
        logger.error("Erreur Telegram détections: %s", e)


def send_daily_summary(target_date: date):
    from app.models import ValueBet, Match, DailySummary
    from app.extensions import db

    bets = (
        ValueBet.query.join(Match)
        .filter(db.func.date(ValueBet.detected_at) == target_date)
        .filter(ValueBet.status != "PENDING")
        .all()
    )
    summary = DailySummary.query.filter_by(date=target_date).first()
    icons = {"WON": "✅", "LOST": "❌", "VOID": "⚪"}
    lines = [f"📋 <b>ValueBet FC — Bilan du {target_date}</b>\n"]

    for bet in bets:
        m = bet.match
        home = m.home_team.name if m.home_team else "?"
        away = m.away_team.name if m.away_team else "?"
        lines.append(
            f"{icons.get(bet.status, '❓')} <b>{home} vs {away}</b> | "
            f"{bet.market}/{bet.selection} @ {bet.best_odd:.2f} → "
            f"<b>{bet.profit_units:+.2f}u</b>"
        )

    if summary:
        streak = _streak_str()
        lines += [
            f"\n{'═'*32}",
            f"📊 <b>Résumé journalier</b>",
            f"Paris: {summary.total_bets} | ✅ {summary.won} | ❌ {summary.lost} | ⚪ {summary.void}",
            f"Profit: <b>{summary.profit_units:+.2f}u</b> | ROI: <b>{summary.roi*100:+.1f}%</b>",
            f"\n📈 <b>Cumul global</b>",
            f"Total: {summary.cumulative_bets} paris | Taux: "
            f"{summary.cumulative_won/max(summary.cumulative_bets,1)*100:.1f}%",
            f"Cumul: <b>{summary.cumulative_profit_units:+.2f}u</b> | ROI: <b>{summary.cumulative_roi*100:+.1f}%</b>",
            f"Série: {streak}",
        ]
    try:
        _run(_send("\n".join(lines)))
        logger.info("Bilan Telegram envoyé.")
    except Exception as e:
        logger.error("Erreur Telegram bilan: %s", e)


def _streak_str(n: int = 10) -> str:
    from app.models import ValueBet
    last = (
        ValueBet.query
        .filter(ValueBet.status.in_(["WON", "LOST"]))
        .order_by(ValueBet.resolved_at.desc())
        .limit(n).all()
    )
    return " ".join("✅" if b.status == "WON" else "❌" for b in reversed(last)) or "—"