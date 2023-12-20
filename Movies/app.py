# app.py
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask import abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_migrate import Migrate

from werkzeug.security import generate_password_hash, check_password_hash

import requests
from models import db, User, Movie, MovieList, movie_list_assoc, SharedList

app = Flask(__name__)
app.config['SECRET_KEY'] = '40ed30bdd2b4dc3e14e9f457ef6e10cf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Clement@localhost/cinemalist_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Import database models
from models import User, Movie, MovieList, movie_list_assoc

# Setup Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Your API key for TMDb (replace with your actual API key)
TMDB_API_KEY = '05c58d5b6362fae54214a4409652d09f'

# Modify the root route to redirect to the login page
@app.route('/')
def home():
    return redirect(url_for('login'))

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Validate and save the new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate login credentials
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)

            # Set the username in the session
            session['username'] = user.username

            flash('Login successful!', 'success')

            # Redirect to the index page after successful login
            return redirect(url_for('index'))
        else:
            flash('Incorrect username or password. Please try again.', 'danger')

    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout successful!', 'success')
    return redirect(url_for('home'))  # Redirect to the login page after logout

# Index route
@app.route('/index')
@login_required  # Require login to access the index page
def index():
    # Fetch popular movies from TMDb API
    tmdb_url = f'https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}&language=en-US&page=1'
    try:
        response = requests.get(tmdb_url)
        response.raise_for_status()
        popular_movies = response.json().get('results', [])

    except requests.exceptions.RequestException as e:
        flash(f"Error accessing TMDb API: {e}", 'danger')
        popular_movies = []

    return render_template('index.html', popular_movies=popular_movies)

# Pagination configuration
MOVIES_PER_PAGE = 20  # Adjust as needed

@app.route('/movies')
@login_required
def movies():
    # Get the page from the query parameters, default to 1
    page = int(request.args.get('page', 1))

    try:
        # Check if there are already enough movies in the database
        existing_movies_count = Movie.query.count()

        # If there are not enough movies, fetch more from TMDb API
        if existing_movies_count < MOVIES_PER_PAGE * page:
            tmdb_url = f'https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=en-US&page={page}'
            response = requests.get(tmdb_url)
            response.raise_for_status()
            tmdb_movies = response.json().get('results', [])

            # Store movies in the database
            for tmdb_movie in tmdb_movies:
                # Check if the movie with tmdb_id already exists in the database
                existing_movie = Movie.query.filter_by(tmdb_id=tmdb_movie['id']).first()
                if not existing_movie:
                    movie = Movie(
                        tmdb_id=tmdb_movie['id'],
                        title=tmdb_movie['title'],
                        overview=tmdb_movie['overview'],
                        poster_path=tmdb_movie['poster_path'],
                        release_date=tmdb_movie['release_date'],
                        genres=','.join(genre['name'] for genre in tmdb_movie.get('genres', []))
                    )
                    db.session.add(movie)

            db.session.commit()

    except requests.exceptions.RequestException as e:
        flash(f"Error accessing TMDb API: {e}", 'danger')

    # Paginate the movies
    movies = Movie.query.paginate(page=page, per_page=MOVIES_PER_PAGE)

    return render_template('movies.html', movies=movies)


# New route for shared lists
@app.route('/shared_lists')
@login_required
def shared_lists():
    # Fetch shared lists for the logged-in user
    shared_lists = SharedList.query.filter_by(shared_with_user_id=current_user.id).all()

    return render_template('shared_lists.html', shared_lists=shared_lists)


# New route for user-specific lists
@app.route('/my_lists')
@login_required
def my_lists():
    # Fetch and display user-specific lists
    user_lists = MovieList.query.filter_by(user_id=current_user.id).all()
    # Fetch all users
    all_users = User.query.all()

    return render_template('my_lists.html', lists=user_lists, all_users=all_users)

# New route for sharing a list
@app.route('/share_list/<int:list_id>', methods=['POST'])
@login_required
def share_list(list_id):
    # Fetch the list to share
    list_to_share = MovieList.query.filter_by(id=list_id, user_id=current_user.id).first()

    if not list_to_share:
        abort(404)  # List not found or doesn't belong to the user

    # Fetch the selected users and the "share with all" option from the form
    selected_users = request.form.getlist('selected_users')
    share_with_all = 'share_with_all' in request.form

    # Share the list with selected users
    if selected_users or share_with_all:
        shared_users = []

        if share_with_all:
            # Share with all users
            all_users = User.query.all()
            shared_users.extend(all_users)

        for user_id in selected_users:
            user = User.query.get(user_id)
            if user:
                shared_users.append(user)

        # Create shared list entries in the database
        for shared_user in shared_users:
            shared_list = SharedList(list_id=list_to_share.id, shared_by_user_id=current_user.id, shared_with_user_id=shared_user.id)
            db.session.add(shared_list)

        db.session.commit()

        flash('List shared successfully!', 'success')
    else:
        flash('Please select users to share with or choose the "Share with all" option.', 'danger')

    return redirect(url_for('my_lists'))
