# ── Stage 1: build deps in a clean layer ──────────────────────────────────────
FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only requirements first — Docker caches this layer separately.
# As long as requirements.txt doesn't change, this RUN step is skipped on rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: copy application source ──────────────────────────────────────────
COPY . .

# Document which port the service listens on (does not actually publish it)
EXPOSE 5001

# Run as the entry point — waitress is used instead of Flask's dev server
CMD ["python", "app.py"]
