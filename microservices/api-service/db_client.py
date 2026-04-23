"""
HTTP client that mirrors the DbManager interface for use inside api-service.
Returns SimpleNamespace objects so Jinja2 templates keep working with dot notation.
"""
import os
from types import SimpleNamespace

import requests

DB_URL = os.getenv("DB_SERVICE_URL", "http://db-service:5003")
_TIMEOUT = 10


# ── conversion helpers ────────────────────────────────────────────────────────

def _ns(d: dict) -> SimpleNamespace:
    if not isinstance(d, dict):
        return d
    obj = SimpleNamespace()
    for k, v in d.items():
        setattr(obj, k, _ns(v) if isinstance(v, dict) else v)
    return obj


def _ns_list(lst: list) -> list:
    return [_ns(d) for d in lst]


def _get(path, **params):
    r = requests.get(f"{DB_URL}{path}", params=params or None, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path, payload):
    r = requests.post(f"{DB_URL}{path}", json=payload, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _put(path, payload):
    r = requests.put(f"{DB_URL}{path}", json=payload, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _delete(path):
    r = requests.delete(f"{DB_URL}{path}", timeout=_TIMEOUT)
    return r.ok


# ── clients ───────────────────────────────────────────────────────────────────

def get_all_clients():
    return _ns_list(_get("/clients"))


def get_client(client_id):
    try:
        return _ns(_get(f"/clients/{client_id}"))
    except requests.HTTPError:
        return None


def add_client(name, email, num_plants=0, has_prod=False):
    return _ns(_post("/clients", {"name": name, "email": email,
                                  "num_plants": num_plants, "has_prod": has_prod}))


def update_client(client_id, **kwargs):
    try:
        return _ns(_put(f"/clients/{client_id}", kwargs))
    except requests.HTTPError:
        return None


def delete_client(client_id):
    return _delete(f"/clients/{client_id}")


# ── plants ────────────────────────────────────────────────────────────────────

def get_all_plants():
    return _ns_list(_get("/plants"))


def get_all_plants_with_client():
    """Returns plant objects with a nested .client attribute for template use."""
    raw = _get("/plants/with-client")
    result = []
    for p in raw:
        plant = _ns(p)
        plant.client = SimpleNamespace(name=p.get("client_name")) if p.get("client_name") else None
        result.append(plant)
    return result


def get_plant(plant_id):
    try:
        return _ns(_get(f"/plants/{plant_id}"))
    except requests.HTTPError:
        return None


def add_plant(name, client_id, max_pwr):
    return _ns(_post("/plants", {"name": name, "client_id": client_id, "max_pwr": max_pwr}))


def update_plant(plant_id, **kwargs):
    try:
        return _ns(_put(f"/plants/{plant_id}", kwargs))
    except requests.HTTPError:
        return None


def delete_plant(plant_id):
    return _delete(f"/plants/{plant_id}")


# ── measurements ──────────────────────────────────────────────────────────────

def get_all_measurements():
    return _ns_list(_get("/measurements"))


def get_measurements_by_plant_and_date(plant_id, date_str):
    """Returns measurement objects with a nested .plant attribute."""
    raw = _get("/measurements/by-plant-date", plant_id=plant_id, date=date_str)
    result = []
    for m in raw:
        meas = _ns(m)
        meas.plant = SimpleNamespace(name=m.get("plant_name")) if m.get("plant_name") else None
        result.append(meas)
    return result


# ── users ─────────────────────────────────────────────────────────────────────

def get_all_users():
    return _ns_list(_get("/users"))


# ── imbalance prices ──────────────────────────────────────────────────────────

def get_all_imbalance_prices():
    return _ns_list(_get("/imbalance-prices"))


def get_imbalance_prices_by_date(date_str):
    return _ns_list(_get(f"/imbalance-prices/by-date/{date_str}"))
