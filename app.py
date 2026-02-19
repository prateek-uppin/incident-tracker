from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_connection
from auth import login_required

app = Flask(__name__)
app.secret_key = "1a2b3c4d5e6f7g8h9i"

@app.get("/")
@login_required
def index():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM incidents ORDER BY created_at DESC")
    incidents = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("index.html", incidents=incidents)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill all fields.")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, password_hash),
            )
            conn.commit()
        except Exception:
            flash("Email already exists. Try logging in.")
            cursor.close()
            conn.close()
            return redirect(url_for("signup"))

        cursor.close()
        conn.close()

        flash("Account created. Please login.")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("index"))

    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/incidents/new", methods=["GET", "POST"])
@login_required
def new_incident():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        severity = request.form.get("severity", "").strip()
        status = request.form.get("status", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not category or not severity or not status:
            flash("Please fill all required fields.")
            return redirect(url_for("new_incident"))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO incidents (title, category, severity, status, description, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (title, category, severity, status, description, session["user_id"]),
        )
        conn.commit()

        cursor.close()
        conn.close()

        flash("Incident created.")
        return redirect(url_for("index"))

    return render_template("new_incident.html")


@app.get("/incidents/<int:incident_id>")
@login_required
def incident_detail(incident_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM incidents WHERE id=%s", (incident_id,))
    incident = cursor.fetchone()

    cursor.close()
    conn.close()

    if not incident:
        return "Incident not found", 404

    return render_template("incident_detail.html", incident=incident)


if __name__ == "__main__":
    app.run(debug=True)
