FROM python:3.11-slim

WORKDIR /app

COPY microservices/scheduler-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Business-logic services used by the scheduler
COPY services/emailclient/ ./services/emailclient/
COPY services/fileprocessator/ ./services/fileprocessator/
COPY services/dropboxclient/ ./services/dropboxclient/
COPY services/importclient/ ./services/importclient/
COPY config.py .

# Service entrypoint
COPY microservices/scheduler-service/app.py .

EXPOSE 5002

CMD ["python", "app.py"]
