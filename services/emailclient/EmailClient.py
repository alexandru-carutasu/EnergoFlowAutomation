

import imaplib


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
            print("Successfully connected to email server.")
        except Exception as e:
            print(f"Failed to connect to email server: {e}")
            self.connection = None
            self.connectionStatus = "Connection failed"
            
    def disconnect(self):
        if self.connection:
            self.connection.logout()
            self.connection = None
            self.connectionStatus = "Disconnected"
        
        print("Successfully disconnected from email server.")