from datetime import date
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from forms import *

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# configuring login_manager (Flask authentication)
login_manager = LoginManager()
login_manager.init_app(app)


# The below function is required to allow authentication feature
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# admin_only decorator - required to block access to certain routes
def admin_only(func):
    # imported from functools - mirrored login_required decorator
    @wraps(func)
    def inner(*args, **kwargs):
        # if user is not admin - return unauthorised messaged using Flask
        if current_user.id != 1:
            return abort(403)
        return func(*args, **kwargs)

    return inner


##CONFIGURE TABLES

##CREATE USER TABLE IN DB
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    name = db.Column(db.String(1000))
    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    blogposts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = relationship("User", back_populates="blogposts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates="comments")
    date = db.Column(db.String(250), nullable=False)


# required when first creating the tables
with app.app_context():
    db.create_all()


@app.route('/')
def get_all_posts():
    global is_admin

    if current_user:
        logged_in = current_user.is_authenticated

    else:
        logged_in = False

    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=logged_in)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if request.method == "POST":
        # retrieving the inputted values
        user_name = request.form["name"]
        user_email = request.form["email"]
        user_password = request.form["password"]

        database_user = User.query.filter_by(email=user_email).first()

        if database_user:
            flash(
                message='The email address you have entered already exists in the system. You have been redirected to the login page.',
                category="error")

            return redirect(url_for('login'))


        else:

            hashed_password = generate_password_hash(user_password, "pbkdf2:sha256", 8)
            # creating a new user with the inputted values
            new_user = User(
                name=user_name,
                email=user_email,
                password=hashed_password
            )
            # adding new user to the database
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts", name=new_user.name))

    return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()

    if request.method == "POST":

        user_email = request.form["email"]
        user_password = request.form["password"]

        database_user = User.query.filter_by(email=user_email).first()

        if database_user:

            if check_password_hash(database_user.password, user_password):
                login_user(database_user)

                return redirect(url_for('get_all_posts'))


            else:
                flash(message='You have entered an invalid password. Please try again', category="error")

        else:
            flash(message='The email address you have entered does not exist in the system. Please create an account.',
                  category="error")

    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()

    return redirect(url_for('get_all_posts', logged_in=False))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()

    if comment_form.validate_on_submit():

        if current_user.is_authenticated:
            new_comment = Comment(
                text=comment_form.comment.data,
                author_id=current_user.id,
                post_id=post_id,
                date=date.today().strftime("%B %d, %Y"),
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("get_all_posts", logged_in=current_user.is_authenticated))

        else:
            flash(message='You need to login or register to comment.', category="error")
            return redirect(url_for('login', logged_in=current_user.is_authenticated))

    gravatar = Gravatar(app,
                        size=20,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)

    all_comments = Comment.query.all()[::-1]

    return render_template("post.html", post=requested_post, form=comment_form, comments=all_comments,
                           gravatar=gravatar, logged_in=current_user.is_authenticated)


@app.route("/about")
def about():
    if current_user:
        logged_in = current_user.is_authenticated

    else:
        logged_in = False
    return render_template("about.html", logged_in=logged_in)


@app.route("/contact")
def contact():
    if current_user:
        logged_in = current_user.is_authenticated

    else:
        logged_in = False
    return render_template("contact.html", logged_in=logged_in)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y"),
            author_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)
