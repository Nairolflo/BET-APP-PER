import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/valuebetfc"
    ).replace("postgres://", "postgresql://")  # Railway fix
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # API-Football
    FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")
    FOOTBALL_API_HOST = os.environ.get(
        "FOOTBALL_API_HOST", "v3.football.api-sports.io"
    )
    FOOTBALL_API_BASE = f"https://{os.environ.get('FOOTBALL_API_HOST', 'v3.football.api-sports.io')}"

    # The Odds API
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
    ODDS_API_BASE = "https://api.the-odds-api.com/v4"

    # Telegram
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    # Detection
    EDGE_THRESHOLD = float(os.environ.get("VALUE_BET_EDGE_THRESHOLD", 0.05))
    KELLY_FRACTION = float(os.environ.get("KELLY_FRACTION", 0.25))
    MAX_STAKE_UNITS = float(os.environ.get("MAX_STAKE_UNITS", 3.0))
    UNIT_SIZE = float(os.environ.get("UNIT_SIZE", 10.0))

    # Leagues (IDs API-Football)
    MONITORED_LEAGUES = [
        int(x)
        for x in os.environ.get("MONITORED_LEAGUES", "39,140,78,61,135").split(",")
    ]

    # Bookmakers (The Odds API keys)
    BOOKMAKERS = ["winamax_fr", "betclic_fr", "unibet_fr"]

    # H2H bête noire: min matchs et seuil de victoire
    BETE_NOIRE_MIN_MATCHES = 4
    BETE_NOIRE_WIN_RATE = 0.65


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/valuebetfc_dev"
    ).replace("postgres://", "postgresql://")


class ProductionConfig(Config):
    pass


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}