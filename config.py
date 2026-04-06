from dotenv import load_dotenv
import os

load_dotenv()


# Constants
PORT = 5000

IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT"))

IMAP_ADDRESS = os.getenv("IMAP_ADDRESS")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")