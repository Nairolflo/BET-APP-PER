"""
Moteur de détection des value bets.
Calcule les probabilités estimées via score composite Elo + forme + stats,
modélisation de Poisson pour O/U, fréquences BTTS, et signal bête noire.
"""
import logging
import math
from typing import Optional
from scipy.stats import poisson

from app.config import Config
from app.models import Team, Match
from app.extensions import db

logger = logging.getLogger(__name__)

ELO_K = 32  # Facteur K Elo standard


# ─────────────────────────────────────────────
# Elo helpers
# ─────────────────────────────────────────────

def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_elo(
    rating_home: float, rating_away: float, result: str
) -> tuple[float, float]:
    """Mise à jour Elo après un match. result: 'H', 'D', 'A'"""
    ea = expected_score(rating_home, rating_away)
    eb = expected_score(rating_away, rating_home)
    if result == "H":
        sa, sb = 1.0, 0.0
    elif result == "A":
        sa, sb = 0.0, 1.0
    else:
        sa, sb = 0.5, 0.5
    new_home = rating_home + ELO_K * (sa - ea)
    new_away = rating_away + ELO_K * (sb - eb)
    return new_home, new_away


# ─────────────────────────────────────────────
# Forme récente
# ─────────────────────────────────────────────

def compute_form_score(matches: list, team_id: int, last_n: int = 5) -> float:
    """
    Calcule un score de forme entre 0 et 1 basé sur les N derniers matchs.
    Victoire = 1, Nul = 0.5, Défaite = 0.
    Pondération exponentielle: matchs récents comptent plus.
    """
    results = []
    for m in matches[-last_n:]:
        if m.home_team_id == team_id:
            if m.result == "H":
                results.append(1.0)
            elif m.result == "D":
                results.append(0.5)
            else:
                results.append(0.0)
        else:
            if m.result == "A":
                results.append(1.0)
            elif m.result == "D":
                results.append(0.5)
            else:
                results.append(0.0)

    if not results:
        return 0.5

    weights = [math.exp(0.3 * i) for i in range(len(results))]
    total_w = sum(weights)
    return sum(r * w for r, w in zip(results, weights)) / total_w


# ─────────────────────────────────────────────
# Score composite 1X2
# ─────────────────────────────────────────────

def compute_composite_score(
    home_team: Team,
    away_team: Team,
    home_recent: list,
    away_recent: list,
    h2h_matches: list,
) -> dict:
    """
    Retourne les probabilités estimées pour HOME, DRAW, AWAY.
    Composantes: Elo (40%), forme (25%), stats dom/ext (25%), H2H (10%).
    """
    # 1. Probabilité Elo
    elo_home_win = expected_score(home_team.elo_rating, away_team.elo_rating)
    # Avantage domicile: +50 Elo points en moyenne
    elo_home_win_adj = expected_score(
        home_team.elo_rating + 50, away_team.elo_rating
    )
    elo_away_win = 1 - elo_home_win_adj
    elo_draw = 0.26  # Fréquence historique de nuls (~26%)
    # Normalize
    raw_sum = elo_home_win_adj + elo_draw + elo_away_win
    elo_p = {
        "HOME": elo_home_win_adj / raw_sum,
        "DRAW": elo_draw / raw_sum,
        "AWAY": elo_away_win / raw_sum,
    }

    # 2. Score de forme
    form_home = compute_form_score(home_recent, home_team.id)
    form_away = compute_form_score(away_recent, away_team.id)
    form_total = form_home + form_away or 1
    form_p = {
        "HOME": form_home / form_total * 0.7 + 0.15,
        "DRAW": 0.30 - abs(form_home - form_away) * 0.2,
        "AWAY": form_away / form_total * 0.7 + 0.15,
    }
    # Normalize
    fs = sum(form_p.values())
    form_p = {k: v / fs for k, v in form_p.items()}

    # 3. Stats domicile/extérieur
    home_att = home_team.avg_goals_scored_home or 1.2
    home_def = home_team.avg_goals_conceded_home or 1.1
    away_att = away_team.avg_goals_scored_away or 1.0
    away_def = away_team.avg_goals_conceded_away or 1.2

    # Buts attendus via Poisson simple
    mu_home = home_att * (away_def / 1.1)
    mu_away = away_att * (home_def / 1.1)
    stats_p = _poisson_match_probs(mu_home, mu_away)

    # 4. H2H
    h2h_p = _compute_h2h_probs(h2h_matches, home_team.id, away_team.id)

    # Poids finaux
    weights = {"elo": 0.40, "form": 0.25, "stats": 0.25, "h2h": 0.10}
    final = {}
    for outcome in ["HOME", "DRAW", "AWAY"]:
        final[outcome] = (
            weights["elo"] * elo_p[outcome]
            + weights["form"] * form_p[outcome]
            + weights["stats"] * stats_p[outcome]
            + weights["h2h"] * h2h_p[outcome]
        )

    # Renormaliser
    total = sum(final.values())
    return {k: v / total for k, v in final.items()}


def _poisson_match_probs(mu_home: float, mu_away: float, max_goals: int = 8) -> dict:
    """Calcule P(home win), P(draw), P(away win) via distribution de Poisson."""
    p_home = p_draw = p_away = 0.0
    for g_h in range(max_goals + 1):
        for g_a in range(max_goals + 1):
            p = poisson.pmf(g_h, mu_home) * poisson.pmf(g_a, mu_away)
            if g_h > g_a:
                p_home += p
            elif g_h == g_a:
                p_draw += p
            else:
                p_away += p
    total = p_home + p_draw + p_away
    return {
        "HOME": p_home / total,
        "DRAW": p_draw / total,
        "AWAY": p_away / total,
    }


