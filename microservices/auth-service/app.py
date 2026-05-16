"""
auth-service  —  JWT authentication and authorisation.
Exposes register / login / validate endpoints.
Port: 5001
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests
from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)

app = Flask(__name__)
metrics = PrometheusMetrics(app)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24
DB_URL = os.getenv("DB_SERVICE_URL", "http://db-service:5003")

# ── helpers ───────────────────────────────────────────────────────────────────


def _db_get(path):
    try:
        return requests.get(f"{DB_URL}{path}", timeout=5)
    except requests.RequestException as e:
        logging.error("db-service unreachable: %s", e)
        return None


def _db_post(path, payload):
    try:
        return requests.post(f"{DB_URL}{path}", json=payload, timeout=5)
    except requests.RequestException as e:
        logging.error("db-service unreachable: %s", e)
        return None


def _make_token(user_id, username):
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not all([username, email, password]):
        return jsonify({"error": "username, email and password are required"}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    r = _db_post("/users", {"username": username, "email": email, "password": hashed})

    if r is None:
        return jsonify({"error": "Service unavailable"}), 503
    if r.status_code == 201:
        return jsonify({"message": "User registered successfully"}), 201
    return jsonify({"error": "Registration failed", "detail": r.text}), r.status_code


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    r = _db_get(f"/users/by-username/{username}")
    if r is None or not r.ok:
        return jsonify({"error": "Invalid credentials"}), 401

    user = r.json()
    if not user.get("is_active"):
        return jsonify({"error": "Account inactive"}), 403

    try:
        if not bcrypt.checkpw(password.encode(), user["password"].encode()):
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception:
        return jsonify({"error": "Invalid credentials"}), 401

    token = _make_token(user["id"], user["username"])
    return jsonify({"token": token, "username": user["username"]})


@app.route("/auth/validate", methods=["POST"])
def validate():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        body = request.get_json() or {}
        token = body.get("token", "")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return jsonify({"valid": True, "user": payload})
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "Invalid token"}), 401


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