# Add a new route for creating a new list with movies
@app.route('/create_list', methods=['GET', 'POST'])
@login_required
def create_list():
    if request.method == 'POST':
        # If a search term is provided, perform the search
        search_term = request.form.get('search_movies', '').strip()
        if search_term:
            # Perform a case-insensitive search for movies containing the search term
            movies = Movie.query.filter(Movie.title.ilike(f"%{search_term}%")).all()
            return render_template('create_list.html', movies=movies, search_term=search_term)

        # Get the list name and selected movies from the form data
        list_name = request.form.get('list_name')
        selected_movie_ids = request.form.getlist('selected_movies')

        # Check if the list name is provided
        if not list_name and not selected_movie_ids:
            flash('Please provide a name for the list or select movies.', 'danger')
            return redirect(url_for('create_list'))

        # If list name is provided, create a new movie list
        if list_name:
            new_list = MovieList(name=list_name, user_id=current_user.id)
            db.session.add(new_list)
            db.session.commit()

            # Add selected movies to the movie list
            for movie_id in selected_movie_ids:
                movie = Movie.query.get(movie_id)
                if movie:
                    new_list.movies.append(movie)

            db.session.commit()

            flash('Movie list created successfully!', 'success')
            return redirect(url_for('my_lists'))

    # Fetch all movies if no search term is provided
    movies = Movie.query.all()

    # Render the create list page with available movies
    return render_template('create_list.html', movies=movies, search_term='')

# the route for editing a list
@app.route('/edit_list/<int:list_id>', methods=['GET', 'POST'])
@login_required
def edit_list(list_id):
    # Fetch the list to edit
    list_to_edit = MovieList.query.filter_by(id=list_id, user_id=current_user.id).first()

    if not list_to_edit:
        abort(404)  # List not found or doesn't belong to the user

    if request.method == 'POST':
        # Update the list with the new data
        list_to_edit.name = request.form.get('list_name')
        selected_movie_ids = request.form.getlist('selected_movies')

        # Clear existing movies from the list
        list_to_edit.movies.clear()

        # Add selected movies to the movie list
        for movie_id in selected_movie_ids:
            movie = Movie.query.get(movie_id)
            if movie:
                list_to_edit.movies.append(movie)

        db.session.commit()

        flash('Movie list updated successfully!', 'success')
        return redirect(url_for('my_lists'))

    # Fetch all movies for the form
    movies = Movie.query.all()

    return render_template('update_list.html', movies=movies, list_to_edit=list_to_edit)

# Add a new route for removing a movie from the list
@app.route('/remove_movie/<int:list_id>/<int:movie_id>')
@login_required
def remove_movie(list_id, movie_id):
    # Fetch the list to edit
    list_to_edit = MovieList.query.filter_by(id=list_id, user_id=current_user.id).first()

    if not list_to_edit:
        abort(404)  # List not found or doesn't belong to the user

    # Fetch the movie to remove
    movie_to_remove = Movie.query.get(movie_id)

    if not movie_to_remove:
        abort(404)  # Movie not found

    # Remove the movie from the list
    list_to_edit.movies.remove(movie_to_remove)
    db.session.commit()

    flash('Movie removed successfully!', 'success')
    return redirect(url_for('edit_list', list_id=list_to_edit.id))

# Add a new route for deleting a list
@app.route('/delete_list/<int:list_id>', methods=['GET'])
@login_required
def delete_list(list_id):
    # Fetch the list to delete
    list_to_delete = MovieList.query.filter_by(id=list_id, user_id=current_user.id).first()

    if not list_to_delete:
        abort(404)  # List not found or doesn't belong to the user

    # Delete the list
    db.session.delete(list_to_delete)
    db.session.commit()

    flash('Movie list deleted successfully!', 'success')
    return redirect(url_for('my_lists'))



if __name__ == '__main__':
    app.run(debug=True)
