from flask import (
    Flask, render_template, request,
    redirect, url_for, session, g, flash
)
import sqlite3
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from functools import wraps
import re

# =========================================================
# APP INITIALIZATION (MUST COME FIRST)
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is not set")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
)

DATABASE = "namesprouts.db"
csrf = CSRFProtect(app)

# =========================================================
# TEMPLATE FILTERS
# =========================================================

@app.template_filter("regex_replace")
def regex_replace(s, find, replace=""):
    return re.sub(find, replace, s)

# =========================================================
# DATABASE HELPERS
# =========================================================

def get_db():
    if "_database" not in g:
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row
        g._database.execute("PRAGMA foreign_keys = ON;")
    return g._database


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("_database", None)
    if db:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name_text TEXT NOT NULL,
            month TEXT NOT NULL,
            flower_image TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()

# =========================================================
# AUTH UTILITIES
# =========================================================

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def flower_image_path(month):
    path = f"flowers/{month}.png"
    full_path = os.path.join(app.static_folder, path)
    return f"static/{path}" if os.path.exists(full_path) else "static/flowers/default.png"

# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():
    return redirect(url_for("design")) if "user_id" in session else redirect(url_for("login"))

# ---------------- AUTH ---------------- #

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        try:
            db = get_db()
            db.execute(
                "INSERT INTO users (username, email, hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "error")
            return redirect(url_for("register"))

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or not check_password_hash(user["hash"], password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True

        flash("Welcome back 🌸", "success")
        return redirect(url_for("design"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

# ---------------- DESIGN ---------------- #

@app.route("/design", methods=["GET", "POST"])
@login_required
def design():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        month = request.form.get("month")

        if not name or not month:
            flash("Please enter a name and select a month.", "error")
            return redirect(url_for("design"))

        db = get_db()
        db.execute(
            """
            INSERT INTO projects (user_id, name_text, month, flower_image, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                name,
                month,
                flower_image_path(month),
                datetime.utcnow().isoformat()
            )
        )
        db.commit()

        flash("Design saved successfully 🌿", "success")
        return redirect(url_for("my_projects"))

    return render_template("design.html")

# ---------------- PROJECTS ---------------- #

@app.route("/projects")
@login_required
def my_projects():
    db = get_db()

    projects = db.execute(
        """
        SELECT *
        FROM projects
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template("my_projects.html", projects=projects)


@app.route("/edit/<int:project_id>", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    db = get_db()

    project = db.execute(
        """
        SELECT *
        FROM projects
        WHERE id = ? AND user_id = ?
        """,
        (project_id, session["user_id"])
    ).fetchone()

    if not project:
        flash("Project not found or access denied.", "error")
        return redirect(url_for("my_projects"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        month = request.form.get("month")

        if not name or not month:
            flash("Name and month are required.", "error")
            return redirect(url_for("edit_project", project_id=project_id))

        db.execute(
            """
            UPDATE projects
            SET name_text = ?, month = ?, flower_image = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                month,
                flower_image_path(month),
                project_id,
                session["user_id"]
            )
        )
        db.commit()

        flash("Project updated successfully 🌸", "success")
        return redirect(url_for("my_projects"))

    return render_template("edit_project.html", project=project)


@app.route("/delete/<int:project_id>", methods=["POST"])
@login_required
def delete_project(project_id):
    db = get_db()

    project = db.execute(
        """
        SELECT id
        FROM projects
        WHERE id = ? AND user_id = ?
        """,
        (project_id, session["user_id"])
    ).fetchone()

    if not project:
        flash("Project not found or access denied.", "error")
        return redirect(url_for("my_projects"))

    db.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (project_id, session["user_id"])
    )
    db.commit()

    flash("Project deleted successfully 🗑️", "success")
    return redirect(url_for("my_projects"))

# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500
