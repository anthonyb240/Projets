import os
import logging
import random
import platform
import socket
import time
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from config import Config
from models import db, User, Category, Topic, Post, ChatMessage, UploadedFile, Video
from forms import (
    RegistrationForm, LoginForm, TopicForm, PostForm,
    AvatarUploadForm, VideoUploadForm, ChangePasswordForm
)
from datetime import datetime
from utils import censor_text
from werkzeug.utils import secure_filename

START_TIME = time.time()

# ── Logging configuration ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

mdp = "vc_ABCDEFABCDEF"
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
    print(f"Hello from {socket.gethostname()}")
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


# ── Change Password ──

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    from flask import session
    import time

    # Rate limiting : max 5 tentatives par 15 min
    now = time.time()
    attempts = session.get('pwd_attempts', [])
    # Nettoyer les tentatives de plus de 15 min
    attempts = [t for t in attempts if now - t < 900]
    session['pwd_attempts'] = attempts

    if len(attempts) >= 5:
        flash('Trop de tentatives. Reessayez dans 15 minutes.', 'danger')
        return redirect(url_for('profile', username=current_user.username))

    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Enregistrer la tentative
        attempts.append(now)
        session['pwd_attempts'] = attempts

        # Verifier l'ancien mot de passe
        if not current_user.check_password(form.current_password.data):
            flash('Mot de passe actuel incorrect.', 'danger')
            return redirect(url_for('change_password'))

        # Verifier que le nouveau mdp est different de l'ancien
        if current_user.check_password(form.new_password.data):
            flash('Le nouveau mot de passe doit etre different de l\'ancien.', 'danger')
            return redirect(url_for('change_password'))

        # Changer le mot de passe
        current_user.set_password(form.new_password.data)
        db.session.commit()

        # Invalider la session et forcer la reconnexion
        logout_user()
        session.clear()
        flash('Mot de passe modifie avec succes. Veuillez vous reconnecter.', 'success')
        return redirect(url_for('login'))

    return render_template('change_password.html', form=form)


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
    """Verifie les magic bytes du fichier."""
    header = file_stream.read(8)
    file_stream.seek(0)
    for fmt, magic in MAGIC_BYTES.items():
        if header[:len(magic)] == magic:
            return True, fmt
    return False, None


def validate_image_extension_matches_content(filename, detected_mime):
    """Verifie que l'extension correspond au contenu detecte."""
    ext = filename.rsplit('.', 1)[1].lower()
    extension_mime_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
    }
    expected_mime = extension_mime_map.get(ext)
    return expected_mime == detected_mime


def scan_image_for_code(file_stream):
    """Scan le fichier entier pour detecter du code injecte."""
    content = file_stream.read()
    file_stream.seek(0)
    dangerous_patterns = [
        b'<?php', b'<?=', b'<script', b'<%', b'<jsp:',
        b'#!/', b'import os', b'eval(', b'exec(',
    ]
    for pattern in dangerous_patterns:
        if pattern in content:
            return True, pattern.decode('utf-8', errors='replace')
    return False, None


def reprocess_image(file_stream, detected_mime):
    """Re-encode l'image via Pillow pour supprimer tout payload cache.
    Retourne les bytes de l'image nettoyee ou None en cas d'echec."""
    from PIL import Image
    import io
    try:
        img = Image.open(file_stream)
        img.verify()
        file_stream.seek(0)
        img = Image.open(file_stream)

        # Limiter les dimensions
        max_dim = 2048
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # Convertir en RGB si necessaire (supprime les modes exotiques)
        if img.mode not in ('RGB', 'RGBA', 'L', 'P'):
            img = img.convert('RGB')

        output = io.BytesIO()
        fmt_map = {
            'image/jpeg': 'JPEG',
            'image/png': 'PNG',
            'image/gif': 'GIF',
        }
        save_fmt = fmt_map.get(detected_mime, 'PNG')
        if save_fmt == 'JPEG' and img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(output, format=save_fmt)
        return output.getvalue()
    except Exception:
        return None


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
    import uuid

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
        valid_magic, detected_format = check_magic_bytes(file.stream)
        if not valid_magic:
            flash('Le fichier ne semble pas etre une image valide.', 'danger')
            return redirect(request.url)

        # ── Couche 4 : Verification extension/contenu coherent ──
        filename = secure_filename(file.filename)
        if not filename:
            flash('Nom de fichier invalide.', 'danger')
            return redirect(request.url)

        if not validate_image_extension_matches_content(filename, detected_type):
            flash('L\'extension ne correspond pas au contenu reel du fichier.', 'danger')
            return redirect(request.url)

        # ── Couche 5 : Scan du contenu pour du code injecte ──
        has_code, found_pattern = scan_image_for_code(file.stream)
        if has_code:
            flash('Contenu suspect detecte dans le fichier. Upload refuse.', 'danger')
            return redirect(request.url)

        # ── Couche 6 : Limite de taille (2 Mo) ──
        file.stream.seek(0, 2)
        file_size = file.stream.tell()
        file.stream.seek(0)
        max_avatar_size = 2 * 1024 * 1024
        if file_size > max_avatar_size:
            flash('Fichier trop volumineux. Maximum 2 Mo.', 'danger')
            return redirect(request.url)

        # ── Couche 7 : Re-processing via Pillow (supprime tout payload) ──
        clean_data = reprocess_image(file.stream, detected_type)
        if clean_data is None:
            flash('Impossible de traiter l\'image. Fichier corrompu ou invalide.', 'danger')
            return redirect(request.url)

        # Sauvegarde avec nom aleatoire (UUID)
        ext = filename.rsplit('.', 1)[1].lower()
        save_name = f"{uuid.uuid4().hex}.{ext}"

        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, save_name)

        with open(filepath, 'wb') as f:
            f.write(clean_data)

        # Supprimer l'ancien avatar s'il existe
        if current_user.avatar_file:
            old_path = os.path.join(upload_folder, current_user.avatar_file)
            if os.path.isfile(old_path):
                os.remove(old_path)

        # Enregistrement en base de donnees
        uploaded = UploadedFile(
            original_name=file.filename,
            saved_name=save_name,
            content_type=detected_type,
            file_size=len(clean_data),
            user_id=current_user.id
        )
        db.session.add(uploaded)

        current_user.avatar_file = save_name
        db.session.commit()

        flash('Avatar mis a jour avec succes !', 'success')
        return redirect(url_for('profile', username=current_user.username))

    return render_template('upload_avatar.html', form=form)


