# Use Python version compatible with Spleeter
FROM python:3.9-slim

# Install system dependencies
# Added: gfortran (sometimes required by numpy/scipy/numba), libopenblas-dev 
# (for optimized linear algebra, which numba/numpy can use)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    gfortran \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt /app/

# Install dependencies
RUN pip install --upgrade pip

# --- FIX START ---
# 1. Pre-install setuptools, numpy, and numba's direct dependency to ensure proper compilation context
# Use specific versions from your requirements.txt for stability
RUN pip install --no-cache-dir setuptools==69.0.3 numpy==1.23.5 numba
# 2. Now install the rest of the requirements, excluding the ones just installed
RUN pip install --no-cache-dir -r requirements.txt --ignore-installed numba numpy setuptools
# --- FIX END ---

# Copy project files
COPY . /app/

# Expose port
EXPOSE 8000

# Run server with Render PORT
CMD ["gunicorn", "songs_project.wsgi:application", "--bind", "0.0.0.0:$PORT"]
