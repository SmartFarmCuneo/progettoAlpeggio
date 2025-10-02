FROM python:3.12-slim

WORKDIR /app

# Installa dipendenze di sistema necessarie per cryptography
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e installa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice
COPY . .

EXPOSE 5000
CMD ["python", "app.py"]
