"""
db-service  —  REST API wrapper over DbManager.
Runs migrations on startup, then exposes all CRUD operations.
Port: 5003
"""
import logging
import os
import sys
from datetime import date as date_type, datetime

from flask import Flask, abort, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

sys.path.insert(0, "/app")
from config import DATABASE_URL, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from migrate import run_migration
from services.dbmanager.DbManager import DbManager

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)

app = Flask(__name__)
metrics = PrometheusMetrics(app)
db: DbManager = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _client(c):
    return {"id": c.id, "name": c.name, "email": c.email,
            "num_plants": c.num_plants, "has_prod": c.has_prod}


def _plant(p, with_client=False):
    d = {"id": p.id, "name": p.name, "client_id": p.client_id, "max_pwr": p.max_pwr}
    if with_client:
        d["client_name"] = p.client.name if p.client else None
    return d


def _meas(m, with_plant=False):
    d = {"id": m.id, "plant_id": m.plant_id, "date": str(m.date),
         "interval": m.interval, "forecast_val": m.forecast_val, "prod_val": m.prod_val}
    if with_plant:
        d["plant_name"] = m.plant.name if m.plant else None
    return d


def _user(u):
    return {"id": u.id, "username": u.username, "email": u.email,
            "is_active": u.is_active, "created_at": str(u.created_at),
            "password": u.password}


def _price(p):
    return {"id": p.id, "date": str(p.date), "interval": p.interval,
            "positive_imbalance": p.positive_imbalance,
            "negative_imbalance": p.negative_imbalance}


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


# ── health ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── clients ───────────────────────────────────────────────────────────────────

@app.route("/clients", methods=["GET"])
def get_clients():
    return jsonify([_client(c) for c in db.get_all_clients()])


@app.route("/clients/<int:cid>", methods=["GET"])
def get_client(cid):
    c = db.get_client(cid)
    return jsonify(_client(c)) if c else abort(404)


@app.route("/clients/by-email/<path:email>", methods=["GET"])
def get_client_by_email(email):
    c = db.get_client_by_email(email)
    return jsonify(_client(c)) if c else abort(404)


@app.route("/clients", methods=["POST"])
def add_client():
    d = request.get_json()
    c = db.add_client(d["name"], d["email"],
                      num_plants=d.get("num_plants", 0),
                      has_prod=d.get("has_prod", False))
    return jsonify(_client(c)), 201


@app.route("/clients/<int:cid>", methods=["PUT"])
def update_client(cid):
    d = request.get_json()
    c = db.update_client(cid, **d)
    return jsonify(_client(c)) if c else abort(404)


@app.route("/clients/<int:cid>", methods=["DELETE"])
def delete_client(cid):
    return jsonify({"deleted": db.delete_client(cid)}) if db.delete_client(cid) else abort(404)


# ── plants ────────────────────────────────────────────────────────────────────

@app.route("/plants", methods=["GET"])
def get_plants():
    return jsonify([_plant(p) for p in db.get_all_plants()])


@app.route("/plants/with-client", methods=["GET"])
def get_plants_with_client():
    return jsonify([_plant(p, with_client=True) for p in db.get_all_plants_with_client()])


@app.route("/plants/by-client/<int:cid>", methods=["GET"])
def get_plants_by_client(cid):
    return jsonify([_plant(p) for p in db.get_plants_by_client(cid)])


@app.route("/plants/<int:pid>", methods=["GET"])
def get_plant(pid):
    p = db.get_plant(pid)
    return jsonify(_plant(p)) if p else abort(404)


@app.route("/plants", methods=["POST"])
def add_plant():
    d = request.get_json()
    p = db.add_plant(d["name"], d["client_id"], d["max_pwr"])
    return jsonify(_plant(p)), 201


@app.route("/plants/<int:pid>", methods=["PUT"])
def update_plant(pid):
    d = request.get_json()
    p = db.update_plant(pid, **d)
    return jsonify(_plant(p)) if p else abort(404)


@app.route("/plants/<int:pid>", methods=["DELETE"])
def delete_plant(pid):
    return jsonify({"deleted": True}) if db.delete_plant(pid) else abort(404)


