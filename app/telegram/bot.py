"""
ValueBet FC — Bot Telegram avec menu interactif
"""
import logging
import threading
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _api(token, method, payload):
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=40)
        return r.json()
    except Exception as e:
        logger.error(f"Telegram API error ({method}): {e}")
        return {}


def send_message(token, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _api(token, "sendMessage", payload)


def answer_callback(token, callback_query_id):
    _api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})


MAIN_MENU = {
    "inline_keyboard": [
        [{"text": "📊 Stats globales",  "callback_data": "cmd_stats"},
         {"text": "🔍 Analyse manuelle","callback_data": "cmd_analyse"}],
        [{"text": "✅ Vérif résultats", "callback_data": "cmd_check"},
         {"text": "🎯 Derniers bets",  "callback_data": "cmd_bets"}],
        [{"text": "⚙️ Paramètres",     "callback_data": "cmd_params"},
         {"text": "❓ Aide",           "callback_data": "cmd_help"}],
    ]
}


def handle_stats(app):
    with app.app_context():
        from app.models.value_bet import ValueBet
        from app.models.daily_summary import DailySummary
        from app.extensions import db
        from sqlalchemy import func
        total   = db.session.query(func.count(ValueBet.id)).scalar() or 0
        won     = db.session.query(func.count(ValueBet.id)).filter_by(status="WON").scalar() or 0
        lost    = db.session.query(func.count(ValueBet.id)).filter_by(status="LOST").scalar() or 0
        pending = db.session.query(func.count(ValueBet.id)).filter_by(status="PENDING").scalar() or 0
        profit  = db.session.query(func.sum(ValueBet.profit_units)).scalar() or 0.0
        resolved = won + lost
        win_rate = (won / resolved * 100) if resolved > 0 else 0
        roi      = (profit / resolved * 100) if resolved > 0 else 0
        since    = datetime.utcnow() - timedelta(days=7)
        week     = db.session.query(func.count(ValueBet.id)).filter(
            ValueBet.detected_at >= since).scalar() or 0
        last = DailySummary.query.order_by(DailySummary.date.desc()).first()
        cum_roi = f"{last.cumulative_roi*100:+.1f}%" if last else "N/A"
        return (
            "📊 <b>Statistiques ValueBet FC</b>\n\n"
            f"🎯 Total détectés : <b>{total}</b>\n"
            f"✅ Gagnés   : <b>{won}</b>\n"
            f"❌ Perdus   : <b>{lost}</b>\n"
            f"⏳ En cours : <b>{pending}</b>\n\n"
            f"📈 Win rate : <b>{win_rate:.1f}%</b>\n"
            f"💰 Profit   : <b>{profit:+.2f}u</b>\n"
            f"📉 ROI      : <b>{roi:+.1f}%</b>\n"
            f"🏆 ROI cumulé : <b>{cum_roi}</b>\n\n"
            f"📅 7 derniers jours : <b>{week} bets</b>"
        )


def handle_bets(app):
    with app.app_context():
        from app.models.value_bet import ValueBet
        bets = (ValueBet.query.filter_by(status="PENDING")
                .order_by(ValueBet.detected_at.desc()).limit(8).all())
        if not bets:
            return "🎯 <b>Bets en cours</b>\n\nAucun bet en attente."
        lines = ["🎯 <b>Value Bets en cours</b>\n"]
        for b in bets:
            m = b.match
            icon = "🔥" if b.is_bete_noire else ("⭐" if b.edge >= 0.10 else "✅")
            lines.append(
                f"{icon} <b>{m.home_team} vs {m.away_team}</b>\n"
                f"   {b.market} → <b>{b.selection}</b> @ {b.best_odd:.2f} ({b.best_bookmaker})\n"
                f"   Edge: <b>{b.edge*100:+.1f}%</b> | Mise: {b.stake_units:.1f}u\n"
                f"   📅 {m.match_date.strftime('%d/%m %H:%M')}\n"
            )
        return "\n".join(lines)


def handle_analyse(app):
    def _run():
        try:
            with app.app_context():
                from app.scheduler.tasks import (
                    fetch_and_store_fixtures, fetch_and_store_odds,
                    run_detection, send_detections_today,
                )
                fetch_and_store_fixtures()
                fetch_and_store_odds()
                run_detection()
                send_detections_today()
        except Exception as e:
            logger.error(f"Analyse manuelle erreur: {e}")
    threading.Thread(target=_run, daemon=True).start()
    return (
        "🔍 <b>Analyse manuelle lancée !</b>\n\n"
        "⏳ Calcul en cours...\n"
        "📬 Notification dès qu'un value bet est détecté.\n"
        "⏱ Durée estimée : <b>30–60 sec</b>"
    )


