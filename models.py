from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import random

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_color = db.Column(db.String(7), nullable=False)
    avatar_file = db.Column(db.String(255), nullable=True)  # Chemin vers l'avatar uploadé
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    topics = db.relationship('Topic', backref='author', lazy='dynamic')
    posts = db.relationship('Post', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def generate_avatar_color():
        colors = [
            '#6C5CE7', '#A29BFE', '#0984E3', '#74B9FF',
            '#00CEC9', '#55EFC4', '#E17055', '#FAB1A0',
            '#FD79A8', '#E84393', '#FDCB6E', '#F39C12',
        ]
        return random.choice(colors)  # nosec B311 - couleur avatar, non crypto

    @property
    def initials(self):
        return self.username[:2].upper()

    @property
    def post_count(self):
        return self.posts.count() + self.topics.count()


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default='💬')
    color = db.Column(db.String(7), nullable=False, default='#6C5CE7')

    topics = db.relationship('Topic', backref='category', lazy='dynamic')

    @property
    def topic_count(self):
        return self.topics.count()

    @property
    def post_count(self):
        total = 0
        for topic in self.topics:
            total += topic.posts.count()
        return total + self.topic_count

    @property
    def last_activity(self):
        latest_topic = self.topics.order_by(Topic.created_at.desc()).first()
        if latest_topic:
            latest_post = latest_topic.posts.order_by(Post.created_at.desc()).first()
            if latest_post:
                return latest_post.created_at
            return latest_topic.created_at
        return None


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    posts = db.relationship('Post', backref='topic', lazy='dynamic',
                            cascade='all, delete-orphan')

    @property
    def reply_count(self):
        return self.posts.count()

    @property
    def last_reply(self):
        return self.posts.order_by(Post.created_at.desc()).first()


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)


class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    saved_name = db.Column(db.String(255), nullable=False, unique=True)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    uploader = db.relationship('User', backref=db.backref('uploaded_files', lazy='dynamic'))


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    original_name = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    uploader = db.relationship('User', backref=db.backref('videos', lazy='dynamic'))


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    author = db.relationship('User', backref=db.backref('chat_messages', lazy='dynamic'))
