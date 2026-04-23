"""
api-service  —  Flask web dashboard.
All DB operations go through db-service via HTTP (db_client).
Port: 5000
"""
import logging
import os
from datetime import datetime

from flask import Flask, Blueprint, flash, redirect, render_template, request, url_for
from prometheus_flask_exporter import PrometheusMetrics
from waitress import serve

import db_client as db

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "energoflow-dev-secret-key")
metrics = PrometheusMetrics(app)

bp = Blueprint("main", __name__)


# ── dashboard ─────────────────────────────────────────────────────────────────

@bp.route("/")
def dashboard():
    stats = {
        "clients": len(db.get_all_clients()),
        "plants": len(db.get_all_plants()),
        "measurements": len(db.get_all_measurements()),
        "imbalance_prices": len(db.get_all_imbalance_prices()),
        "users": len(db.get_all_users()),
    }
    recent_clients = db.get_all_clients()[:5]
    return render_template("dashboard.html", stats=stats, recent_clients=recent_clients)


# ── clients ───────────────────────────────────────────────────────────────────

@bp.route("/clients")
def clients_list():
    return render_template("clients_list.html", clients=db.get_all_clients())


@bp.route("/clients/add", methods=["GET", "POST"])
def clients_add():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        num_plants = int(request.form.get("num_plants", 0))
        has_prod = "has_prod" in request.form
        try:
            db.add_client(name, email, num_plants=num_plants, has_prod=has_prod)
            flash(f"Client '{name}' adăugat cu succes!", "success")
            return redirect(url_for("main.clients_list"))
        except Exception as e:
            flash(f"Eroare: {e}", "error")
    return render_template("clients_form.html", client=None)


@bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
def clients_edit(client_id):
    client = db.get_client(client_id)
    if not client:
        flash("Client negăsit.", "error")
        return redirect(url_for("main.clients_list"))
    if request.method == "POST":
        try:
            db.update_client(
                client_id,
                name=request.form["name"].strip(),
                email=request.form["email"].strip(),
                num_plants=int(request.form.get("num_plants", 0)),
                has_prod="has_prod" in request.form,
            )
            flash("Client actualizat!", "success")
            return redirect(url_for("main.clients_list"))
        except Exception as e:
            flash(f"Eroare: {e}", "error")
    return render_template("clients_form.html", client=client)


@bp.route("/clients/<int:client_id>/delete", methods=["POST"])
def clients_delete(client_id):
    if db.delete_client(client_id):
        flash("Client șters.", "success")
    else:
        flash("Client negăsit.", "error")
    return redirect(url_for("main.clients_list"))


# ── plants ────────────────────────────────────────────────────────────────────

@bp.route("/plants")
def plants_list():
    return render_template("plants_list.html", plants=db.get_all_plants_with_client())


@bp.route("/plants/add", methods=["GET", "POST"])
def plants_add():
    if request.method == "POST":
        name = request.form["name"].strip()
        client_id = int(request.form["client_id"])
        max_pwr = float(request.form["max_pwr"])
        try:
            db.add_plant(name, client_id, max_pwr)
            flash(f"Parc '{name}' adăugat cu succes!", "success")
            return redirect(url_for("main.plants_list"))
        except Exception as e:
            flash(f"Eroare: {e}", "error")
    return render_template("plants_form.html", plant=None, clients=db.get_all_clients())


@bp.route("/plants/<int:plant_id>/edit", methods=["GET", "POST"])
def plants_edit(plant_id):
    plant = db.get_plant(plant_id)
    if not plant:
        flash("Parc negăsit.", "error")
        return redirect(url_for("main.plants_list"))
    if request.method == "POST":
        try:
            db.update_plant(
                plant_id,
                name=request.form["name"].strip(),
                client_id=int(request.form["client_id"]),
                max_pwr=float(request.form["max_pwr"]),
            )
            flash("Parc actualizat!", "success")
            return redirect(url_for("main.plants_list"))
        except Exception as e:
            flash(f"Eroare: {e}", "error")
    return render_template("plants_form.html", plant=plant, clients=db.get_all_clients())


@bp.route("/plants/<int:plant_id>/delete", methods=["POST"])
def plants_delete(plant_id):
    if db.delete_plant(plant_id):
        flash("Parc șters.", "success")
    else:
        flash("Parc negăsit.", "error")
    return redirect(url_for("main.plants_list"))


# ── measurements ──────────────────────────────────────────────────────────────

@bp.route("/measurements")
def measurements_view():
    plants = db.get_all_plants()
    selected_plant = request.args.get("plant_id", type=int)
    selected_date = request.args.get("date", "")
    measurements = []
    if selected_plant and selected_date:
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")  # validate format
            measurements = db.get_measurements_by_plant_and_date(selected_plant, selected_date)
        except ValueError:
            flash("Format dată invalid.", "error")
    return render_template(
        "measurements.html",
        plants=plants,
        measurements=measurements,
        selected_plant=selected_plant,
        selected_date=selected_date,
    )


# ── imbalance prices ──────────────────────────────────────────────────────────

@bp.route("/imbalance")
def imbalance_view():
    selected_date = request.args.get("date", "")
    prices = []
    if selected_date:
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")
            prices = db.get_imbalance_prices_by_date(selected_date)
        except ValueError:
            flash("Format dată invalid.", "error")
    return render_template(
        "imbalance_prices.html",
        prices=prices,
        selected_date=selected_date,
    )


app.register_blueprint(bp)

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)