# ── measurements ──────────────────────────────────────────────────────────────

@app.route("/measurements", methods=["GET"])
def get_measurements():
    return jsonify([_meas(m) for m in db.get_all_measurements()])


@app.route("/measurements/by-plant-date", methods=["GET"])
def get_measurements_by_plant_date():
    plant_id = request.args.get("plant_id", type=int)
    date_str = request.args.get("date")
    if not plant_id or not date_str:
        abort(400)
    d = _parse_date(date_str)
    measurements = db.get_measurements_by_plant_and_date_eager(plant_id, d)
    return jsonify([_meas(m, with_plant=True) for m in measurements])


@app.route("/measurements", methods=["POST"])
def add_measurement():
    d = request.get_json()
    m = db.add_measurement(d["plant_id"], _parse_date(d["date"]), d["interval"],
                           forecast_val=d.get("forecast_val"),
                           prod_val=d.get("prod_val"))
    return jsonify(_meas(m)), 201


@app.route("/measurements/upsert", methods=["POST"])
def upsert_measurement():
    d = request.get_json()
    m = db.upsert_measurement(d["plant_id"], _parse_date(d["date"]), d["interval"],
                              forecast_val=d.get("forecast_val"),
                              prod_val=d.get("prod_val"))
    return jsonify(_meas(m))


@app.route("/measurements/<int:mid>", methods=["DELETE"])
def delete_measurement(mid):
    return jsonify({"deleted": True}) if db.delete_measurement(mid) else abort(404)


# ── users ─────────────────────────────────────────────────────────────────────

@app.route("/users", methods=["GET"])
def get_users():
    return jsonify([_user(u) for u in db.get_all_users()])


@app.route("/users/<int:uid>", methods=["GET"])
def get_user(uid):
    u = db.get_user(uid)
    return jsonify(_user(u)) if u else abort(404)


@app.route("/users/by-username/<username>", methods=["GET"])
def get_user_by_username(username):
    u = db.get_user_by_username(username)
    return jsonify(_user(u)) if u else abort(404)


@app.route("/users", methods=["POST"])
def add_user():
    d = request.get_json()
    u = db.add_user(d["username"], d["email"], d["password"])
    return jsonify(_user(u)), 201


@app.route("/users/<int:uid>", methods=["PUT"])
def update_user(uid):
    d = request.get_json()
    u = db.update_user(uid, **d)
    return jsonify(_user(u)) if u else abort(404)


@app.route("/users/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    return jsonify({"deleted": True}) if db.delete_user(uid) else abort(404)


# ── imbalance prices ──────────────────────────────────────────────────────────

@app.route("/imbalance-prices", methods=["GET"])
def get_imbalance_prices():
    return jsonify([_price(p) for p in db.get_all_imbalance_prices()])


@app.route("/imbalance-prices/by-date/<date_str>", methods=["GET"])
def get_imbalance_prices_by_date(date_str):
    d = _parse_date(date_str)
    return jsonify([_price(p) for p in db.get_imbalance_prices_by_date(d)])


@app.route("/imbalance-prices", methods=["POST"])
def add_imbalance_price():
    d = request.get_json()
    p = db.add_imbalance_price(_parse_date(d["date"]), d["interval"],
                               positive_imbalance=d.get("positive_imbalance"),
                               negative_imbalance=d.get("negative_imbalance"))
    return jsonify(_price(p)), 201


@app.route("/imbalance-prices/upsert", methods=["POST"])
def upsert_imbalance_price():
    d = request.get_json()
    p = db.upsert_imbalance_price(_parse_date(d["date"]), d["interval"],
                                  positive_imbalance=d.get("positive_imbalance"),
                                  negative_imbalance=d.get("negative_imbalance"))
    return jsonify(_price(p))


@app.route("/imbalance-prices/<int:pid>", methods=["DELETE"])
def delete_imbalance_price(pid):
    return jsonify({"deleted": True}) if db.delete_imbalance_price(pid) else abort(404)


# ── startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = run_migration()
    app.run(host="0.0.0.0", port=5003)
