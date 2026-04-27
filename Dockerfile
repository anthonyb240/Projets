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

RUN python init_db.py

USER appuser
ENV HOME=/home/appuser

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]