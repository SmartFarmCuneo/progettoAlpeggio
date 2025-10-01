FROM python:3.12-slim

WORKDIR /app

# Copia requirements e installa
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice
COPY . .

EXPOSE 5000

CMD ["python3", "app.py"]
