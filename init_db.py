"""Initialize the database with default categories."""
from app import app, db
from models import Category, User
from secrets_manager import get_secret

categories = [
    {
        'name': 'Actualites & Patchs',
        'description': 'Sorties de legendes, equilibrages et annonces officielles',
        'icon': '\U0001f4f0',
        'color': '#F39C12'
    },
    {
        'name': 'Discussion Generale',
        'description': 'Discussions sur Brawlhalla, l\'esport, et la meta',
        'icon': '\u2694\ufe0f',
        'color': '#3498DB'
    },
    {
        'name': 'Clips & Highlights',
        'description': 'Partagez vos meilleures actions et 0 to death !',
        'icon': '\U0001f3ac',
        'color': '#E74C3C'
    },
    {
        'name': 'Entraide & Conseils',
        'description': 'Besoin d\'aide pour monter en Elo ? Demandez ici !',
        'icon': '\U0001f91d',
        'color': '#2ECC71'
    }
]

with app.app_context():
    # Creer toutes les tables (y compris uploaded_file)
    db.create_all()

    # Migration : ajouter la colonne avatar_file si elle n'existe pas
    try:
        import sqlite3
        db_path = db.engine.url.database
        if db_path:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'avatar_file' not in columns:
                cursor.execute("ALTER TABLE user ADD COLUMN avatar_file VARCHAR(255)")
                conn.commit()
                print('[OK] Colonne avatar_file ajoutee a la table user.')
            conn.close()
    except Exception as e:
        print(f'[INFO] Migration skip: {e}')

    if Category.query.count() == 0:
        for cat_data in categories:
            cat = Category(**cat_data)
            db.session.add(cat)
        db.session.commit()
        print(f'[OK] {len(categories)} categories creees avec succes !')
    else:
        print('[INFO] Les categories existent deja.')

    if User.query.count() == 0:
        admin_username = get_secret('USERNAME_DB')
        admin_password = get_secret('PASSWORD_DB')
        if not admin_username or not admin_password:
            print('[WARN] USERNAME_DB/PASSWORD_DB indisponibles (Bao pas pret?). Skip creation admin.')
        else:
            admin_user = User(
                username=admin_username,
                email='admin@valhalla.fr',
                avatar_color='#FDCB6E',
                is_admin=True
            )
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()
            # NE PAS LOGGER LE PASSWORD
            print(f'[OK] Compte administrateur cree (username={admin_username})')

    print('[OK] Base de donnees initialisee.')
