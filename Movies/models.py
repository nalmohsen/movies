# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import current_user

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    overview = db.Column(db.Text)
    poster_path = db.Column(db.String(255))  # Assuming the poster path is stored in the database
    release_date = db.Column(db.Date)
    genres = db.Column(db.String(255))  # Assuming the genres are stored as a string in the database

    def __init__(self, tmdb_id, title, overview, poster_path, release_date, genres):
        self.tmdb_id = tmdb_id
        self.title = title
        self.overview = overview
        self.poster_path = poster_path
        self.release_date = release_date
        self.genres = genres

    # Add a property to get the full poster URL
    @property
    def poster_url(self):
        if self.poster_path:
            return f'https://image.tmdb.org/t/p/w500{self.poster_path}'
        return None

class MovieList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movies = db.relationship('Movie', secondary='movie_list_assoc', backref='lists')
    # Add a relationship with SharedList
    shared_lists = db.relationship('SharedList', backref='list', lazy='dynamic')

# Association table for the many-to-many relationship between Movie and MovieList
movie_list_assoc = db.Table('movie_list_assoc',
    db.Column('movie_id', db.Integer, db.ForeignKey('movie.id'), primary_key=True),
    db.Column('list_id', db.Integer, db.ForeignKey('movie_list.id'), primary_key=True)
)

class SharedList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('movie_list.id'), nullable=False)
    shared_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Add relationships
    shared_by_user = db.relationship('User', foreign_keys=[shared_by_user_id], backref='shared_lists')
    shared_with_user = db.relationship('User', foreign_keys=[shared_with_user_id])
