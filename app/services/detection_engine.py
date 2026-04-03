"""
Moteur de détection des value bets.
Probabilités via Elo + forme + Poisson (pur Python) + H2H.
Signal bête noire.
"""
import logging
import math

from app.config import Config

logger = logging.getLogger(__name__)

ELO_K = 32
HOME_ADVANTAGE_ELO = 50


# ── Poisson pur Python (sans scipy) ───────────────────────────────────

def _poisson_pmf(k: int, mu: float) -> float:
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    return (mu ** k) * math.exp(-mu) / math.factorial(k)


# ── Elo ───────────────────────────────────────────────────────────────

def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def update_elo(rating_home: float, rating_away: float, result: str) -> tuple:
    ea = expected_score(rating_home, rating_away)
    eb = 1 - ea
    sa, sb = {"H": (1.0, 0.0), "D": (0.5, 0.5), "A": (0.0, 1.0)}.get(result, (0.5, 0.5))
    return rating_home + ELO_K * (sa - ea), rating_away + ELO_K * (sb - eb)


# ── Forme récente ─────────────────────────────────────────────────────

def compute_form_score(matches: list, team_id: int, last_n: int = 5) -> float:
    results = []
    for m in matches[-last_n:]:
        if m.home_team_id == team_id:
            pts = {"H": 1.0, "D": 0.5, "A": 0.0}.get(m.result or "", 0.5)
        else:
            pts = {"A": 1.0, "D": 0.5, "H": 0.0}.get(m.result or "", 0.5)
        results.append(pts)
    if not results:
        return 0.5
    weights = [math.exp(0.3 * i) for i in range(len(results))]
    total_w = sum(weights)
    return sum(r * w for r, w in zip(results, weights)) / total_w


# ── Poisson match ─────────────────────────────────────────────────────

def poisson_match_probs(mu_home: float, mu_away: float, max_goals: int = 9) -> dict:
    p_home = p_draw = p_away = 0.0
    for gh in range(max_goals + 1):
        for ga in range(max_goals + 1):
            p = _poisson_pmf(gh, max(mu_home, 0.01)) * _poisson_pmf(ga, max(mu_away, 0.01))
            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p
    total = p_home + p_draw + p_away or 1
    return {"HOME": p_home / total, "DRAW": p_draw / total, "AWAY": p_away / total}


# ── H2H ───────────────────────────────────────────────────────────────

def compute_h2h_probs(h2h_matches: list, home_id: int, away_id: int) -> dict:
    if not h2h_matches:
        return {"HOME": 0.45, "DRAW": 0.26, "AWAY": 0.29}
    wh = wd = wa = 0
    for m in h2h_matches:
        if m.home_team_id == home_id:
            if m.result == "H": wh += 1
            elif m.result == "D": wd += 1
            else: wa += 1
        else:
            if m.result == "A": wh += 1
            elif m.result == "D": wd += 1
            else: wa += 1
    t = wh + wd + wa or 1
    return {"HOME": wh / t, "DRAW": wd / t, "AWAY": wa / t}


# ── Score composite 1X2 ───────────────────────────────────────────────

def compute_1x2_probs(home_team, away_team, home_recent, away_recent, h2h_matches) -> dict:
    elo_home = expected_score(home_team.elo_rating + HOME_ADVANTAGE_ELO, away_team.elo_rating)
    elo_away = 1 - elo_home
    elo_draw = 0.265
    s = elo_home + elo_draw + elo_away
    elo_p = {"HOME": elo_home / s, "DRAW": elo_draw / s, "AWAY": elo_away / s}

    fh = compute_form_score(home_recent, home_team.id)
    fa = compute_form_score(away_recent, away_team.id)
    ft = fh + fa or 1
    raw_form = {
        "HOME": fh / ft * 0.70 + 0.15,
        "DRAW": 0.28 - abs(fh - fa) * 0.15,
        "AWAY": fa / ft * 0.70 + 0.15,
    }
    fs = sum(raw_form.values())
    form_p = {k: v / fs for k, v in raw_form.items()}

    mu_h = (home_team.avg_goals_scored_home or 1.3) * ((away_team.avg_goals_conceded_away or 1.1) / 1.1)
    mu_a = (away_team.avg_goals_scored_away or 1.0) * ((home_team.avg_goals_conceded_home or 1.1) / 1.1)
    stats_p = poisson_match_probs(mu_h, mu_a)

    h2h_p = compute_h2h_probs(h2h_matches, home_team.id, away_team.id)

    w = {"elo": 0.40, "form": 0.25, "stats": 0.25, "h2h": 0.10}
    final = {}
    for o in ["HOME", "DRAW", "AWAY"]:
        final[o] = (
            w["elo"] * elo_p[o] + w["form"] * form_p[o]
            + w["stats"] * stats_p[o] + w["h2h"] * h2h_p[o]
        )
    t = sum(final.values())
    return {k: v / t for k, v in final.items()}


# ── Over/Under ────────────────────────────────────────────────────────

