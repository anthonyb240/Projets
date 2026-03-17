FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code backend
COPY . .

EXPOSE 5000

# Lancer Flask avec Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]