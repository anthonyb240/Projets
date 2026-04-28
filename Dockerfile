FROM python:3.12-slim

RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appgroup /app

ENV SQLALCHEMY_DATABASE_URI=sqlite:///forum.db

RUN mkdir -p static/aatvl5xf/avatars

# Init DB au RUNTIME (apres mount Bao secrets) puis lance gunicorn
COPY --chown=appuser:appgroup entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser
ENV HOME=/home/appuser

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]