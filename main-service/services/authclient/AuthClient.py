import logging
import requests

logger = logging.getLogger(__name__)


class AuthClient:
    """HTTP client for the auth-service microservice."""

    def __init__(self, base_url: str) -> None:
        # base_url e.g. "http://auth-service:5001" in Docker, "http://localhost:5001" locally
        self.base_url = base_url.rstrip("/")

    def register(self, username: str, email: str, password: str) -> dict:
        """Create a new user. Returns {"id": ..., "username": ...} or raises on error."""
        resp = requests.post(
            f"{self.base_url}/auth/register",
            json={"username": username, "email": email, "password": password},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def login(self, username: str, password: str) -> dict:
        """Authenticate a user. Returns {"access_token": ..., "refresh_token": ..., "token_type": "Bearer"}."""
        resp = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def verify(self, access_token: str) -> dict:
        """Validate an access token. Returns {"valid": True, "user_id": ..., "username": ...}."""
        resp = requests.get(
            f"{self.base_url}/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def refresh(self, refresh_token: str) -> dict:
        """Exchange a refresh token for a new access token. Returns {"access_token": ..., "token_type": "Bearer"}."""
        resp = requests.post(
            f"{self.base_url}/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
