import imaplib
import logging
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from email.header import decode_header

from config import FORECAST_ADDRESS, FORECAST_TAG, IBD_ADDRESS, IBD_TAG

logging.basicConfig(format='%(levelname)s: [%(asctime)s]:: %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %I:%M:%S %p')

class EmailClient:
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
        self.connectionStatus = "Not connected"
        
    def connect(self):
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port)
            mail.login(self.user, self.password)
            mail.select("inbox")
            self.connection = mail
            self.connectionStatus = "Connected"
            logging.info("Successfully connected to email server.")
        except Exception as e:
            logging.error(f"Failed to connect to email server: {e}")
            self.connection = None
            self.connectionStatus = "Connection failed"
            
    def isConnected(self):
        return self.connection is not None and self.connectionStatus == "Connected"        
    
    def disconnect(self):
        if self.isConnected():
            self.connection.logout()
            self.connection = None
            self.connectionStatus = "Disconnected"
        
        logging.info("Successfully disconnected from email server.")
    

    def runEmailImport(self):
        if not self.isConnected():
            self.connect()
        
        try:
            logging.info("Running email import...")
            self.connection.select("inbox")

            status, messages = self.connection.uid('SEARCH', None, 'UNSEEN')
            if status != 'OK':
                raise Exception("Error searching Inbox.")

            email_uids = messages[0].split()
            xlsx_files = []

            logging.info(f"Found {len(email_uids)} new email(s) to process.")
            for uid in email_uids:
                status, msg_data = self.connection.uid('FETCH', uid, '(RFC822)')
                if status != 'OK':
                    raise Exception("Error fetching mail.")

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg, sender, email_timestamp, email_address, subject = self.get_mail_data(response_part)
                        logging.info(f"Processing email from {sender} with subject '{subject}' received at {email_timestamp}")
                        if self.mail_is_forecast(subject, email_address):
                            self.parse_forecast_mail(msg, uid, xlsx_files, email_timestamp)
                        elif self.mail_is_ibd(subject, email_address):
                            self.parse_ibd_mail(msg, uid, xlsx_files, email_timestamp)

                            
                # Mark the email as unread (use UID)
                self.connection.uid('STORE', uid, '-FLAGS', '\\Seen')
        
            return xlsx_files
        
        except Exception as e:
            logging.error(f"Error during email import: {e}")
            
    def get_mail_data(self, response_part):
        msg = message_from_bytes(response_part[1])
        sender = msg.get("From")
        date_header = msg.get("Date")
        email_timestamp = parsedate_to_datetime(date_header)  # datetime object

        email_address = sender.split()[-1]
        email_address = email_address[1:-1]
        
        subject = self.get_mail_subject(msg)

        return msg, sender, email_timestamp, email_address, subject
    
    def get_mail_subject(self, mail):
        subject = mail.get("Subject")
        decoded_subject = decode_header(subject)
        subject = ''.join(
            part.decode(encoding or 'utf-8') if isinstance(part, bytes) else part
            for part, encoding in decoded_subject
        )
        return subject
    
    def mail_is_forecast(self, subject, email_address):
        return (email_address == FORECAST_ADDRESS and subject.__contains__("Production forecast"))

    def parse_forecast_mail(self, msg, uid, xlsx_files, email_timestamp):
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            file_name = part.get_filename()
            if file_name.endswith('.xlsx'):
                data = part.get_payload(decode=True)
                logging.info(f"Found forecast email with attachment: {file_name}")
                xlsx_files.append((file_name, data, uid, FORECAST_TAG, FORECAST_ADDRESS, email_timestamp))

    def mail_is_ibd(self, subject, email_address):
        return (email_address == IBD_ADDRESS and subject.__contains__("Actual Production Data"))
    
    def parse_ibd_mail(self, msg, uid, xlsx_files, email_timestamp):
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            file_name = part.get_filename()
            if file_name.endswith('.xlsx'):
                data = part.get_payload(decode=True)
                logging.info(f"Found IBD email with attachment: {file_name}")
                xlsx_files.append((file_name, data, uid, IBD_TAG, IBD_ADDRESS, email_timestamp))