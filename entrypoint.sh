#!/bin/sh
set -e

# Init DB au runtime (lit secrets via secrets_manager -> Bao)
# Tente plusieurs fois si fichier secrets pas encore monte
for i in 1 2 3 4 5; do
    if python init_db.py 2>&1; then
        break
    fi
    echo "Retry init_db ($i/5)..."
    sleep 3
done

# Lance commande passee (gunicorn par defaut)
exec "$@"
