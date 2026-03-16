from flask_wtf import FlaskForm
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
    password_confirm = PasswordField('Confirmer le mot de passe',
                                     validators=[DataRequired(), EqualTo('password', message='Les mots de passe ne correspondent pas.')])
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
