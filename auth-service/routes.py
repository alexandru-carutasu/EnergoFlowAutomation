from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import logging

from config import (
    DATABASE_URL,
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRY_MINUTES,
    REFRESH_TOKEN_EXPIRY_DAYS,
)
from models import User

logger = logging.getLogger(__name__)
bp = Blueprint("auth", __name__, url_prefix="/auth")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine)


def _make_access_token(user_id: int, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _make_refresh_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with SessionFactory() as s:
        if s.scalars(select(User).where(User.username == username)).first():
            return jsonify({"error": "username already taken"}), 409
        if s.scalars(select(User).where(User.email == email)).first():
            return jsonify({"error": "email already registered"}), 409

        user = User(username=username, email=email, password=hashed)
        s.add(user)
        s.commit()
        s.refresh(user)
        logger.info("Registered new user: %s", username)
        return jsonify({"id": user.id, "username": user.username}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with SessionFactory() as s:
        user = s.scalars(select(User).where(User.username == username)).first()
        if not user or not bcrypt.checkpw(password.encode(), user.password.encode()):
            return jsonify({"error": "invalid credentials"}), 401
        if not user.is_active:
            return jsonify({"error": "account deactivated"}), 403

        access_token = _make_access_token(user.id, user.username)
        refresh_token = _make_refresh_token(user.id)
        logger.info("User logged in: %s", username)
        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        }), 200


@bp.get("/verify")
def verify():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "missing or malformed Authorization header"}), 401

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("not an access token")
        return jsonify({
            "valid": True,
            "user_id": payload["sub"],
            "username": payload["username"],
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "token expired"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": str(e)}), 401


@bp.post("/refresh")
def refresh():
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token", "")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("not a refresh token")
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "refresh token expired, please log in again"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": str(e)}), 401

    user_id = payload["sub"]
    with SessionFactory() as s:
        user = s.get(User, user_id)
        if not user or not user.is_active:
            return jsonify({"error": "user not found or deactivated"}), 401

    access_token = _make_access_token(user_id, user.username)
    return jsonify({
        "access_token": access_token,
        "token_type": "Bearer",
    }), 200
