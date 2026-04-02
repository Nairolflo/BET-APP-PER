"""
ValueBet FC — Application Factory
"""
import os
import logging
from flask import Flask
from app.extensions import db, migrate
from apscheduler.schedulers.background import BackgroundScheduler  # ← import direct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    # ── Config ───────────────────────────────────────────────
    from app.config import Config
    app.config.from_object(Config)

    # ── Extensions ───────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    # ── Blueprints ───────────────────────────────────────────
    from app.routes.dashboard import dashboard_bp
    from app.routes.api import api_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Modèles (pour Flask-Migrate) ─────────────────────────
    with app.app_context():
        from app.models import team, match, odds, value_bet, daily_summary

    # ── Scheduler ────────────────────────────────────────────
    _start_scheduler(app)

    return app


def _start_scheduler(app: Flask):
    """Démarre APScheduler uniquement hors contexte flask db upgrade/migrate."""

    # Ne pas lancer le scheduler pendant les commandes CLI Flask
    import sys
    cli_commands = {"db", "shell", "routes"}
    if len(sys.argv) > 1 and sys.argv[1] in cli_commands:
        logger.info("Commande CLI détectée — scheduler non démarré.")
        return

    # Créer l'instance APScheduler ICI (pas via extensions)
    scheduler = BackgroundScheduler(timezone="Europe/Paris")

    # Enregistrer les jobs
    from app.scheduler.jobs import register_jobs
    register_jobs(scheduler, app)

    scheduler.start()
    logger.info("✅ APScheduler démarré — jobs enregistrés.")

    # Arrêt propre à la fermeture de l'app
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))