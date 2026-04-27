FROM python:3.12-slim

# Create a non-root user for security

RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appgroup /app

# Variables d'environnement Flask
ENV SECRET_KEY=votre_clef_super_secrete_ultra_longue_123456789!
ENV SQLALCHEMY_DATABASE_URI=sqlite:///forum.db

# Cree le dossier aatvl5xf
RUN mkdir -p static/aatvl5xf/avatars 

# Initialiser la base de donnees au build
RUN python init_db.py


# Run as non-root user
USER appuser
ENV HOME=/home/appuser



EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
