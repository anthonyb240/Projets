from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from config import Config
from models import db, User, Category, Topic, Post, ChatMessage
from forms import RegistrationForm, LoginForm, TopicForm, PostForm
from datetime import datetime
from utils import censor_text

app = Flask(__name__, template_folder='../front/templates', static_folder='../front/static')
app.config.from_object(Config)

# Protection avec Flask-Talisman pour Content Security Policy et HTTP Headers
csp = {
    'default-src': ["'self'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'script-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:"]
}
talisman = Talisman(app, content_security_policy=csp, force_https=False) # Force HTTPS=False en developpement local

csrf = CSRFProtect(app)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
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
        return 'À l\'instant'
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


@app.route('/category/<int:category_id>')
def category(category_id):
    cat = Category.query.get_or_404(category_id)
    page = request.args.get('page', 1, type=int)
    topics = cat.topics.order_by(Topic.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False)
    return render_template('category.html', category=cat, topics=topics)


@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    t = Topic.query.get_or_404(topic_id)
    form = PostForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Connectez-vous pour répondre.', 'warning')
            return redirect(url_for('login'))
        post = Post(
            content=censor_text(form.content.data),
            user_id=current_user.id,
            topic_id=t.id
        )
        db.session.add(post)
        db.session.commit()
        flash('Réponse publiée !', 'success')
        return redirect(url_for('topic', topic_id=t.id))
    page = request.args.get('page', 1, type=int)
    posts = t.posts.order_by(Post.created_at.asc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('topic.html', topic=t, posts=posts, form=form)


@app.route('/new-topic/<int:category_id>', methods=['GET', 'POST'])
@login_required
def new_topic(category_id):
    cat = Category.query.get_or_404(category_id)
    if cat.name == 'Actualités & Patchs' and not current_user.is_admin:
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
        flash('Sujet créé avec succès !', 'success')
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
        flash('Inscription réussie ! Vous pouvez vous connecter.', 'success')
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
    flash('Vous êtes déconnecté.', 'info')
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
    flash('Sujet supprimé.', 'info')
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
    flash('Réponse supprimée.', 'info')
    return redirect(url_for('topic', topic_id=topic_id))


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
    # Reverse to have chronological order
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
    # Debug mode désactivé pour la sécurité
    app.run(port=5000)
