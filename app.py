from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
from flask import Flask
from config import PORT
from services.emailclient.EmailClient import EmailClient
from services.fileprocessator.FileProcessator import FileProcessator
from config import IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD
from migrate import run_migration
from routes import bp as routes_bp, init_routes
import logging

app = Flask(__name__)
app.secret_key = "energoflow-dev-secret-key"
logging.basicConfig(format='%(levelname)s: [%(asctime)s]:: %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %I:%M:%S %p')

emailClient = EmailClient(IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD)
fileProcessator = FileProcessator()

def runImbalanceImport():
    logging.info("Running imbalance import...")

def download_files(xlsx_files):
    try:
        for (file_name, data, uid, tag, email_address, email_timestamp) in xlsx_files:
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
    
    fileProcessator.set_xlsx_files(xlsx_files)
    fileProcessator.process_xlsx_files()
    
    

if __name__ == '__main__':
    # Auto-migration: creates DB + all tables if they don't exist
    db = run_migration()
    
    # Inject db into routes and register blueprint
    init_routes(db)
    app.register_blueprint(routes_bp)
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=runImbalanceImport, trigger="interval", minutes=15, max_instances=1)
    scheduler.add_job(func=runEmailImport, trigger="interval", seconds=10, max_instances=1)
    scheduler.start()
    
    logging.info("🌐 EnergoFlow running on http://127.0.0.1:%s", PORT)
    serve(app, host='127.0.0.1', port=PORT)
    