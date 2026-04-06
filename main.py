from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve
from flask import Flask
from config import PORT

app = Flask(__name__)

def runImbalanceImport():
    print("Running imbalance import...")
    


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=runImbalanceImport, trigger="interval", seconds=10, max_instances=1)
    scheduler.start()
    
    serve(app, host='127.0.0.1', port=PORT)
    