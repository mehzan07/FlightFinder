# app.py — FlightFinder main Flask app

import uuid
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect
from dotenv import load_dotenv
import os

# === Load environment variables ===
load_dotenv()

# === App configuration ===
IS_LOCAL = os.getenv("IS_LOCAL", "false").lower() == "true"
AFFILIATE_MARKER = os.getenv("AFFILIATE_MARKER")
FLASK_ENV = os.getenv("FLASK_ENV", "development")
PORT = int(os.getenv("PORT", 10000))
API_TOKEN = os.getenv("TRAVELPAYOUTS_API_TOKEN")
MARKER = os.getenv("TRAVELPAYOUTS_MARKER")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# === Initialize Flask app ===
app = Flask(__name__, static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "flightfinder-secret")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["ENV"] = FLASK_ENV
app.config["DEBUG"] = FLASK_ENV == "development"

# === Configure SQLAlchemy ===
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# === Initialize database ===
from database import db
db.init_app(app)

# === Import models AFTER db.init_app ===
from models import Booking

# === Register blueprints ===
from travel_ui import travel_bp
app.register_blueprint(travel_bp)

# === Create tables ===
with app.app_context():
    db.create_all()

# === Error handling ===
@app.errorhandler(500)
def internal_error(error):
    return f"Internal Server Error: {error}", 500

# === Logging ===
from config import get_logger
logger = get_logger(__name__)

logging.basicConfig(
    level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}


if IS_LOCAL:
    logging.info("Running in local mode.")

# === Dev-only Debugging ===
if __name__ == "__main__" and FLASK_ENV == "development":
    import debugpy
    debugpy.listen(("0.0.0.0", 5681))
    print("Waiting for debugger connection...")
    app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False, use_debugger=False)

# === Show Registered Routes ===
print("Registered routes:")
for rule in app.url_map.iter_rules():
    print(rule)