# Backend Dockerfile - Django + Gunicorn
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files at BUILD time.
# Use the development settings (SQLite-capable, no required SECRET_KEY/DATABASE_URL)
# so the build does not need production secrets. Runtime uses production settings.
ENV DJANGO_SETTINGS_MODULE=config.settings.development
RUN python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Run Gunicorn (via entrypoint that migrates first)
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
# PORT is injected by Hugging Face Spaces (default 7860). Bind to 0.0.0.0:$PORT.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
