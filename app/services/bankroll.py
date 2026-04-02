"""
Logique de gestion de bankroll — Kelly fractionné avec plafond.
"""
from app.config import Config


def kelly_stake(
    estimated_prob: float,
    odd: float,
    fraction: float = None,
    max_units: float = None,
) -> float:
    """
    Calcule la mise en unités via Kelly fractionné.

    Kelly = (p * b - (1 - p)) / b  où b = odd - 1
    Stake = Kelly * fraction * bankroll (en unités normalisées → 1 unité = 1)
    """
    fraction = fraction or Config.KELLY_FRACTION
    max_units = max_units or Config.MAX_STAKE_UNITS

    b = odd - 1.0
    if b <= 0 or estimated_prob <= 0:
        return 0.0

    kelly = (estimated_prob * b - (1 - estimated_prob)) / b
    if kelly <= 0:
        return 0.0

    stake = kelly * fraction
    # Arrondi à 0.25 unité, plafonné
    stake = round(stake * 4) / 4
    return min(stake, max_units)


def compute_confidence(
    edge: float,
    stake: float,
    h2h_count: int,
    form_score: float,
) -> float:
    """
    Score de confiance normalisé [0, 1].
    Basé sur l'edge, la mise, le nombre de H2H disponibles et la forme.
    """
    edge_score = min(edge / 0.20, 1.0) * 0.40
    stake_score = min(stake / Config.MAX_STAKE_UNITS, 1.0) * 0.20
    h2h_score = min(h2h_count / 10, 1.0) * 0.20
    form_score_w = form_score * 0.20
    return round(edge_score + stake_score + h2h_score + form_score_w, 3)