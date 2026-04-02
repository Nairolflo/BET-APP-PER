"""
ValueBet FC — Point d'entrée principal.
  - Dev local  : python run.py
  - Production : gunicorn run:app (via Procfile / railway.toml)
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n⚽ ValueBet FC démarré → http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)