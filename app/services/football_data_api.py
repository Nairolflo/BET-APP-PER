"""
Client football-data.org v4
Récupère matchs, résultats et historique.
"""
import logging
from datetime import date, timedelta

import requests

from app.config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"


def _headers():
    return {"X-Auth-Token": Config.FOOTBALL_DATA_API_KEY}


def _get(endpoint: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error("football-data.org erreur %s : %s", endpoint, e)
        return {}


def fetch_upcoming_matches(league_id: int, days_ahead: int = 2) -> list:
    today = date.today()
    date_to = today + timedelta(days=days_ahead)
    data = _get(
        f"/competitions/{league_id}/matches",
        params={
            "dateFrom": today.isoformat(),
            "dateTo": date_to.isoformat(),
            "status": "SCHEDULED",
        },
    )
    return data.get("matches", [])


def fetch_finished_matches(league_id: int, days_back: int = 3) -> list:
    today = date.today()
    date_from = today - timedelta(days=days_back)
    data = _get(
        f"/competitions/{league_id}/matches",
        params={
            "dateFrom": date_from.isoformat(),
            "dateTo": today.isoformat(),
            "status": "FINISHED",
        },
    )
    return data.get("matches", [])


def fetch_team_matches(team_id: int, limit: int = 20) -> list:
    data = _get(f"/teams/{team_id}/matches", params={"limit": limit, "status": "FINISHED"})
    return data.get("matches", [])


def parse_match_status(status: str) -> str:
    mapping = {
        "SCHEDULED":   "SCHEDULED",
        "TIMED":       "SCHEDULED",
        "IN_PLAY":     "IN_PLAY",
        "PAUSED":      "IN_PLAY",
        "FINISHED":    "FINISHED",
        "CANCELLED":   "CANCELLED",
        "POSTPONED":   "CANCELLED",
        "SUSPENDED":   "CANCELLED",
        "AWARDED":     "FINISHED",
    }
    return mapping.get(status, "SCHEDULED")
