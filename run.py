import logging
from app import create_app
from app.extensions import db

logging.basicConfig(level=logging.INFO)
app = create_app()

with app.app_context():
    try:
        db.create_all()
        logging.info("✅ Tables créées/vérifiées.")
    except Exception as e:
        logging.error("⚠️ DB non disponible: %s", e)

if __name__ == "__main__":
    app.run()
