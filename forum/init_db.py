"""Initialize the database with default categories."""
from app import app, db
from models import Category, User

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
        
    if User.query.count() == 0:
        admin_user = User(
            username='admin',
            email='admin@valhalla.fr',
            avatar_color='#FDCB6E',
            is_admin=True
        )
        admin_user.set_password('AdminBrawlhalla123!')
        db.session.add(admin_user)
        db.session.commit()
        print('[OK] Compte administrateur cree : admin / AdminBrawlhalla123!')
        
    print('[OK] Base de donnees initialisee.')
