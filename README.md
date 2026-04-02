# ⚽ ValueBet FC

Système automatique de détection de value bets football.

## Stack
- **Backend**: Flask + SQLAlchemy + PostgreSQL
- **Données matchs**: football-data.org (v4)
- **Cotes**: The Odds API (rotation jusqu'à 5 clés)
- **Scheduler**: APScheduler (cron jobs)
- **Notifications**: python-telegram-bot
- **Deploy**: Railway

## Installation rapide

```bash
git clone <votre-repo>
cd valuebetfc
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec vos clés API
flask db upgrade
python run.py
```

## Configuration `.env`

| Variable | Description |
|---|---|
| `FOOTBALL_DATA_API_KEY` | Clé football-data.org |
| `ODDS_API_KEY_1` à `_5` | Clés The Odds API (1 minimum, 5 max) |
| `TELEGRAM_BOT_TOKEN` | Token @BotFather |
| `TELEGRAM_CHAT_ID` | Votre chat ID Telegram |
| `DATABASE_URL` | URL PostgreSQL |

## Pipelines automatiques

| Heure | Action |
|---|---|
| 06h00 | Refresh stats équipes + Elo |
| 07h00 | Fetch matchs + cotes + détection + Telegram |
| 23h30 | Résultats + validation + bilan Telegram |

## Déclenchement manuel

```bash
curl -X POST http://localhost:5000/api/trigger/morning
curl -X POST http://localhost:5000/api/trigger/evening
```

## Marchés détectés

- **1X2** : Victoire domicile / Nul / Victoire extérieur
- **Over/Under 2.5** : Modélisation Poisson
- **BTTS** : Les deux équipes marquent
- **Bête Noire** : Signal H2H historique

## Deploy sur Railway

1. Push sur GitHub
2. Nouveau projet Railway → Deploy from GitHub
3. Ajouter PostgreSQL plugin
4. Variables d'environnement dans Railway dashboard
5. `railway up`