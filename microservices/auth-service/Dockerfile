FROM python:3.11-slim

WORKDIR /app

COPY microservices/auth-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY microservices/auth-service/app.py .

EXPOSE 5001

CMD ["python", "app.py"]
