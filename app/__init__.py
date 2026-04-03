import logging, sys, threading
from flask import Flask
from app.extensions import db, migrate

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
CLI_COMMANDS = {"db", "shell", "routes", "flask"}

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
    _auto_migrate(app)
    _start_scheduler(app)
    return app

def _start_scheduler(app):
    if len(sys.argv) > 1 and sys.argv[1] in CLI_COMMANDS:
        logger.info("Commande CLI — scheduler non démarré.")
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Europe/Paris")
    from app.scheduler.jobs import register_jobs
    register_jobs(scheduler, app)
    scheduler.start()
    logger.info("✅ APScheduler démarré.")
    from app.telegram.bot import start_polling
    start_polling(app)
    _send_startup(app)
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))

def _send_startup(app):
    def _send():
        import time, requests
        time.sleep(3)
        try:
            token   = app.config.get("TELEGRAM_BOT_TOKEN","")
            chat_id = app.config.get("TELEGRAM_CHAT_ID","")
            if not token or not chat_id: return
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "parse_mode": "HTML",
                    "text": (
                        "✅ <b>ValueBet FC est en ligne !</b>\n\n"
                        "🤖 Bot opérationnel sur Railway.\n"
                        "⏰ Détections : <b>07h · 12h · 17h · 21h</b>\n\n"
                        "👇 <b>Utilise le menu ci-dessous</b>"
                    ),
                    "reply_markup": {"inline_keyboard": [
                        [{"text":"📊 Stats","callback_data":"cmd_stats"},
                         {"text":"🔍 Analyse","callback_data":"cmd_analyse"}],
                        [{"text":"✅ Résultats","callback_data":"cmd_check"},
                         {"text":"🎯 Bets","callback_data":"cmd_bets"}],
                        [{"text":"⚙️ Paramètres","callback_data":"cmd_params"},
                         {"text":"❓ Aide","callback_data":"cmd_help"}],
                    ]}},
                timeout=10)
            logger.info("✅ Message Telegram démarrage envoyé.")
        except Exception as e:
            logger.error(f"Erreur Telegram startup: {e}")
    threading.Thread(target=_send, daemon=True).start()

def _auto_migrate(app):
    """Ajoute les colonnes manquantes au démarrage si besoin."""
    from sqlalchemy import text
    with app.app_context():
        try:
            db.session.execute(text("""
                ALTER TABLE daily_summaries
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
                ALTER TABLE teams
                    ADD COLUMN IF NOT EXISTS country VARCHAR(64),
                    ADD COLUMN IF NOT EXISTS short_name VARCHAR(64),
                    ADD COLUMN IF NOT EXISTS logo_url VARCHAR(256),
                    ADD COLUMN IF NOT EXISTS elo_rating FLOAT DEFAULT 1500,
                    ADD COLUMN IF NOT EXISTS elo_updated_at TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS avg_goals_scored_home FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS avg_goals_conceded_home FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS avg_goals_scored_away FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS avg_goals_conceded_away FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS btts_rate_home FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS btts_rate_away FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS clean_sheet_rate_home FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS clean_sheet_rate_away FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS over25_rate_home FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS over25_rate_away FLOAT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
                ALTER TABLE matches
                    ADD COLUMN IF NOT EXISTS round VARCHAR(64),
                    ADD COLUMN IF NOT EXISTS home_xg FLOAT,
                    ADD COLUMN IF NOT EXISTS away_xg FLOAT,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()
