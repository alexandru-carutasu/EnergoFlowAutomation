FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps in a separate layer so they are cached between code-only rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (templates, static, services, *.py)
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
