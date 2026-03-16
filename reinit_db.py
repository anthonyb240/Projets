from app import app, db
from models import Category, User, Topic, Post, ChatMessage

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    print("Database reset complete.")
