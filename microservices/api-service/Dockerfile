FROM python:3.11-slim

WORKDIR /app

COPY microservices/api-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Web dashboard assets
COPY templates/ ./templates/
COPY static/ ./static/

# Service code
COPY microservices/api-service/app.py .
COPY microservices/api-service/db_client.py .

EXPOSE 5000

CMD ["python", "app.py"]
