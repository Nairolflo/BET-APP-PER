import logging
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from app.config import Config

logger = logging.getLogger(__name__)

HEADERS = {
    "x-apisports-key": Config.FOOTBALL_API_KEY,
    "x-apisports-host": Config.FOOTBALL_API_HOST,
}
BASE = Config.FOOTBALL_API_BASE
TIMEOUT = 15


def _get(endpoint: str, params: dict) -> Optional[dict]:
    """Safe GET wrapper with error handling."""
    url = f"{BASE}/{endpoint}"
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            logger.warning("API-Football error: %s", data["errors"])
            return None
        return data
    except requests.exceptions.Timeout:
        logger.error("API-Football timeout: %s", url)
    except requests.exceptions.RequestException as e:
        logger.error("API-Football request error: %s", e)
    return None


def fetch_fixtures_by_date(target_date: date, league_id: int, season: int) -> list:
    """Récupère les matchs d'une ligue pour une date donnée."""
    data = _get(
        "fixtures",
        {"league": league_id, "season": season, "date": str(target_date)},
    )
    return data.get("response", []) if data else []


def fetch_upcoming_fixtures(league_id: int, season: int, next_n: int = 10) -> list:
    data = _get("fixtures", {"league": league_id, "season": season, "next": next_n})
    return data.get("response", []) if data else []


def fetch_fixture_by_id(fixture_id: int) -> Optional[dict]:
    data = _get("fixtures", {"id": fixture_id})
    resp = data.get("response", []) if data else []
    return resp[0] if resp else None


def fetch_team_statistics(team_id: int, league_id: int, season: int) -> Optional[dict]:
    data = _get(
        "teams/statistics",
        {"team": team_id, "league": league_id, "season": season},
    )
    return data.get("response") if data else None


def fetch_head_to_head(home_id: int, away_id: int, last: int = 10) -> list:
    data = _get("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": last})
    return data.get("response", []) if data else []


def fetch_team_last_matches(team_id: int, last: int = 10) -> list:
    data = _get("fixtures", {"team": team_id, "last": last, "status": "FT"})
    return data.get("response", []) if data else []


def fetch_fixture_stats(fixture_id: int) -> list:
    data = _get("fixtures/statistics", {"fixture": fixture_id})
    return data.get("response", []) if data else []


def get_current_season(league_id: int) -> int:
    """Retourne la saison courante d'une ligue."""
    data = _get("leagues", {"id": league_id, "current": "true"})
    if not data:
        return datetime.utcnow().year
    try:
        seasons = data["response"][0]["seasons"]
        current = [s for s in seasons if s.get("current")]
        return current[0]["year"] if current else datetime.utcnow().year
    except (IndexError, KeyError):
        return datetime.utcnow().year