def handle_check(app):
    with app.app_context():
        from app.models.value_bet import ValueBet
        from app.models.match import Match
        from app.extensions import db
        since = datetime.utcnow() - timedelta(hours=48)
        pending = (ValueBet.query.join(Match)
                   .filter(ValueBet.status == "PENDING",
                           Match.match_date <= datetime.utcnow(),
                           Match.match_date >= since).all())
        if not pending:
            return "✅ <b>Résultats</b>\n\nAucun bet récent en attente."
        updated = 0
        for bet in pending:
            m = bet.match
            if m.result is None:
                continue
            if bet.market == "1X2":
                won = ((bet.selection == "HOME" and m.result == "H") or
                       (bet.selection == "DRAW" and m.result == "D") or
                       (bet.selection == "AWAY" and m.result == "A"))
            elif bet.market == "BTTS":
                btts = (m.home_goals or 0) > 0 and (m.away_goals or 0) > 0
                won = (bet.selection == "YES") == btts
            elif bet.market == "O25":
                total = (m.home_goals or 0) + (m.away_goals or 0)
                won = (bet.selection == "OVER") == (total > 2.5)
            else:
                continue
            bet.status = "WON" if won else "LOST"
            bet.profit_units = (bet.best_odd - 1) * bet.stake_units if won else -bet.stake_units
            bet.resolved_at = datetime.utcnow()
            updated += 1
        db.session.commit()
        won_c  = sum(1 for b in pending if b.status == "WON")
        lost_c = sum(1 for b in pending if b.status == "LOST")
        profit = sum(b.profit_units for b in pending if b.status in ("WON","LOST"))
        return (
            "✅ <b>Résultats mis à jour</b>\n\n"
            f"📋 Bets vérifiés : <b>{updated}</b>\n"
            f"✅ Gagnés : <b>{won_c}</b>\n"
            f"❌ Perdus : <b>{lost_c}</b>\n"
            f"💰 Profit : <b>{profit:+.2f}u</b>"
        )


def handle_params(app):
    with app.app_context():
        cfg = app.config
        leagues_map = {
            2021:"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", 2014:"🇪🇸 La Liga",
            2002:"🇩🇪 Bundesliga",    2015:"🇫🇷 Ligue 1",
            2019:"🇮🇹 Serie A",       2001:"🏆 UCL",
            2146:"🏆 UEL",            2003:"🇳🇱 Eredivisie",
            2017:"🇵🇹 Primeira Liga", 2013:"🇧🇷 Série A",
            2145:"🇺🇸 MLS",           2024:"🇦🇷 Liga Prof.",
        }
        leagues_str = "\n".join(
            f"   • {leagues_map.get(lid, str(lid))}"
            for lid in cfg.get("MONITORED_LEAGUES", []))
        books = ", ".join(cfg.get("BOOKMAKERS", []))
        return (
            "⚙️ <b>Paramètres actifs</b>\n\n"
            f"📐 Edge min       : <b>{cfg.get('EDGE_THRESHOLD',0.05)*100:.0f}%</b>\n"
            f"💧 Kelly fraction : <b>{cfg.get('KELLY_FRACTION',0.25)*100:.0f}%</b>\n"
            f"📦 Mise max       : <b>{cfg.get('MAX_STAKE_UNITS',3.0)}u</b>\n"
            f"💶 Taille unité   : <b>{cfg.get('UNIT_SIZE',10.0)}€</b>\n\n"
            f"🏟 Ligues :\n{leagues_str}\n\n"
            f"📚 Bookmakers : {books}\n\n"
            "✏️ <i>Modifier → Railway → Variables → Redeploy</i>"
        )


def handle_help():
    return (
        "❓ <b>ValueBet FC — Aide</b>\n\n"
        "<b>Variables Railway modifiables :</b>\n"
        "<code>VALUE_BET_EDGE_THRESHOLD</code> — Edge min (ex: 0.05)\n"
        "<code>KELLY_FRACTION</code>           — Fraction Kelly (ex: 0.25)\n"
        "<code>MAX_STAKE_UNITS</code>          — Mise max (ex: 3)\n"
        "<code>UNIT_SIZE</code>                — Taille unité € (ex: 10)\n"
        "<code>MONITORED_LEAGUES</code>        — IDs séparés par virgule\n"
        "<code>BOOKMAKERS</code>               — ex: winamax_fr,betclic_fr\n\n"
        "⏰ <b>Détections auto :</b> 07h · 12h · 17h · 21h"
    )


def start_polling(app):
    token   = app.config.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = app.config.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("Telegram: TOKEN ou CHAT_ID manquant — polling non démarré.")
        return

    def _poll():
        offset = 0
        logger.info("🤖 Telegram polling démarré.")
        while True:
            try:
                data = _api(token, "getUpdates", {
                    "offset": offset, "timeout": 30,
                    "allowed_updates": ["message", "callback_query"],
                })
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    _dispatch(app, token, chat_id, update)
            except Exception as e:
                logger.error(f"Polling erreur: {e}")
                import time; time.sleep(5)

    threading.Thread(target=_poll, daemon=True, name="telegram-poll").start()


def _dispatch(app, token, chat_id, update):
    msg = update.get("message", {})
    cb  = update.get("callback_query", {})
    cmd = None
    reply_to = None
    if msg:
        text = msg.get("text", "")
        reply_to = str(msg.get("chat", {}).get("id", chat_id))
        if text.startswith("/"):
            cmd = text.split()[0].lstrip("/").split("@")[0]
    elif cb:
        cmd = cb.get("data", "").replace("cmd_", "")
        reply_to = str(cb.get("message", {}).get("chat", {}).get("id", chat_id))
        answer_callback(token, cb["id"])
    if not cmd or reply_to != str(chat_id):
        return
    handlers = {
        "start":   lambda: ("👋 <b>ValueBet FC</b>\n\nChoisissez une action :", MAIN_MENU),
        "menu":    lambda: ("👋 <b>ValueBet FC</b>\n\nChoisissez une action :", MAIN_MENU),
        "stats":   lambda: (handle_stats(app), None),
        "analyse": lambda: (handle_analyse(app), None),
        "check":   lambda: (handle_check(app), None),
        "bets":    lambda: (handle_bets(app), None),
        "params":  lambda: (handle_params(app), None),
        "help":    lambda: (handle_help(), None),
    }
    handler = handlers.get(cmd)
    if handler:
        text_out, markup = handler()
        send_message(token, reply_to, text_out, reply_markup=markup)
