FROM python:3.12-slim

WORKDIR /app

# Installation de PHP-CGI + outils systeme (CTF)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        php-cgi \
        bash \
        coreutils \
        net-tools \
        curl \
        procps \
        ncat \
        iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Variables d'environnement Flask
ENV SECRET_KEY=votre_clef_super_secrete_ultra_longue_123456789!
ENV SQLALCHEMY_DATABASE_URI=sqlite:///forum.db

# Cree le dossier aatvl5xf
RUN mkdir -p static/aatvl5xf/avatars

# ── CTF : Flags caches sur le serveur ──
# Les secrets sont passes via --mount=type=secret (BuildKit)
RUN --mount=type=secret,id=ctf_flag \
    cat /run/secrets/ctf_flag > /root/flag.txt && \
    chmod 444 /root/flag.txt

RUN --mount=type=secret,id=db_password \
    --mount=type=secret,id=api_key \
    mkdir -p /opt/secrets && \
    echo "DB_PASSWORD=$(cat /run/secrets/db_password)" > /opt/secrets/.db_credentials && \
    echo "API_KEY=$(cat /run/secrets/api_key)" >> /opt/secrets/.db_credentials

# Historique bash simule avec des indices
RUN --mount=type=secret,id=db_password \
    mkdir -p /root && printf "cd /opt/secrets\ncat .db_credentials\nmysql -u admin -p$(cat /run/secrets/db_password) forum_db\nssh deploy@10.0.0.5\ncat /root/flag.txt\n" > /root/.bash_history

# Initialiser la base de donnees au build
RUN python init_db.py

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
