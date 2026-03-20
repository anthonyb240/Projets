import os
import subprocess
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from config import Config
from models import db, User, Category, Topic, Post, ChatMessage, UploadedFile, Video
from forms import RegistrationForm, LoginForm, TopicForm, PostForm, AvatarUploadForm, VideoUploadForm
from datetime import datetime
from utils import censor_text
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)

# Protection avec Flask-Talisman pour Content Security Policy et HTTP Headers
csp = {
    'default-src': ["'self'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'script-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:"]
}
talisman = Talisman(app, content_security_policy=csp, force_https=False)

csrf = CSRFProtect(app)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour acceder a cette page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Template filters ──

@app.template_filter('timeago')
def timeago_filter(dt):
    if dt is None:
        return 'Jamais'
    now = datetime.utcnow()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'A l\'instant'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f'Il y a {minutes} min'
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f'Il y a {hours}h'
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f'Il y a {days}j'
    else:
        return dt.strftime('%d/%m/%Y')


# ── Routes ──

@app.route('/')
def index():
    categories = Category.query.all()
    total_topics = Topic.query.count()
    total_posts = Post.query.count()
    total_users = User.query.count()
    return render_template('index.html',
                           categories=categories,
                           total_topics=total_topics,
                           total_posts=total_posts,
                           total_users=total_users)


@app.route('/category/<int:category_id>', methods=['GET', 'POST'])
def category(category_id):
    cat = Category.query.get_or_404(category_id)
    page = request.args.get('page', 1, type=int)
    topics = cat.topics.order_by(Topic.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False)

    # Si c'est la categorie Clips & Highlights, gerer l'upload video
    video_form = None
    videos = None
    if cat.name == 'Clips & Highlights':
        video_form = VideoUploadForm()
        if video_form.validate_on_submit() and current_user.is_authenticated:
            file = video_form.video.data
            if file and file.filename != '':
                upload_result = _handle_video_upload(video_form, file)
                if upload_result:
                    return redirect(url_for('category', category_id=category_id))
        videos = Video.query.order_by(Video.uploaded_at.desc()).paginate(
            page=request.args.get('vpage', 1, type=int), per_page=12, error_out=False)

    return render_template('category.html', category=cat, topics=topics,
                           video_form=video_form, videos=videos)


