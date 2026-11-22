FROM python:3.12-slim

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install packages
COPY pyproject.toml /app/
RUN pip install --upgrade pip && \
    pip install ".[dev]"

# Copy project files
COPY . /app/

# Expose Django port
EXPOSE 8000

# Default entrypoint runs migrations and starts dev server (or production gunicorn)
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

