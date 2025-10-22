from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secret_key_here"  # replace with environment variable for production
DATABASE = "namesprouts.db"


# ---------------- Database Helpers ---------------- #

def get_db():
    """Connect to SQLite database; reuse connection if already open."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # allows name-based access to columns
    return db


@app.teardown_appcontext
def close_db(exception):
    """Close the database connection at the end of the request."""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database tables if they don’t exist."""
    db = get_db()
    cursor = db.cursor()
    cursor.executescript("""
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
            flower_image TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()


# ---------------- Utility ---------------- #

def logged_in():
    """Check if user is logged in."""
    return "user_id" in session


# ---------------- Routes ---------------- #

@app.route("/")
def home():
    return render_template("design.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration route."""
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            return "All fields required.", 400

        hash_pw = generate_password_hash(password)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, hash) VALUES (?, ?, ?)",
                (username, email, hash_pw),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return "Username or email already exists.", 400

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login route with password verification."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["hash"], password):
            return "Invalid username or password", 403

        session["user_id"] = user["id"]
        return redirect(url_for("design"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout route clears session."""
    session.clear()
    return redirect(url_for("home"))


@app.route("/design", methods=["GET", "POST"])
def design():
    """Design page for creating and saving flower designs."""
    if not logged_in():
        return redirect(url_for("login"))

    db = get_db()

    if request.method == "POST":
        # When "Save" button is clicked (not the preview)
        name = request.form.get("name")
        month = request.form.get("month")
        flower_image = f"static/flowers/{month}.png"

        db.execute(
            """
            INSERT INTO projects (user_id, name_text, month, flower_image, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session["user_id"], name, month, flower_image, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()

        return redirect(url_for("my_projects"))

    # For GET requests, just show design page
    return render_template("design.html")


@app.route("/preview", methods=["POST"])
def preview():
    """
    Optional API endpoint — returns JSON for live preview if needed later.
    Currently, preview is handled client-side with JS canvas.
    """
    data = request.get_json()
    name = data.get("name")
    month = data.get("month")
    return jsonify({
        "status": "ok",
        "message": f"Previewing {name} as a {month} flower"
    })


@app.route("/my_projects")
def my_projects():
    """Show all saved projects for logged-in user."""
    if not logged_in():
        return redirect(url_for("login"))

    db = get_db()
    projects = db.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()

    return render_template("my_projects.html", projects=projects)


# ---------------- Main Entry ---------------- #

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