@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    t = Topic.query.get_or_404(topic_id)
    form = PostForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Connectez-vous pour repondre.', 'warning')
            return redirect(url_for('login'))
        post = Post(
            content=censor_text(form.content.data),
            user_id=current_user.id,
            topic_id=t.id
        )
        db.session.add(post)
        db.session.commit()
        flash('Reponse publiee !', 'success')
        return redirect(url_for('topic', topic_id=t.id))
    page = request.args.get('page', 1, type=int)
    posts = t.posts.order_by(Post.created_at.asc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('topic.html', topic=t, posts=posts, form=form)


@app.route('/new-topic/<int:category_id>', methods=['GET', 'POST'])
@login_required
def new_topic(category_id):
    cat = Category.query.get_or_404(category_id)
    if cat.name == 'Actualites & Patchs' and not current_user.is_admin:
        abort(403)

    form = TopicForm()
    if form.validate_on_submit():
        t = Topic(
            title=censor_text(form.title.data),
            content=censor_text(form.content.data),
            user_id=current_user.id,
            category_id=cat.id
        )
        db.session.add(t)
        db.session.commit()
        flash('Sujet cree avec succes !', 'success')
        return redirect(url_for('topic', topic_id=t.id))
    return render_template('new_topic.html', category=cat, form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            avatar_color=User.generate_avatar_color()
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Inscription reussie ! Vous pouvez vous connecter.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        flash(f'Bienvenue, {user.username} !', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous etes deconnecte.', 'info')
    return redirect(url_for('index'))


@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    recent_topics = user.topics.order_by(Topic.created_at.desc()).limit(5).all()
    recent_posts = user.posts.order_by(Post.created_at.desc()).limit(5).all()
    return render_template('profile.html', user=user,
                           recent_topics=recent_topics,
                           recent_posts=recent_posts)


@app.route('/topic/<int:topic_id>/delete', methods=['POST'])
@login_required
def delete_topic(topic_id):
    t = Topic.query.get_or_404(topic_id)
    if t.user_id != current_user.id:
        abort(403)
    cat_id = t.category_id
    db.session.delete(t)
    db.session.commit()
    flash('Sujet supprime.', 'info')
    return redirect(url_for('category', category_id=cat_id))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    p = Post.query.get_or_404(post_id)
    if p.user_id != current_user.id:
        abort(403)
    topic_id = p.topic_id
    db.session.delete(p)
    db.session.commit()
    flash('Reponse supprimee.', 'info')
    return redirect(url_for('topic', topic_id=topic_id))


# ── Upload Avatar ──

# Whitelist stricte des extensions autorisees
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

# Signatures magic bytes pour les images
# Vulnerabilite volontaire : ne verifie que les premiers octets,
# un fichier polyglotte (magic bytes valides + payload PHP) passe cette verification
MAGIC_BYTES = {
    'jpeg': b'\xff\xd8\xff',
    'png': b'\x89PNG',
    'gif': b'GIF8',
}


def check_magic_bytes(file_stream):
    """Verifie les magic bytes du fichier.
    Vulnerabilite : ne verifie que les premiers octets du header,
    un fichier polyglotte peut passer cette verification."""
    header = file_stream.read(8)
    file_stream.seek(0)
    for fmt, magic in MAGIC_BYTES.items():
        if header[:len(magic)] == magic:
            return True, fmt
    return False, None


def is_allowed_extension(filename):
    """Whitelist d'extensions -- une seule extension autorisee, insensible a la casse.
    Bloque les doubles extensions (ex: shell.php.jpg) et les variantes de casse."""
    if '.' not in filename:
        return False
    parts = filename.rsplit('.', 1)
    basename = parts[0]
    ext = parts[1].lower()
    if '.' in basename:
        return False
    return ext in ALLOWED_EXTENSIONS


def detect_content_type(file_stream):
    """Detecte le vrai type MIME a partir des magic bytes du fichier,
    independamment du Content-Type envoye par le client."""
    header = file_stream.read(8)
    file_stream.seek(0)
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    elif header[:4] == b'\x89PNG':
        return 'image/png'
    elif header[:4] == b'GIF8':
        return 'image/gif'
    return None


@app.route('/upload-avatar', methods=['GET', 'POST'])
@login_required
def upload_avatar():
    form = AvatarUploadForm()
    if form.validate_on_submit():
        file = form.avatar.data
        if not file or file.filename == '':
            flash('Aucun fichier selectionne.', 'warning')
            return redirect(request.url)

        # ── Couche 1 : Verification de l'extension (whitelist stricte) ──
        if not is_allowed_extension(file.filename):
            flash('Extension non autorisee. Seuls .jpg, .png et .gif sont acceptes.', 'danger')
            return redirect(request.url)

        # ── Couche 2 : Detection du Content-Type cote serveur ──
        detected_type = detect_content_type(file.stream)
        if detected_type not in ('image/jpeg', 'image/png', 'image/gif'):
            flash('Le contenu du fichier ne correspond pas a une image valide.', 'danger')
            return redirect(request.url)

        # ── Couche 3 : Verification des magic bytes ──
        # Vulnerabilite volontaire : ne verifie que les premiers octets.
        valid_magic, detected_format = check_magic_bytes(file.stream)
        if not valid_magic:
            flash('Le fichier ne semble pas etre une image valide.', 'danger')
            return redirect(request.url)

        # Sauvegarde du fichier
        filename = secure_filename(file.filename)
        if not filename:
            flash('Nom de fichier invalide.', 'danger')
            return redirect(request.url)

        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        save_name = filename
        filepath = os.path.join(upload_folder, save_name)

        # Calcul de la taille du fichier
        file.stream.seek(0, 2)
        file_size = file.stream.tell()
        file.stream.seek(0)

        file.save(filepath)

        # Enregistrement en base de donnees
        uploaded = UploadedFile(
            original_name=file.filename,
            saved_name=save_name,
            content_type=detected_type,
            file_size=file_size,
            user_id=current_user.id
        )
        db.session.add(uploaded)

        current_user.avatar_file = save_name
        db.session.commit()

        flash('Avatar mis a jour avec succes !', 'success')
        return redirect(url_for('profile', username=current_user.username))

    return render_template('upload_avatar.html', form=form)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Sert les fichiers uploades.
    Vulnerabilite CTF : si PHP est installe sur le serveur,
    les fichiers contenant du code PHP sont interpretes via php-cgi.
    Simule un serveur Apache mal configure avec AddHandler php."""
    upload_folder = app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_folder, filename)

    if not os.path.isfile(filepath):
        abort(404)

    # Lecture du fichier pour detecter du contenu PHP
    with open(filepath, 'rb') as f:
        content = f.read()

    # Si le fichier contient des tags PHP et que PHP est disponible,
    # on l'interprete (simule un serveur mal configure)
    if b'<?php' in content:
        try:
            # Construit les variables d'environnement CGI pour passer $_GET
            env = os.environ.copy()
            env['QUERY_STRING'] = request.query_string.decode('utf-8')
            env['REQUEST_METHOD'] = 'GET'
            env['SCRIPT_FILENAME'] = filepath
            env['REDIRECT_STATUS'] = '200'

            result = subprocess.run(
                ['php-cgi', filepath],
                capture_output=True,
                timeout=30,
                env=env
            )
            # Separe les headers CGI du body
            output = result.stdout
            if b'\r\n\r\n' in output:
                body = output.split(b'\r\n\r\n', 1)[1]
            else:
                body = output
            return Response(body, content_type='text/html')
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Sinon, sert le fichier normalement comme image
    return send_from_directory(upload_folder, filename)


# ── Video Upload Security ──

VIDEO_ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}

# Magic bytes pour les formats video
VIDEO_MAGIC_BYTES = {
    'mp4': {
        'check': lambda h: h[4:8] == b'ftyp',
        'mime': 'video/mp4'
    },
    'mov': {
        'check': lambda h: h[4:8] in (b'ftyp', b'moov', b'mdat', b'wide', b'free'),
        'mime': 'video/quicktime'
    },
    'webm': {
        'check': lambda h: h[:4] == b'\x1a\x45\xdf\xa3',
        'mime': 'video/webm'
    },
    'avi': {
        'check': lambda h: h[:4] == b'RIFF' and h[8:12] == b'AVI ',
        'mime': 'video/x-msvideo'
    },
}

VALID_VIDEO_MIMES = {'video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo'}


def is_allowed_video_extension(filename):
    """Whitelist stricte - une seule extension, pas de double extension."""
    if '.' not in filename:
        return False
    parts = filename.rsplit('.', 1)
    basename = parts[0]
    ext = parts[1].lower()
    # Bloque les doubles extensions (ex: video.php.mp4)
    if '.' in basename:
        return False
    return ext in VIDEO_ALLOWED_EXTENSIONS


def detect_video_content_type(file_stream):
    """Detecte le vrai type MIME via magic bytes, ignore le Content-Type client."""
    header = file_stream.read(12)
    file_stream.seek(0)
    if len(header) < 12:
        return None
    for fmt, spec in VIDEO_MAGIC_BYTES.items():
        if spec['check'](header):
            return spec['mime']
    return None


def check_video_magic_bytes(file_stream):
    """Verifie que les magic bytes correspondent a un format video valide."""
    header = file_stream.read(12)
    file_stream.seek(0)
    if len(header) < 12:
        return False, None
    for fmt, spec in VIDEO_MAGIC_BYTES.items():
        if spec['check'](header):
            return True, fmt
    return False, None


def scan_video_for_code(file_stream):
    """Scan les premiers et derniers Ko du fichier pour detecter du code injecte.
    Ne scanne pas tout le binaire pour eviter les faux positifs."""
    # Scan le debut (header zone, 4 Ko)
    header = file_stream.read(4096)
    # Scan la fin (trailer zone, 4 Ko)
    file_stream.seek(0, 2)
    size = file_stream.tell()
    tail_start = max(0, size - 4096)
    file_stream.seek(tail_start)
    trailer = file_stream.read()
    file_stream.seek(0)

    zones = header + trailer
    dangerous_patterns = [
        b'<?php', b'<?=', b'<script',
    ]
    for pattern in dangerous_patterns:
        if pattern in zones:
            return True, pattern.decode('utf-8', errors='replace')
    return False, None


def validate_video_extension_matches_content(filename, detected_mime):
    """Verifie que l'extension correspond au contenu detecte."""
    ext = filename.rsplit('.', 1)[1].lower()
    extension_mime_map = {
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
    }
    expected_mime = extension_mime_map.get(ext)
    # MP4 et MOV partagent le magic byte ftyp
    if ext in ('mp4', 'mov') and detected_mime in ('video/mp4', 'video/quicktime'):
        return True
    return expected_mime == detected_mime


def _handle_video_upload(form, file):
    """Gere l'upload video avec toutes les couches de securite. Retourne True si succes."""
    import uuid

    if not is_allowed_video_extension(file.filename):
        flash('Extension non autorisee. Seuls .mp4, .webm, .mov et .avi sont acceptes.', 'danger')
        return False

    file.stream.seek(0, 2)
    file_size = file.stream.tell()
    file.stream.seek(0)
    max_size = app.config.get('VIDEO_MAX_SIZE', 50 * 1024 * 1024)
    if file_size > max_size:
        flash(f'Fichier trop volumineux. Maximum {max_size // (1024*1024)} MB.', 'danger')
        return False

    detected_type = detect_video_content_type(file.stream)
    if detected_type not in VALID_VIDEO_MIMES:
        flash('Le contenu du fichier ne correspond pas a une video valide.', 'danger')
        return False

    valid_magic, detected_format = check_video_magic_bytes(file.stream)
    if not valid_magic:
        flash('Les magic bytes ne correspondent pas a un format video valide.', 'danger')
        return False

    if not validate_video_extension_matches_content(file.filename, detected_type):
        flash('L\'extension ne correspond pas au contenu reel du fichier.', 'danger')
        return False

    has_code, found_pattern = scan_video_for_code(file.stream)
    if has_code:
        flash('Contenu suspect detecte dans le fichier. Upload refuse.', 'danger')
        return False

    filename = secure_filename(file.filename)
    if not filename:
        flash('Nom de fichier invalide.', 'danger')
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    video_folder = app.config.get('VIDEO_UPLOAD_FOLDER',
                                   os.path.join(app.root_path, 'static', 'uploads', 'videos'))
    os.makedirs(video_folder, exist_ok=True)
    filepath = os.path.join(video_folder, safe_name)

    file.stream.seek(0)
    file.save(filepath)

    video = Video(
        title=censor_text(form.title.data),
        filename=safe_name,
        original_name=file.filename,
        content_type=detected_type,
        file_size=file_size,
        user_id=current_user.id
    )
    db.session.add(video)
    db.session.commit()

    flash('Clip publie avec succes !', 'success')
    return True


@app.route('/clips/<int:video_id>/delete', methods=['POST'])
@login_required
def delete_clip(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    video_folder = app.config.get('VIDEO_UPLOAD_FOLDER',
                                   os.path.join(app.root_path, 'static', 'uploads', 'videos'))
    filepath = os.path.join(video_folder, video.filename)
    if os.path.isfile(filepath):
        os.remove(filepath)
    db.session.delete(video)
    db.session.commit()
    flash('Clip supprime.', 'info')
    clips_cat = Category.query.filter_by(name='Clips & Highlights').first()
    if clips_cat:
        return redirect(url_for('category', category_id=clips_cat.id))
    return redirect(url_for('index'))


# ── Brawlhalla Specific Routes ──

@app.route('/tier-list')
def tier_list():
    return render_template('tier_list.html')


@app.route('/true-combos')
def true_combos():
    return render_template('true_combos.html')


@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')


@app.route('/api/chat/messages', methods=['GET', 'POST'])
@login_required
def api_chat_messages():
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('content'):
            return {'error': 'Message vide'}, 400

        msg = ChatMessage(content=censor_text(data['content']), user_id=current_user.id)
        db.session.add(msg)
        db.session.commit()
        return {'status': 'success'}

    # GET: return last 50 messages
    messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(50).all()
    messages.reverse()

    return {
        'messages': [{
            'id': m.id,
            'username': m.author.username,
            'avatar_color': m.author.avatar_color,
            'initials': m.author.initials,
            'content': m.content,
            'time': m.created_at.strftime('%H:%M')
        } for m in messages]
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5000, debug=True, host="0.0.0.0")
