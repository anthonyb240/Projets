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

# Cree le dossier uploads
RUN mkdir -p static/uploads/avatars

# ── CTF : Flags caches sur le serveur ──
RUN echo "FLAG{upl04d_byp4ss_p0lygl0t_m4st3r}" > /root/flag.txt && \
    chmod 444 /root/flag.txt

RUN mkdir -p /opt/secrets && \
    echo "DB_PASSWORD=S3cur3F0rum!2026" > /opt/secrets/.db_credentials && \
    echo "API_KEY=sk-ctf-4b8f2e91a3d7c056" >> /opt/secrets/.db_credentials

# Historique bash simule avec des indices
RUN mkdir -p /root && printf 'cd /opt/secrets\ncat .db_credentials\nmysql -u admin -pS3cur3F0rum!2026 forum_db\nssh deploy@10.0.0.5\ncat /root/flag.txt\n' > /root/.bash_history

# Initialiser la base de donnees au build
RUN python init_db.py

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