@app.route('/aatvl5xf/<path:filename>')
def serve_upload(filename):
    """Sert les fichiers uploades en tant qu'images uniquement."""
    # Empecher le path traversal
    filename = os.path.basename(filename)
    upload_folder = app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_folder, filename)

    if not os.path.isfile(filepath):
        abort(404)

    # Ne servir que les fichiers avec une extension image valide
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mime_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'mp4': 'video/mp4',
        'webm': 'video/webm',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
    }
    content_type = mime_map.get(ext)
    if not content_type:
        abort(403)

    return send_from_directory(upload_folder, filename, mimetype=content_type)


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

    video_folder = app.config.get(
        'VIDEO_UPLOAD_FOLDER',
        os.path.join(app.root_path, 'static', 'aatvl5xf', 'videos'))
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
    video_folder = app.config.get(
        'VIDEO_UPLOAD_FOLDER',
        os.path.join(app.root_path, 'static', 'aatvl5xf', 'videos'))
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

@app.route('/gif-wall')
def gif_wall():
    return render_template('gif_wall.html')


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

# ── Feature 2 : /health ──


@app.route('/health')
def health():
    logger.info('Health check called')
    uptime = round(time.time() - START_TIME, 2)
    errors = []

    # Check DB
    try:
        db.session.execute(db.text('SELECT 1'))
    except Exception as e:
        errors.append(f"database: {str(e)}")

    # Check fichiers critiques / config
    if not os.getenv("SECRET_KEY"):
        errors.append("missing SECRET_KEY")

    status_code = 200 if not errors else 400

    return jsonify({
        "status": "ok" if not errors else "unhealthy",
        "errors": errors,
        "service": "forum-api",
        "timestamp": int(time.time()),
        "uptime_seconds": uptime,
        "version": "1.0.0",
        "environment": os.getenv("FLASK_MODE", "dev")
    }), status_code

# ── Feature 2 : /info ──


@app.route('/info')
def info():
    logger.info('Info endpoint called')
    return jsonify({
        "app": "mon-api",
        "version": "1.0",
        "mode": os.getenv("FLASK_MODE", "dev"),
        "port": int(os.getenv("PORT", 5000)),
        "python_version": platform.python_version(),
        "hostname": socket.gethostname()
    }), 200


# ── Feature 3 : /random-fail ──

@app.route('/random-fail')
def random_fail():
    try:
        if random.randint(1, 3) == 1:  # nosec B311 - simulation erreur, non crypto
            raise Exception("Erreur simulee en production")
        logger.info('random-fail: succes')
        return jsonify({"status": "success", "message": "Tout va bien !"}), 200
    except Exception as e:
        logger.error(f'random-fail: {e}')
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Feature 4 : /logs-demo ──

@app.route('/logs-demo')
def logs_demo():
    logger.info('logs-demo: Ceci est un log INFO - tout fonctionne normalement')
    logger.warning('logs-demo: Ceci est un log WARNING - attention, seuil proche')
    logger.error('logs-demo: Ceci est un log ERROR - une erreur est survenue')
    return jsonify({
        "logs_generated": [
            {"level": "INFO", "code": 200, "message": "Fonctionnement normal"},
            {"level": "WARNING", "code": 400, "message": "Requete suspecte ou seuil proche"},
            {"level": "ERROR", "code": 500, "message": "Erreur interne du serveur"}
        ]
    }), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Prod = gunicorn via Dockerfile CMD. Ce bloc = dev local uniquement.
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(port=5000, debug=debug_mode, host="0.0.0.0")  # nosec B104
