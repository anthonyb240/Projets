from app import app, db
import models  # noqa: F401 - needed so SQLAlchemy knows about all tables

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    print("Database reset complete.")
