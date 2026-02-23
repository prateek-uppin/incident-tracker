from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Response
import csv
import io

from db import get_connection
from auth import login_required

app = Flask(__name__)
app.secret_key = "1a2b3c4d5e6f7g8h9i"

@app.get("/")
@login_required
def index():
    severity = request.args.get("severity", "")
    status = request.args.get("status", "")
    scope = request.args.get("scope", "all")  # all | mine

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    base = """
        FROM incidents i
        JOIN users u ON u.id = i.created_by
        WHERE 1=1
    """
    params = []

    if scope == "mine":
        base += " AND i.created_by=%s"
        params.append(session["user_id"])

    if severity:
        base += " AND i.severity=%s"
        params.append(severity)

    if status:
        base += " AND i.status=%s"
        params.append(status)

    cursor.execute(
        "SELECT COUNT(*) AS total " + base,
        params,
    )
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS open_count " + base + " AND i.status='Open'",
        params,
    )
    open_count = cursor.fetchone()["open_count"]

    cursor.execute(
        "SELECT COUNT(*) AS critical_count " + base + " AND i.severity='Critical'",
        params,
    )
    critical_count = cursor.fetchone()["critical_count"]

    cursor.execute(
        """
        SELECT i.*, u.name AS creator_name
        """ + base + """
        ORDER BY i.created_at DESC
        """,
        params,
    )
    incidents = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        incidents=incidents,
        severity=severity,
        status=status,
        scope=scope,
        total=total,
        open_count=open_count,
        critical_count=critical_count,
    )


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

@app.get("/profile")
@login_required
def profile():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name, email, created_at FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)

@app.get("/export")
@login_required
def export_csv():
    severity = request.args.get("severity", "")
    status = request.args.get("status", "")
    scope = request.args.get("scope", "all")  

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT
            i.id,
            i.title,
            i.category,
            i.severity,
            i.status,
            u.name AS created_by,
            i.created_at
        FROM incidents i
        JOIN users u ON u.id = i.created_by
        WHERE 1=1
    """
    params = []

    if scope == "mine":
        query += " AND i.created_by=%s"
        params.append(session["user_id"])

    if severity:
        query += " AND i.severity=%s"
        params.append(severity)

    if status:
        query += " AND i.status=%s"
        params.append(status)

    query += " ORDER BY i.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "Title", "Category", "Severity", "Status", "Created By", "Created At"])

    for r in rows:
        created_at = r.get("created_at")
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else ""

        writer.writerow([
            r.get("id", ""),
            r.get("title", ""),
            r.get("category", ""),
            r.get("severity", ""),
            r.get("status", ""),
            r.get("created_by", ""),
            created_at_str,
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidents.csv"},
    )


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

    cursor.execute(
        """
        SELECT i.*, u.name AS creator_name
        FROM incidents i
        JOIN users u ON u.id = i.created_by
        WHERE i.id=%s
        """,
        (incident_id,),
    )
    incident = cursor.fetchone()

    cursor.close()
    conn.close()

    if not incident:
        return "Incident not found", 404

    is_owner = (incident["created_by"] == session["user_id"])
    return render_template("incident_detail.html", incident=incident, is_owner=is_owner)

@app.post("/incidents/<int:incident_id>/status")
@login_required
def update_incident_status(incident_id):
    new_status = request.form.get("status", "").strip()

    if new_status not in ["Open", "In Progress", "Resolved"]:
        flash("Invalid status.")
        return redirect(url_for("incident_detail", incident_id=incident_id))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE incidents SET status=%s WHERE id=%s",
        (new_status, incident_id),
    )
    conn.commit()

    cursor.close()
    conn.close()

    flash("Status updated.")
    return redirect(url_for("incident_detail", incident_id=incident_id))

@app.route("/incidents/<int:incident_id>/edit", methods=["GET", "POST"])
@login_required
def edit_incident(incident_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM incidents WHERE id=%s", (incident_id,))
    incident = cursor.fetchone()

    if not incident:
        cursor.close()
        conn.close()
        return "Incident not found", 404

    # Simple ownership check (optional but recommended)
    if incident["created_by"] != session["user_id"]:
        cursor.close()
        conn.close()
        flash("You don’t have permission to edit this incident.", "error")
        return redirect(url_for("incident_detail", incident_id=incident_id))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        severity = request.form.get("severity", "").strip()
        status = request.form.get("status", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not category or not severity or not status:
            flash("Please fill all required fields.")
            cursor.close()
            conn.close()
            return redirect(url_for("edit_incident", incident_id=incident_id))

        cursor2 = conn.cursor()
        cursor2.execute(
            """
            UPDATE incidents
            SET title=%s, category=%s, severity=%s, status=%s, description=%s
            WHERE id=%s
            """,
            (title, category, severity, status, description, incident_id),
        )
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()

        flash("Incident updated.")
        return redirect(url_for("incident_detail", incident_id=incident_id))

    cursor.close()
    conn.close()
    return render_template("edit_incident.html", incident=incident)

@app.route("/incidents/<int:incident_id>/delete", methods=["GET", "POST"])
@login_required
def delete_incident(incident_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM incidents WHERE id=%s", (incident_id,))
    incident = cursor.fetchone()

    if not incident:
        cursor.close()
        conn.close()
        return "Incident not found", 404

    if incident["created_by"] != session["user_id"]:
        cursor.close()
        conn.close()
        return "Not allowed", 403

    if request.method == "POST":
        cursor2 = conn.cursor()
        cursor2.execute("DELETE FROM incidents WHERE id=%s", (incident_id,))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()

        flash("Incident deleted.")
        return redirect(url_for("index"))

    cursor.close()
    conn.close()
    return render_template("delete_confirm.html", incident=incident)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
