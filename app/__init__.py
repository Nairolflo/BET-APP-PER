"""
ValueBet FC — Application Factory
"""
import os
import logging
from flask import Flask
from app.extensions import db, migrate
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    from app.config import Config
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    from app.routes.dashboard import dashboard_bp
    from app.routes.api import api_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    with app.app_context():
        from app.models import team, match, odds, value_bet, daily_summary
    _start_scheduler(app)
    return app


def _send_startup_message(app):
    import threading
    def _send():
        try:
            import requests
            token = app.config.get("TELEGRAM_BOT_TOKEN")
            chat_id = app.config.get("TELEGRAM_CHAT_ID")
            if not token or not chat_id:
                logger.warning("Telegram non configuré — message ignoré.")
                return
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "parse_mode": "HTML",
                    "text": (
                        "✅ <b>ValueBet FC est en ligne !</b>\n\n"
                        "🤖 Bot opérationnel sur Railway.\n"
                        "⏰ Prochaine détection : <b>07h00</b>\n"
                        "📊 Ligues surveillées : PL · LaLiga · Bundesliga · L1 · Serie A"
                    ),
                },
                timeout=10,
            )
            if resp.ok:
                logger.info("✅ Message Telegram démarrage envoyé.")
            else:
                logger.warning(f"Telegram erreur {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Erreur Telegram démarrage: {e}")
    threading.Thread(target=_send, daemon=True).start()


def _start_scheduler(app: Flask):
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in {"db", "shell", "routes"}:
        logger.info("Commande CLI — scheduler non démarré.")
        return
    scheduler = BackgroundScheduler(timezone="Europe/Paris")
    from app.scheduler.jobs import register_jobs
    register_jobs(scheduler, app)
    scheduler.start()
    logger.info("✅ APScheduler démarré.")
    _send_startup_message(app)
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))
