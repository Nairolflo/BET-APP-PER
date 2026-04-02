import logging
from typing import Optional

import requests

from app.config import Config

logger = logging.getLogger(__name__)

BASE = Config.ODDS_API_BASE
API_KEY = Config.ODDS_API_KEY
TIMEOUT = 15

# Mapping sport_key par ligue (API-Football league_id → The Odds API sport_key)
LEAGUE_SPORT_MAP = {
    39: "soccer_epl",
    140: "soccer_spain_la_liga",
    78: "soccer_germany_bundesliga",
    61: "soccer_france_ligue_one",
    135: "soccer_italy_serie_a",
}

BOOKMAKERS = ",".join(Config.BOOKMAKERS)


def _get(endpoint: str, params: dict) -> Optional[dict]:
    url = f"{BASE}/{endpoint}"
    params["apiKey"] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("Odds API timeout: %s", url)
    except requests.exceptions.RequestException as e:
        logger.error("Odds API error: %s", e)
    return None


def fetch_odds_for_sport(league_id: int) -> list:
    """Récupère les cotes 1X2, O/U 2.5 et BTTS pour une ligue."""
    sport_key = LEAGUE_SPORT_MAP.get(league_id)
    if not sport_key:
        logger.warning("No sport key for league %s", league_id)
        return []

    results = []

    # Marché 1X2
    data = _get(
        f"sports/{sport_key}/odds",
        {
            "regions": "fr",
            "markets": "h2h",
            "bookmakers": BOOKMAKERS,
            "oddsFormat": "decimal",
        },
    )
    if data:
        results.extend(_parse_events(data, "1X2"))

    # Over/Under 2.5
    data = _get(
        f"sports/{sport_key}/odds",
        {
            "regions": "fr",
            "markets": "totals",
            "bookmakers": BOOKMAKERS,
            "oddsFormat": "decimal",
        },
    )
    if data:
        results.extend(_parse_events(data, "TOTALS"))

    # BTTS
    data = _get(
        f"sports/{sport_key}/odds",
        {
            "regions": "fr",
            "markets": "btts",
            "bookmakers": BOOKMAKERS,
            "oddsFormat": "decimal",
        },
    )
    if data:
        results.extend(_parse_events(data, "BTTS"))

    return results


def _parse_events(events: list, market_type: str) -> list:
    """Normalise les événements de l'API Odds en structure exploitable."""
    parsed = []
    for event in events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")
        event_id = event.get("id", "")

        for bm in event.get("bookmakers", []):
            bm_key = bm.get("key", "")
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    parsed.append(
                        {
                            "event_id": event_id,
                            "home_team": home,
                            "away_team": away,
                            "commence_time": commence,
                            "bookmaker": bm_key,
                            "market_type": market_type,
                            "market_key": market.get("key", ""),
                            "selection": outcome.get("name", ""),
                            "odd": float(outcome.get("price", 0)),
                            "point": outcome.get("point"),  # pour O/U
                        }
                    )
    return parsed


def get_best_odds(
    all_odds: list, home_team: str, away_team: str, market: str, selection: str
) -> tuple[float, str]:
    """Retourne la meilleure cote et le bookmaker pour un marché/sélection."""
    candidates = [
        o
        for o in all_odds
        if _fuzzy_match(o["home_team"], home_team)
        and _fuzzy_match(o["away_team"], away_team)
        and o["market_type"] == market
        and _normalize_selection(o["selection"]) == _normalize_selection(selection)
    ]
    if not candidates:
        return 0.0, ""
    best = max(candidates, key=lambda x: x["odd"])
    return best["odd"], best["bookmaker"]


def _fuzzy_match(a: str, b: str) -> bool:
    """Matching tolérant pour les noms d'équipes."""
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a in b or b in a or a[:6] == b[:6]


def _normalize_selection(sel: str) -> str:
    mapping = {
        "home": "HOME", "1": "HOME",
        "draw": "DRAW", "x": "DRAW",
        "away": "AWAY", "2": "AWAY",
        "over": "OVER",
        "under": "UNDER",
        "yes": "YES",
        "no": "NO",
    }
    return mapping.get(sel.lower(), sel.upper())