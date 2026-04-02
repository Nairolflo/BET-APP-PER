"""Jobs APScheduler — pipeline matin + soir + refresh stats."""
import logging
from flask import Flask

logger = logging.getLogger(__name__)


def register_jobs(scheduler, app: Flask):
    scheduler.add_job(
        func=_morning, trigger="cron", hour=7, minute=0,
        id="morning_pipeline", replace_existing=True, kwargs={"app": app},
    )
    scheduler.add_job(
        func=_evening, trigger="cron", hour=23, minute=30,
        id="evening_pipeline", replace_existing=True, kwargs={"app": app},
    )
    scheduler.add_job(
        func=_stats, trigger="cron", hour=6, minute=0,
        id="refresh_stats", replace_existing=True, kwargs={"app": app},
    )
    logger.info("Jobs APScheduler enregistrés.")


def _morning(app):
    with app.app_context():
        logger.info("[SCHEDULER] Morning START")
        try:
            from app.scheduler.tasks import (
                fetch_and_store_fixtures, fetch_and_store_odds,
                run_detection, send_detections_today,
            )
            fetch_and_store_fixtures()
            fetch_and_store_odds()
            run_detection()
            send_detections_today(app)
            logger.info("[SCHEDULER] Morning OK")
        except Exception as e:
            logger.error("[SCHEDULER] Morning ERREUR: %s", e, exc_info=True)


def _evening(app):
    with app.app_context():
        logger.info("[SCHEDULER] Evening START")
        try:
            from app.scheduler.tasks import (
                update_results, validate_bets,
                compute_summaries, send_summary_today,
            )
            update_results()
            validate_bets()
            compute_summaries()
            send_summary_today(app)
            logger.info("[SCHEDULER] Evening OK")
        except Exception as e:
            logger.error("[SCHEDULER] Evening ERREUR: %s", e, exc_info=True)


def _stats(app):
    with app.app_context():
        try:
            from app.scheduler.tasks import refresh_team_stats
            refresh_team_stats()
        except Exception as e:
            logger.error("[SCHEDULER] Stats ERREUR: %s", e, exc_info=True)