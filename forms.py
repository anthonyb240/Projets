from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User


class RegistrationForm(FlaskForm):
    username = StringField('Nom d\'utilisateur',
                           validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe',
                             validators=[DataRequired(), Length(min=6)])
    password_confirm = PasswordField(
        'Confirmer le mot de passe',
        validators=[
            DataRequired(),
            EqualTo('password',
                    message='Les mots de passe ne correspondent pas.')
        ])
    submit = SubmitField('S\'inscrire')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Ce nom d\'utilisateur est déjà pris.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Cet email est déjà utilisé.')


class LoginForm(FlaskForm):
    username = StringField('Nom d\'utilisateur',
                           validators=[DataRequired()])
    password = PasswordField('Mot de passe',
                             validators=[DataRequired()])
    submit = SubmitField('Se connecter')


class TopicForm(FlaskForm):
    title = StringField('Titre du sujet',
                        validators=[DataRequired(), Length(min=5, max=200)])
    content = TextAreaField('Contenu',
                            validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Créer le sujet')


class PostForm(FlaskForm):
    content = TextAreaField('Votre réponse',
                            validators=[DataRequired(), Length(min=2)])
    submit = SubmitField('Répondre')


class AvatarUploadForm(FlaskForm):
    avatar = FileField('Photo de profil')
    submit = SubmitField('Mettre à jour l\'avatar')


class VideoUploadForm(FlaskForm):
    title = StringField('Titre du clip',
                        validators=[DataRequired(), Length(min=3, max=200)])
    video = FileField('Fichier video')
    submit = SubmitField('Publier le clip')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Mot de passe actuel',
                                     validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe',
                                 validators=[DataRequired(), Length(min=12, max=128)])
    new_password_confirm = PasswordField(
        'Confirmer le nouveau mot de passe',
        validators=[
            DataRequired(),
            EqualTo('new_password',
                    message='Les mots de passe ne correspondent pas.')
        ])
    submit = SubmitField('Modifier le mot de passe')

    def validate_new_password(self, field):
        password = field.data
        import re
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Le mot de passe doit contenir au moins une majuscule.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Le mot de passe doit contenir au moins une minuscule.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Le mot de passe doit contenir au moins un chiffre.')
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError('Le mot de passe doit contenir au moins un caractere special.')
