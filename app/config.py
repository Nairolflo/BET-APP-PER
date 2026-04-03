import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = False

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/valuebetfc"
    ).replace("postgres://", "postgresql://")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Football-data.org (pas API-Football)
    FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

    # The Odds API — jusqu'à 5 clés
    ODDS_API_KEYS = [
        k for k in [
            os.environ.get("ODDS_API_KEY_1"),
            os.environ.get("ODDS_API_KEY_2"),
            os.environ.get("ODDS_API_KEY_3"),
            os.environ.get("ODDS_API_KEY_4"),
            os.environ.get("ODDS_API_KEY_5"),
        ] if k
    ]

    # Telegram
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    # Détection
    EDGE_THRESHOLD = float(os.environ.get("VALUE_BET_EDGE_THRESHOLD", 0.05))
    KELLY_FRACTION = float(os.environ.get("KELLY_FRACTION", 0.25))
    MAX_STAKE_UNITS = float(os.environ.get("MAX_STAKE_UNITS", 3.0))
    UNIT_SIZE = float(os.environ.get("UNIT_SIZE", 10.0))

    # Ligues football-data.org
    MONITORED_LEAGUES = [
        int(x)
        for x in os.environ.get("MONITORED_LEAGUES", "2021,2014,2002,2015,2019,2001,2003,2017").split(",")
    ]

    BETE_NOIRE_MIN_MATCHES = 4
    BETE_NOIRE_WIN_RATE = 0.65


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    pass


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": ProductionConfig,
}
