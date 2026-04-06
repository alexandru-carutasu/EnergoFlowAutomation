from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
from flask import Flask, config
from config import PORT
from services.emailclient.EmailClient import EmailClient
from config import IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD

app = Flask(__name__)

emailClient = EmailClient(IMAP_SERVER, IMAP_PORT, IMAP_ADDRESS, IMAP_PASSWORD)

def runImbalanceImport():
    print("Running imbalance import...")
    
def runEmailImport():
    print("Running email import...")
    emailClient.connect()
    emailClient.disconnect()
    


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=runImbalanceImport, trigger="interval", minutes=15, max_instances=1)
    scheduler.add_job(func=runEmailImport, trigger="interval", seconds=10, max_instances=1)
    scheduler.start()
    
    serve(app, host='127.0.0.1', port=PORT)
    