FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

ENV PORT=8000

EXPOSE 8000

CMD ["gunicorn", "karaoke_project.wsgi:application", "--bind", "0.0.0.0:8000"]
