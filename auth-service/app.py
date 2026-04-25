from flask import Flask
from waitress import serve
from sqlalchemy import create_engine

from config import DATABASE_URL, PORT
from models import Base
from routes import bp as auth_bp
import logging

logging.basicConfig(
    format="%(levelname)s: [%(asctime)s]:: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %I:%M:%S %p",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)


def init_db():
    db_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(db_engine)
    logger.info("Auth service DB tables ensured.")


if __name__ == "__main__":
    init_db()
    logger.info("Auth service running on port %s", PORT)
    serve(app, host="0.0.0.0", port=PORT)