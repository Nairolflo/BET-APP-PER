"""
Client The Odds API v4
Rotation automatique sur jusqu'à 5 clés API.
"""
import logging

import requests

from app.config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"

# Correspondance ID football-data.org → sport key The Odds API
LEAGUE_SPORT_KEY = {
    2021: "soccer_epl",
    2014: "soccer_spain_la_liga",
    2015: "soccer_france_ligue_one",
    2002: "soccer_germany_bundesliga",
    2019: "soccer_italy_serie_a",
    2001: "soccer_uefa_champs_league",
    2018: "soccer_uefa_europa_league",
    2003: "soccer_netherlands_eredivisie",
    2017: "soccer_portugal_primeira_liga",
}

MARKET_MAP = {
    "1X2":          "h2h",
    "OVER_25":      "totals",
    "UNDER_25":     "totals",
    "OVER_15":      "totals",
    "UNDER_15":     "totals",
    "OVER_35":      "totals",
    "UNDER_35":     "totals",
    "OVER_45":      "totals",
    "UNDER_45":     "totals",
    "BTTS":    "btts",
}

BOOKMAKERS_FR = [
    "betclic_fr", "winamax_fr", "unibet_fr",
]

_key_index = 0


def _next_key() -> str | None:
    global _key_index
    keys = Config.ODDS_API_KEYS
    if not keys:
        return None
    key = keys[_key_index % len(keys)]
    _key_index += 1
    return key


def _get(endpoint: str, params: dict) -> list | dict | None:
    for _ in range(len(Config.ODDS_API_KEYS) or 1):
        key = _next_key()
        if not key:
            logger.warning("Aucune clé Odds API configurée.")
            return None
        try:
            params["apiKey"] = key
            r = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=15)
            remaining = r.headers.get("x-requests-remaining", "?")
            logger.info("Odds API — clé …%s | quota restant: %s", key[-4:], remaining)
            if r.status_code == 401 or remaining == "0":
                logger.warning("Clé épuisée — rotation vers la suivante.")
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error("Odds API erreur: %s", e)
    return None


def fetch_odds_for_league(league_id: int) -> list:
    sport_key = LEAGUE_SPORT_KEY.get(league_id)
    if not sport_key:
        logger.warning("Ligue %d non mappée dans Odds API.", league_id)
        return []
    data = _get(
        f"/sports/{sport_key}/odds",
        params={
            "regions":  "fr",
            "markets":  "h2h,totals",
            "oddsFormat": "decimal",
        },
    )
    return data if isinstance(data, list) else []


def get_best_odd(all_odds: list, home_name: str, away_name: str,
                 market: str, selection: str) -> tuple:
    api_market = MARKET_MAP.get(market)
    if not api_market:
        return 0.0, ""

    best_odd = 0.0
    best_bm  = ""

    home_lower = home_name.lower()
    away_lower = away_name.lower()

    for event in all_odds:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if not (home_lower in h or h in home_lower):
            continue
        if not (away_lower in a or a in away_lower):
            continue

        for bm in event.get("bookmakers", []):
            if bm.get("key") not in BOOKMAKERS_FR:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != api_market:
                    continue
                for outcome in mkt.get("outcomes", []):
                    if _matches_selection(outcome, market, selection):
                        odd = float(outcome.get("price", 0))
                        if odd > best_odd:
                            best_odd = odd
                            best_bm  = bm.get("key", "")
    return best_odd, best_bm


def _matches_selection(outcome: dict, market: str, selection: str) -> bool:
    name = outcome.get("name", "").upper()
    point = outcome.get("point")
    if market == "1X2":
        return {"HOME": "HOME", "DRAW": "DRAW", "AWAY": "AWAY"}.get(selection) == name
    elif market == "OVER_25":
        return name == "OVER" and point is not None and float(point) == 2.5
    elif market == "UNDER_25":
        return name == "UNDER" and point is not None and float(point) == 2.5
    elif market == "BTTS":
        return name == selection.upper()
    return False


def get_market_consensus(all_odds: list, home_name: str, away_name: str,
                         market: str, selection: str) -> float:
    """
    Calcule la fair odd consensus sur TOUS les bookmakers (FR + US/EU).
    Retourne la fair odd (ex: 1.72), ou 0.0 si aucune donnée.
    """
    api_market = MARKET_MAP.get(market)
    if not api_market:
        return 0.0

    home_lower = home_name.lower()
    away_lower = away_name.lower()
    probas = []

    for event in all_odds:
        h = event.get("home_team", "").lower()
        a = event.get("away_team", "").lower()
        if not (home_lower in h or h in home_lower):
            continue
        if not (away_lower in a or a in away_lower):
            continue
        for bm in event.get("bookmakers", []):
            if bm.get("key") not in BOOKMAKERS_FR + BOOKMAKERS_DISPLAY:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != api_market:
                    continue
                for outcome in mkt.get("outcomes", []):
                    if _matches_selection(outcome, market, selection):
                        odd = float(outcome.get("price", 0))
                        if odd > 1.0:
                            probas.append(1 / odd)

    if not probas:
        return 0.0

    avg_proba = sum(probas) / len(probas)
    return round(1 / avg_proba, 3)
