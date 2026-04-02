from flask import Blueprint, jsonify

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def index():
    return jsonify({"status": "ok", "app": "ValueBet FC"}), 200
