from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
from flask import Flask, config
from config import PORT
from services.emailclient.EmailClient import EmailClient
from config import IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD
import logging

app = Flask(__name__)
logging.basicConfig(format='%(levelname)s: [%(asctime)s]:: %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %I:%M:%S %p')

emailClient = EmailClient(IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD)

def runImbalanceImport():
    logging.info("Running imbalance import...")
    
def runEmailImport():
    logging.info("Running email import...")
    emailClient.connect()
    xlsx_files = emailClient.runEmailImport()
    emailClient.disconnect()
    


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=runImbalanceImport, trigger="interval", minutes=15, max_instances=1)
    scheduler.add_job(func=runEmailImport, trigger="interval", seconds=10, max_instances=1)
    scheduler.start()
    
    serve(app, host='127.0.0.1', port=PORT)
    