def _compute_h2h_probs(
    h2h_matches: list, home_id: int, away_id: int
) -> dict:
    """Probabilités basées sur les confrontations directes historiques."""
    if not h2h_matches:
        return {"HOME": 0.45, "DRAW": 0.26, "AWAY": 0.29}

    wins_home = wins_away = draws = 0
    for m in h2h_matches:
        if m.home_team_id == home_id:
            if m.result == "H":
                wins_home += 1
            elif m.result == "D":
                draws += 1
            else:
                wins_away += 1
        else:
            if m.result == "A":
                wins_home += 1
            elif m.result == "D":
                draws += 1
            else:
                wins_away += 1

    total = wins_home + draws + wins_away or 1
    return {
        "HOME": wins_home / total,
        "DRAW": draws / total,
        "AWAY": wins_away / total,
    }


# ─────────────────────────────────────────────
# Over/Under via Poisson
# ─────────────────────────────────────────────

def compute_over_under_probs(
    home_team: Team, away_team: Team, threshold: float = 2.5
) -> dict:
    """Retourne P(over), P(under) via Poisson."""
    mu_home = (
        home_team.avg_goals_scored_home + away_team.avg_goals_conceded_away
    ) / 2
    mu_away = (
        away_team.avg_goals_scored_away + home_team.avg_goals_conceded_home
    ) / 2
    mu_total = mu_home + mu_away

    p_over = 0.0
    p_under = 0.0
    for total_goals in range(20):
        p = poisson.pmf(total_goals, mu_total)
        if total_goals > threshold:
            p_over += p
        else:
            p_under += p

    return {"OVER": p_over, "UNDER": p_under}


# ─────────────────────────────────────────────
# BTTS
# ─────────────────────────────────────────────

def compute_btts_probs(home_team: Team, away_team: Team) -> dict:
    """
    P(BTTS YES) basée sur:
    - Fréquence BTTS de chaque équipe
    - Régularité offensive (avg buts marqués)
    - Fragilité défensive (clean sheet rate)
    """
    # Fréquence BTTS directe
    btts_home = getattr(home_team, "btts_rate_home", 0.5)
    btts_away = getattr(away_team, "btts_rate_away", 0.5)
    btts_base = (btts_home + btts_away) / 2

    # Probabilité de marquer (Poisson: 1 - P(0 buts))
    mu_home_score = home_team.avg_goals_scored_home or 1.2
    mu_away_score = away_team.avg_goals_scored_away or 1.0
    p_home_scores = 1 - poisson.pmf(0, mu_home_score)
    p_away_scores = 1 - poisson.pmf(0, mu_away_score)
    btts_poisson = p_home_scores * p_away_scores

    # Combinaison 60% fréquences, 40% Poisson
    btts_yes = 0.60 * btts_base + 0.40 * btts_poisson
    btts_yes = max(0.05, min(0.95, btts_yes))

    return {"YES": btts_yes, "NO": 1 - btts_yes}


# ─────────────────────────────────────────────
# Signal Bête Noire
# ─────────────────────────────────────────────

def detect_bete_noire(
    h2h_matches: list, challenger_id: int, opponent_id: int
) -> tuple[bool, float, str]:
    """
    Détecte si challenger_id réussit régulièrement contre opponent_id
    malgré une logique statistique potentiellement inverse.
    Retourne: (is_bete_noire, win_rate, explanation)
    """
    min_matches = Config.BETE_NOIRE_MIN_MATCHES
    threshold = Config.BETE_NOIRE_WIN_RATE

    challenger_wins = total = 0
    for m in h2h_matches:
        if m.result in ("H", "A", "D"):
            total += 1
            if m.home_team_id == challenger_id and m.result == "H":
                challenger_wins += 1
            elif m.away_team_id == challenger_id and m.result == "A":
                challenger_wins += 1

    if total < min_matches:
        return False, 0.0, ""

    win_rate = challenger_wins / total
    if win_rate >= threshold:
        explanation = (
            f"Bête noire détectée: {win_rate*100:.0f}% de victoires "
            f"sur les {total} dernières confrontations directes."
        )
        return True, win_rate, explanation

    return False, win_rate, ""


# ─────────────────────────────────────────────
# Calcul Edge + Value Bet
# ─────────────────────────────────────────────

def compute_edge(estimated_prob: float, odd: float) -> float:
    """Edge = prob_estimée - prob_implicite."""
    if odd <= 1.0:
        return -1.0
    implied_prob = 1.0 / odd
    return estimated_prob - implied_prob


def is_value_bet(edge: float) -> bool:
    return edge >= Config.EDGE_THRESHOLD


def build_reason(
    market: str,
    selection: str,
    estimated_prob: float,
    implied_prob: float,
    edge: float,
    form_home: float,
    form_away: float,
    bete_noire: bool,
    bete_noire_rate: float = 0.0,
) -> str:
    parts = [
        f"Marché {market} / {selection}.",
        f"Prob. estimée: {estimated_prob*100:.1f}% vs implicite: {implied_prob*100:.1f}% → Edge: +{edge*100:.1f}%.",
        f"Forme domicile: {form_home*100:.0f}% | Forme extérieur: {form_away*100:.0f}%.",
    ]
    if bete_noire:
        parts.append(
            f"⚠️ Signal bête noire actif ({bete_noire_rate*100:.0f}% H2H)."
        )
    return " ".join(parts)