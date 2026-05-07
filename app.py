from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
from flask import Flask
from config import PORT
from services.emailclient.EmailClient import EmailClient
from services.fileprocessator.FileProcessator import FileProcessator
from services.dropboxclient.DropboxClient import DropboxClient
from services.importclient.ImportClient import ImportClient
from config import (
    IMAP_SERVER,
    IMAP_PORT,
    IMAP_ADDRESS,
    IMAP_PASSWORD,
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_TOKEN_FILE,
    DROPBOX_EVAL_FILE_PATH,
)
from migrate import run_migration
from routes import bp as routes_bp, init_routes
import logging

app = Flask(__name__)
app.secret_key = "energoflow-dev-secret-key"
logging.basicConfig(format='%(levelname)s: [%(asctime)s]:: %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %I:%M:%S %p')

emailClient = EmailClient(IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD)
dropboxClient = DropboxClient(
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_TOKEN_FILE,
    DROPBOX_EVAL_FILE_PATH,
)
db = None
fileProcessator = None

def runImbalanceImport():
    logging.info("Running imbalance import...")
    if db is None:
        logging.error("DbManager is not initialized. Skipping imbalance import.")
        return
    importer = ImportClient(db)
    imported = importer.import_latest_prices()
    logging.info("Imported %s imbalance price record(s).", imported)

def download_files(xlsx_files):
    try:
        for (file_name, data, uid, tag, email_address, email_timestamp, _client_name) in xlsx_files:
            local_file_path = f"{file_name}"

            with open(local_file_path, "wb") as f:
                f.write(data)
    
    except Exception as e:
        logging.error(f"Error saving attachments: {e}")
        return -1
    finally:
        return len(xlsx_files)

def runEmailImport():
    logging.info("Running email import...")
    
    emailClient.connect()
    xlsx_files = emailClient.runEmailImport()
    emailClient.disconnect()

    if not xlsx_files:
        return

    nr_files = download_files(xlsx_files)
    logging.info(f"Downloaded {nr_files} file(s) from email attachments.")
    if nr_files == -1:
        return
    
    if fileProcessator is None:
        logging.error("FileProcessator not initialized. Skipping processing.")
        return
    fileProcessator.set_xlsx_files(xlsx_files)
    fileProcessator.process_xlsx_files()
    
    

if __name__ == '__main__':
    # Auto-migration: creates DB + all tables if they don't exist
    db = run_migration()
    fileProcessator = FileProcessator(db)
    
    # Inject db into routes and register blueprint
    init_routes(db)
    app.register_blueprint(routes_bp)
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=runImbalanceImport, trigger="interval", minutes=15, max_instances=1)
    scheduler.add_job(func=runEmailImport, trigger="interval", minutes=10, max_instances=1)
    scheduler.start()
    
    logging.info("🌐 EnergoFlow running on http://127.0.0.1:%s", PORT)
    serve(app, host='127.0.0.1', port=PORT)
    