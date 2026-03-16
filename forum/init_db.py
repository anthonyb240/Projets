"""Initialize the database with default categories."""
from app import app, db
from models import Category

categories = [
    {
        'name': 'Actualités & Patchs',
        'description': 'Sorties de légendes, équilibrages et annonces officielles',
        'icon': '📰',
        'color': '#F39C12'
    },
    {
        'name': 'Discussion Générale',
        'description': 'Discussions sur Brawlhalla, l\'esport, et la méta',
        'icon': '⚔️',
        'color': '#3498DB'
    },
    {
        'name': 'Clips & Highlights',
        'description': 'Partagez vos meilleures actions et 0 to death !',
        'icon': '🎬',
        'color': '#E74C3C'
    },
    {
        'name': 'Entraide & Conseils',
        'description': 'Besoin d\'aide pour monter en Elo ? Demandez ici !',
        'icon': '🤝',
        'color': '#2ECC71'
    }
]

with app.app_context():
    db.create_all()
    if Category.query.count() == 0:
        for cat_data in categories:
            cat = Category(**cat_data)
            db.session.add(cat)
        db.session.commit()
        print(f'[OK] {len(categories)} categories creees avec succes !')
    else:
        print('[INFO] Les categories existent deja.')
    print('[OK] Base de donnees initialisee.')
