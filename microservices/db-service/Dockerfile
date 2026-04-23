FROM python:3.11-slim

WORKDIR /app

COPY microservices/db-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Shared application code
COPY services/dbmanager/ ./services/dbmanager/
COPY config.py .
COPY migrate.py .

# Service entrypoint
COPY microservices/db-service/app.py .

EXPOSE 5003

CMD ["python", "app.py"]
