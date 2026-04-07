import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# Load environment variables from .env file
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or 'sqlite:///' + os.path.join(basedir, 'forum.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sécurisation des cookies de session (Flask/Flask-Login)
    SESSION_COOKIE_SECURE = True       # Envoie les cookies uniquement sur HTTPS
    SESSION_COOKIE_HTTPONLY = True     # Empêche l'accès aux cookies via JavaScript (Anti-XSS)
    SESSION_COOKIE_SAMESITE = 'Lax'    # Empêche l'envoi des cookies depuis des sites tiers (Anti-CSRF)

    # Sécurisation des cookies CSRF (Flask-WTF)
    WTF_CSRF_SSL_STRICT = True         # Exige HTTPS strict pour le referrer

    # Limitation de la taille des requêtes entrantes à 50 MB (pour supporter les aatvl5xf video)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    # Upload d'avatars
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'aatvl5xf', 'avatars')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    BLOCKED_EXTENSIONS = {'php', 'exe', 'sh', 'bat', 'cmd', 'js'}  # Blacklist incomplète volontairement

    # Upload de videos
    VIDEO_UPLOAD_FOLDER = os.path.join(basedir, 'static', 'aatvl5xf', 'videos')
    VIDEO_ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
    VIDEO_MAX_SIZE = 50 * 1024 * 1024  # 50 MB