def compute_ou_probs(home_team, away_team, threshold: float = 2.5,
                     half: bool = False,
                     home_recent: list = None,
                     away_recent: list = None,
                     h2h_matches: list = None) -> dict:
    """Poisson Over/Under — fusionne stats générales + forme récente + H2H.
    Retourne TOUS les thresholds (0.5, 1.5, 2.5, 3.5, 4.5) FT ou HT.
    """
    # ── 1. mu de base (stats générales) ──────────────────────────────
    mu_h = ((home_team.avg_goals_scored_home or 1.3) + (away_team.avg_goals_conceded_away or 1.1)) / 2
    mu_a = ((away_team.avg_goals_scored_away or 1.0) + (home_team.avg_goals_conceded_home or 1.1)) / 2

    # ── 2. ajustement forme récente ───────────────────────────────────
    def _avg_goals_recent(matches, team_id):
        if not matches:
            return None
        goals = []
        for m in matches[-5:]:
            g = m.home_goals if m.home_team_id == team_id else m.away_goals
            if g is not None:
                goals.append(g)
        return sum(goals) / len(goals) if goals else None

    if home_recent:
        fg = _avg_goals_recent(home_recent, home_team.id)
        if fg is not None:
            mu_h = 0.6 * mu_h + 0.4 * fg
    if away_recent:
        fg = _avg_goals_recent(away_recent, away_team.id)
        if fg is not None:
            mu_a = 0.6 * mu_a + 0.4 * fg

    mu_total = max(mu_h + mu_a, 0.1)

    # ── 3. ajustement H2H ─────────────────────────────────────────────
    if h2h_matches and len(h2h_matches) >= 3:
        h2h_goals = [
            (m.home_goals or 0) + (m.away_goals or 0)
            for m in h2h_matches if m.home_goals is not None
        ]
        if h2h_goals:
            mu_h2h = sum(h2h_goals) / len(h2h_goals)
            mu_total = 0.5 * mu_total + 0.5 * mu_h2h

    # ── 4. mi-temps ───────────────────────────────────────────────────
    if half:
        mu_total = mu_total / 2

    # ── 5. calcul pour tous les thresholds ───────────────────────────
    def _p_over(thr):
        return round(sum(_poisson_pmf(g, mu_total) for g in range(int(thr) + 1, 20)), 4)

    prefix = "HT_" if half else ""
    result = {}
    for thr, label in [(0.5, "05"), (1.5, "15"), (2.5, "25"), (3.5, "35"), (4.5, "45")]:
        p = _p_over(thr)
        result[f"{prefix}OVER_{label}"]  = p
        result[f"{prefix}UNDER_{label}"] = round(1 - p, 4)

    # Aliases rétrocompat pour l'appel threshold= unique
    key_label = {0.5: "05", 1.5: "15", 2.5: "25", 3.5: "35", 4.5: "45"}.get(threshold, "25")
    result["OVER"]  = result.get(f"{prefix}OVER_{key_label}",  result.get(f"{prefix}OVER_25",  0))
    result["UNDER"] = result.get(f"{prefix}UNDER_{key_label}", result.get(f"{prefix}UNDER_25", 0))
    return result


# ── BTTS ──────────────────────────────────────────────────────────────

def compute_btts_probs(home_team, away_team) -> dict:
    btts_freq = ((home_team.btts_rate_home or 0.5) + (away_team.btts_rate_away or 0.5)) / 2
    mu_h = home_team.avg_goals_scored_home or 1.3
    mu_a = away_team.avg_goals_scored_away or 1.0
    p_h_scores = 1 - _poisson_pmf(0, max(mu_h, 0.01))
    p_a_scores = 1 - _poisson_pmf(0, max(mu_a, 0.01))
    btts_poisson = p_h_scores * p_a_scores
    btts_yes = max(0.05, min(0.95, 0.60 * btts_freq + 0.40 * btts_poisson))
    return {"YES": btts_yes, "NO": 1 - btts_yes}


# ── Bête Noire ────────────────────────────────────────────────────────

def detect_bete_noire(h2h_matches: list, challenger_id: int) -> tuple:
    mn = Config.BETE_NOIRE_MIN_MATCHES
    thresh = Config.BETE_NOIRE_WIN_RATE
    wins = total = 0
    for m in h2h_matches:
        total += 1
        if (m.home_team_id == challenger_id and m.result == "H") or \
           (m.away_team_id == challenger_id and m.result == "A"):
            wins += 1
    if total < mn:
        return False, 0.0, ""
    rate = wins / total
    if rate >= thresh:
        return True, rate, f"Bête noire: {rate*100:.0f}% sur {total} confrontations."
    return False, rate, ""


# ── Edge & Bankroll ───────────────────────────────────────────────────

def compute_edge(estimated_prob: float, odd: float) -> float:
    if odd <= 1.0:
        return -1.0
    return estimated_prob - (1.0 / odd)


def is_value_bet(edge: float) -> bool:
    return edge >= Config.EDGE_THRESHOLD


def kelly_stake(estimated_prob: float, odd: float) -> float:
    b = odd - 1.0
    if b <= 0 or estimated_prob <= 0:
        return 0.0
    kelly = (estimated_prob * b - (1 - estimated_prob)) / b
    if kelly <= 0:
        return 0.0
    stake = round(kelly * Config.KELLY_FRACTION * 4) / 4
    return min(stake, Config.MAX_STAKE_UNITS)


def compute_confidence(edge: float, stake: float, h2h_count: int, avg_form: float) -> float:
    e = min(edge / 0.20, 1.0) * 0.40
    s = min(stake / Config.MAX_STAKE_UNITS, 1.0) * 0.20
    h = min(h2h_count / 10, 1.0) * 0.20
    f = avg_form * 0.20
    return round(e + s + h + f, 3)


def build_reason(market, selection, est_prob, implied_prob, edge,
                 fh, fa, is_bn, bn_rate=0.0) -> str:
    parts = [
        f"Marché {market}/{selection}.",
        f"Prob. estimée {est_prob*100:.1f}% vs implicite {implied_prob*100:.1f}% → Edge +{edge*100:.1f}%.",
        f"Forme dom. {fh*100:.0f}% | ext. {fa*100:.0f}%.",
    ]
    if is_bn:
        parts.append(f"⚠️ Bête noire ({bn_rate*100:.0f}% H2H).")
    return " ".join(parts)
