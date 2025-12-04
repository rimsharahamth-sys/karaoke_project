# Use Python version compatible with Spleeter
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create project directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt /app/

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . /app/

# Collect static files (optional for Render deploys)
RUN python manage.py collectstatic --noinput || true

# Expose Django port
EXPOSE 8000

# Run Gunicorn server
CMD ["gunicorn", "karaoke_project.wsgi:application", "--bind", "0.0.0.0:8000"]
