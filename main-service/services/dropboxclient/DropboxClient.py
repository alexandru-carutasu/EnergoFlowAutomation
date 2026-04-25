import json
import logging
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import dropbox
import requests
from dropbox.files import WriteMode

logger = logging.getLogger(__name__)


class DropboxClient:
    def __init__(self, app_key: str, app_secret: str, token_file: str, eval_file_path: str) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.token_file = token_file
        self.eval_file_path = eval_file_path

    def save_refresh_token(self, refresh_token: str) -> None:
        with open(self.token_file, "w") as token_file:
            json.dump({"refresh_token": refresh_token}, token_file)

    def load_refresh_token(self) -> Optional[str]:
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as token_file:
                    data = json.load(token_file)
                    return data.get("refresh_token")
            except (json.JSONDecodeError, ValueError):
                logger.error("%s is empty or invalid JSON. Reauthorization required.", self.token_file)
                return None
        logger.error("%s does not exist. Reauthorization required.", self.token_file)
        return None

    def run_authorization(self, redirect_uri: str = "http://localhost:8000") -> str:
        auth_url = (
            f"https://www.dropbox.com/oauth2/authorize?client_id={self.app_key}"
            f"&token_access_type=offline&response_type=code&redirect_uri={redirect_uri}"
        )
        webbrowser.open(auth_url)

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if "code=" in self.path:
                    code = self.path.split("code=")[-1]
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Authorization successful! You may close this window.")
                    self.server.authorization_code = code
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Invalid request.")

        server = HTTPServer(("localhost", 8000), RedirectHandler)
        server.handle_request()

        authorization_code = getattr(server, "authorization_code", None)
        if not authorization_code:
            raise Exception("Failed to retrieve authorization code.")
        return authorization_code

    def exchange_code_for_tokens(self, auth_code: str, redirect_uri: str = "http://localhost:8000") -> dict:
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "client_id": self.app_key,
            "client_secret": self.app_secret,
            "redirect_uri": redirect_uri,
        }
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()
        logger.error("Failed to exchange authorization code for tokens: %s", response.text)
        raise Exception(f"Token exchange failed: {response.text}")

    def get_access_token(self, refresh_token: str) -> Optional[dropbox.Dropbox]:
        try:
            dbx = dropbox.Dropbox(
                app_key=self.app_key,
                app_secret=self.app_secret,
                oauth2_refresh_token=refresh_token,
            )
            return dbx
        except Exception as ex:
            logger.error("Failed to authenticate with Dropbox: %s", ex)
            return None

    def upload_excel_to_dropbox(self, local_file_path: str, dropbox_folder_path: str) -> str:
        try:
            refresh_token = self.load_refresh_token()
            if not refresh_token:
                raise Exception("Refresh token not found. Please authorize the app.")

            dbx = self.get_access_token(refresh_token)
            if not dbx:
                raise Exception("Failed to authenticate with Dropbox.")

            if not os.path.exists(local_file_path):
                raise Exception(f"Local file not found: {local_file_path}")

            file_name = os.path.basename(local_file_path)
            dropbox_path = f"{dropbox_folder_path}/{file_name}".replace("//", "/")

            with open(local_file_path, "rb") as file:
                dbx.files_upload(file.read(), dropbox_path, mode=WriteMode("overwrite"))

            return f"File uploaded successfully to Dropbox at: {dropbox_path}"

        except dropbox.exceptions.ApiError as api_error:
            logger.error("Dropbox API Error: %s", api_error)
        except Exception as ex:
            logger.error("An error occurred: %s", ex)

        return ""

    def check_file_in_dropbox(self, company_name: str, date_str: str) -> bool:
        try:
            folder_path = f"/{company_name}"
            file_name = f"Evaluare_{company_name}_{date_str}.xlsx"

            logger.info("Checking for file: %s/%s", folder_path, file_name)

            refresh_token = self.load_refresh_token()
            if not refresh_token:
                logger.error("Refresh token not found. Please authorize the app.")
                return False

            dbx = self.get_access_token(refresh_token)
            if not dbx:
                logger.error("Failed to authenticate with Dropbox.")
                return False

            try:
                folder_metadata = dbx.files_list_folder(folder_path)
                for entry in folder_metadata.entries:
                    if isinstance(entry, dropbox.files.FileMetadata) and entry.name == file_name:
                        logger.info("File found: %s", file_name)
                        return True

                logger.info("File not found: %s", file_name)
                return False
            except dropbox.exceptions.ApiError as api_error:
                logger.error("Dropbox API Error: %s", api_error)
                return False

        except Exception as ex:
            logger.error("An error occurred: %s", ex)
            return False

    def download_file_from_dropbox(self, client_name: str, current_date: str) -> Optional[str]:
        try:
            refresh_token = self.load_refresh_token()
            if not refresh_token:
                logger.error("Refresh token not found. Please authorize the app.")
                return None

            dbx = self.get_access_token(refresh_token)
            if not dbx:
                logger.error("Failed to authenticate with Dropbox.")
                return None

            remote_folder_path = f"/{client_name}"
            try:
                for entry in dbx.files_list_folder(remote_folder_path).entries:
                    expected_name = f"Evaluare_{client_name}_{current_date}.xlsx"
                    if entry.name != expected_name:
                        continue
                    if isinstance(entry, dropbox.files.FileMetadata):
                        local_file_path = os.path.join(self.eval_file_path, expected_name)
                        with open(local_file_path, "wb") as f:
                            _, res = dbx.files_download(path=f"{remote_folder_path}/{expected_name}")
                            f.write(res.content)
                        logger.info("Downloaded: %s", entry.name)
                        return local_file_path

                logger.error(
                    "File Evaluare not found for %s on %s",
                    client_name,
                    current_date,
                )

            except dropbox.exceptions.ApiError as api_error:
                logger.error("Dropbox API Error: %s", api_error)
        except Exception as ex:
            logger.error("An error occurred: %s", ex)
        return None

    def download_model_eval_from_dropbox(self) -> Optional[str]:
        try:
            refresh_token = self.load_refresh_token()
            if not refresh_token:
                logger.error("Refresh token not found. Please authorize the app.")
                return None

            dbx = self.get_access_token(refresh_token)
            if not dbx:
                logger.error("Failed to authenticate with Dropbox.")
                return None

            remote_folder_path = "/Forecast Automat"
            try:
                for entry in dbx.files_list_folder(remote_folder_path).entries:
                    if entry.name == "Evaluare.xlsx":
                        local_file_path = os.path.join(self.eval_file_path, "Evaluare.xlsx")
                        with open(local_file_path, "wb") as f:
                            _, res = dbx.files_download(path=f"{remote_folder_path}/Evaluare.xlsx")
                            f.write(res.content)
                        logger.info("Downloaded: %s", entry.name)
                        return local_file_path
            except dropbox.exceptions.ApiError as api_error:
                logger.error("Dropbox API Error: %s", api_error)
        except Exception as ex:
            logger.error("An error occurred: %s", ex)
        return None
