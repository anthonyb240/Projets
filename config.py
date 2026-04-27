import os
from dotenv import load_dotenv
from secrets_manager import get_secret

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = get_secret('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or 'sqlite:///' + os.path.join(basedir, 'forum.db')
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = True     
    SESSION_COOKIE_HTTPONLY = True   
    SESSION_COOKIE_SAMESITE = 'Lax'    

    WTF_CSRF_SSL_STRICT = True        
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'aatvl5xf', 'avatars')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    BLOCKED_EXTENSIONS = {'php', 'exe', 'sh', 'bat', 'cmd', 'js'}
    VIDEO_UPLOAD_FOLDER = os.path.join(basedir, 'static', 'aatvl5xf', 'videos')
    VIDEO_ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
    VIDEO_MAX_SIZE = 50 * 1024 * 1024  # 50 MB
